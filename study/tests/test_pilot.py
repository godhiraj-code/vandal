import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from study.common import approval_reason, digest, paths, read_rows, write_rows
from study.pilot import preflight, summary
from study.run_study import confirmation, main, wheel_hashes
from study.worker import validate_recipe

ROOT = Path(__file__).resolve().parents[2]


def test_reviewed_manifest_has_exact_two_approved_snapshots_and_existing_recipes():
    for name in ("repos.csv", "repos.proposed.csv"):
        for row in read_rows(ROOT / "study" / name):
            assert (ROOT / "study" / row["recipe"]).is_file()
    rows = preflight(ROOT / "study/repos.csv", confirmation(ROOT / "study/repos.csv"))
    assert {(r["repo"], r["commit_sha"], r["recipe"]) for r in rows} == {
        ("atdr/contrail", "2465e368b7658bd23f0d41f1473c114db3573005", "recipes/contrail.json"),
        ("tegataiprime/Platelet-Movie", "14664611814b126289f291ad24ee294102efb07c", "recipes/platelet.json")}
    for row in rows:
        assert approval_reason(row) is None
        assert row["reviewer"] == "Dhiraj Das" and row["reviewed_at"] == "2026-10-21T12:20:00Z"
        recipe = validate_recipe(json.loads((ROOT / "study" / row["recipe"]).read_text()))
        assert recipe["test_paths"] == paths(row["test_paths"])


@pytest.mark.parametrize("mode", ["matching", "mismatch", "interactive"])
def test_confirmation_path_uses_mocks_only(tmp_path, monkeypatch, mode):
    from test_harness import candidate
    row = candidate()
    row.update(approved="yes", reviewer="Person", reviewed_at="2026-10-21T12:20:00Z")
    manifest = tmp_path / "repos.csv"
    write_rows(manifest, [row])
    (tmp_path / "recipes").mkdir()
    (tmp_path / "recipes/repo.json").write_text(json.dumps({"test_paths": paths(row["test_paths"])}))
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    argv = ["run_study", "--repos", str(manifest), "--image", "sha256:" + "a" * 64,
            "--wheelhouse", str(wheels), "--results", str(tmp_path / "results")]
    if mode != "interactive":
        argv += ["--confirm", confirmation(manifest) if mode == "matching" else "RUN wrong"]
    monkeypatch.setattr(sys, "argv", argv)
    def prompt(_):
        assert mode == "interactive"
        return confirmation(manifest)
    monkeypatch.setattr("builtins.input", prompt)
    calls = []
    def fake_run(*args, **kwargs):
        calls.append(args[0]["repo"])
        return {"status": "skipped", "reason": "owned mock", "cleanup": {"exit_code": 0}}
    monkeypatch.setattr("study.run_study.run_one", fake_run)
    if mode == "mismatch":
        with pytest.raises(SystemExit):
            main()
        assert calls == []
    else:
        main()
        assert calls == [row["repo"]]


def test_print_confirm_needs_no_image_or_execution(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["run_study", "--repos", str(ROOT / "study/repos.csv"), "--print-confirm"])
    main()
    assert capsys.readouterr().out.strip() == confirmation(ROOT / "study/repos.csv")
    with pytest.raises(ValueError, match="exactly"):
        preflight(ROOT / "study/repos.csv", "wrong")


def test_manifest_bytes_are_preserved_across_git_platforms():
    assert "repos.csv -text" in (ROOT / "study/.gitattributes").read_text()
    assert b"\r" not in (ROOT / "study/repos.csv").read_bytes()


def test_workflow_is_manual_guarded_and_normal_ci_never_uses_public_manifest():
    text = (ROOT / ".github/workflows/study-pilot.yml").read_text()
    trigger = text.split("on:\n", 1)[1].split("permissions:", 1)[0]
    assert "workflow_dispatch:" in trigger and "required: true" in trigger
    assert not any(x in trigger for x in ("push:", "pull_request:", "schedule:"))
    assert "environment: study-pilot" in text and "timeout-minutes: 60" in text
    assert text.count("contents: read") == 2 and "persist-credentials: false" in text
    assert "group: study-pilot" in text and "cancel-in-progress: false" in text
    assert "secrets." not in text and "git push" not in text and "git commit" not in text
    actions = re.findall(r"uses: (\S+)", text)
    assert actions and all(re.fullmatch(r"actions/[\w-]+@[0-9a-f]{40}", a) for a in actions)
    assert text.index("study.pilot preflight") < text.index("docker build") < text.index("study.run_study")
    for workflow in (ROOT / ".github/workflows").glob("*.yml"):
        if workflow.name == "study-pilot.yml":
            continue
        for line in workflow.read_text().splitlines():
            if "-m study.run_study" in line:
                assert "--owned-fixture" in line


def test_wheel_manifest_checks_hashes_and_is_not_a_dependency(tmp_path):
    from study.wheelhouse.fetch import manifest
    wheel = tmp_path / "owned-1-py3-none-any.whl"
    wheel.write_bytes(b"owned test data, not imported")
    item = {"filename": wheel.name, "sha256": digest(wheel), "license": "MIT"}
    assert manifest(tmp_path, [item])[0] == item
    assert wheel_hashes(tmp_path) == {wheel.name: item["sha256"]}
    (tmp_path / "MANIFEST.csv").unlink()
    wheel.write_bytes(b"changed")
    with pytest.raises(ValueError, match="hash"):
        manifest(tmp_path, [item])


def test_download_is_binary_only_hash_locked_and_has_clean_environment(tmp_path, monkeypatch):
    from study.wheelhouse import fetch
    monkeypatch.setenv("GITHUB_TOKEN", "owned-test-sentinel")
    monkeypatch.setenv("HTTPS_PROXY", "owned-test-sentinel")
    seen = []
    def fake_run(command, **kwargs):
        seen.append(command)
        assert "GITHUB_TOKEN" not in kwargs["env"] and "HTTPS_PROXY" not in kwargs["env"]
        assert kwargs["env"]["HOME"] != os.environ.get("HOME")
        assert kwargs["timeout"] == 600 and kwargs["check"]
        assert all(flag in command for flag in ("--require-hashes", "--only-binary=:all:", "--isolated"))
        assert not any(word in command for word in ("install", "wheel"))
        assert any(p.endswith("requirements-contrail.lock") for p in command)
    monkeypatch.setattr(fetch.subprocess, "run", fake_run)
    monkeypatch.setattr(fetch, "manifest", lambda directory, metadata: [])
    assert fetch.download(tmp_path / "wheels") == [] and len(seen) == 1


@pytest.mark.skipif(os.name == "nt", reason="bash wrapper syntax is checked on Linux CI")
def test_fetch_shell_syntax_without_running_download():
    subprocess.run(["bash", "-n", str(ROOT / "study/wheelhouse/fetch.sh")], check=True, timeout=10)


def test_pilot_summary_reports_not_run_without_invented_score(tmp_path):
    manifest = ROOT / "study/repos.csv"
    output = tmp_path / "summary.md"
    summary(manifest, tmp_path, tmp_path / "image.txt", output)
    text = output.read_text()
    assert text.count("not run") == 2 and text.count("N/A (n=N/A)") == 2
    assert "not observed" in text and "not built" in text


@pytest.mark.parametrize("worker", [{"baseline": [1]}, [1], None])
def test_pilot_summary_retains_other_rows_when_worker_evidence_is_malformed(tmp_path, worker):
    manifest = ROOT / "study/repos.csv"
    row = read_rows(manifest)[0]
    (tmp_path / "status.json").write_text(json.dumps({"repo": row["repo"], "commit_sha": row["commit_sha"],
        "group": "agent", "kind": "public", "status": "incomplete", "reason": "invalid worker", "worker": worker}))
    output = tmp_path / "summary.md"
    summary(manifest, tmp_path, tmp_path / "image.txt", output)
    assert "unavailable: malformed evidence" in output.read_text()
    assert "Platelet-Movie" in output.read_text() and "not run" in output.read_text()


def test_imported_page_object_calls_are_counted_once():
    from study.find_repos import static_screen
    source = {"tests/test_login.py": "from .pages import Login\ndef test_login(page): Login(page).submit()"}
    support = {"requirements.txt": "pytest-playwright", "tests/pages.py": '''class Login:
    def __init__(self, page): self.page = page
    def submit(self):
        self.page.get_by_role("button").click()
'''}
    result = static_screen(source, support)
    assert result["observable_calls"] == 2
    assert result["files"]["tests/pages.py"]["calls"] == {"get_by_role": 1, "click": 1}


def test_home_redaction_in_nodeid_lines_and_file_urls():
    from study.redact import host_paths
    from test_harness import report
    from study.summarize import metrics
    node = "tests/home/test_a.py::test_ok"
    value = f"{node} PASSED cache=/home/person/cache url=file:///home/person/output"
    result = host_paths(value)
    assert node in result and "/home/person" not in result
    assert "file://<HOST_HOME>/output" in result
    assert host_paths(f"cache=/home/person/cache {node} PASSED").startswith("cache=<HOST_HOME>/cache")
    raw = report(["killed", "survived"])
    raw["tests"][0]["nodeid"] = "/home/person/my tests/test_a.py::test_ok"
    raw["message"] = value
    updated = host_paths(raw)
    assert updated["tests"] == raw["tests"] and metrics(updated) == metrics(raw)
