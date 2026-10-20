"""Mutations must follow native resolution of replacement nodes and frames."""
import pytest

from test_plugin import APP, run_suite


def fixture(api, html=APP):
    async_ = api == "async"
    wait = "await " if async_ else ""
    return f'''
import pytest, pytest_asyncio
from playwright.{api}_api import {api}_playwright
@{"pytest_asyncio.fixture" if async_ else "pytest.fixture"}
{"async " if async_ else ""}def ready():
    {"async " if async_ else ""}with {api}_playwright() as p:
        browser = {wait}p.chromium.launch()
        page = {wait}browser.new_page()
        {wait}page.set_content({html!r})
        yield page
        {wait}browser.close()
'''


@pytest.mark.parametrize("api", ["sync", "async"])
@pytest.mark.parametrize("during_retry", [False, True])
def test_replacement_assertion_mutates_each_new_node(tmp_path, api, during_retry):
    wait = "await " if api == "async" else ""
    source = f'''
import pytest
from playwright.{api}_api import expect
{"@pytest.mark.asyncio" if api == "async" else ""}
@pytest.mark.vandal(targets=["#b"])
{"async " if api == "async" else ""}def test_flow(ready):
    {wait}ready.set_content('<p id="b">Go</p>')
    {wait}ready.evaluate("""() => {{
        {"setTimeout(() => {" if during_retry else ""}
        document.querySelector('#b').remove();
        setTimeout(() => {{
            const p = document.createElement('p');
            p.id = 'b'; p.textContent = 'Go'; document.body.append(p);
        }}, 150);
        {"}, 100);" if during_retry else ""}
    }}""")
    {wait}expect(ready.locator("#b")).to_have_text("Go", timeout=600)
'''
    run, report = run_suite(tmp_path, source, "--vandal",
                           "--vandal-strategies=data_sabotage",
                           conftest=fixture(api))
    assert report["summary"]["killed"] == 1, report
    assert report["summary"]["error"] == 0, report
    assert run.returncode == 0, run.stdout + run.stderr


@pytest.mark.parametrize("api", ["sync", "async"])
def test_detached_false_keeps_native_absence_semantics(tmp_path, api):
    wait = "await " if api == "async" else ""
    source = f'''
import pytest
from playwright.{api}_api import expect
{"@pytest.mark.asyncio" if api == "async" else ""}
@pytest.mark.vandal(targets=["#b"])
{"async " if api == "async" else ""}def test_flow(ready):
    {wait}expect(ready.locator("#missing")).to_be_attached(attached=False, timeout=100)
    {wait}ready.locator("#b").click()
'''
    run, report = run_suite(tmp_path, source, "--vandal",
                           "--vandal-strategies=logic_sabotage",
                           conftest=fixture(api))
    assert report["summary"]["survived"] == 1, report
    assert report["summary"]["error"] == 0, report
    assert run.returncode == 0, run.stdout + run.stderr


@pytest.mark.parametrize("api", ["sync", "async"])
@pytest.mark.parametrize("nested", [False, True])
def test_relative_marker_resolves_in_frame_locator_context(tmp_path, api, nested):
    wait = "await " if api == "async" else ""
    setup = fixture(api, '<iframe id="frame" name="frame"></iframe>')
    setup = setup.replace("        yield page", f'''
        frame = page.frame(name="frame")
        {wait}frame.set_content({('<iframe id="inner" name="inner"></iframe>' if nested else APP)!r})
        {f'frame = page.frame(name="inner")' if nested else ''}
        {wait + "frame.set_content(" + repr(APP) + ")" if nested else ""}
        yield page''')
    locator = 'ready.frame_locator("#frame")' + ('.frame_locator("#inner")' if nested else "")
    source = f'''
import pytest
from playwright.{api}_api import expect
{"@pytest.mark.asyncio" if api == "async" else ""}
@pytest.mark.vandal(targets=["#b"])
{"async " if api == "async" else ""}def test_flow(ready):
    {wait}{locator}.get_by_role("button", name="Go").click()
    {wait}expect({locator}.locator("#result")).to_have_text("done", timeout=100)
'''
    run, report = run_suite(tmp_path, source, "--vandal",
                           "--vandal-strategies=logic_sabotage",
                           conftest=setup)
    assert report["summary"]["killed"] == 1, report
    assert report["summary"]["error"] == 0, report
    assert run.returncode == 0, run.stdout + run.stderr


@pytest.mark.parametrize("api", ["sync", "async"])
def test_late_positive_array_assertion_is_mutated(tmp_path, api):
    wait = "await " if api == "async" else ""
    source = f'''
import pytest
from playwright.{api}_api import expect
{"@pytest.mark.asyncio" if api == "async" else ""}
@pytest.mark.vandal(targets=["#late"])
{"async " if api == "async" else ""}def test_flow(ready):
    {wait}ready.evaluate("""() => setTimeout(() => {{
        const p = document.createElement('p'); p.id = 'late';
        p.textContent = 'Go'; document.body.append(p);
    }}, 100)""")
    {wait}expect(ready.locator("#late")).to_have_text(["Go"], timeout=600)
'''
    run, report = run_suite(tmp_path, source, "--vandal",
                           "--vandal-strategies=data_sabotage",
                           conftest=fixture(api))
    assert report["summary"]["killed"] == 1, report
    assert run.returncode == 0, run.stdout + run.stderr


@pytest.mark.parametrize("api", ["sync", "async"])
def test_replacement_during_actionability_retry_is_mutated(tmp_path, api):
    wait = "await " if api == "async" else ""
    source = f'''
import pytest
from playwright.{api}_api import expect
{"@pytest.mark.asyncio" if api == "async" else ""}
@pytest.mark.vandal(targets=["#b"])
{"async " if api == "async" else ""}def test_flow(ready):
    {wait}ready.set_content('<button id="b" disabled>Go</button><p id="result">waiting</p>')
    {wait}ready.evaluate("""() => setTimeout(() => {{
        document.querySelector('#b').remove();
        const b = document.createElement('button'); b.id = 'b'; b.textContent = 'Go';
        b.onclick = () => document.querySelector('#result').textContent = 'done';
        document.body.append(b);
    }}, 150)""")
    {wait}ready.locator("#b").click(timeout=1500)
    {wait}expect(ready.locator("#result")).to_have_text("done", timeout=100)
'''
    run, report = run_suite(tmp_path, source, "--vandal",
                           "--vandal-strategies=logic_sabotage",
                           conftest=fixture(api))
    assert report["summary"]["killed"] == 1, report
    assert report["summary"]["error"] == 0, report
    assert run.returncode == 0, run.stdout + run.stderr


@pytest.mark.parametrize("api", ["sync", "async"])
@pytest.mark.parametrize("factory", ["get_by_role", "get_by_text"])
def test_frame_traversal_text_inside_regex_is_not_a_frame(tmp_path, api, factory):
    wait = "await " if api == "async" else ""
    html = APP.replace(">Go</button>", ">before >> internal:control=enter-frame >> after</button>")
    locator = ('get_by_role("button", name=pattern)' if factory == "get_by_role"
               else "get_by_text(pattern)")
    source = f'''
import pytest, re
from playwright.{api}_api import expect
{"@pytest.mark.asyncio" if api == "async" else ""}
@pytest.mark.vandal(targets=["#b"])
{"async " if api == "async" else ""}def test_flow(ready):
    pattern = re.compile("before >> internal:control=enter-frame >> after")
    {wait}ready.{locator}.click(timeout=800)
    {wait}expect(ready.locator("#result")).to_have_text("done", timeout=100)
'''
    run, report = run_suite(tmp_path, source, "--vandal",
                           "--vandal-strategies=logic_sabotage",
                           conftest=fixture(api, html))
    assert report["summary"]["killed"] == 1, report
    assert report["summary"]["error"] == 0, report
    assert run.returncode == 0, run.stdout + run.stderr
