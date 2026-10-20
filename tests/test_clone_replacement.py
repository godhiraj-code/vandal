"""Copied DOM markers are not proof that a replacement retained its mutation."""
import pytest

from test_native_retry import fixture
from test_plugin import APP, run_suite


@pytest.mark.parametrize("api", ["sync", "async"])
@pytest.mark.parametrize("strategy", ["logic_sabotage", "slow_load"])
def test_cloned_nodes_receive_their_own_mutation(tmp_path, api, strategy):
    wait = "await " if api == "async" else ""
    app = APP + """<button id="reload" onclick="const old=document.querySelector('#b');
        old.replaceWith(old.cloneNode(true))">Reload</button>"""
    outcome = (f'{wait}ready.locator("#b").click()\n'
               f'    {wait}expect(ready.locator("#result")).to_have_text("done", timeout=100)'
               if strategy == "logic_sabotage" else
               f'{wait}ready.wait_for_timeout(5300)\n'
               f'    assert {wait}ready.locator("#b").is_visible()')
    source = f'''
import pytest
from playwright.{api}_api import expect
{"@pytest.mark.asyncio" if api == "async" else ""}
@pytest.mark.vandal(targets=["#b"])
{"async " if api == "async" else ""}def test_flow(ready):
    {wait}ready.set_content({app!r})
    {wait}ready.locator("#reload").click()
    assert {wait}ready.locator("#b").count() == 1
    {outcome}
'''
    run, report = run_suite(tmp_path, source, "--vandal",
                           "--vandal-strategies=" + strategy, conftest=fixture(api))
    assert report["summary"]["error"] == 0, report
    expected = "killed" if strategy == "logic_sabotage" else "survived"
    assert report["summary"][expected] == 1, report
    assert run.returncode == 0, run.stdout + run.stderr
