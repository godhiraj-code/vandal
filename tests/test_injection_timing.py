"""Browser regressions for targets, auto-wait ordering and mutation lifetime."""
import pytest

from test_plugin import APP, run_suite


@pytest.mark.parametrize("api", ["sync", "async"])
@pytest.mark.parametrize("locator", ['get_by_role("button", name="Go")',
                                    'locator("body").locator("#b")'])
def test_explicit_target_is_independent_of_action_locator(tmp_path, api, locator):
    asynchronous = api == "async"
    await_ = "await " if asynchronous else ""
    fixture = f'''
import pytest, pytest_asyncio
from playwright.{api}_api import {api}_playwright
@{"pytest_asyncio.fixture" if asynchronous else "pytest.fixture"}
{"async " if asynchronous else ""}def ready_page():
    {"async " if asynchronous else ""}with {api}_playwright() as p:
        browser = {await_}p.chromium.launch()
        page = {await_}browser.new_page()
        {await_}page.set_content({APP!r})
        yield page
        {await_}browser.close()
'''
    source = f'''
import pytest
{"@pytest.mark.asyncio" if asynchronous else ""}
@pytest.mark.parametrize("strong", [False, True])
@pytest.mark.vandal(targets=["#b"])
{"async " if asynchronous else ""}def test_flow(ready_page, strong):
    {await_}ready_page.{locator}.click()
    if strong:
        assert {await_}ready_page.locator("#result").inner_text() == "done"
'''
    run, report = run_suite(tmp_path, source, "--vandal",
                           "--vandal-strategies=logic_sabotage",
                           "--vandal-min-score=100", conftest=fixture)
    assert report is not None, run.stdout + run.stderr
    assert report["summary"]["killed"] == 1, report
    assert report["summary"]["survived"] == 1, report
    assert report["summary"]["not_applied"] == 0
    assert report["summary"]["score"] == 50
    assert run.returncode == 1


@pytest.mark.parametrize("api", ["sync", "async"])
@pytest.mark.parametrize("action", ['click("#b")',
                                   'get_by_role("button", name="Go").click()'])
@pytest.mark.parametrize("explicit", [False, True])
def test_late_target_is_mutated_before_auto_waited_action(tmp_path, api, action, explicit):
    asynchronous = api == "async"
    await_ = "await " if asynchronous else ""
    source = f'''
import pytest
from playwright.{api}_api import {api}_playwright
{"@pytest.mark.asyncio" if asynchronous else ""}
{"@pytest.mark.vandal(targets=['#b'])" if explicit else ""}
{"async " if asynchronous else ""}def test_flow():
    {"async " if asynchronous else ""}with {api}_playwright() as p:
        browser = {await_}p.chromium.launch()
        page = {await_}browser.new_page()
        {await_}page.set_content('<p id="result">waiting</p>')
        {await_}page.evaluate("""() => setTimeout(() => {{
            const b = document.createElement('button');
            b.id = 'b'; b.textContent = 'Go';
            b.onclick = () => document.querySelector('#result').textContent = 'done';
            document.body.append(b);
        }}, 250)""")
        try:
            {await_}page.{action}
            assert {await_}page.inner_text("#result") == "done"
        finally:
            {await_}browser.close()
'''
    run, report = run_suite(tmp_path, source, "--vandal",
                           "--vandal-strategies=logic_sabotage", "--vandal-max-mutants=1")
    assert run.returncode == 0, run.stdout + run.stderr
    assert report["summary"]["killed"] == 1, report
    assert report["summary"]["survived"] == 0


@pytest.mark.parametrize("api", ["sync", "async"])
def test_slow_load_restoration_does_not_reapply_to_same_node(tmp_path, api):
    asynchronous = api == "async"
    await_ = "await " if asynchronous else ""
    source = f'''
import pytest
from playwright.{api}_api import {api}_playwright
{"@pytest.mark.asyncio" if asynchronous else ""}
@pytest.mark.vandal(targets=["#b"])
{"async " if asynchronous else ""}def test_flow():
    {"async " if asynchronous else ""}with {api}_playwright() as p:
        browser = {await_}p.chromium.launch()
        page = {await_}browser.new_page()
        {await_}page.set_content({APP!r})
        try:
            {await_}page.wait_for_timeout(5300)
            assert {await_}page.locator("#b").is_visible()
            assert {await_}page.is_visible("#b")
        finally:
            {await_}browser.close()
'''
    run, report = run_suite(tmp_path, source, "--vandal", "--vandal-strategies=slow_load")
    assert run.returncode == 0, run.stdout + run.stderr
    assert report["summary"]["survived"] == 1, report
    assert report["summary"]["killed"] == 0


@pytest.mark.parametrize("api", ["sync", "async"])
def test_assertion_only_locator_from_fixture_is_mutated(tmp_path, api):
    asynchronous = api == "async"
    await_ = "await " if asynchronous else ""
    fixture = f'''
import pytest, pytest_asyncio
from playwright.{api}_api import {api}_playwright
@{"pytest_asyncio.fixture" if asynchronous else "pytest.fixture"}
{"async " if asynchronous else ""}def target():
    {"async " if asynchronous else ""}with {api}_playwright() as p:
        browser = {await_}p.chromium.launch()
        page = {await_}browser.new_page()
        {await_}page.set_content({APP!r})
        yield page.locator("#b")
        {await_}browser.close()
'''
    source = f'''
import pytest
from playwright.{api}_api import expect
{"@pytest.mark.asyncio" if asynchronous else ""}
{"async " if asynchronous else ""}def test_text(target):
    {await_}expect(target).to_have_text("Go", timeout=200)
'''
    run, report = run_suite(tmp_path, source, "--vandal",
                           "--vandal-strategies=data_sabotage",
                           conftest=fixture)
    assert run.returncode == 0, run.stdout + run.stderr
    assert report["summary"]["killed"] == 1, report
    assert report["summary"]["not_applied"] == 0


def test_dirty_external_state_cannot_count_as_a_kill(tmp_path):
    source = f'''
from pathlib import Path
import pytest
@pytest.mark.vandal(targets=["#b"])
def test_flow(page):
    page.set_content({APP!r})
    marker = Path("application-state.txt")
    assert not marker.exists(), "dirty application state"
    marker.write_text("created")
    page.click("#b")
'''
    run, report = run_suite(tmp_path, source, "--vandal",
                           "--vandal-strategies=ui_shift", "--vandal-min-score=100")
    assert report["summary"]["killed"] == 0, report
    assert report["summary"]["error"] == 1
    assert report["summary"]["score"] is None
    assert "Clean replay" in report["tests"][0]["mutants"][0]["details"]
    assert run.returncode == 1


def test_failed_post_control_invalidates_a_possible_kill(tmp_path):
    source = f'''
from pathlib import Path
import pytest
@pytest.mark.vandal(targets=["#b"])
def test_flow(page):
    marker = Path("application-state.txt")
    assert not marker.exists(), "dirty application state"
    page.set_content({APP!r})
    if page.locator("#b").evaluate("el => getComputedStyle(el).transform") != "none":
        marker.write_text("changed external state")
    assert not marker.exists()
'''
    run, report = run_suite(tmp_path, source, "--vandal", "--vandal-strategies=ui_shift")
    mutant = report["tests"][0]["mutants"][0]
    assert mutant["controls"] == {"before": "passed", "after": "error"}
    assert mutant["status"] == "error"
    assert "Clean replay after" in mutant["details"]
    assert report["summary"]["killed"] == 0
    assert run.returncode == 1


def test_immediate_reads_and_absence_assertions_do_not_wait_for_attachment(tmp_path):
    source = f'''
import pytest
from playwright.sync_api import expect
@pytest.mark.vandal(targets=["#b"])
def test_absence(page):
    page.set_default_timeout(100)
    page.set_content({APP!r})
    missing = page.locator("#missing")
    assert missing.count() == 0
    assert not missing.is_visible()
    missing.wait_for(state="hidden")
    missing.wait_for(state="detached")
    expect(missing).to_be_hidden()
    expect(missing).not_to_be_visible()
    expect(missing).to_have_count(0)
    expect(missing).to_have_text([])
'''
    run, report = run_suite(tmp_path, source, "--vandal", "--vandal-strategies=logic_sabotage")
    assert run.returncode == 0, run.stdout + run.stderr
    assert report["summary"]["survived"] == 1, report
    assert report["summary"]["error"] == 0


@pytest.mark.parametrize("strategy,assertion", [
    ("stealth_disable", 'expect(target).to_have_css("pointer-events", "auto", timeout=100)'),
    ("ghost_element", 'expect(target).to_have_css("opacity", "1", timeout=100)'),
    ("data_sabotage", 'expect(target).to_have_text("Go", timeout=100)'),
    ("ui_shift", 'expect(target).to_have_css("transform", "none", timeout=100)'),
    ("slow_load", 'assert target.is_visible()'),
    ("logic_sabotage", 'target.click(); assert page.inner_text("#result") == "done"'),
])
def test_each_strategy_changes_its_intended_browser_behavior(tmp_path, strategy, assertion):
    source = f'''
import pytest
from playwright.sync_api import expect
@pytest.mark.vandal(targets=["#b"])
def test_effect(page):
    page.set_content({APP!r})
    target = page.locator("#b")
    {assertion}
'''
    run, report = run_suite(tmp_path, source, "--vandal", "--vandal-strategies=" + strategy)
    assert run.returncode == 0, run.stdout + run.stderr
    assert report["summary"]["killed"] == 1, report
    assert report["summary"]["error"] == 0
