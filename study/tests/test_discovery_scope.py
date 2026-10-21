import base64
import json

import pytest

from study.find_repos import static_screen, parse_candidate, sources_at, supporting_at


@pytest.mark.parametrize("source", [
    "from selenium import webdriver\ndef test_ui(page): page.locator('x').click()",
    "from appium import webdriver\ndef test_ui(page): page.locator('x').click()",
    "def test_data(table): table.fill(1); table.check(); table.inner_text()",
    "def test_data(page): page.fill(1); page.check()",
    "def test_data(page): page.locator('x').click()",
])
def test_other_stacks_and_non_browser_tests_score_zero(source):
    result = static_screen({"test_other.py": source})
    assert result["observable_calls"] == 0
    assert result["files"]["test_other.py"]["selected"] is False
    commit = {"sha": "a" * 40, "commit": {"message": "Generated tests"},
              "html_url": "https://github.com/o/r/commit/" + "a" * 40,
              "files": [{"filename": "test_other.py"}]}
    assert parse_candidate({"full_name": "o/r"}, commit,
                           {"license": {"spdx_id": "MIT"}}, {"test_other.py": source}) is None


def test_only_browser_receiver_chains_and_locator_aliases_count():
    source = '''from playwright.sync_api import Page, expect as assert_that
def test_ui(page: Page, table):
    button = page.get_by_role("button")
    button.click()
    assert_that(button).to_be_visible()
    table.click(); table.fill(1); table.locator("x"); expect(table)
    button = table
    button.hover()
    page = table
    page.check()
'''
    result = static_screen({"test_ui.py": source})
    assert result["observable_calls"] == 3
    assert result["files"]["test_ui.py"]["calls"] == {"click": 1, "expect": 1, "get_by_role": 1}


def test_declared_pytest_playwright_page_fixture_needs_no_import_or_locator():
    result = static_screen({"test_ui.py": "def test_ui(page): page.fill('input', 'x'); page.click('button')"},
                           {"pyproject.toml": 'dependencies = ["pytest-playwright"]'})
    assert result["observable_calls"] == 2


def test_unrelated_expect_is_not_a_playwright_assertion():
    result = static_screen({"test_ui.py": "from playwright.sync_api import Page\nfrom expecter import expect\ndef test_ui(page: Page): expect(page)"})
    assert result["observable_calls"] == 0


def test_page_returning_fixture_and_factory_are_traced_without_execution():
    support = {"tests/conftest.py": '''import pytest
@pytest.fixture
def site_page(page):
    return page
@pytest.fixture
def open_site(page):
    def open_():
        return page
    return open_
'''}
    source = '''from playwright.sync_api import expect
def test_ui(site_page, open_site):
    page = site_page
    expect(page.locator("x")).to_be_visible()
    other = open_site()
    other.get_by_text("x").click()
'''
    assert static_screen({"test_ui.py": source}, support)["observable_calls"] == 4


def test_bom_and_configuration_risks_are_read_only():
    sources = {"test_ui.py": "\ufeffdef test_ui(page): page.locator('x').click()"}
    support = {
        "tests/conftest.py": "import subprocess, shutil\nsubprocess.run(['git', 'clone', 'https://example.org/app'])\nshutil.which('docker')\nsubprocess.run(['docker', 'compose', 'up'])",
        "pytest.ini": "[pytest]\naddopts = --base-url=https://example.net",
        "setup.cfg": "[tool:pytest]\nbase_url = http://localhost:8000",
        "tox.ini": "[testenv]\ncommands = docker info",
        "pyproject.toml": 'dependencies=["pytest-playwright"]\n[tool.pytest.ini_options]\nbase_url="https://example.com"',
    }
    result = static_screen(sources, support)
    assert result["observable_calls"] == 2
    kinds = {x["kind"] for x in result["offline_risk"]}
    assert {"external_host", "base_url", "git_clone", "docker_use", "docker_availability", "setup_command"} <= kinds
    assert set(result["external_host_literals"]) == {"example.org", "example.net", "example.com"}


def test_bom_decoding_and_support_reads_use_pinned_sha():
    import urllib.error
    calls = []
    class API:
        def get(self, path, **kw):
            calls.append((path, kw))
            assert kw["ref"] == "a" * 40
            if path.endswith(("test_ui.py", "tests/conftest.py", "pytest.ini")):
                return {"content": base64.b64encode(b"\xef\xbb\xbf# source").decode()}
            raise urllib.error.HTTPError(path, 404, "not found", {}, None)
    assert sources_at(API(), "o/r", "a" * 40, ["test_ui.py"])["test_ui.py"] == "# source"
    support = supporting_at(API(), "o/r", "a" * 40, ["tests/test_ui.py"])
    assert "tests/conftest.py" in support
    assert all(any(path.endswith(name) for path, _ in calls) for name in ("setup.cfg", "tox.ini", "pyproject.toml"))


def test_explicit_fixture_history_keeps_failure_out_of_main_report(tmp_path, monkeypatch):
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    from study.summarize import summarize
    failed = tmp_path / "failed"
    failed.mkdir()
    (failed / "status.json").write_text(json.dumps({"repo": "owned", "commit_sha": "a" * 40,
        "kind": "fixture", "group": "fixture", "status": "incomplete", "reason": "early fixture failure"}))
    summarize(tmp_path, tmp_path / "REPORT.md", write_fixture_attempts=True)
    assert "early fixture failure" not in (tmp_path / "REPORT.md").read_text()
    assert "early fixture failure" in (tmp_path / "FIXTURE_ATTEMPTS.md").read_text()
    assert "human" not in (tmp_path / "REPORT.md").read_text().lower()
