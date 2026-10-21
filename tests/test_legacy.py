import json

import pytest
from playwright.async_api import async_playwright

from vandal import Vandal


@pytest.mark.asyncio
async def test_legacy_context_revert_and_report(tmp_path):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        try:
            page = await browser.new_page()
            await page.set_content('<button id="b">Original</button>')
            async with Vandal(page) as passed:
                await passed.apply_mutation("data_sabotage", "#b", persistent=False)
                assert await page.inner_text("#b") == "VANDALIZED_TEXT"
                await passed.revert_mutation("data_sabotage", "#b")
                assert await page.inner_text("#b") == "Original"
            assert len(passed.mutants) == 1 and not passed.mutants[0].killed
            with pytest.raises(AssertionError, match="expected failure"):
                async with Vandal(page) as failed:
                    await failed.apply_mutation("data_sabotage", "#b")
                    raise AssertionError("expected failure")
            assert failed.mutants[0].killed
            output = tmp_path / "legacy.json"
            failed.save_report(str(output))
            assert isinstance(json.loads(output.read_text()), list)
            assert output.with_suffix(".html").exists()
            # The registered manual init script still applies after navigation.
            await page.goto("data:text/html,<button id='b'>Original</button>")
            assert await page.inner_text("#b") == "VANDALIZED_TEXT"
        finally:
            await browser.close()
