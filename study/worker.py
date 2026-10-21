"""Trusted worker. Public mode must only be invoked inside the study container."""
import argparse
import json
import os
import tarfile
import time
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from study.common import safe_path, write_json
from study.process import clean_env, run


def extract_source(archive, destination):
    """No symlinks, hardlinks, devices, traversal, duplicate members or oversized trees."""
    with tarfile.open(archive) as tar:
        members = tar.getmembers()
        if len(members) > 20000 or sum(m.size for m in members) > 128 * 1024 * 1024:
            raise ValueError("source archive exceeds limits")
        seen = set()
        for m in members:
            name = m.name.rstrip("/")
            safe_path(name)
            if name in seen or not (m.isfile() or m.isdir()):
                raise ValueError("archive contains duplicate or nonregular entry")
            seen.add(name)
        for m in members:
            target = destination / m.name
            if m.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(m) as src, target.open("xb") as dst:
                    while chunk := src.read(65536):
                        dst.write(chunk)


def validate_recipe(recipe):
    allowed = {"test_paths", "requirements", "install_project", "extras", "pytest_args"}
    if set(recipe) - allowed:
        raise ValueError("unsupported recipe key")
    for key in ("test_paths", "requirements", "extras", "pytest_args"):
        if not isinstance(recipe.get(key, []), list) or any(not isinstance(x, str) for x in recipe.get(key, [])):
            raise ValueError("recipe fields must be lists of strings")
    if not recipe.get("test_paths") or len(recipe["test_paths"]) > 100:
        raise ValueError("recipe requires bounded test selection")
    for path in recipe["test_paths"] + recipe.get("requirements", []):
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
        return status
    mutation = run(base + ["--vandal", "--vandal-report=" + str(output / "vandal_report.json")] + selected,
                   source, output / "mutation.log", max(0.1, deadline - time.monotonic()), env)
    status["mutation"] = mutation
    report = output / "vandal_report.json"
    if mutation["timed_out"] or mutation["log_limited"]:
        status.update(status="incomplete", reason="mutation timeout or log limit; partial report excluded from comparison")
    elif mutation["exit_code"] != 0 or not report.exists():
        status.update(reason="mutation failed or did not produce report; see mutation.log")
    else:
        status.update(status="completed", reason="")
    return status


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--seconds", type=int, required=True)
    args = p.parse_args()
    source, output = Path("/work/source"), Path("/work/out")
    source.mkdir(parents=True)
    output.mkdir(parents=True)
    started = time.monotonic()
    status = {"status": "skipped", "reason": "worker did not complete"}
    try:
        recipe = validate_recipe(json.loads(Path("/input/recipe.json").read_text()))
        extract_source("/input/source.tar", source)
        env = clean_env()
        env.update(HOME="/work/home", TMPDIR="/tmp", PLAYWRIGHT_BROWSERS_PATH="/ms-playwright",
                   PIP_NO_INDEX="1", PIP_FIND_LINKS="/deps")
        Path(env["HOME"]).mkdir()
        creation = run([sys.executable, "-m", "venv", "/work/venv"], source, output / "venv.log",
                       max(0.1, args.seconds - (time.monotonic() - started)), env)
        if creation["exit_code"] or creation["timed_out"] or creation["log_limited"]:
            raise RuntimeError("fresh venv creation failed or exceeded bounds; see venv.log")
        python = Path("/work/venv/bin/python")
        cmd = [str(python), "-m", "pip", "install", "--no-index", "--find-links=/deps",
               "/opt/study/vandal.whl"]
        # The image preserves the actual valid wheel filename in this list.
        cmd[-1:] = [str(x) for x in Path("/opt/wheels").glob("*.whl")]
        cmd += ["pytest-playwright==0.10.0", "playwright==1.64.0"]
        for req in recipe.get("requirements", []):
            cmd += ["-r", str(source / req)]
        if recipe.get("install_project"):
            project = str(source)
            if recipe.get("extras"):
                project += "[" + ",".join(recipe["extras"]) + "]"
            cmd += [project]
        installation = run(cmd, source, output / "install.log",
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
    write_json(output / "worker-status.json", status)
    # Keep tmpfs alive for bounded host export, never wait indefinitely.
    Path("/work/done").touch()
    time.sleep(60)


if __name__ == "__main__":
    main()
