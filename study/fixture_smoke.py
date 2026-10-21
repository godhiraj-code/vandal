"""Host-only owned fixture validation. No path option for arbitrary repositories."""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from study.common import digest, write_json
from study.process import clean_env, run
from study.worker import execute


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results", type=Path, default=Path("study/results/pilot/owned-fixture"))
    args = p.parse_args()
    output = args.results.resolve()
    output.mkdir(parents=True, exist_ok=False)
    fixture = Path(__file__).resolve().parent / "fixture/test_local_app.py"
    env = clean_env()
    with tempfile.TemporaryDirectory(prefix="vandal-owned-fixture-") as directory:
        source = Path(directory)
        shutil.copyfile(fixture, source / fixture.name)
        # A new local fixture repository exercises pinning without third-party code.
        for command in (["git", "init", "--template=", "."], ["git", "add", fixture.name],
                        ["git", "-c", "user.name=Study fixture", "-c", "user.email=fixture@invalid",
                         "-c", "core.hooksPath=/dev/null", "commit", "-m", "Owned harness fixture"]):
            result = run(command, source, output / "fixture-git.log", 15, env)
            if result["exit_code"]:
                raise RuntimeError("fixture git setup failed")
        sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, env=env, text=True).strip()
        recipe = {"test_paths": [fixture.name], "requirements": [], "install_project": False,
                  "extras": [], "pytest_args": []}
        run([sys.executable, "-m", "pip", "freeze", "--all"], source, output / "environment.txt", 15, env)
        status = execute(source, output, recipe, Path(sys.executable), 180, env)
        if status["status"] == "completed":
            from study.summarize import metrics
            measured, _ = metrics(json.loads((output / "vandal_report.json").read_text()))
            if not measured["n_scored"] or measured["error"]:
                status.update(status="unscored", reason="owned fixture did not produce error-free scored mutants")
    status.update(repo="owned-local-fixture", commit_sha=sha, group="fixture", kind="fixture",
                  isolation="host-only owned source; NOT container validation",
                  fixture_sha256=digest(fixture), python=sys.version,
                  reason=status.get("reason", ""))
    from study.redact import host_paths, redact_file
    for artifact in output.iterdir():
        if artifact.is_file():
            redact_file(artifact)
    status = host_paths(status)
    status["artifact_sha256"] = {f.name: digest(f) for f in output.iterdir() if f.is_file()}
    write_json(output / "status.json", status)
    print(status["status"], status["reason"])
    if status["status"] != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
