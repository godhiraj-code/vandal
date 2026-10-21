"""Adversarial browser/pytest cases beyond the main happy-path regressions."""
import json
import pytest
from playwright.sync_api import expect, sync_playwright

from test_plugin import APP, run_suite
from vandal.reporting import make_report, write_report


def test_worker_exception_before_injection_is_an_error(tmp_path):
    source = f'''
import os, pytest
@pytest.mark.vandal(targets=["#missing"])
def test_worker_error(page):
    if "_VANDAL_WORKER" in os.environ:
        raise RuntimeError("backend unavailable before injection")
    page.set_content({APP!r})
    page.click("#b")
'''
    run, report = run_suite(tmp_path, source, "--vandal", "--vandal-strict", "--vandal-strategies=logic_sabotage")
    assert run.returncode == 1, run.stdout
    assert report["summary"]["error"] == 1
    assert report["summary"]["not_applied"] == 0


def test_mutants_do_not_poison_normal_last_failed_cache(tmp_path):
    source = f'''
import pytest
@pytest.mark.vandal(targets=["#b"])
def test_strong(page):
    page.set_content({APP!r})
    page.click("#b")
    assert page.inner_text("#result") == "done"
'''
    run, report = run_suite(tmp_path, source, "--vandal", "--vandal-strategies=logic_sabotage")
    assert run.returncode == 0, run.stdout
    assert report["summary"]["killed"] == 1
    cache = tmp_path / ".pytest_cache/v/cache/lastfailed"
    assert not cache.exists() or json.loads(cache.read_text()) == {}


def test_last_failed_selection_survives_baseline_cache_update(tmp_path):
    source = f'''
import pytest
@pytest.mark.vandal(targets=["#b"])
def test_was_failing(page):
    page.set_content({APP!r})
    page.click("#b")
def test_should_not_run():
    raise AssertionError("not selected")
'''
    cache = tmp_path / ".pytest_cache/v/cache"
    cache.mkdir(parents=True)
    (cache / "lastfailed").write_text(json.dumps({
        "test_sample.py::test_was_failing[chromium]": True,
    }))
    run, report = run_suite(
        tmp_path, source, "--vandal", "--lf", "--lfnf=none",
        "--vandal-strategies=logic_sabotage",
    )
    assert run.returncode == 0, run.stdout
    assert len(report["tests"]) == 1
    assert report["summary"]["survived"] == 1


@pytest.mark.parametrize("operation", ["evaluate", "element_handle"])
def test_unsupported_only_interactions_have_no_fabricated_score(tmp_path, operation):
    source = f'''
def test_raw(page):
    page.set_content({APP!r})
    if {operation!r} == "evaluate":
        page.evaluate("document.querySelector('#b').click()")
    else:
        page.query_selector("#b").click()
    assert page.evaluate("document.querySelector('#result').textContent") == "done"
'''
    run, report = run_suite(tmp_path, source, "--vandal", "--vandal-min-score=0")
    assert run.returncode == 1
    assert report["tests"][0]["targets"] == []
    assert report["summary"]["score"] is None
    assert report["tests"][0]["mutants"] == []


@pytest.mark.parametrize("strategy", ["logic_sabotage", "data_sabotage"])
def test_async_chained_locator_after_reload(tmp_path, strategy):
    source = f'''
import pytest
from playwright.async_api import async_playwright
@pytest.mark.asyncio
async def test_async():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        try:
            page = await browser.new_page()
            page.set_default_timeout(500)
            await page.set_content({APP!r})
            await page.set_content({APP!r})
            target = page.locator("body").locator("#b").nth(0)
            await target.click()
            assert await target.inner_text() == "Go"
            assert await page.inner_text("#result") == "done"
        finally:
            await browser.close()
'''
    run, report = run_suite(tmp_path, source, "--vandal",
                           "--vandal-strategies=" + strategy, "--vandal-max-mutants=4")
    assert report is not None, run.stdout
    # Parent selectors are also candidates; all outcomes remain explicit.
    assert report["summary"]["killed"] >= 1
    assert any("nth=0" in m["selector"] for m in report["tests"][0]["mutants"])
    assert report["summary"]["score"] is not None


def test_baseline_setup_failure_excludes_mutants(tmp_path):
    source = '''
import pytest
@pytest.mark.vandal(targets=["#b"])
def test_never_called(page): pass
'''
    run, report = run_suite(tmp_path, source, "--vandal", conftest='''
import pytest
@pytest.fixture(autouse=True)
def broken():
    raise RuntimeError("setup infrastructure failure")
''')
    assert run.returncode == 1
    assert report["tests"][0]["baseline"] == "baseline failing"
    assert report["tests"][0]["mutants"] == []


def test_invalid_selector_is_error_not_survival(tmp_path):
    source = f'''
import pytest
@pytest.mark.vandal(targets=["["])
def test_selector(page):
    page.set_content({APP!r})
    page.click("#b")
'''
    run, report = run_suite(tmp_path, source, "--vandal", "--vandal-strict", "--vandal-strategies=logic_sabotage")
    assert run.returncode == 1
    assert report["summary"]["error"] == 1
    assert report["summary"]["score"] is None


def test_html_report_is_inert_in_real_browser(tmp_path):
    attack = '<img src=x onerror="window.__vandal_xss=1"><script>window.__vandal_xss=1</script>'
    mutant = dict(strategy="logic_sabotage", selector=attack, status="survived",
                  hint=attack, details=attack)
    report = make_report([dict(nodeid=attack, baseline="passed", targets=[attack], mutants=[mutant])])
    output = tmp_path / "report.json"
    write_report(report, output)
    # Close the sync driver before later pytest-asyncio tests need their loop.
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            page.goto(output.with_suffix(".html").as_uri())
            assert page.evaluate("window.__vandal_xss") is None
            assert page.locator("img,script").count() == 0
            expect(page.locator("h1")).to_have_text("Vandal strength: 0.0%")
            assert attack in page.locator("table").inner_text()
        finally:
            browser.close()
    assert json.loads(output.read_text(encoding="utf-8")) == report


def test_ordinary_run_does_not_patch_playwright(tmp_path):
    run, report = run_suite(tmp_path, f'''
from playwright.sync_api import Page, Locator
def test_normal(page):
    assert not hasattr(Page.click, "__wrapped__")
    assert not hasattr(Locator.click, "__wrapped__")
    page.set_content({APP!r})
    page.click("#b")
    assert page.inner_text("#result") == "done"
''')
    assert run.returncode == 0, run.stdout
    assert report is None


def test_mutants_use_fresh_processes_and_session_fixtures(tmp_path):
    source = f'''
import pytest
@pytest.mark.vandal(targets=["#b"])
def test_isolated(page, session_state):
    assert session_state == []
    session_state.append("used")
    page.set_content({APP!r})
    page.locator("#b").text_content()
'''
    conftest = '''
import os, pytest
from pathlib import Path
@pytest.fixture(scope="session")
def session_state():
    with Path("processes.txt").open("a") as log:
        log.write(str(os.getpid()) + "\\n")
    return []
'''
    run, report = run_suite(
        tmp_path, source, "--vandal", "--vandal-strategies=logic_sabotage,ui_shift",
        conftest=conftest,
    )
    assert run.returncode == 0, run.stdout
    assert report["summary"]["survived"] == 2
    pids = (tmp_path / "processes.txt").read_text().splitlines()
    # Baseline, two clean controls and two mutants all use fresh processes.
    assert len(pids) == 5 and len(set(pids)) == 5


@pytest.mark.parametrize("phase", ["setup", "teardown"])
def test_deadline_includes_fixture_phases(tmp_path, phase):
    source = f'''
import pytest
@pytest.mark.vandal(targets=["#b"])
def test_deadline(page):
    page.set_content({APP!r})
    page.click("#b")
'''
    conftest = f'''
import os, time, pytest
@pytest.fixture(autouse=True)
def hanging_fixture():
    if "_VANDAL_WORKER" in os.environ and {phase!r} == "setup":
        time.sleep(60)
    yield
    if "_VANDAL_WORKER" in os.environ and {phase!r} == "teardown":
        time.sleep(60)
'''
    run, report = run_suite(
        tmp_path, source, "--vandal", "--vandal-strict", "--vandal-strategies=logic_sabotage",
        "--vandal-timeout=5", conftest=conftest,
    )
    assert run.returncode == 1
    assert report["summary"]["error"] == 1
    assert report["summary"]["killed"] == 0
    assert "timeout" in report["tests"][0]["mutants"][0]["details"].lower()


def test_quoted_selector_is_not_interpolated_as_javascript(tmp_path):
    selector = """button[data-name="O'Reilly"]"""
    app = """<button data-name="O'Reilly" onclick="this.textContent='done'">Go</button>"""
    source = f'''
import pytest
@pytest.mark.vandal(targets=[{selector!r}])
def test_quotes(page):
    page.set_content({app!r})
    page.locator({selector!r}).click()
    assert page.locator({selector!r}).inner_text() == "done"
'''
    run, report = run_suite(tmp_path, source, "--vandal", "--vandal-strategies=logic_sabotage")
    assert run.returncode == 0, run.stdout
    assert report["summary"]["killed"] == 1
    assert report["tests"][0]["mutants"][0]["selector"] == selector


def test_plugin_works_with_pytest_cache_disabled(tmp_path):
    source = f'''
import pytest
@pytest.mark.vandal(targets=["#b"])
def test_no_cache(page):
    page.set_content({APP!r})
    page.click("#b")
'''
    run, report = run_suite(tmp_path, source, "--vandal", "-p", "no:cacheprovider",
                           "--vandal-strategies=logic_sabotage")
    assert run.returncode == 0, run.stdout
    assert report["summary"]["survived"] == 1


def test_worker_preserves_baseline_junit_and_basetemp(tmp_path):
    import hashlib
    import xml.etree.ElementTree as ET
    source = f'''
import os, pytest
@pytest.mark.vandal(targets=["#b"])
def test_artifacts(page, tmp_path):
    (tmp_path / "phase.txt").write_text("worker" if "_VANDAL_WORKER" in os.environ else "baseline")
    page.set_content({APP!r})
    page.click("#b")
    assert page.inner_text("#result") == "done"
'''
    scratch = tmp_path / "scratch"
    junit = tmp_path / "baseline.xml"
    artifacts = tmp_path / "browser-artifacts"
    conftest = '''
import hashlib, json, os, pytest
from pathlib import Path
@pytest.hookimpl(tryfirst=True)
def pytest_sessionfinish(session):
    if "_VANDAL_WORKER" not in os.environ:
        output = Path(session.config.getoption("output"))
        snapshot = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in output.rglob("*.zip")}
        Path("baseline-traces.json").write_text(json.dumps(snapshot))
'''
    run, report = run_suite(
        tmp_path, source, "--vandal", "--vandal-strategies=logic_sabotage",
        "--basetemp=" + str(scratch), "--junitxml=" + str(junit),
        "--tracing=on", "--output=" + str(artifacts), conftest=conftest,
    )
    assert run.returncode == 0, run.stdout
    assert report["summary"]["killed"] == 1
    suite = ET.parse(junit).getroot().find("testsuite")
    assert suite.get("failures") == "0"
    assert {p.read_text() for p in scratch.rglob("phase.txt")} == {"baseline"}
    traces = json.loads((tmp_path / "baseline-traces.json").read_text())
    assert traces
    from pathlib import Path
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == digest
               for p, digest in traces.items())


def test_mixed_sync_async_suite_with_function_scoped_driver(tmp_path):
    source = f'''
import pytest
from playwright.sync_api import sync_playwright
from playwright.async_api import async_playwright
@pytest.fixture
def sync_page():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            yield browser.new_page()
        finally:
            browser.close()
@pytest.mark.vandal(targets=["#b"])
def test_sync(sync_page):
    sync_page.set_content({APP!r})
    sync_page.click("#b")
    assert sync_page.inner_text("#result") == "done"
@pytest.mark.asyncio
@pytest.mark.vandal(targets=["#b"])
async def test_async():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        try:
            page = await browser.new_page()
            await page.set_content({APP!r})
            await page.click("#b")
            assert await page.inner_text("#result") == "done"
        finally:
            await browser.close()
'''
    run, report = run_suite(tmp_path, source, "--vandal", "--vandal-strategies=logic_sabotage",
                           "--vandal-min-score=100")
    assert run.returncode == 0, run.stdout
    assert report["summary"]["killed"] == 2
    assert report["summary"]["error"] == 0
