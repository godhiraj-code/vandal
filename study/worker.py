"""Trusted worker. Public mode must only be invoked inside the study container."""
import argparse
import json
import os
import tarfile
import time
import sys
import posixpath
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

from study.common import safe_path, write_json
from study.process import clean_env, run


def extract_source(archive, destination, recipe=None):
    """Skip only inert documentation links in recipe mode; never materialize links."""
    with tarfile.open(archive) as tar:
        members = tar.getmembers()
        if len(members) > 20000 or sum(m.size for m in members) > 128 * 1024 * 1024:
            raise ValueError("source archive exceeds limits")
        seen, links, skipped = set(), {}, []
        protected = [] if recipe is None else recipe['test_paths'] + recipe.get('requirements', [])
        protected += [] if recipe is None else recipe.get('source_paths', [])
        def runtime(path):
            parts = Path(path).parts
            return (parts[0] in {'src', 'site', 'static', 'templates', 'tests', 'test'} or
                    any(path == p or path.startswith(p.rstrip('/') + '/') or
                        (str(Path(p).parent) != '.' and path.startswith(Path(p).parent.as_posix() + '/'))
                        for p in protected) or
                    (recipe.get('install_project', False) and Path(path).name.lower().startswith(('readme', 'license'))))
        def documentation(path):
            return (Path(path).suffix.lower() in {'.md', '.rst', '.txt'} and
                    (path.split('/')[0] == 'docs' or Path(path).name in {'CLAUDE.md', 'AGENTS.md'}))
        for m in members:
            name = m.name.rstrip("/")
            safe_path(name)
            if name in seen or not (m.isfile() or m.isdir() or (recipe is not None and m.issym())):
                raise ValueError("archive contains duplicate or nonregular entry")
            seen.add(name)
            if m.issym():
                target = m.linkname
                if not target or target.startswith('/') or any(c in target for c in '\\:\x00\r\n'):
                    raise ValueError('symlink escapes archive or has unsafe target: ' + name)
                target = posixpath.normpath(posixpath.join(posixpath.dirname(name), target))
                safe_path(target)
                links[name] = target
        for name, target in links.items():
            visited = {name}
            while target in links:
                if target in visited:
                    raise ValueError('symlink cycle: ' + name)
                visited.add(target)
                target = links[target]
            if target not in seen or any(part in links for part in (p.as_posix() for p in Path(target).parents)):
                raise ValueError('symlink target missing or traverses a link: ' + name)
            if runtime(name) or runtime(target) or not (documentation(name) and documentation(target)):
                raise ValueError('symlink intersects test/source or unknown runtime scope: ' + name)
            skipped.append({'path': name, 'target': links[name], 'reason': 'documentation outside recipe runtime scope'})
        if any(any(p.as_posix() in links for p in Path(m.name).parents) for m in members):
            raise ValueError('archive member traverses symlink')
        for m in members:
            if m.issym():
                continue
            target = destination / m.name
            if m.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(m) as src, target.open("xb") as dst:
                    while chunk := src.read(65536):
                        dst.write(chunk)
        return skipped


def validate_recipe(recipe):
    allowed = {"test_paths", "source_paths", "requirements", "install_project", "extras", "pytest_args"}
    if set(recipe) - allowed:
        raise ValueError("unsupported recipe key")
    for key in ("test_paths", "source_paths", "requirements", "extras", "pytest_args"):
        if not isinstance(recipe.get(key, []), list) or any(not isinstance(x, str) for x in recipe.get(key, [])):
            raise ValueError("recipe fields must be lists of strings")
    if not recipe.get("test_paths") or len(recipe["test_paths"]) > 100:
        raise ValueError("recipe requires bounded test selection")
    for path in recipe["test_paths"] + recipe.get("requirements", []) + recipe.get('source_paths', []):
        safe_path(path)
    if type(recipe.get("install_project", False)) is not bool:
        raise ValueError("install_project must be boolean")
    import re
    if any(not re.fullmatch(r"[A-Za-z0-9_-]+", x) for x in recipe.get("extras", [])):
        raise ValueError("invalid project extras")
    # Scope and configuration overrides must be reviewed, but cannot change runner
    # plugins, output paths, strategies, browser mode or spawn distributed workers.
    args = recipe.get("pytest_args", [])
    if len(args) % 2 or any(args[i] not in {"-m", "-k"} for i in range(0, len(args), 2)):
        raise ValueError("only -m/-k expression pairs are supported")
    return recipe


def baseline_reason(result, junit):
    if result["timed_out"]:
        return "baseline timeout"
    if result["log_limited"]:
        return "baseline log limit exceeded"
    if result["exit_code"] != 0:
        return f"baseline failed (pytest exit {result['exit_code']}); see baseline.log"
    try:
        root = ET.parse(junit).getroot()
        cases = list(root.iter("testcase"))
        if not cases:
            return "baseline collected no tests"
        if any(c.find("failure") is not None or c.find("error") is not None for c in cases):
            return "baseline contains failure/error despite successful exit"
        if any(c.find("skipped") is not None for c in cases):
            return "baseline skipped or xfailed tests; selection not fully exercised"
    except (OSError, ET.ParseError):
        return "baseline has no valid JUnit evidence"
    return None


def classify_failed_run(status, output):
    if status.get('status') != 'completed':
        text = status.get('reason', '')
        for name in ('baseline.log', 'mutation.log', 'install.log', 'venv.log', 'harness-install.log'):
            path = output / name
            if path.is_file() and not path.is_symlink():
                with path.open('r', encoding='utf-8', errors='replace') as stream:
                    text += stream.read(8 * 1024 * 1024)
        if any(token in text.lower() for token in ('pthread_create', 'resource temporarily unavailable')):
            status['error_class'] = 'resource_exhausted'
    return status


def execute(source, output, recipe, python, seconds, env=None):
    """Shared real baseline/mutation pipeline; fixture runner supplies its own venv."""
    output.mkdir(parents=True, exist_ok=True)
    recipe = validate_recipe(recipe)
    # Exact same selection and addopts override both times. Repo-specific startup
    # remains in its fixtures. No display or external network is supplied.
    base = [str(python), "-m", "pytest", "-o", "addopts=", "-q"] + recipe.get("pytest_args", [])
    selected = recipe["test_paths"]
    deadline = time.monotonic() + seconds
    # Vandal appends worker flags to the original invocation. A '--' delimiter
    # would turn those flags into paths. Selection paths are validated instead.
    baseline = run(base + ["-p", "no:vandal", "--junitxml=" + str(output / "baseline.xml")] + selected,
                   source, output / "baseline.log", max(0.1, deadline - time.monotonic()), env)
    status = {"status": "skipped", "baseline": baseline, "recipe": recipe}
    reason = baseline_reason(baseline, output / "baseline.xml")
    if reason:
        status["reason"] = reason
        return classify_failed_run(status, output)
    guarded = [str(python), str(Path(__file__).with_name('pytest_entry.py'))] + base[3:]
    guarded_env = dict(env or clean_env(), STUDY_RESOURCE_LOG=str(output / 'resources.jsonl'))
    mutation = run(guarded + ["--vandal", "--vandal-report=" + str(output / "vandal_report.json")] + selected,
                   source, output / "mutation.log", max(0.1, deadline - time.monotonic()), guarded_env)
    status["mutation"] = mutation
    report = output / "vandal_report.json"
    if mutation["timed_out"] or mutation["log_limited"]:
        status.update(status="incomplete", reason="mutation timeout or log limit; partial report excluded from comparison")
    elif mutation["exit_code"] != 0 or not report.exists():
        status.update(reason="mutation failed or did not produce report; see mutation.log")
    else:
        status.update(status="completed", reason="")
    return classify_failed_run(status, output)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--seconds", type=int, required=True)
    args = p.parse_args()
    source, output = Path("/work/source"), Path("/work/out")
    source.mkdir(parents=True)
    output.mkdir(parents=True)
    started = time.monotonic()
    status = {"status": "skipped", "reason": "worker did not complete"}
    skipped_links = []
    try:
        shutil.copyfile('/opt/harness.lock', output / 'harness.lock')
        recipe = validate_recipe(json.loads(Path("/input/recipe.json").read_text()))
        skipped_links = extract_source("/input/source.tar", source, recipe)
        env = clean_env()
        env.update(HOME="/work/home", TMPDIR="/tmp", PLAYWRIGHT_BROWSERS_PATH="/ms-playwright",
                   PIP_NO_INDEX="1", PIP_FIND_LINKS="/deps")
        Path(env["HOME"]).mkdir()
        creation = run([sys.executable, "-m", "virtualenv", "--no-download", "--no-seed", "/work/venv"], source, output / "venv.log",
                       max(0.1, args.seconds - (time.monotonic() - started)), env)
        if creation["exit_code"] or creation["timed_out"] or creation["log_limited"]:
            raise RuntimeError("fresh venv creation failed or exceeded bounds; see venv.log")
        python = Path("/work/venv/bin/python")
        harness_install = run([sys.executable, '-m', 'pip', '--python', str(python), 'install',
                              '--no-index', '--find-links=/opt/wheels', '--require-hashes', '-r', '/opt/harness.lock'],
                             source, output / 'harness-install.log',
                             max(0.1, args.seconds - (time.monotonic() - started)), env)
        if harness_install['exit_code'] or harness_install['timed_out'] or harness_install['log_limited']:
            raise RuntimeError('hash-locked harness installation failed; see harness-install.log')
        # Owned package and dependencies are already hash-installed.
        cmd = [str(python), "-m", "pip", "install", "--no-index", "--find-links=/deps"]
        for req in recipe.get("requirements", []):
            cmd += ["-r", str(source / req)]
        if recipe.get("install_project"):
            project = str(source)
            if recipe.get("extras"):
                project += "[" + ",".join(recipe["extras"]) + "]"
            cmd += [project]
        installation = run(cmd if len(cmd) > 6 else [str(python), '-m', 'pip', 'check'], source, output / "install.log",
                           max(0.1, args.seconds - (time.monotonic() - started)), env)
        if installation["exit_code"] or installation["timed_out"] or installation["log_limited"]:
            status["reason"] = "offline installation failed or exceeded limit; see install.log"
        else:
            run([str(python), "-m", "pip", "freeze", "--all"], source, output / "environment.txt", 15, env)
            status = execute(source, output, recipe, python,
                             max(0.1, args.seconds - (time.monotonic() - started)), env)
        status["installation"] = installation
    except Exception as exc:
        status.update(status="skipped", reason=f"{type(exc).__name__}: {exc}")
    status['skipped_links'] = skipped_links
    classify_failed_run(status, output)
    write_json(output / "worker-status.json", status)
    # Keep tmpfs alive for bounded host export, never wait indefinitely.
    Path("/work/done").touch()
    time.sleep(60)


if __name__ == "__main__":
    main()
