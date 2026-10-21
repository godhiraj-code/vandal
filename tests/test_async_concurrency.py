"""Concurrent async operations must not lose confirmed application counts."""
import pytest

from test_plugin import run_suite


@pytest.mark.parametrize("operation", [
    "target.inner_text()", 'expect(target).to_have_text("Go")',
])
def test_parallel_async_reads_keep_confirmed_injection(tmp_path, operation):
    fixture = '''
import pytest_asyncio
from playwright.async_api import async_playwright
@pytest_asyncio.fixture
async def ready():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.set_content('<button id="b">Go</button>')
        yield page
        await browser.close()
'''
    source = f'''
import asyncio, pytest
from playwright.async_api import expect
@pytest.mark.asyncio
@pytest.mark.vandal(targets=["#b"])
async def test_reads(ready):
    target = ready.locator("#b")
    await asyncio.gather({operation}, {operation})
'''
    run, report = run_suite(
        tmp_path, source, "--vandal", "--vandal-strategies=logic_sabotage",
        "--vandal-min-score=0", conftest=fixture,
    )
    assert report["summary"]["survived"] == 1, report
    assert report["summary"]["not_applied"] == 0
    assert run.returncode == 0, run.stdout + run.stderr
