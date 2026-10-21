"""Read-only GitHub discovery. Never approves candidates or executes their code."""
import argparse
import base64
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from study.common import FIELDS, LICENSES, SHA, write_json, write_rows

AGENT = re.compile(r"co-authored-by:.*(?:claude|codex|copilot|cursor|devin|jules)|"
                   r"(?:tests? (?:were )?generated (?:by|with) (?:claude|codex|copilot|cursor))", re.I)
QUERIES = ['playwright pytest "Co-Authored-By: Claude"',
           'playwright pytest "Co-authored-by: Cursor"',
           'playwright pytest "Co-authored-by: Copilot"']


class GitHub:
    def __init__(self, token):
        self.token = token

    def get(self, path, **params):
        url = "https://api.github.com/" + path.lstrip("/")
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={
            "Authorization": "Bearer " + self.token,
            "Accept": "application/vnd.github+json", "User-Agent": "vandal-study",
            "X-GitHub-Api-Version": "2022-11-28"})
        # Do not forward credentials through redirects or print request headers.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        with urllib.request.build_opener(NoRedirect).open(req, timeout=30) as response:
            data = response.read(8 * 1024 * 1024 + 1)
        if len(data) > 8 * 1024 * 1024:
            raise ValueError("GitHub response exceeds size limit")
        return json.loads(data)


def test_files(commit):
    return [f["filename"] for f in commit.get("files", [])
            if f.get("status") != "removed" and f["filename"].endswith(".py")
            and (Path(f["filename"]).name.startswith("test_") or
                 Path(f["filename"]).name.endswith("_test.py"))]


def parse_candidate(repo, commit, license_info, sources):
    """A lead only: inspect exact changed test files, never infer from a repo name."""
    message = commit["commit"]["message"]
    selected = [p for p in test_files(commit) if p in sources and
                ("playwright" in sources[p] or re.search(r"\bpage[.:]", sources[p])) and
                re.search(r"\bdef test_", sources[p])]
    spdx = (license_info.get("license") or {}).get("spdx_id")
    if repo.get("private") or spdx not in LICENSES or not selected or not AGENT.search(message):
        return None
    sha = commit["sha"]
    if not SHA.fullmatch(sha):
        raise ValueError("GitHub returned a non-pinned commit")
    row = dict.fromkeys(FIELDS, "")
    row.update(repo=repo["full_name"], commit_sha=sha, group="agent",
               evidence_kind="test_commit", evidence_url=commit["html_url"],
               evidence_detail="Commit modifies selected Python browser tests; " + AGENT.search(message).group(0),
               test_paths=json.dumps(selected), license=spdx,
               license_url=license_info["html_url"], approved="no",
               recipe="recipes/REVIEW_REQUIRED.json")
    return row


def discover(api, queries, pages):
    rows, audit, seen = [], [], set()
    for query in queries:
        for page in range(1, pages + 1):
            hits = api.get("search/commits", q=query, per_page=30, page=page)
            audit.append({"query": query, "page": page,
                          "incomplete_results": hits.get("incomplete_results", False),
                          "total_count": hits.get("total_count")})
            for item in hits.get("items", []):
                repo, sha = item["repository"]["full_name"], item["sha"]
                if (repo, sha) in seen:
                    continue
                seen.add((repo, sha))
                try:
                    metadata = api.get("repos/" + repo)
                    commit = api.get(f"repos/{repo}/commits/{sha}")
                    # License endpoint is pinned too; current default-branch license is insufficient.
                    license_info = api.get(f"repos/{repo}/license", ref=sha)
                    sources = {}
                    for path in test_files(commit):
                        blob = api.get(f"repos/{repo}/contents/{urllib.parse.quote(path)}", ref=sha)
                        sources[path] = base64.b64decode(blob["content"]).decode("utf-8")
                    row = parse_candidate(metadata, commit, license_info, sources)
                    if row:
                        rows.append(row)
                    audit.append({"repo": repo, "sha": sha, "candidate": bool(row),
                                  "reason": "person must verify pytest, E2E scope, provenance and recipe" if row
                                  else "no recognized license, test-specific agent evidence, or Python browser test"})
                except (OSError, ValueError, KeyError) as exc:
                    audit.append({"repo": repo, "sha": sha, "error": str(exc)})
            if len(hits.get("items", [])) < 30:
                break
    return rows, audit


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, default=Path("study/candidates.csv"))
    p.add_argument("--query", action="append")
    p.add_argument("--pages", type=int, default=1)
    args = p.parse_args()
    if not 1 <= args.pages <= 10:
        p.error("pages must be between 1 and 10 (bounded discovery)")
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        p.error("GITHUB_TOKEN is required for search; never pass it to run_study or Docker")
    rows, audit = discover(GitHub(token), args.query or QUERIES, args.pages)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_rows(args.output, rows)
    write_json(args.output.with_suffix(".audit.json"), {
        "retrieved_at": datetime.now(timezone.utc).isoformat(), "queries": args.query or QUERIES,
        "records": audit, "automatic_approvals": False})
    print(f"Wrote {len(rows)} unapproved leads to {args.output}")


if __name__ == "__main__":
    main()
