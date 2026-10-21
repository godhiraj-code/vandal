# Can your passing Playwright tests detect a broken UI?

A passing click is useful, but it does not establish that the click produced the
expected result. Vandal injects faults into the live DOM so you can test that
assumption directly.

## Run the pytest plugin

```bash
pip install project-vandal pytest-playwright
playwright install chromium
pytest --vandal --vandal-strategies=logic_sabotage
```

The plugin runs clean baselines, discovers observed targets, and replays each
selected test with individual faults. It supports sync and async Playwright.
Unmutated controls run before mutation and after a possible kill, excluding
reproducible replay failures from the score. JSON and HTML reports include
survivors, excluded outcomes and hints for reviewing assertions.

Try `examples/test_strength.py` for a local app with a click-only test and a test
that checks the resulting message. Read its generated report for measured results.
No production improvement or timing benchmark is claimed here.

## Keep manual control when needed

The existing async `Vandal` context manager remains available:

```python
from vandal import Vandal

async def test_checkout(page):
    async with Vandal(page) as v:
        await v.apply_mutation("logic_sabotage", "#checkout-btn")
        await page.click("#checkout-btn")
        assert await page.locator("#confirmation").inner_text() == "Order placed"
```

Exceptions must leave the context for the manual API to record a kill. Its
exception-based accounting is broader than the pytest plugin's assertion and
control rules. Manual persistence uses observers; the automatic plugin observes
Playwright operations instead. Reversion is supported only for the strategies
listed in the [test guide](TESTER_GUIDE.md).

## Improve the test contract

A survivor is a candidate for review. It can mean a missing outcome assertion,
but it can also reflect an equivalent mutation or an intentionally unchecked
property. Inspect the strategy, selector, errors and hints before changing a test.
A score gate is available with `--vandal-min-score`, and the optional MCP server
lets coding agents run the same feedback loop. See [README.md](README.md) for the
quick start and [TESTER_GUIDE.md](TESTER_GUIDE.md) for discovery and isolation limits.
