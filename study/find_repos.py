"""Read-only GitHub discovery; every result remains a lead requiring person review."""
import argparse
import ast
import base64
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from study.common import FIELDS, LICENSES, SHA, write_json, write_rows

AGENT = re.compile(r"co-authored-by:.*(?:claude|codex|copilot|cursor|devin|jules|anthropic-code-agent)|generated tests|tests? (?:were )?generated(?: by| with)?", re.I)
QUERIES = ['playwright pytest "Co-Authored-By: Claude"', 'playwright pytest "Co-authored-by: Cursor"', 'playwright pytest "Co-authored-by: Copilot"', 'playwright "generated tests"']
PR_AUTHORS = ("app/copilot-swe-agent", "devin-ai-integration", "google-labs-jules")
HISTORICAL_CUTOFF = "2021-01-01T00:00:00Z"
OBSERVABLE = {"locator", "expect", "click", "fill", "check", "hover", "inner_text", "input_value"}


def static_screen(sources):
    """Count syntactic call sites, not runtime targets or proof of attribution.

    Aliases, wrappers, dynamic selectors and imported fixture/application code can
    evade this heuristic; unrelated methods with matching names can overcount.
    """
    per_file, hosts = {}, set()
    for path, source in sorted(sources.items()):
        tree = ast.parse(source, filename=path)
        names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id if isinstance(node.func, ast.Name) else ""
                if name in OBSERVABLE or name.startswith("get_by_"):
                    names.append(name)
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                for url in re.findall(r"https?://[^\s\"'<>]+", node.value):
                    host = urllib.parse.urlparse(url).hostname
                    if host and host not in {"localhost", "127.0.0.1", "::1"}:
                        hosts.add(host)
        per_file[path] = {"count": len(names), "calls": dict(sorted(Counter(names).items()))}
    return {"observable_calls": sum(x["count"] for x in per_file.values()), "files": per_file,
            "external_host_literals": sorted(hosts), "heuristic_only": True}


class GitHub:
    def __init__(self, token):
        self.token = token

    def get(self, path, **params):
        url = "https://api.github.com/" + path.lstrip("/")
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"Authorization": "Bearer " + self.token,
            "Accept": "application/vnd.github+json", "User-Agent": "vandal-study", "X-GitHub-Api-Version": "2022-11-28"})
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        with urllib.request.build_opener(NoRedirect).open(req, timeout=30) as response:
            data = response.read(8 * 1024 * 1024 + 1)
        if len(data) > 8 * 1024 * 1024:
            raise ValueError("GitHub response exceeds size limit")
        return json.loads(data)


def pinned_license(api, repo, sha):
    try:
        return api.get(f"repos/{repo}/license", ref=sha)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {"license": None, "reason": "no license"}
        raise


def test_files(commit):
    return [f["filename"] for f in commit.get("files", []) if f.get("status") != "removed"
            and f["filename"].endswith(".py") and (Path(f["filename"]).name.startswith("test_") or Path(f["filename"]).name.endswith("_test.py"))]


def parse_candidate(repo, commit, license_info, sources, *, evidence_kind=None, evidence_url=None, detail=None):
    message = commit["commit"]["message"]
    selected = [p for p in test_files(commit) if p in sources and ("playwright" in sources[p] or re.search(r"\bpage[.:]", sources[p])) and re.search(r"\bdef test_", sources[p])]
    spdx = (license_info.get("license") or {}).get("spdx_id")
    match = AGENT.search(message)
    if repo.get("private") or spdx not in LICENSES or not selected or (not evidence_kind and not match):
        return None
    sha = commit["sha"]
    if not SHA.fullmatch(sha):
        raise ValueError("GitHub returned a non-pinned commit")
    kind = evidence_kind or ("generated_tests" if not match.group(0).lower().startswith("co-authored") else "test_commit")
    row = dict.fromkeys(FIELDS, "")
    row.update(repo=repo["full_name"], commit_sha=sha, group="unresolved" if kind in {"guidance_only", "historical_lead"} else "agent",
               evidence_kind=kind, evidence_url=evidence_url or commit["html_url"],
               evidence_detail=detail or "Commit modifies selected Python browser tests; " + match.group(0),
               test_paths=json.dumps(selected), license=spdx, license_url=license_info["html_url"],
               approved="no", recipe="recipes/REVIEW_REQUIRED.json",
               observable_calls=str(static_screen({p: sources[p] for p in selected})["observable_calls"]))
    return row


def sources_at(api, repo, sha, paths):
    sources = {}
    for path in paths[:100]:
        blob = api.get(f"repos/{repo}/contents/{urllib.parse.quote(path)}", ref=sha)
        sources[path] = base64.b64decode(blob["content"]).decode("utf-8")
    return sources


def tree_tests(api, repo, sha):
    tree = api.get(f"repos/{repo}/git/trees/{sha}", recursive=1)
    if tree.get("truncated"):
        raise ValueError("tree truncated; manual file selection required")
    return test_files({"files": [{"filename": x["path"]} for x in tree["tree"] if x["type"] == "blob"]})[:100]


def search_specs(mode, queries):
    if mode in {"all", "commits"}:
        for q in queries:
            yield "commits", q, None
    if mode in {"all", "agent-prs"}:
        for author in PR_AUTHORS:
            yield "issues", f"is:pr author:{author} playwright pytest", "agent_pr"
    if mode in {"all", "guidance"}:
        for name in ("AGENTS.md", "CLAUDE.md"):
            yield "code", f"filename:{name} playwright test", "guidance_only"
    if mode in {"all", "human"}:
        yield "repositories", "playwright language:Python created:<2021-01-01", "historical_lead"


def discover(api, queries, pages, mode="commits"):
    rows, audit, seen = [], [], set()
    for endpoint, query, kind in search_specs(mode, queries):
        for page in range(1, pages + 1):
            try:
                hits = api.get("search/" + endpoint, q=query, per_page=30, page=page)
            except (OSError, ValueError) as exc:
                audit.append({"query": query, "evidence_kind": kind or "test_commit", "error": str(exc)})
                break
            audit.append({"query": query, "evidence_kind": kind or "test_commit", "page": page,
                          "incomplete_results": hits.get("incomplete_results", False), "total_count": hits.get("total_count")})
            for item in hits.get("items", []):
                repo, sha = "", ""
                try:
                    if endpoint == "commits":
                        repo, sha = item["repository"]["full_name"], item["sha"]
                    elif endpoint == "issues":
                        repo = item["repository_url"].split("/repos/")[1]
                    elif endpoint == "code":
                        repo = item["repository"]["full_name"]
                    else:
                        repo = item["full_name"]
                    metadata = api.get("repos/" + repo)
                    detail, evidence = None, None
                    if kind == "agent_pr":
                        pr = api.get(f"repos/{repo}/pulls/{item['number']}")
                        sha = pr["head"]["sha"]
                        changed = []
                        for files_page in range(1, 4):
                            batch = api.get(f"repos/{repo}/pulls/{item['number']}/files", per_page=100, page=files_page)
                            changed.extend(batch)
                            if len(batch) < 100:
                                break
                        if pr.get("changed_files", 0) > len(changed):
                            raise ValueError("PR file list truncated")
                        commit = {"sha": sha, "html_url": pr["html_url"], "commit": {"message": ""}, "files": changed}
                        evidence, detail = pr["html_url"], "Agent-authored PR modifies selected Python browser tests; review diff and attribution."
                    else:
                        if kind == "historical_lead":
                            if metadata["created_at"] >= HISTORICAL_CUTOFF:
                                continue
                            old = api.get(f"repos/{repo}/commits", until=HISTORICAL_CUTOFF, per_page=1)
                            if not old:
                                continue
                            sha = old[0]["sha"]
                        elif kind == "guidance_only":
                            sha = api.get(f"repos/{repo}/commits/{metadata['default_branch']}")["sha"]
                        commit = api.get(f"repos/{repo}/commits/{sha}")
                        if kind in {"guidance_only", "historical_lead"}:
                            if kind == "historical_lead" and (commit["commit"]["author"]["date"] >= HISTORICAL_CUTOFF or commit["commit"]["committer"]["date"] >= HISTORICAL_CUTOFF):
                                continue
                            commit["files"] = [{"filename": p} for p in tree_tests(api, repo, sha)]
                            if kind == "guidance_only":
                                guidance = sources_at(api, repo, sha, [item["path"]])[item["path"]]
                                if not re.search(r"test", guidance, re.I):
                                    continue
                                evidence = f"https://github.com/{repo}/blob/{sha}/{item['path']}"
                                detail = "Guidance mentions tests; does not prove selected tests were agent-written."
                            else:
                                detail = f"Historical lead only: repo created {metadata['created_at']}; author date {commit['commit']['author']['date']}; commit date {commit['commit']['committer']['date']}. Dates are not authorship proof; person must classify."
                    identity = (repo, sha, kind)
                    if identity in seen:
                        continue
                    seen.add(identity)
                    license_info = pinned_license(api, repo, sha)
                    if license_info.get("reason") == "no license":
                        audit.append({"repo": repo, "sha": sha, "evidence_kind": kind or "test_commit", "candidate": False, "reason": "no license"})
                        continue
                    sources = sources_at(api, repo, sha, test_files(commit))
                    row = parse_candidate(metadata, commit, license_info, sources, evidence_kind=kind, evidence_url=evidence, detail=detail)
                    if row:
                        rows.append(row)
                    audit.append({"repo": repo, "sha": sha, "evidence_kind": row["evidence_kind"] if row else kind or "test_commit",
                                  "candidate": bool(row), "screen": static_screen(sources),
                                  "reason": "person review required" if row else "no recognized license, matching evidence or Python browser tests"})
                except (OSError, ValueError, KeyError, SyntaxError) as exc:
                    audit.append({"repo": repo, "sha": sha, "evidence_kind": kind or "test_commit", "error": str(exc)})
            if len(hits.get("items", [])) < 30:
                break
    return rows, audit


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, default=Path("study/candidates.csv"))
    p.add_argument("--query", action="append")
    p.add_argument("--mode", choices=("all", "commits", "agent-prs", "guidance", "human"), default="all")
    p.add_argument("--pages", type=int, default=1)
    args = p.parse_args()
    if not 1 <= args.pages <= 10:
        p.error("pages must be between 1 and 10")
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        p.error("GITHUB_TOKEN is required for search; never pass it to run_study or Docker")
    rows, audit = discover(GitHub(token), args.query or QUERIES, args.pages, args.mode)
    # Multiple provenance routes can identify the same snapshot. Keep the first
    # lead in the manifest; retain every evidence route in the audit.
    unique = {}
    for row in rows:
        unique.setdefault((row["repo"], row["commit_sha"]), row)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_rows(args.output, list(unique.values()))
    totals = dict(Counter(row["evidence_kind"] for row in unique.values()))
    write_json(args.output.with_suffix(".audit.json"), {"retrieved_at": datetime.now(timezone.utc).isoformat(),
        "mode": args.mode, "queries": args.query or QUERIES, "records": audit, "candidate_counts_by_evidence_type": totals,
        "automatic_approvals": False})
    print(json.dumps({"unapproved_leads": len(unique), "by_evidence_type": totals}))


if __name__ == "__main__":
    main()
