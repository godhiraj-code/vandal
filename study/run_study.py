"""Run person-approved public manifests, or the hardwired owned container fixture."""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from study.common import approval_reason, digest, paths, read_rows, write_json
from study.process import clean_env, run
from study.worker import extract_source, validate_recipe

PROXY_KEYS = ("HTTP_PROXY", "HTTPS_PROXY", "FTP_PROXY", "ALL_PROXY", "NO_PROXY",
              "http_proxy", "https_proxy", "ftp_proxy", "all_proxy", "no_proxy")
OWNED_TEST = "study/fixture/test_local_app.py"


def container_command(image, name, inputs, deps, seconds):
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
        raise ValueError("image must be an inspected local sha256 image ID")
    for path in (inputs, deps):
        if any(c in str(path) for c in ",\r\n"):
            raise ValueError("Docker mount source contains a delimiter")
    return ["docker", "run", "--detach", "--pull=never", "--name", name,
            "--network=none", "--read-only", "--user=10001:10001",
            "--cap-drop=ALL", "--security-opt=no-new-privileges", "--pids-limit=256",
            "--cpus=2", "--memory=4g", "--memory-swap=4g", "--shm-size=256m",
            "--ulimit=nofile=1024:1024", "--ulimit=fsize=134217728:134217728",
            "--log-driver=local", "--log-opt=max-size=8m", "--log-opt=max-file=1", "--log-opt=compress=false",
            "--tmpfs=/work:rw,exec,nosuid,nodev,size=3g,uid=10001,gid=10001,mode=700",
            "--tmpfs=/tmp:rw,nosuid,nodev,size=256m,uid=10001,gid=10001,mode=700",
            *["--env=" + key + "=" for key in PROXY_KEYS],
            "--mount", f"type=bind,src={inputs},dst=/input,readonly",
            "--mount", f"type=bind,src={deps},dst=/deps,readonly",
            image, "python", "-m", "study.worker", "--seconds", str(seconds)]


def acquire(row, temporary, output, seconds):
    """Bare, pinned fetch: no checkout, hooks, filters, submodules or repo code."""
    bare = temporary / "source.git"
    env = clean_env()
    env["HOME"] = str(temporary)
    commands = [["git", "-c", "init.templateDir=", "init", "--bare", str(bare)],
                ["git", "-C", str(bare), "-c", "credential.helper=", "-c", "core.hooksPath=/dev/null",
                 "-c", "protocol.file.allow=never", "fetch", "--depth=1", "--no-tags",
                 "https://github.com/" + row["repo"] + ".git", row["commit_sha"]],
                ["git", "-C", str(bare), "rev-parse", "FETCH_HEAD"],
                ["git", "-C", str(bare), "archive", "--format=tar",
                 "--output=" + str(temporary / "input/source.tar"), row["commit_sha"]]]
    deadline = time.monotonic() + seconds
    records = []
    for index, cmd in enumerate(commands):
        log = output / f"acquire-{index}.log"
        # Source acquisition has its own quota; reviewed dependency wheels are
        # staged beside it and must not consume the source-only disk allowance.
        monitored = bare if index < 3 else temporary / "input"
        result = run(cmd, temporary, log, max(0.1, deadline - time.monotonic()), env, disk_root=monitored)
        records.append(result)
        if result["exit_code"] or result["timed_out"] or result["log_limited"] or result["disk_limited"]:
            raise RuntimeError(f"acquisition failed or exceeded bounds; see {log.name}")
        if index == 2 and log.read_text().strip() != row["commit_sha"]:
            raise ValueError("fetched SHA differs from reviewed SHA")
    write_json(output / "acquisition.json", records)


def wheel_hashes(wheelhouse):
    result = {}
    total = 0
    for file in sorted(wheelhouse.iterdir()):
        if file.name == "MANIFEST.csv" and file.is_file() and not file.is_symlink():
            continue  # Reviewed inventory metadata is never mounted or executed.
        if file.is_symlink() or not file.is_file() or file.suffix != ".whl":
            raise ValueError("wheelhouse may contain only regular .whl files")
        total += file.stat().st_size
        if file.stat().st_size > 256 * 1024 * 1024 or total > 1024 * 1024 * 1024:
            raise ValueError("dependency wheel/total size exceeds limit")
        result[file.name] = digest(file)
    return result


def acquire_owned_fixture(row, temporary, output, seconds):
    """Archive only the committed owned fixture; no arbitrary path or remote input."""
    root = Path(__file__).resolve().parent.parent
    if (row["repo"] != "owned-local-fixture" or row["group"] != "fixture"
            or not re.fullmatch(r"[0-9a-f]{40}", row["commit_sha"])):
        raise ValueError("owned fixture identity is fixed")
    command = ["git", "-C", str(root), "archive", "--format=tar",
               "--output=" + str(temporary / "input/source.tar"), row["commit_sha"], OWNED_TEST]
    result = run(command, temporary, output / "acquire-owned.log", seconds)
    if result["exit_code"] or result["timed_out"] or result["log_limited"]:
        raise RuntimeError("owned fixture archive failed; see acquire-owned.log")
    write_json(output / "acquisition.json", {"kind": "local Git archive of owned fixture only", "result": result})


def inspect_owned_container(name, temporary, output):
    """Capture bounded, sanitized isolation evidence before the fixture is removed."""
    raw = temporary / "inspect.json"
    result = run(["docker", "inspect", name], temporary, raw, 10, env=clean_env(docker_client=True), max_bytes=512 * 1024)
    if result["exit_code"] or result["timed_out"] or result["log_limited"]:
        raise RuntimeError("owned container inspection failed")
    inspected = json.loads(raw.read_text())[0]
    config, host = inspected["Config"], inspected["HostConfig"]
    environment = dict(item.split("=", 1) for item in config.get("Env", []))
    evidence = {"state": inspected["State"], "container_id": inspected["Id"], "image": inspected["Image"], "user": config["User"],
                "host_config": {key: host[key] for key in ("NetworkMode", "ReadonlyRootfs", "Privileged",
                    "CapDrop", "SecurityOpt", "Memory", "MemorySwap", "NanoCpus", "PidsLimit", "Tmpfs", "LogConfig")},
                "mounts": [{**{key: mount[key] for key in ("Type", "Destination", "RW")}, "Source": "<host-staged-input>"}
                           for mount in inspected["Mounts"]],
                "environment_keys": sorted(environment), "github_token_present": "GITHUB_TOKEN" in environment,
                "proxy_values_empty": all(environment.get(key) == "" for key in PROXY_KEYS)}
    write_json(output / "isolation.json", evidence)
    probe = "import json; print(json.dumps([x.strip() for x in open('/proc/mounts') if x.split()[1] in ('/work','/tmp','/')]))"
    result = run(["docker", "exec", name, "python", "-c", probe], temporary, output / "mounts.log", 10, env=clean_env(docker_client=True))
    if result["exit_code"] or result["timed_out"] or result["log_limited"]:
        raise RuntimeError("owned container mount inspection failed")


def run_one(row, recipe, image, wheelhouse, output, seconds, reviewed_hashes, *, owned_fixture=False):
    name = "vandal-study-" + uuid.uuid4().hex
    container_attempted = False
    deadline = time.monotonic() + seconds
    status = {"repo": row["repo"], "commit_sha": row["commit_sha"], "group": row["group"],
              "manifest": row, "image": image, "kind": "fixture" if owned_fixture else "public",
              "started_at": datetime.now(timezone.utc).isoformat(),
              "status": "skipped", "reason": "not started"}
    with tempfile.TemporaryDirectory(prefix="vandal-study-") as temp:
        temporary = Path(temp).resolve()
        inputs, deps = temporary / "input", temporary / "deps"
        inputs.mkdir()
        deps.mkdir()
        try:
            # Copy only individually reviewed wheels, never mount a user's directory
            # with incidental credentials or symlink escapes into a candidate.
            if wheel_hashes(wheelhouse) != reviewed_hashes:
                raise ValueError("dependency wheels changed after approval")
            for file in sorted(wheelhouse.glob("*.whl")):
                shutil.copyfile(file, deps / file.name)
            if wheel_hashes(deps) != reviewed_hashes:
                raise ValueError("dependency wheels changed during staging")
            status["dependency_sha256"] = reviewed_hashes
            write_json(inputs / "recipe.json", recipe)
            status["recipe_sha256"] = digest(inputs / "recipe.json")
            acquisition = acquire_owned_fixture if owned_fixture else acquire
            acquisition(row, temporary, output, min(max(0.1, deadline - time.monotonic()), 120))
            status["source_sha256"] = digest(inputs / "source.tar")
            remaining = int(deadline - time.monotonic())
            if remaining < 1:
                raise RuntimeError("repository deadline exhausted during acquisition")
            command = container_command(image, name, inputs, deps, remaining)
            status["container_command"] = command
            container_attempted = True
            result = run(command, temporary, output / "container.log", 30, env=clean_env(docker_client=True))
            if result["exit_code"] or result["timed_out"]:
                raise RuntimeError("container unavailable; see container.log")
            if owned_fixture:
                inspect_owned_container(name, temporary, output)
            finished = False
            while time.monotonic() < deadline:
                probe = subprocess.run(["docker", "exec", name, "test", "-f", "/work/done"],
                                       env=clean_env(docker_client=True), stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL, timeout=10)
                if probe.returncode == 0:
                    finished = True
                    break
                time.sleep(1)
            # Export regular whitelisted files while tmpfs is alive, even on timeout.
            export = temporary / "artifacts.tar"
            copied = run(["docker", "exec", name, "python", "-m", "study.export"],
                         temporary, export, 20, env=clean_env(docker_client=True), max_bytes=33 * 1024 * 1024)
            if copied["exit_code"] == 0 and not copied["log_limited"]:
                artifacts = temporary / "artifacts"
                artifacts.mkdir()
                extract_source(export, artifacts)
                from study.export import NAMES
                for file in artifacts.iterdir():
                    if file.name not in NAMES or not file.is_file():
                        raise ValueError("unexpected exported artifact")
                    shutil.copyfile(file, output / file.name)
            if not finished:
                status.update(status="incomplete", reason="container deadline; partial output excluded")
            elif not (output / "worker-status.json").exists():
                raise RuntimeError("worker produced no valid status artifact")
            else:
                worker = json.loads((output / "worker-status.json").read_text())
                if worker.get("status") not in {"completed", "skipped", "incomplete"}:
                    raise ValueError("invalid worker status")
                if not isinstance(worker.get("reason", ""), str):
                    raise ValueError("worker reason must be a string")
                status.update(status=worker["status"], reason=worker.get("reason", ""))
                status["worker"] = worker
        except Exception as exc:
            status.update(status="skipped", reason=f"{type(exc).__name__}: {exc}")
        finally:
            if container_attempted:
                try:
                    run(["docker", "logs", name], temporary, output / "worker-console.log", 10, env=clean_env(docker_client=True))
                except Exception:
                    pass  # Diagnostics must never prevent container cleanup.
            # Kill the whole container, including detached candidate children.
            try:
                status["cleanup"] = (run(["docker", "rm", "--force", name], temporary, output / "cleanup.log", 15, env=clean_env(docker_client=True))
                                     if container_attempted else {"exit_code": 0, "not_required": True})
            except Exception as exc:
                status["cleanup"] = {"error": f"{type(exc).__name__}: {exc}"}
            if not cleanup_confirmed(status):
                status.update(status="incomplete", reason=status["reason"] + "; container cleanup unconfirmed")
            # Persist the outcome even if export, Docker cleanup or temporary
            # directory removal fails. Never let a failed run disappear.
            from study.redact import host_paths, redact_file
            for artifact in output.iterdir():
                if artifact.is_file():
                    try:
                        redact_file(artifact)
                    except Exception as exc:
                        status.update(status="incomplete", reason=status["reason"] + "; evidence redaction failed: " + type(exc).__name__)
            try:
                status = host_paths(status)
            except RecursionError:
                # The exported worker object is untrusted and may parse as JSON
                # while exceeding the redactor's recursion depth. Its raw file
                # remains evidence; do not let it suppress the host outcome.
                status.pop("worker", None)
                status.update(status="incomplete", reason="worker status nesting exceeds evidence redaction bounds")
                status = host_paths(status)
            status["evidence_redaction"] = "Host paths redacted before artifact hashing; measured outcomes unchanged."
            status["artifact_sha256"] = {p.name: digest(p) for p in output.iterdir() if p.is_file()}
            write_json(output / "status.json", status)
    return status


def cleanup_confirmed(status):
    cleanup = status.get("cleanup", {})
    return cleanup.get("exit_code") == 0 and not any(
        cleanup.get(key) for key in ("timed_out", "log_limited", "error"))


def confirmation(manifest):
    """Exact action-time token for the current manifest bytes."""
    return "RUN " + digest(manifest)[:12]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    source = p.add_mutually_exclusive_group()
    source.add_argument("--repos", type=Path)
    source.add_argument("--owned-fixture", action="store_true", help="only the committed in-repository fixture; never public code")
    p.add_argument("--results", type=Path)
    p.add_argument("--image", help="reviewed local sha256 image ID")
    p.add_argument("--wheelhouse", type=Path)
    p.add_argument("--confirm", help="exact RUN token; default remains interactive")
    p.add_argument("--print-confirm", action="store_true", help="print manifest token without executing anything")
    p.add_argument("--seconds", type=int, default=900)
    args = p.parse_args()
    manifest = args.repos or Path("study/repos.csv")
    if args.print_confirm:
        if args.owned_fixture:
            p.error("owned fixture has no public manifest confirmation")
        print(confirmation(manifest))
        return
    if args.confirm is not None:
        if args.owned_fixture or args.confirm != confirmation(manifest):
            p.error("action-time execution approval not given: confirm mismatch")
    if not args.image or args.wheelhouse is None:
        p.error("--image and --wheelhouse are required for execution")
    if not 30 <= args.seconds <= 3600:
        p.error("seconds must be 30..3600")
    if args.owned_fixture:
        # This mode has no source path, manifest, URL or test-selection input.
        # It cannot grant approval to any public candidate.
        root = Path(__file__).resolve().parent.parent
        sha = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"],
                                      env=clean_env(), text=True, timeout=10).strip()
        row = {"repo": "owned-local-fixture", "commit_sha": sha, "group": "fixture"}
        recipe = {"test_paths": [OWNED_TEST], "requirements": [], "install_project": False,
                  "extras": [], "pytest_args": []}
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", args.image):
            p.error("image must be a local sha256 image ID")
        reviewed_hashes = wheel_hashes(args.wheelhouse.resolve())
        output = (args.results or Path("study/results/pilot/owned-container-fixture")).resolve()
        output.mkdir(parents=True, exist_ok=False)
        status = run_one(row, recipe, args.image, args.wheelhouse.resolve(), output,
                         args.seconds, reviewed_hashes, owned_fixture=True)
        if status["status"] == "completed":
            from study.summarize import metrics
            measured, _ = metrics(json.loads((output / "vandal_report.json").read_text()))
            if not measured["n_scored"] or measured["error"]:
                status.update(status="unscored", reason="owned fixture did not produce error-free scored mutants")
        status["isolation"] = "container pipeline; local owned Git archive, not public GitHub acquisition"
        write_json(output / "status.json", status)
        print(status["status"], status["reason"])
        if status["status"] != "completed" or not cleanup_confirmed(status):
            p.exit(1)
        return
    args.repos = args.repos or Path("study/repos.csv")
    args.results = args.results or Path("study/results/public")
    rows = read_rows(args.repos)
    if not rows:
        print("No approved repositories. Nothing executed.")
        return
    # Validate all rows/recipes before requesting execution of a frozen manifest.
    recipes = []
    for row in rows:
        reason = approval_reason(row)
        if reason:
            p.error(f"{row['repo']}: {reason}")
        recipe_path = (args.repos.parent / row["recipe"]).resolve()
        if args.repos.parent.resolve() not in recipe_path.parents:
            p.error("recipe escapes manifest directory")
        recipe = validate_recipe(json.loads(recipe_path.read_text()))
        if recipe["test_paths"] != paths(row["test_paths"]):
            p.error("recipe selection differs from reviewed manifest")
        recipes.append(recipe)
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", args.image):
        p.error("image must be a local sha256 image ID")
    manifest_hash = digest(args.repos)
    reviewed_hashes = wheel_hashes(args.wheelhouse.resolve())
    print(json.dumps({"manifest_sha256": manifest_hash, "image": args.image,
                      "repositories": rows, "recipes": recipes, "wheel_sha256": reviewed_hashes}, indent=2))
    approval = args.confirm if args.confirm is not None else input("Person: approve executing these unknown repositories offline? Type RUN " + manifest_hash[:12] + ": ")
    if approval != "RUN " + manifest_hash[:12]:
        p.error("action-time execution approval not given")
    if digest(args.repos) != manifest_hash:
        p.error("manifest changed after approval")
    for row, recipe in zip(rows, recipes):
        identifier = row["repo"].replace("/", "__") + "__" + row["commit_sha"][:12]
        output = args.results / identifier
        output.mkdir(parents=True, exist_ok=False)
        status = run_one(row, recipe, args.image, args.wheelhouse.resolve(), output, args.seconds, reviewed_hashes)
        print(row["repo"], status["status"], status["reason"])
        if not cleanup_confirmed(status):
            p.exit(1, "Container cleanup unconfirmed; stopping before any further repository. Inspect status/cleanup.log.\n")


if __name__ == "__main__":
    main()
