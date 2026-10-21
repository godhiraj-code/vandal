import base64
import json
import urllib.error

import pytest

from study.find_repos import offline_flags, parse_candidate, static_screen, supporting_at
from study.summarize import summarize


@pytest.mark.parametrize("statement,kind", [
    ('url="http://[odd"', "malformed_url"),
    ('Repo.clone_from("source", "target")', "git_clone"),
    ('shutil.which("docker")', "docker_availability"),
    ('ensure_docker_available()', "docker_use"),
])
def test_offline_risks_survive_odd_urls_and_helper_calls(statement, kind):
    assert kind in {r["kind"] for r in offline_flags({"helper.py": statement})}


def test_local_helpers_follow_pinned_imports_recursively():
    sources = {"tests/test_ui.py": "from .helper import setup\nfrom playwright.sync_api import Page\ndef test_ui(page): page.click('x')",
               "tests/helper.py": "from app.service import start\nRepo.clone_from('source','target')",
               "src/app/service.py": "shutil.which('docker')", "src/app/__init__.py": "Repo.clone_from('pkg','target')"}
    class API:
        def get(self, path, **kwargs):
            if "/git/trees/" in path:
                assert path.endswith("a" * 40)
                return {"tree": [{"path": p, "type": "blob"} for p in sources]}
            assert kwargs == {"ref": "a" * 40}
            file = path.split("/contents/")[1]
            if file not in sources:
                raise urllib.error.HTTPError(path, 404, "missing", {}, None)
            return {"content": base64.b64encode(sources[file].encode()).decode()}
    support = supporting_at(API(), "o/r", "a" * 40, ["tests/test_ui.py"], {"tests/test_ui.py": sources["tests/test_ui.py"]})
    assert set(support) == {"tests/helper.py", "src/app/service.py", "src/app/__init__.py"}
    assert {r["kind"] for r in offline_flags(support)} == {"git_clone", "docker_availability"}


def test_page_objects_nested_helpers_frames_and_all_loops():
    source = '''from playwright.sync_api import Page, expect
class Screen:
    def submit(self):
        self.page.get_by_role("button").click()
        self.other.click()
    def __init__(self, page: Page):
        self.page = page
def test_ui(page):
    def helper():
        page.frame_locator("iframe").locator("input").fill("x")
    for item in page.locator("button").all():
        item.click()
        expect(item).to_be_visible()
    def shadow(page):
        page = object()
        page.click()
'''
    result = static_screen({"test_ui.py": source})
    assert result["observable_calls"] == 8
    assert result["files"]["test_ui.py"]["calls"] == {"get_by_role": 1, "click": 2, "frame_locator": 1, "locator": 2, "fill": 1, "expect": 1}


def test_generated_tests_alone_is_weak_and_zero_calls_are_not_candidates():
    commit = {"sha": "a" * 40, "html_url": "https://github.com/o/r/commit/" + "a" * 40,
              "commit": {"message": "Generated tests"}, "files": [{"filename": "test_ui.py"}]}
    license_info = {"license": {"spdx_id": "MIT"}, "html_url": "https://github.com/o/r/LICENSE"}
    source = {"test_ui.py": "from playwright.sync_api import Page\ndef test_ui(page): page.click('x')"}
    row = parse_candidate({"full_name": "o/r"}, commit, license_info, source)
    assert row["group"] == "unresolved" and row["evidence_kind"] == "generated_tests" and row["approved"] == "no"
    commit["commit"]["message"] += "\nCo-Authored-By: Claude"
    assert parse_candidate({"full_name": "o/r"}, commit, license_info, source)["group"] == "agent"
    source["test_ui.py"] = "from playwright.sync_api import Page\ndef test_ui(page): page.goto('/')"
    assert parse_candidate({"full_name": "o/r"}, commit, license_info, source) is None


def test_fixture_history_default_untouched_and_never_written_in_ci(tmp_path, monkeypatch):
    history = tmp_path / "FIXTURE_ATTEMPTS.md"
    history.write_text("historical evidence")
    before = history.stat().st_mtime_ns
    summarize(tmp_path, tmp_path / "REPORT.md")
    assert history.read_text() == "historical evidence" and history.stat().st_mtime_ns == before
    monkeypatch.setenv("CI", "true")
    with pytest.raises(ValueError, match="never"):
        summarize(tmp_path, tmp_path / "REPORT.md", write_fixture_attempts=True)
    assert history.read_text() == "historical evidence"


@pytest.mark.parametrize("status", ["skipped", "incomplete", "failed", "completed"])
def test_no_public_results_title_for_failed_skipped_or_missing_reports(tmp_path, status):
    (tmp_path / "status.json").write_text(json.dumps({"repo": "o/r", "commit_sha": "a" * 40,
        "kind": "public", "group": "agent", "status": status, "reason": "attempt"}))
    summarize(tmp_path, tmp_path / "REPORT.md")
    assert (tmp_path / "REPORT.md").read_text().splitlines()[0] == "# Study protocol (no public runs yet)"


def test_completed_valid_public_report_gets_results_title(tmp_path):
    from test_harness import candidate, report
    from study.common import digest
    manifest = candidate()
    manifest.update(approved="yes", reviewer="person", reviewed_at="2026-10-21T00:00:00Z")
    raw = tmp_path / "vandal_report.json"
    raw.write_text(json.dumps(report(["killed", "survived"])))
    (tmp_path / "status.json").write_text(json.dumps({"repo": manifest["repo"], "commit_sha": manifest["commit_sha"],
        "kind": "public", "group": "agent", "status": "completed", "reason": "", "manifest": manifest,
        "artifact_sha256": {"vandal_report.json": digest(raw)}}))
    rows = summarize(tmp_path, tmp_path / "REPORT.md")
    assert rows[0]["eligible"]
    assert (tmp_path / "REPORT.md").read_text().splitlines()[0] == "# Study protocol and results"


def test_redaction_preserves_full_report_metrics_and_node_ids():
    from test_harness import report
    from study.redact import host_paths
    from study.summarize import metrics
    raw = report(["killed", "survived", "error", "not_applied", "skipped"])
    raw["tests"][0]["nodeid"] = "/home/person/my tests/test_a.py::test_ui"
    raw["host_path"] = "/home/person/output"
    redacted = host_paths(raw)
    assert redacted["tests"] == raw["tests"]
    assert metrics(redacted) == metrics(raw)
