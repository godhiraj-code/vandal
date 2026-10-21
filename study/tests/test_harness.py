import io
import json
import sys
import tarfile
from pathlib import Path

import pytest

from study.common import FIELDS, approval_reason, safe_path, write_rows, read_rows
from study.find_repos import parse_candidate, test_files as select_files
from study.process import clean_env, run
from study.run_study import PROXY_KEYS, container_command
from study.summarize import counts, metrics, spread, summarize
from study.worker import baseline_reason, extract_source, validate_recipe


def candidate():
    return dict(zip(FIELDS, ["owner/repo", "a" * 40, "agent", "test_commit",
                "https://github.com/owner/repo/commit/" + "a" * 40, "Claude adds browser tests",
                '["tests/test_ui.py"]', "MIT", "https://github.com/owner/repo/blob/" + "a" * 40 + "/LICENSE",
                "no", "", "", "recipes/repo.json", "0", "[]"]))


def report(statuses):
    mutants = [{"status": s, "strategy": "data_sabotage"} for s in statuses]
    test = {"nodeid": "test.py::test_x", "baseline": "passed", "mutants": mutants,
            "summary": counts(mutants), "untested_targets": ["#select"], "skipped_by_cap": 3}
    return {"schema_version": 1, "tests": [test], "summary": counts(mutants)}


def test_discovery_requires_test_specific_evidence_and_license():
    commit = {"sha": "a" * 40, "html_url": candidate()["evidence_url"],
              "commit": {"message": "Add tests\nCo-Authored-By: Claude <noreply@anthropic.com>"},
              "files": [{"filename": "tests/test_ui.py", "status": "added"}]}
    license_info = {"license": {"spdx_id": "MIT"}, "html_url": candidate()["license_url"]}
    repo = {"full_name": "owner/repo", "private": False}
    source = {"tests/test_ui.py": "from playwright.sync_api import Page\ndef test_ui(page): page.locator('x').click()"}
    row = parse_candidate(repo, commit, license_info, source)
    assert row["approved"] == "no" and row["reviewer"] == ""
    assert json.loads(row["test_paths"]) == ["tests/test_ui.py"]
    assert parse_candidate(repo, commit, {"license": None}, source) is None
    commit["commit"]["message"] = "Update instructions for Claude"
    assert parse_candidate(repo, commit, license_info, source) is None
    assert parse_candidate(repo, commit, license_info, {"tests/test_ui.py": "def test_unit(): pass"}) is None


def test_removed_tests_not_selected():
    assert select_files({"files": [{"filename": "test_ui.py", "status": "removed"}]}) == []


def test_person_review_and_csv(tmp_path):
    row = candidate()
    assert approval_reason(row) == "not approved by a person"
    row.update(approved="yes", reviewer="person", reviewed_at="2026-10-21T00:00:00Z")
    assert approval_reason(row) is None
    path = tmp_path / "repos.csv"
    write_rows(path, [row])
    assert read_rows(path) == [row]
    row["group"] = "human"
    assert "unresolved" in approval_reason(row)
    row["evidence_kind"] = "historical_authorship"
    assert "unresolved" in approval_reason(row)
    row.update(group="agent", evidence_kind="test_commit")
    row["commit_sha"] = "main"
    assert "SHA" in approval_reason(row)


@pytest.mark.parametrize("path", [".", "../escape", "/abs", "C:/file", "a\\b", "-p", "a/../b", "a//b", "a\nfoo"])
def test_path_rejection(path):
    with pytest.raises(ValueError):
        safe_path(path)


@pytest.mark.parametrize("kind", [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.CHRTYPE])
def test_archive_nonregular_rejected(tmp_path, kind):
    path = tmp_path / "source.tar"
    with tarfile.open(path, "w") as tf:
        entry = tarfile.TarInfo("evil")
        entry.type = kind
        entry.linkname = "/etc/passwd"
        tf.addfile(entry)
    with pytest.raises(ValueError):
        extract_source(path, tmp_path / "dest")


def test_archive_regular_and_traversal(tmp_path):
    path = tmp_path / "source.tar"
    with tarfile.open(path, "w") as tf:
        entry = tarfile.TarInfo("tests/test_ui.py")
        entry.size = 3
        tf.addfile(entry, io.BytesIO(b"abc"))
    extract_source(path, tmp_path / "dest")
    assert (tmp_path / "dest/tests/test_ui.py").read_bytes() == b"abc"
    with tarfile.open(path, "w") as tf:
        tf.addfile(tarfile.TarInfo("../escape"))
    with pytest.raises(ValueError):
        extract_source(path, tmp_path / "dest2")


@pytest.mark.parametrize("xml,code,expected", [
    ("<testsuite/>", 0, "no tests"),
    ("<testsuite><testcase><skipped/></testcase></testsuite>", 0, "skipped"),
    ("<testsuite><testcase><failure/></testcase></testsuite>", 0, "failure/error"),
    ("<testsuite><testcase/></testsuite>", 1, "failed"),
    ("broken", 0, "no valid"),
    ("<testsuite><testcase/></testsuite>", 0, None)])
def test_baseline_skip_rules(tmp_path, xml, code, expected):
    path = tmp_path / "baseline.xml"
    path.write_text(xml)
    reason = baseline_reason({"exit_code": code, "timed_out": False, "log_limited": False}, path)
    assert reason is None if expected is None else expected in reason


def test_container_and_environment_do_not_inherit_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "secret")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("PYTHONPATH", "evil")
    env = clean_env()
    assert not {"GITHUB_TOKEN", "AWS_SECRET_ACCESS_KEY", "PYTHONPATH"} & env.keys()
    cmd = container_command("sha256:" + "a" * 64, "test", tmp_path, tmp_path, 60)
    assert "--network=none" in cmd and "--cap-drop=ALL" in cmd
    assert "--read-only" in cmd and "--memory=4g" in cmd and "--pids-limit=256" in cmd
    # Docker's local driver rejects compression with just one log file.
    assert "--log-opt=max-file=1" in cmd and "--log-opt=compress=false" in cmd
    assert "--privileged" not in cmd and not any("docker.sock" in s for s in cmd)
    assert all("readonly" in cmd[i + 1] for i, x in enumerate(cmd) if x == "--mount")
    assert all("--env=" + key + "=" in cmd for key in PROXY_KEYS)


def test_recipe_cannot_override_runner():
    for args in [["--headed", "true"], ["--vandal-strategies", "logic_sabotage"], ["-n", "auto"]]:
        with pytest.raises(ValueError):
            validate_recipe({"test_paths": ["test.py"], "pytest_args": args})


def test_summary_math_and_tampering():
    data, _ = metrics(report(["killed", "survived", "survived", "error", "not_applied", "skipped"]))
    assert data["score"] == pytest.approx(100 / 3)
    assert data["untested"] == 2 and data["untested_targets"] == 1 and data["skipped_by_cap"] == 3
    assert data["n_scored"] == 3 and data["n_mutants"] == 6
    assert metrics(report(["error"]))[0]["score"] is None
    bad = report(["killed"])
    bad["summary"]["score"] = 1
    with pytest.raises(ValueError):
        metrics(bad)
    assert spread([])["median"] is None
    assert spread([25]) == {"n": 1, "median": 25, "min": 25, "max": 25, "iqr": None}
    assert spread([0, 25, 50, 100])["iqr"] == 43.75


def test_fixtures_and_incomplete_runs_excluded(tmp_path):
    for name, kind, state in [("fixture", "fixture", "completed"), ("partial", "public", "incomplete")]:
        dest = tmp_path / name
        dest.mkdir()
        (dest / "status.json").write_text(json.dumps({"repo": name, "commit_sha": "a" * 40,
           "kind": kind, "group": "agent", "status": state, "reason": "timeout" if state == "incomplete" else ""}))
        (dest / "vandal_report.json").write_text(json.dumps(report(["killed"])))
    rows = summarize(tmp_path, tmp_path / "REPORT.md")
    assert not any(r["eligible"] for r in rows)
    assert "descriptive study of agent-written suites only" in (tmp_path / "REPORT.md").read_text()


def test_real_process_timeout_and_log_bound(tmp_path):
    result = run([sys.executable, "-c", "import time; time.sleep(10)"], tmp_path, tmp_path / "sleep.log", .2)
    assert result["timed_out"] and result["seconds"] < 5
    result = run([sys.executable, "-c", "print('x'*100000)"], tmp_path, tmp_path / "noise.log", 5, max_bytes=100)
    assert result["log_limited"] and (tmp_path / "noise.log").stat().st_size == 100


def test_public_results_require_review_and_detect_duplicate_repos(tmp_path):
    from study.common import digest
    for folder, sha in [("one", "a" * 40), ("two", "b" * 40)]:
        destination = tmp_path / folder
        destination.mkdir()
        manifest = candidate()
        manifest.update(commit_sha=sha, approved="yes", reviewer="person", reviewed_at="2026-10-21T00:00:00Z")
        raw = destination / "vandal_report.json"
        raw.write_text(json.dumps(report(["killed", "survived"])))
        (destination / "status.json").write_text(json.dumps({
            "repo": "owner/repo", "commit_sha": sha, "kind": "public", "group": "agent",
            "status": "completed", "reason": "", "manifest": manifest,
            "artifact_sha256": {"vandal_report.json": digest(raw)}}))
    rows = summarize(tmp_path, tmp_path / "REPORT.md")
    assert not any(r["eligible"] for r in rows)
    assert all(r["status"] == "invalid" for r in rows)


def test_baseline_deadline_and_partial_skip(tmp_path):
    result = {"exit_code": 0, "timed_out": True, "log_limited": False}
    assert baseline_reason(result, tmp_path / "absent") == "baseline timeout"
    result.update(timed_out=False, log_limited=True)
    assert "log limit" in baseline_reason(result, tmp_path / "absent")
    result["log_limited"] = False
    xml = tmp_path / "partial.xml"
    xml.write_text("<testsuite><testcase/><testcase><skipped/></testcase></testsuite>")
    assert "skipped" in baseline_reason(result, xml)


def test_changed_wheelhouse_rejected_before_acquisition(tmp_path, monkeypatch):
    from study.run_study import run_one
    wheelhouse, output = tmp_path / "wheels", tmp_path / "out"
    wheelhouse.mkdir()
    output.mkdir()
    (wheelhouse / "dependency.whl").write_bytes(b"changed")
    called = []
    monkeypatch.setattr("study.run_study.acquire", lambda *a: called.append(a))
    monkeypatch.setattr("study.run_study.run", lambda *a, **kw: {"exit_code": 1})
    status = run_one(candidate(), {}, "sha256:" + "a" * 64, wheelhouse, output, 30, {"dependency.whl": "reviewed"})
    assert not called and "changed after approval" in status["reason"]


@pytest.mark.parametrize("bad", [[], {"schema_version": 1, "tests": [42]},
    {"schema_version": 1, "tests": [{"nodeid": "x", "baseline": "passed", "mutants": [3], "summary": {}}]}])
def test_malformed_report_is_invalid_not_crash(tmp_path, bad):
    dest = tmp_path / "run"
    dest.mkdir()
    (dest / "status.json").write_text(json.dumps({"repo": "owned", "commit_sha": "a" * 40,
        "kind": "fixture", "group": "fixture", "status": "completed", "reason": ""}))
    (dest / "vandal_report.json").write_text(json.dumps(bad))
    rows = summarize(tmp_path, tmp_path / "REPORT.md")
    assert rows[0]["status"] == "invalid" and not rows[0]["eligible"]


@pytest.mark.parametrize("failure", ["malformed_export", "missing_docker", "malformed_worker_cleanup", "malformed_report", "nested_report", "nested_worker", "redaction_failure"])
def test_failed_export_or_cleanup_still_records_status(tmp_path, monkeypatch, failure):
    from study.run_study import run_one
    wheelhouse, output = tmp_path / "wheels", tmp_path / "out"
    wheelhouse.mkdir()
    output.mkdir()
    def acquire(row, temporary, output, seconds):
        (temporary / "input/source.tar").write_bytes(b"owned mock")
    def fake_run(cmd, cwd, log, seconds, **kwargs):
        if failure == "missing_docker":
            raise FileNotFoundError("docker missing")
        if failure in {"malformed_worker_cleanup", "malformed_report", "nested_report", "nested_worker", "redaction_failure"} and cmd[1] == "exec":
            payload = json.dumps({"status": "completed", "reason": [] if failure == "malformed_worker_cleanup" else ""}).encode()
            if failure == "nested_worker":
                payload = b'{"status":"completed","reason":"","data":' + b'[' * 600 + b'0' + b']' * 600 + b'}'
            with tarfile.open(log, "w") as archive:
                entry = tarfile.TarInfo("worker-status.json")
                entry.size = len(payload)
                archive.addfile(entry, io.BytesIO(payload))
                if failure in {"malformed_report", "nested_report"}:
                    report = tarfile.TarInfo("vandal_report.json")
                    raw = b"{" if failure == "malformed_report" else b"[" * 1200 + b"0" + b"]" * 1200
                    report.size = len(raw)
                    archive.addfile(report, io.BytesIO(raw))
            return {"exit_code": 0, "timed_out": False, "log_limited": False}
        Path(log).write_bytes(b"not an archive" if cmd[1] == "exec" else b"owned mock")
        return {"exit_code": int(failure == "malformed_worker_cleanup" and cmd[1] == "rm"),
                "timed_out": False, "log_limited": False}
    monkeypatch.setattr("study.run_study.acquire", acquire)
    monkeypatch.setattr("study.run_study.run", fake_run)
    monkeypatch.setattr("study.run_study.subprocess.run", lambda *a, **kw: type("Probe", (), {"returncode": 0})())
    if failure == "redaction_failure":
        def fail_redaction(path):
            raise OSError("owned mock failure")
        monkeypatch.setattr("study.redact.redact_file", fail_redaction)
    result = run_one(candidate(), {}, "sha256:" + "a" * 64, wheelhouse, output, 30, {})
    assert (output / "status.json").exists()
    if failure in {"malformed_report", "nested_report"}:
        assert result["cleanup"]["exit_code"] == 0
        assert (output / "vandal_report.json").exists()
        assert summarize(output, output / "REPORT.md")[0]["status"] == "invalid"
        return
    if failure == "nested_worker":
        # Comprehension recursion costs differ between supported Python versions.
        # Both retaining a representable object and rejecting excessive nesting
        # are valid; neither may suppress the terminal status or cleanup.
        assert result["status"] in {"completed", "incomplete"}
        assert result["cleanup"]["exit_code"] == 0
        if result["status"] == "incomplete":
            assert "nesting exceeds" in result["reason"]
        return
    assert result["status"] == ("skipped" if failure == "malformed_export" else "incomplete")
    expected = {"malformed_export": "ReadError", "missing_docker": "FileNotFoundError",
                "malformed_worker_cleanup": "worker reason must be a string", "nested_worker": "nesting exceeds", "redaction_failure": "evidence redaction failed"}
    assert expected[failure] in result["reason"]


def test_approval_is_bound_to_result_repository(tmp_path):
    from study.common import digest
    manifest = candidate()
    manifest.update(approved="yes", reviewer="person", reviewed_at="2026-10-21T00:00:00Z")
    raw = tmp_path / "vandal_report.json"
    raw.write_text(json.dumps(report(["killed"])))
    (tmp_path / "status.json").write_text(json.dumps({
        "repo": "different/repo", "commit_sha": "a" * 40, "kind": "public", "group": "agent",
        "status": "completed", "reason": "", "manifest": manifest,
        "artifact_sha256": {"vandal_report.json": digest(raw)}}))
    rows = summarize(tmp_path, tmp_path / "REPORT.md")
    assert rows[0]["status"] == "invalid" and "reviewed repository" in rows[0]["reason"]


def test_source_disk_quota_excludes_staged_dependencies(tmp_path, monkeypatch):
    from study.run_study import acquire
    (tmp_path / "input").mkdir()
    output = tmp_path / "out"
    output.mkdir()
    monitors = []
    def fake_run(cmd, cwd, log, seconds, env, **kwargs):
        monitors.append(kwargs["disk_root"])
        Path(log).write_text("a" * 40 if "rev-parse" in cmd else "owned acquisition mock")
        return {"exit_code": 0, "timed_out": False, "log_limited": False, "disk_limited": False}
    monkeypatch.setattr("study.run_study.run", fake_run)
    acquire(candidate(), tmp_path, output, 30)
    assert monitors == [tmp_path / "source.git"] * 3 + [tmp_path / "input"]


def test_cleanup_failure_stops_next_repository(tmp_path, monkeypatch):
    from study.common import digest
    from study.run_study import main
    rows = []
    for repo in ("one/repo", "two/repo"):
        row = candidate()
        row.update(repo=repo, approved="yes", reviewer="person", reviewed_at="2026-10-21T00:00:00Z")
        row["evidence_url"] = row["evidence_url"].replace("owner/repo", repo)
        row["license_url"] = row["license_url"].replace("owner/repo", repo)
        rows.append(row)
    manifest = tmp_path / "repos.csv"
    write_rows(manifest, rows)
    (tmp_path / "recipes").mkdir()
    (tmp_path / "recipes/repo.json").write_text(json.dumps({"test_paths": ["tests/test_ui.py"]}))
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    monkeypatch.setattr(sys, "argv", ["run_study", "--repos", str(manifest),
        "--results", str(tmp_path / "results"), "--image", "sha256:" + "a" * 64,
        "--wheelhouse", str(wheels)])
    monkeypatch.setattr("builtins.input", lambda prompt: "RUN " + digest(manifest)[:12])
    seen = []
    def failed_cleanup(row, *args):
        seen.append(row["repo"])
        return {"status": "incomplete", "reason": "cleanup failed", "cleanup": {"exit_code": 1}}
    monkeypatch.setattr("study.run_study.run_one", failed_cleanup)
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1 and seen == ["one/repo"]


def test_owned_acquisition_contains_only_committed_fixture(tmp_path):
    import subprocess
    from study.run_study import acquire_owned_fixture, OWNED_TEST
    root = Path(__file__).resolve().parents[2]
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    (tmp_path / "input").mkdir()
    output = tmp_path / "out"
    output.mkdir()
    acquire_owned_fixture({"repo": "owned-local-fixture", "group": "fixture", "commit_sha": sha}, tmp_path, output, 15)
    with tarfile.open(tmp_path / "input/source.tar") as archive:
        files = [m.name for m in archive if m.isfile()]
        assert files == [OWNED_TEST]
        assert archive.extractfile(OWNED_TEST).read() == subprocess.check_output(["git", "show", sha + ":" + OWNED_TEST], cwd=root)


def test_owned_acquisition_rejects_public_identity(tmp_path):
    from study.run_study import acquire_owned_fixture
    with pytest.raises(ValueError, match="identity is fixed"):
        acquire_owned_fixture(candidate(), tmp_path, tmp_path, 15)


def test_owned_mode_rejects_manifest_option(monkeypatch):
    from study.run_study import main
    monkeypatch.setattr(sys, "argv", ["run_study", "--owned-fixture", "--repos", "candidates.csv",
        "--image", "sha256:" + "a" * 64, "--wheelhouse", "."])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2


def test_owned_mode_has_fixed_source_and_does_not_review_public_rows(tmp_path, monkeypatch):
    from study.run_study import main, OWNED_TEST
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    monkeypatch.setattr(sys, "argv", ["run_study", "--owned-fixture", "--results", str(tmp_path / "out"),
        "--image", "sha256:" + "a" * 64, "--wheelhouse", str(wheels)])
    def forbidden(*args):
        raise AssertionError("owned mode must not read or approve a public manifest")
    monkeypatch.setattr("builtins.input", forbidden)
    monkeypatch.setattr("study.run_study.read_rows", forbidden)
    seen = []
    def owned(row, recipe, *args, **kwargs):
        seen.append((row, recipe, kwargs))
        return {"status": "skipped", "reason": "owned test mock", "cleanup": {"exit_code": 0}}
    monkeypatch.setattr("study.run_study.run_one", owned)
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    row, recipe, kwargs = seen[0]
    assert row["repo"] == "owned-local-fixture" and row["group"] == "fixture"
    assert recipe["test_paths"] == [OWNED_TEST] and kwargs == {"owned_fixture": True}


def test_docker_client_context_never_reaches_candidate_environment(monkeypatch):
    client_keys = ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_CONFIG", "HOME")
    for key in client_keys:
        monkeypatch.setenv(key, "client-only-" + key)
    monkeypatch.setenv("GITHUB_TOKEN", "never-forward")
    monkeypatch.setenv("HTTPS_PROXY", "never-forward")
    assert all(clean_env(docker_client=True)[key] == "client-only-" + key for key in client_keys)
    assert not set(client_keys) & clean_env().keys()
    assert not {"GITHUB_TOKEN", "HTTPS_PROXY"} & clean_env(docker_client=True).keys()


def test_container_venv_mount_is_executable_but_temporary_mount_is_not(tmp_path):
    command = container_command("sha256:" + "a" * 64, "fixture", tmp_path, tmp_path, 60)
    work = next(x for x in command if x.startswith("--tmpfs=/work:"))
    temp = next(x for x in command if x.startswith("--tmpfs=/tmp:"))
    assert ":rw,exec,nosuid,nodev," in work
    assert ",exec," not in temp


def test_single_repository_iqr_is_unavailable():
    assert spread([80])["median"] == 80
    assert spread([80])["iqr"] is None
    assert spread([20, 80])["iqr"] == 30


def test_no_public_runs_title_and_pooled_units(tmp_path):
    output = tmp_path / "REPORT.md"
    summarize(tmp_path / "results", output)
    text = output.read_text()
    assert text.startswith("# Study protocol (no public runs yet)")
    assert "Pooled by mutant" in text and "n_repos | n_mutants" in text


def test_static_screen_counts_calls_not_comments_and_reports_host_literals():
    from study.find_repos import static_screen
    source = '''# page.click() does not count
from playwright.sync_api import expect
def test_ui(page):
    page.get_by_role("button").click()
    expect(page.locator("#x")).to_be_visible()
    page.locator("#x").fill("value")
    page.check("#x")
    page.hover("#x")
    page.inner_text("#x")
    page.input_value("#x")
    page.goto("http://127.0.0.1:8000")
    page.goto("https://cdn.example.test/app")
'''
    result = static_screen({"test_ui.py": source})
    assert result["observable_calls"] == 10
    assert result["external_host_literals"] == ["cdn.example.test"]
    assert result["heuristic_only"] is True


def test_license_404_is_a_missing_license_not_error():
    import urllib.error
    from study.find_repos import pinned_license
    class API:
        def get(self, *args, **kwargs):
            raise urllib.error.HTTPError("url", 404, "missing", {}, None)
    assert pinned_license(API(), "owner/repo", "a" * 40)["reason"] == "no license"


def test_discovery_modes_keep_guidance_unclassified_and_remove_human_mode():
    from study.find_repos import search_specs, QUERIES, PR_AUTHORS
    specs = list(search_specs("all", QUERIES))
    assert all(any("author:" + author in q and "is:pr" in q for _, q, _ in specs) for author in PR_AUTHORS)
    assert any('"generated tests"' in q for _, q, _ in specs)
    assert sum(kind == "guidance_only" for _, _, kind in specs) == 2
    commit = {"sha": "a" * 40, "html_url": candidate()["evidence_url"], "commit": {"message": "ordinary update"},
              "files": [{"filename": "test_ui.py"}]}
    assert list(search_specs("human", QUERIES)) == []
    assert "app/devin-ai-integration" in PR_AUTHORS
    for kind in ("guidance_only",):
        row = parse_candidate({"full_name": "owner/repo"}, commit,
              {"license": {"spdx_id": "MIT"}, "html_url": candidate()["license_url"]},
              {"test_ui.py": "from playwright.sync_api import Page\ndef test_ui(page): page.locator('#x').click()"}, evidence_kind=kind, detail="review needed")
        assert row["approved"] == "no" and row["group"] == "unresolved"
        assert approval_reason(row) == "authorship is unresolved"
        assert row["observable_calls"] == "2"


def test_discovery_agent_pr_checks_python_files_at_head():
    import base64
    from study.find_repos import discover
    calls = []
    class API:
        def get(self, path, **kw):
            calls.append((path, kw))
            if path == "search/issues":
                return {"items": [{"repository_url": "https://api.github.com/repos/owner/repo", "number": 3}]}
            if path == "repos/owner/repo":
                return {"full_name": "owner/repo"}
            if path.endswith("/pulls/3"):
                return {"head": {"sha": "a" * 40}, "html_url": "https://github.com/owner/repo/pull/3", "changed_files": 1}
            if path.endswith("/files"):
                return [{"filename": "test_ui.py", "status": "added"}]
            if path.endswith("/license"):
                assert kw["ref"] == "a" * 40
                return {"license": {"spdx_id": "MIT"}, "html_url": candidate()["license_url"]}
            if "/git/trees/" in path:
                return {"tree": []}
            if "/contents/" in path:
                assert kw["ref"] == "a" * 40
                return {"content": base64.b64encode(b"from playwright.sync_api import Page\ndef test_ui(page): page.locator('#x').click()").decode()}
            raise AssertionError(path)
    rows, audit = discover(API(), [], 1, "agent-prs")
    assert len(rows) == 1 and rows[0]["evidence_kind"] == "agent_pr"
    assert rows[0]["observable_calls"] == "2" and rows[0]["approved"] == "no"
    assert any(x.get("candidate") for x in audit)
