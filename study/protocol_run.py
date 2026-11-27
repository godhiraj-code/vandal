"""Score one agent-written suite for one approved protocol app.

The agent wrote study/protocol/suites/<agent>/<app>/tests_agent/ against a
snapshot of the pinned app. The harness fetches the same pinned SHA, places the
suite under <app_path>/tests_agent, runs it repeats times on the unchanged app
(flakiness), then mutation scores it only if every run was green. Execution
needs the exact RUN token printed by `print-confirm` and an approved workflow run.
"""
import argparse
import csv
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

from study.budget import validate_run_budget
from study.common import LICENSES, REPO, SHA, safe_path

ROOT = Path(__file__).resolve().parent / "protocol"
FIELDS = ["app", "repo", "commit_sha", "app_path", "license", "license_url", "recipe",
          "approved", "reviewer", "reviewed_at"]
NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,39}\Z")
SUITE_DIR = "tests_agent"


def read_apps(manifest):
    with Path(manifest).open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != FIELDS:
            raise ValueError("protocol manifest columns must match study/protocol_run.py FIELDS")
        rows = list(reader)
    if any(None in r or None in r.values() for r in rows):
        raise ValueError("malformed CSV row")
    if len({r["app"] for r in rows}) != len(rows):
        raise ValueError("duplicate app")
    return {r["app"]: r for r in rows}


def app_reason(row):
    if not NAME.fullmatch(row["app"]):
        return "invalid app name"
    if not REPO.fullmatch(row["repo"]) or not SHA.fullmatch(row["commit_sha"]):
        return "invalid repository or SHA"
    if row["license"] not in LICENSES:
        return "license requires explicit OSI verification/support"
    if not row["license_url"].startswith("https://github.com/" + row["repo"] + "/blob/" + row["commit_sha"] + "/"):
        return "license URL must reference the pinned commit"
    try:
        safe_path(row["recipe"])
        if row["app_path"]:
            safe_path(row["app_path"])
    except ValueError:
        return "invalid recipe or app path"
    if row["approved"] != "yes" or not row["reviewer"].strip():
        return "not approved by a person"
    try:
        datetime.strptime(row["reviewed_at"], "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return "invalid UTC review timestamp"
    return None


def plan(agent, app, manifest=ROOT / "apps.csv", suites=ROOT / "suites"):
    """Validated row, recipe and suite path; reads files only, executes nothing."""
    if not NAME.fullmatch(agent):
        raise ValueError("invalid agent name")
    rows = read_apps(manifest)
    if app not in rows:
        raise ValueError("unknown app")
    row = rows[app]
    reason = app_reason(row)
    if reason:
        raise ValueError(app + ": " + reason)
    recipe_path = (Path(manifest).parent / row["recipe"]).resolve()
    if Path(manifest).parent.resolve() not in recipe_path.parents:
        raise ValueError("recipe escapes manifest directory")
    recipe = json.loads(recipe_path.read_text())
    if {"test_paths", "overlay_root"} & set(recipe):
        raise ValueError("protocol recipes must not preselect tests")
    suite = Path(suites) / agent / app / SUITE_DIR
    if suite.is_symlink() or not suite.is_dir():
        raise ValueError("no committed suite at " + suite.as_posix())
    root = (row["app_path"] + "/" if row["app_path"] else "") + SUITE_DIR
    tests = sorted(p.relative_to(suite).as_posix() for p in suite.rglob("*.py")
                   if (p.name.startswith("test_") or p.name.endswith("_test.py")) and "__pycache__" not in p.parts)
    if not tests:
        raise ValueError("suite has no pytest test files")
    recipe.update(test_paths=[root + "/" + t for t in tests], overlay_root=root)
    from study.worker import validate_recipe
    recipe = validate_recipe(recipe)
    validate_run_budget([recipe])
    return row, recipe, suite


def confirmation(agent, app, manifest=ROOT / "apps.csv", suites=ROOT / "suites"):
    """Token binds the manifest row, recipe and every suite file byte."""
    row, recipe, suite = plan(agent, app, manifest, suites)
    h = hashlib.sha256(json.dumps({"agent": agent, "row": row, "recipe": recipe}, sort_keys=True).encode())
    for path in sorted(suite.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            h.update(path.relative_to(suite).as_posix().encode() + b"\0" + hashlib.sha256(path.read_bytes()).digest())
    return "RUN " + h.hexdigest()[:12]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["print-confirm", "preflight", "run"])
    p.add_argument("--agent", required=True)
    p.add_argument("--app", required=True)
    p.add_argument("--confirm")
    p.add_argument("--image")
    p.add_argument("--wheelhouse", type=Path)
    p.add_argument("--results", type=Path, default=Path("study/results/protocol"))
    args = p.parse_args()
    token = confirmation(args.agent, args.app)
    if args.action == "print-confirm":
        print(token)
        return
    if args.confirm != token:
        p.error("action-time execution approval not given: confirm mismatch")
    row, recipe, suite = plan(args.agent, args.app)
    if args.action == "preflight":
        print(json.dumps({"agent": args.agent, "app": row, "recipe": recipe}, indent=2))
        return
    if not args.image or args.wheelhouse is None:
        p.error("--image and --wheelhouse are required for execution")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", args.image):
        p.error("image must be a local sha256 image ID")
    from study.run_study import cleanup_confirmed, run_one, wheel_hashes
    reviewed = wheel_hashes(args.wheelhouse.resolve())
    manifest_row = {"repo": row["repo"], "commit_sha": row["commit_sha"], "group": "protocol",
                    "agent": args.agent, "app": args.app}
    output = (args.results / args.agent / (args.app + "__" + row["commit_sha"][:12])).resolve()
    output.mkdir(parents=True, exist_ok=False)
    status = run_one(manifest_row, recipe, args.image, args.wheelhouse.resolve(), output,
                     recipe["budget_seconds"], reviewed, overlay=suite)
    print(args.agent, args.app, status["status"], status["reason"])
    if not cleanup_confirmed(status):
        p.exit(1, "Container cleanup unconfirmed. Inspect status/cleanup.log.\n")


if __name__ == "__main__":
    main()
