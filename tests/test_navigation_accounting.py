"""A mutation receipt must outlive the document it changed."""
import pytest

from test_native_retry import fixture
from test_plugin import run_suite


@pytest.mark.parametrize("api", ["sync", "async"])
@pytest.mark.parametrize("mixed_gate", [False, True])
def test_native_mutation_accounting_survives_navigation(tmp_path, api, mixed_gate):
    wait = "await " if api == "async" else ""
    async_def = "async " if api == "async" else ""
    mark = "@pytest.mark.asyncio" if api == "async" else ""
    values = "[False]" if mixed_gate else "[False, True]"
    source = f'''
import json, pytest
from playwright.{api}_api import expect
{mark}
@pytest.mark.parametrize("strong", {values})
@pytest.mark.vandal(targets=["#late"])
{async_def}def test_navigation(ready, tmp_path, strong):
    destination = tmp_path / "result.html"
    destination.write_text("<h1>Result</h1>")
    app = tmp_path / "app.html"
    app.write_text('<script>setTimeout(() => {{const b=document.createElement("button");'
        'b.id="late"; b.textContent="Go"; b.onclick=()=>location.href='
        + json.dumps(destination.as_uri()) +
        '+"?label="+encodeURIComponent(b.textContent);document.body.append(b);}},750);</script>')
    {wait}ready.goto(app.as_uri())
    {wait}ready.locator("#late").click()
    {wait}expect(ready.locator("h1")).to_have_text("Result")
    if strong:
        assert ready.url.endswith("?label=Go")
'''
    if mixed_gate:
        source += f'''
{mark}
@pytest.mark.vandal(targets=["#static"])
{async_def}def test_static(ready):
    {wait}ready.set_content('<p id="static">Go</p>')
    assert {wait}ready.locator("#static").inner_text() == "Go"
'''
    run, report = run_suite(tmp_path, source, "--vandal",
                           "--vandal-strategies=data_sabotage",
                           "--vandal-min-score=100" if mixed_gate else "--vandal-min-score=50",
                           conftest=fixture(api))
    assert report["summary"]["killed"] == 1, report
    assert report["summary"]["survived"] == 1, report
    assert report["summary"]["error"] == 0, report
    assert report["summary"]["not_applied"] == 0, report
    assert report["summary"]["score"] == 50
    assert run.returncode == (1 if mixed_gate else 0), run.stdout + run.stderr
