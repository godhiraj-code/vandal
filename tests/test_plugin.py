"""Real pytest subprocesses and headless Chromium, including actual fixtures."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

APP = """<button id="b" onclick="document.querySelector('#result').textContent='done'">Go</button>
<p id="result">waiting</p>"""


def run_suite(tmp_path, source, *options, conftest=""):
    (tmp_path / "test_sample.py").write_text(source, encoding="utf-8")
    (tmp_path / "conftest.py").write_text(conftest, encoding="utf-8")
    env = dict(os.environ)
    env.pop("_VANDAL_WORKER", None)
    env.pop("PYTEST_ADDOPTS", None)
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "test_sample.py", "-q", *options],
        cwd=tmp_path, env=env, text=True, capture_output=True, timeout=180,
    )
    path = tmp_path / "vandal_report.json"
    report = json.loads(path.read_text()) if path.exists() else None
    return completed, report


def test_sync_discovery_selection_and_min_score(tmp_path):
    source = f'''
from playwright.sync_api import expect
def test_weak(page):
    page.set_content({APP!r})
    page.locator("#b").click(force=True)
def test_strong(page):
    page.set_content({APP!r})
    page.locator("#b").click()
    expect(page.locator("#result")).to_have_text("done", timeout=200)
def test_not_selected():
    assert False
'''
    run, report = run_suite(tmp_path, source, "--vandal", "-k", "not not_selected",
                           "--vandal-strategies=logic_sabotage", "--vandal-max-mutants=1",
                           "--vandal-min-score=75")
    assert report is not None, run.stdout + run.stderr
    assert run.returncode == 1, run.stdout
    assert report["summary"]["score"] == 50
    assert len(report["tests"]) == 2
    assert report["tests"][0]["mutants"][0]["selector"] == "#b"
    assert "force=True" in report["tests"][0]["mutants"][0]["hint"]
    assert "SURVIVED" in run.stdout
    assert (tmp_path / "vandal_report.html").exists()


def test_baseline_failing_and_ordinary_runs(tmp_path):
    source = '''
import pytest
@pytest.mark.vandal(targets=["#b"])
def test_bad():
    assert False
'''
    run, report = run_suite(tmp_path, source, "--vandal")
    assert run.returncode == 1
    assert report["tests"][0]["baseline"] == "baseline failing"
    assert report["tests"][0]["mutants"] == []
    (tmp_path / "vandal_report.json").unlink()
    run, report = run_suite(tmp_path, source)
    assert run.returncode == 1 and report is None
    assert "Vandal strength" not in run.stdout


def test_async_and_role_locator(tmp_path):
    source = f'''
import pytest
from playwright.async_api import async_playwright, expect
@pytest.mark.asyncio
async def test_strong():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.set_content({APP!r})
        await page.get_by_role("button", name="Go").click()
        await expect(page.locator("#result")).to_have_text("done", timeout=200)
        await browser.close()
'''
    run, report = run_suite(tmp_path, source, "--vandal", "--vandal-strategies=logic_sabotage",
                           "--vandal-max-mutants=1", "--vandal-min-score=100")
    assert run.returncode == 0, run.stdout + run.stderr
    assert report["summary"]["killed"] == 1
    assert "role=button" in report["tests"][0]["mutants"][0]["selector"]


@pytest.mark.parametrize("failure", ["setup", "teardown", "timeout", "runtime", "action_timeout"])
def test_worker_errors_cannot_inflate_score(tmp_path, failure):
    source = f'''
import os, time, pytest
@pytest.mark.vandal(targets=["#b"])
def test_error(page):
    page.set_content({APP!r})
    page.click("#b")
    if "_VANDAL_WORKER" in os.environ:
        if {failure!r} == "timeout": time.sleep(30)
        if {failure!r} == "runtime": raise RuntimeError("infrastructure")
        if {failure!r} == "action_timeout": page.click("#missing", timeout=50)
'''
    conftest = f'''
import pytest, os
@pytest.fixture(autouse=True)
def bad_fixture():
    if "_VANDAL_WORKER" in os.environ and {failure!r} == "setup":
        assert False, "setup assertion is not a kill"
    yield
    if "_VANDAL_WORKER" in os.environ and {failure!r} == "teardown":
        assert False, "teardown assertion is not a kill"
'''
    run, report = run_suite(
        tmp_path, source, "--vandal", "--vandal-strategies=logic_sabotage",
        "--vandal-timeout=" + ("8" if failure == "timeout" else "30"), conftest=conftest,
    )
    assert run.returncode == 1, run.stdout
    assert report["summary"]["error"] == 1
    assert report["summary"]["killed"] == 0
    assert report["summary"]["score"] is None


def test_missing_target_not_scored(tmp_path):
    source = f'''
import pytest
@pytest.mark.vandal(targets=["#missing"])
def test_ok(page):
    page.set_content({APP!r})
    page.click("#b")
'''
    run, report = run_suite(tmp_path, source, "--vandal", "--vandal-strategies=logic_sabotage",
                           "--vandal-min-score=0")
    assert run.returncode == 1, run.stdout
    assert report["summary"]["not_applied"] == 1
    assert report["summary"]["score"] is None


def test_parameterized_selection_and_cap(tmp_path):
    source = f'''
import pytest
@pytest.mark.parametrize("n", [1, 2])
@pytest.mark.vandal(targets=["#b"])
def test_param(page, n):
    page.set_content({APP!r})
    page.click("#b", force=True)
'''
    run, report = run_suite(tmp_path, source, "--vandal", "-k", "2",
                           "--vandal-strategies=logic_sabotage,ui_shift", "--vandal-max-mutants=1")
    assert run.returncode == 0, run.stdout
    assert len(report["tests"]) == 1
    assert report["summary"]["survived"] == 1


def test_baseline_teardown_failure(tmp_path):
    source = f'''
def test_ok(page):
    page.set_content({APP!r})
    page.click("#b")
'''
    conftest = '''
import pytest
@pytest.fixture(autouse=True)
def cleanup():
    yield
    raise RuntimeError("cleanup failed")
'''
    run, report = run_suite(tmp_path, source, "--vandal", conftest=conftest)
    assert run.returncode == 1
    assert report["tests"][0]["baseline"] == "baseline failing"
    assert report["tests"][0]["mutants"] == []


def test_all_strategies_are_isolated(tmp_path):
    source = f'''
import pytest
@pytest.mark.vandal(targets=["#b"])
def test_strategies(page):
    page.set_content({APP!r})
    # Read without actionability waits: all six injected strategies are observable.
    page.locator("#b").text_content()
'''
    run, report = run_suite(tmp_path, source, "--vandal", "--vandal-max-mutants=6")
    assert run.returncode == 0, run.stdout
    assert report["summary"]["survived"] == 6
    assert len({m["strategy"] for m in report["tests"][0]["mutants"]}) == 6


def test_fill_discovery_and_marker_selection(tmp_path):
    source = '''
import pytest
@pytest.mark.vandal
def test_fill(page):
    page.set_content('<input id="name">')
    page.fill("#name", "Alice")
    assert page.input_value("#name") == "Alice"
def test_unmarked():
    assert False
'''
    run, report = run_suite(tmp_path, source, "--vandal", "-m", "vandal",
                           "--vandal-strategies=data_sabotage")
    assert run.returncode == 0, run.stdout
    assert len(report["tests"]) == 1
    assert report["tests"][0]["targets"] == ["#name"]
    assert report["summary"]["survived"] == 1


def test_baseline_skip_and_xfail_are_excluded(tmp_path):
    source = '''
import pytest
@pytest.mark.skip(reason="not applicable")
def test_skip(): pass
@pytest.mark.xfail(reason="known failure")
def test_xfail(): assert False
@pytest.mark.xfail(reason="unexpected pass")
def test_xpass(): pass
'''
    run, report = run_suite(tmp_path, source, "--vandal")
    assert run.returncode == 0
    assert all(t["baseline"] == "skipped" and not t["mutants"] for t in report["tests"])
    assert report["summary"]["score"] is None


@pytest.mark.parametrize("option", [
    "--vandal-max-mutants=0", "--vandal-timeout=nan",
    "--vandal-min-score=101", "--vandal-strategies=unknown",
])
def test_invalid_options(tmp_path, option):
    run, report = run_suite(tmp_path, "def test_ok(): pass", "--vandal", option)
    assert run.returncode == 4
    assert report is None


@pytest.mark.parametrize("filename", ["report.html", "report.HTML"])
def test_report_collision_fails_before_running_tests(tmp_path, filename):
    destination = tmp_path / filename
    destination.write_text("existing report", encoding="utf-8")
    run, report = run_suite(
        tmp_path, 'def test_never_runs(): assert False', "--vandal",
        "--vandal-report=" + filename,
    )
    assert run.returncode == 4, run.stdout + run.stderr
    assert "distinct" in run.stderr
    assert "test_never_runs" not in run.stdout
    assert destination.read_text(encoding="utf-8") == "existing report"
