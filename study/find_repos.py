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

AGENT = re.compile(r"co-authored-by:.*(?:claude|codex|copilot|cursor|devin|jules|anthropic-code-agent|aider|openhands)", re.I)
GENERATED = re.compile(r"generated tests|tests? (?:were )?generated(?: by| with)?", re.I)
QUERIES = ['playwright pytest "Co-Authored-By: Claude"', 'playwright pytest "Co-authored-by: Cursor"', 'playwright pytest "Co-authored-by: Copilot"', 'playwright "generated tests"']
QUERIES += ['playwright pytest "Co-authored-by: aider"', 'playwright pytest "Co-authored-by: OpenHands"']
PR_AUTHORS = ("app/copilot-swe-agent", "app/devin-ai-integration", "app/google-labs-jules")
PR_SIGNALS = (
    'is:pr is:merged "Generated with Claude Code" in:body pytest-playwright',
    'is:pr is:merged "Generated with Claude Code" in:body playwright pytest',
    'is:pr head:cursor/ playwright pytest',
    'is:pr "aider" playwright pytest',
    'is:pr "OpenHands" playwright pytest',
)
CODE_QUERIES = ('language:Python "playwright.sync_api" path:tests',
                'language:Python "def test_" "page" "pytest" path:tests')
OBSERVABLE = {"locator", "frame_locator", "expect", "click", "fill", "check", "hover", "inner_text", "input_value"}


def _tree(source, path):
    return ast.parse(source.lstrip("\ufeff"), filename=path)


def browser_file(tree, support=""):
    imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
    modules = [node.module or "" for node in imports if isinstance(node, ast.ImportFrom)]
    modules += [alias.name for node in imports if isinstance(node, ast.Import) for alias in node.names]
    playwright = any(name == "playwright" or name.startswith("playwright.") for name in modules)
    foreign = any(name.split(".")[0] in {"selenium", "appium"} for name in modules)
    # A page-shaped argument alone is insufficient: require a pinned declaration
    # of pytest-playwright in supporting configuration/fixtures as well.
    fixture = any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                  and node.name.startswith("test_") and any(a.arg == "page" for a in node.args.args)
                  and any(isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                          and (call.func.attr in OBSERVABLE | {"goto"} or call.func.attr.startswith("get_by_"))
                          and isinstance(call.func.value, ast.Name) and call.func.value.id == "page"
                          for call in ast.walk(node)) for node in ast.walk(tree))
    plugin = bool(re.search(r"pytest[-_]playwright", support))
    page_object = any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test_")
                      and any(a.arg == "page" for a in n.args.args)
                      and any(isinstance(c, ast.Call) and any(isinstance(a, ast.Name) and a.id == "page" for a in c.args)
                              for c in ast.walk(n)) for n in ast.walk(tree))
    return playwright or ((fixture or page_object) and plugin and not foreign)


def page_fixtures(sources):
    """Recognize simple pytest fixtures returning page or a page-returning factory."""
    pages, factories = {"page"}, set()
    for path, source in sources.items():
        if not path.endswith("conftest.py"):
            continue
        for node in ast.walk(_tree(source, path)):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or not any(a.arg == "page" for a in node.args.args):
                continue
            if not any("fixture" in ast.unparse(d) for d in node.decorator_list):
                continue
            inner = {n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                     and any(isinstance(r, ast.Return) and isinstance(r.value, ast.Name) and r.value.id == "page" for r in ast.walk(n))}
            returned = {n.value.id for n in node.body if isinstance(n, ast.Return) and isinstance(n.value, ast.Name)}
            if "page" in returned:
                pages.add(node.name)
            if inner & returned:
                factories.add(node.name)
    return pages, factories


def offline_flags(sources):
    """Conservative source/config risk flags; never an observed offline failure."""
    flags = []
    for path, source in sorted(sources.items()):
        source = source.lstrip("\ufeff")
        for number, line in enumerate(source.splitlines(), 1):
            for url in re.findall(r"https?://[^\s\"'<>]+", line):
                try:
                    host = urllib.parse.urlparse(url).hostname
                except ValueError:
                    flags.append({"file": path, "line": number, "kind": "malformed_url", "detail": "URL requires manual review"})
                    continue
                if host and host not in {"localhost", "127.0.0.1", "::1"}:
                    flags.append({"file": path, "line": number, "kind": "external_host", "detail": host})
            if re.search(r"base[_-]url", line, re.I):
                flags.append({"file": path, "line": number, "kind": "base_url", "detail": "review configured browser origin"})
        if path.endswith(".py"):
            tree = _tree(source, path)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                literals = " ".join(str(x.value) for x in ast.walk(node) if isinstance(x, ast.Constant) and isinstance(x.value, str))
                function = ast.unparse(node.func)
                # Inspect arguments as data, including argv lists and shell strings.
                if ("git" in literals and "clone" in literals) or function.endswith(".clone_from"):
                    flags.append({"file": path, "line": node.lineno, "kind": "git_clone", "detail": "runtime source acquisition"})
                if re.search(r"\bdocker\b", literals) or "docker" in function.lower():
                    kind = "docker_availability" if any(x in function + " " + literals for x in ("which", "info", "version", "ping", "from_env")) else "docker_use"
                    flags.append({"file": path, "line": node.lineno, "kind": kind, "detail": "requires Docker/runtime review"})
        elif re.search(r"\bdocker\b|git\s+clone", source):
            flags.append({"file": path, "line": 0, "kind": "setup_command", "detail": "Docker or git clone mentioned in configuration"})
    return [dict(x) for x in {tuple(sorted(flag.items())): flag for flag in flags}.values()]


def local_import_paths(path, tree, available):
    found = set()
    for node in ast.walk(tree):
        modules = []
        bases = [Path("."), Path("src"), Path(path).parent]
        if isinstance(node, ast.Import):
            modules = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            modules = [node.module or ""] + [(node.module + "." if node.module else "") + a.name for a in node.names if a.name != "*"]
            if node.level:
                base = Path(path).parent
                for _ in range(node.level - 1):
                    base = base.parent
                bases = [base]
        for module in modules:
            for base in bases:
                stem = base / module.replace(".", "/")
                targets = [str(stem) + ".py", str(stem / "__init__.py")]
                targets += [str(parent / "__init__.py") for parent in stem.parents if parent != Path(".")]
                found.update(Path(p).as_posix() for p in targets if Path(p).as_posix() in available)
    return sorted(found)


def static_screen(sources, supporting_sources=None):
    """Count browser-rooted call sites only; no imports or candidate execution.

    Canonical page variables, locator assignments and expect arguments are tracked.
    This is conservative syntactic provenance, not Python type or runtime analysis.
    Imported/custom wrappers and dynamically produced locators can be missed.
    """
    support = supporting_sources or {}
    fixture_pages, fixture_factories = page_fixtures(support)
    # Include statically imported local page-object modules once, without imports
    # or evaluating their constructors. Dynamic dispatch remains a heuristic.
    expanded = dict(sources)
    available = set(support)
    pending = [p for p, text in sources.items() if browser_file(_tree(text, p), "\n".join(support.values()))]
    while pending:
        path = pending.pop()
        tree = _tree(expanded[path], path)
        for helper in local_import_paths(path, tree, available):
            if helper not in expanded:
                expanded[helper] = support[helper]
                pending.append(helper)
    per_file = {}
    for path, source in sorted(expanded.items()):
        tree = _tree(source, path)
        selected = browser_file(tree, "\n".join(support.values())) or path not in sources
        names = []
        expect_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("playwright"):
                expect_names.update(a.asname or a.name for a in node.names if a.name == "expect")

        class Calls(ast.NodeVisitor):
            def __init__(self):
                self.roots = set()
                self.factories = set()
                self.attributes = set()

            def rooted(self, node):
                if isinstance(node, ast.Name):
                    return node.id in self.roots
                if isinstance(node, ast.Attribute):
                    return ast.unparse(node) in self.attributes or self.rooted(node.value)
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id in self.factories:
                        return True
                    if isinstance(node.func, ast.Name) and node.func.id in expect_names:
                        return bool(node.args) and self.rooted(node.args[0])
                    if isinstance(node.func, ast.Attribute) and (node.func.attr in {"locator", "frame_locator", "nth", "filter", "all"} or node.func.attr.startswith("get_by_")):
                        return self.rooted(node.func.value)
                return False

            def visit_FunctionDef(self, node):
                saved, saved_factories = self.roots, self.factories
                self.roots = (saved - {a.arg for a in node.args.args}) | {a.arg for a in node.args.args if a.arg in fixture_pages
                              or (a.annotation and ast.unparse(a.annotation).split(".")[-1] in {"Page", "Locator"})}
                self.factories = (saved_factories - {a.arg for a in node.args.args}) | {a.arg for a in node.args.args if a.arg in fixture_factories}
                for statement in node.body:
                    self.visit(statement)
                self.roots = saved
                self.factories = saved_factories

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_ClassDef(self, node):
                saved = self.attributes
                self.attributes = set()
                # Establish page-object fields from constructor arguments before
                # visiting methods, irrespective of method definition order.
                constructor = next((n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == "__init__"), None)
                if constructor:
                    self.visit(constructor)
                for statement in node.body:
                    if statement is not constructor:
                        self.visit(statement)
                self.attributes = saved

            def visit_For(self, node):
                self.visit(node.iter)
                saved = self.roots.copy()
                if isinstance(node.target, ast.Name):
                    self.roots.discard(node.target.id)
                    if isinstance(node.iter, ast.Call) and isinstance(node.iter.func, ast.Attribute) and node.iter.func.attr == "all" and self.rooted(node.iter.func.value):
                        self.roots.add(node.target.id)
                for statement in node.body + node.orelse:
                    self.visit(statement)
                self.roots = saved

            visit_AsyncFor = visit_For

            def visit_Assign(self, node):
                self.visit(node.value)
                for target in node.targets:
                    if isinstance(target, ast.Attribute):
                        if self.rooted(node.value):
                            self.attributes.add(ast.unparse(target))
                        else:
                            self.attributes.discard(ast.unparse(target))
                    if isinstance(target, ast.Name):
                        if self.rooted(node.value):
                            self.roots.add(target.id)
                        else:
                            self.roots.discard(target.id)

            def visit_AnnAssign(self, node):
                if node.value is not None:
                    self.visit_Assign(ast.Assign(targets=[node.target], value=node.value))

            def visit_Call(self, node):
                name = node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id if isinstance(node.func, ast.Name) else ""
                is_expect = isinstance(node.func, ast.Name) and name in expect_names
                if (is_expect and node.args and self.rooted(node.args[0])) or (
                    isinstance(node.func, ast.Attribute) and (name in OBSERVABLE - {"expect"} or name.startswith("get_by_")) and self.rooted(node.func.value)):
                    names.append("expect" if is_expect else name)
                self.generic_visit(node)

        if selected:
            Calls().visit(tree)
        per_file[path] = {"selected": selected, "count": len(names), "calls": dict(sorted(Counter(names).items()))}
    risks = offline_flags({**support, **sources})
    return {"observable_calls": sum(x["count"] for x in per_file.values()), "files": per_file,
            "external_host_literals": sorted({f["detail"] for f in risks if f["kind"] == "external_host"}),
            "offline_risk": risks, "heuristic_only": True}


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
        return json.loads(data.decode("utf-8-sig"))


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


def parse_candidate(repo, commit, license_info, sources, *, evidence_kind=None, evidence_url=None, detail=None, supporting_sources=None):
    message = commit["commit"]["message"]
    screen = static_screen(sources, supporting_sources)
    selected = [p for p in test_files(commit) if p in screen["files"] and screen["files"][p]["selected"]
                and re.search(r"\bdef test_", sources[p])]
    spdx = (license_info.get("license") or {}).get("spdx_id")
    strong = AGENT.search(message)
    match = strong or GENERATED.search(message)
    if repo.get("private") or spdx not in LICENSES or not selected or (not evidence_kind and not match):
        return None
    # Risks in unrelated changed unit tests must not be attributed to this selection.
    screen = static_screen({p: sources[p] for p in selected}, supporting_sources)
    if not screen["observable_calls"]:
        return None
    sha = commit["sha"]
    if not SHA.fullmatch(sha):
        raise ValueError("GitHub returned a non-pinned commit")
    kind = evidence_kind or ("test_commit" if strong else "generated_tests")
    row = dict.fromkeys(FIELDS, "")
    row.update(repo=repo["full_name"], commit_sha=sha, group="unresolved" if kind in {"guidance_only", "generated_tests"} else "agent",
               evidence_kind=kind, evidence_url=evidence_url or commit["html_url"],
               evidence_detail=detail or "Commit modifies selected Python browser tests; " + (match.group(0) if match else kind),
               test_paths=json.dumps(selected), license=spdx, license_url=license_info["html_url"],
               approved="no", recipe="recipes/REVIEW_REQUIRED.json",
               observable_calls=str(screen["observable_calls"]),
               offline_risk=json.dumps(screen["offline_risk"]))
    return row


def sources_at(api, repo, sha, paths):
    sources = {}
    for path in paths[:100]:
        blob = api.get(f"repos/{repo}/contents/{urllib.parse.quote(path)}", ref=sha)
        sources[path] = base64.b64decode(blob["content"]).decode("utf-8-sig")
    return sources


def supporting_at(api, repo, sha, test_paths, sources=None):
    """Read config/fixtures at the same SHA, never import them. Missing is normal."""
    candidates = set()
    for test in test_paths:
        for parent in Path(test).parents:
            for name in ("conftest.py", "pytest.ini", "setup.cfg", "tox.ini", "pyproject.toml", "requirements.txt", "requirements-dev.txt"):
                candidates.add((parent / name).as_posix())
    result = {}
    for path in sorted(candidates):
        try:
            result.update(sources_at(api, repo, sha, [path]))
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
    # Resolve only repository-local imports, using a pinned tree as an allowlist.
    seeds = {**(sources or sources_at(api, repo, sha, test_paths)), **result}
    if any(path.endswith(".py") and any(isinstance(n, (ast.Import, ast.ImportFrom)) for n in ast.walk(_tree(text, path))) for path, text in seeds.items()):
        tree = api.get(f"repos/{repo}/git/trees/{sha}", recursive=1)
        if tree.get("truncated"):
            raise ValueError("helper tree truncated; manual inspection required")
        available = {x["path"] for x in tree["tree"] if x["type"] == "blob" and x["path"].endswith(".py")}
        pending, visited = list(seeds.items()), set(seeds)
        while pending:
            path, source = pending.pop()
            if not path.endswith(".py"):
                continue
            for candidate in local_import_paths(path, _tree(source, path), available):
                if candidate in visited:
                    continue
                if len(visited) >= 200:
                    raise ValueError("helper scan exceeds 200 files; manual inspection required")
                visited.add(candidate)
                fetched = sources_at(api, repo, sha, [candidate])
                result.update(fetched)
                pending.extend(fetched.items())
    return result


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
        for query in PR_SIGNALS:
            yield "issues", query, "pr_signal"
    if mode in {"all", "guidance"}:
        for name in ("AGENTS.md", "CLAUDE.md"):
            yield "code", f"filename:{name} playwright test", "guidance_only"
    if mode in {"all", "code"}:
        for query in CODE_QUERIES:
            yield "code", query, "code_only"


def pr_provenance(pr):
    """Verify signals in the fetched PR, not merely its search result."""
    body = pr.get("body") or ""
    author = (pr.get("user") or {}).get("login", "").lower()
    bots = {"copilot", "copilot-swe-agent[bot]", "devin-ai-integration[bot]",
            "google-labs-jules[bot]", "openhands[bot]", "cursor[bot]"}
    generated = bool(re.search(r"generated with\s+\[?claude code\b", body, re.I)) and bool(pr.get("merged_at"))
    if author in bots or generated or AGENT.search(body):
        return "agent_pr", "Visible agent involvement in PR modifying selected tests; review diff, not exclusive-authorship proof."
    return "guidance_only", "Branch/keyword/code signal only; test-specific agent authorship remains unverified."


def discover(api, queries, pages, mode="commits"):
    if type(pages) is not int or not 1 <= pages <= 10:
        raise ValueError("pages must be 1..10 (100 results/page, GitHub's 1000-result cap)")
    rows, audit, seen = [], [], set()
    for endpoint, query, kind in search_specs(mode, queries):
        for page in range(1, pages + 1):
            try:
                hits = api.get("search/" + endpoint, q=query, per_page=100, page=page)
            except (OSError, ValueError) as exc:
                audit.append({"query": query, "evidence_kind": kind or "test_commit", "error": str(exc)})
                if isinstance(exc, urllib.error.HTTPError) and exc.code in {403, 429}:
                    audit.append({"reason": "search stopped on access/rate-limit response; no automatic retries or alternate credentials"})
                    return rows, audit
                break
            audit.append({"query": query, "evidence_kind": kind or "test_commit", "page": page,
                          "per_page": 100, "returned": len(hits.get("items", [])),
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
                    row_kind = kind
                    if endpoint == "issues":
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
                        row_kind, detail = pr_provenance(pr)
                        evidence = pr["html_url"]
                    else:
                        if kind in {"guidance_only", "code_only"}:
                            sha = api.get(f"repos/{repo}/commits/{metadata['default_branch']}")["sha"]
                        commit = api.get(f"repos/{repo}/commits/{sha}")
                        if kind == "code_only":
                            commit["files"] = [{"filename": item["path"]}]
                            row_kind = "guidance_only"
                            evidence = f"https://github.com/{repo}/blob/{sha}/{item['path']}"
                            detail = "Python browser code presence only; no test-specific agent authorship established."
                        if kind == "guidance_only":
                            commit["files"] = [{"filename": p} for p in tree_tests(api, repo, sha)]
                            if kind == "guidance_only":
                                guidance = sources_at(api, repo, sha, [item["path"]])[item["path"]]
                                if not re.search(r"test", guidance, re.I):
                                    continue
                                evidence = f"https://github.com/{repo}/blob/{sha}/{item['path']}"
                                detail = "Guidance mentions tests; does not prove selected tests were agent-written."
                    # Code hits select individual files, and provenance modes may
                    # share a label without having screened the same evidence.
                    identity = (repo, sha, endpoint, row_kind,
                                (kind, item["path"]) if endpoint == "code" else None)
                    if identity in seen:
                        continue
                    seen.add(identity)
                    license_info = pinned_license(api, repo, sha)
                    if license_info.get("reason") == "no license":
                        audit.append({"repo": repo, "sha": sha, "evidence_kind": kind or "test_commit", "candidate": False, "reason": "no license"})
                        continue
                    sources = sources_at(api, repo, sha, test_files(commit))
                    support = supporting_at(api, repo, sha, list(sources), sources)
                    row = parse_candidate(metadata, commit, license_info, sources, evidence_kind=row_kind, evidence_url=evidence, detail=detail, supporting_sources=support)
                    if row:
                        rows.append(row)
                    audit.append({"repo": repo, "sha": sha, "evidence_kind": row["evidence_kind"] if row else kind or "test_commit",
                                  "candidate": bool(row), "screen": static_screen(sources, support),
                                  "reason": "person review required" if row else "no recognized license, matching evidence or Python browser tests"})
                except (OSError, ValueError, KeyError, SyntaxError) as exc:
                    audit.append({"repo": repo, "sha": sha, "evidence_kind": kind or "test_commit", "error": str(exc)})
                    if isinstance(exc, urllib.error.HTTPError) and exc.code in {403, 429}:
                        audit.append({"reason": "discovery stopped on access/rate-limit response; no automatic retries or alternate credentials"})
                        return rows, audit
            if page == 10 and hits.get("total_count", 0) > 1000:
                audit.append({"query": query, "reason": "GitHub 1000-result search cap; remaining hits not retrieved"})
            if len(hits.get("items", [])) < 100:
                break
    return rows, audit


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, default=Path("study/candidates.csv"))
    p.add_argument("--query", action="append")
    p.add_argument("--mode", choices=("all", "commits", "agent-prs", "guidance", "code"), default="all")
    p.add_argument("--pages", type=int, default=10)
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
