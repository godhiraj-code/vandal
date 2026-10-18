# Project Vandal: UI Mutation Testing Engine

[![PyPI version](https://img.shields.io/pypi/v/project-vandal.svg)](https://pypi.org/project/project-vandal/)
[![Python versions](https://img.shields.io/pypi/pyversions/project-vandal.svg)](https://pypi.org/project/project-vandal/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/godhiraj-code/vandal/blob/main/LICENSE)
[![Project Vandal CI](https://github.com/godhiraj-code/vandal/actions/workflows/vandal-ci.yml/badge.svg)](https://github.com/godhiraj-code/vandal/actions/workflows/vandal-ci.yml)

**Your E2E suite is green, but would it catch a broken button?** Vandal injects realistic UI faults (unclickable buttons, hidden elements, junk data, swallowed click handlers) into a live Playwright page and reports which "mutants" your tests failed to kill.

Project Vandal is a lightweight, non-LLM UI mutation testing engine integrated with Playwright. It allows you to sabotage your UI in subtle ways to verify if your end-to-end tests are resilient and capable of detecting regressions.

**Learn more:** [Project Vandal: UI mutation testing](https://www.dhirajdas.dev/blog/project-vandal-ui-mutation-testing) · [Project page](https://www.dhirajdas.dev/project/project-vandal) · [Tester's Guide](https://github.com/godhiraj-code/vandal/blob/main/TESTER_GUIDE.md) · [Follow @dkkkkd on X](https://x.com/dkkkkd)

## Installation

Ensure you have Playwright installed:

```bash
# Install the engine from PyPI
pip install project-vandal

# Or clone for local development
git clone https://github.com/godhiraj-code/vandal.git
cd vandal
pip install .

# Setup Playwright
playwright install chromium
```

## Usage

You can use the `Vandal` class as a context manager in your Playwright tests (Vandal uses Playwright's async API):

```python
from vandal import Vandal

async with Vandal(page) as v:
    # Apply a mutation to an element
    await v.apply_mutation("stealth_disable", "#login-btn")
    
    # Run your test logic
    await page.click("#login-btn")
    
    # Assert the outcome
    assert await page.inner_text("#msg") == "Success"
```

If the test fails inside the `async with` block, the mutant is recorded as **killed** (your test noticed the sabotage). If it passes, the mutant **survived**, which points to a gap in your assertions. Call `v.report()` to print the results or `v.save_report()` to write `vandal_report.json` and `vandal_report.html`.

## Features

- **Mutation Strategies**:
    - `stealth_disable`: Disables pointer events on elements, making them unclickable while remaining visually present.
    - `ghost_element`: Makes elements invisible and unclickable.
    - `data_sabotage`: Replaces text or input values with junk data.
    - `logic_sabotage`: Prevents event propagation (e.g., stopping click handlers from firing).
    - `ui_shift`: Moves elements 100px right and down with a CSS transform.
    - `slow_load`: Hides elements for 5 seconds, then shows them again.
- **Playwright Integration**: Easy-to-use context manager (`Vandal`) for wrapping test logic.
- **Shadow DOM and navigation**: Mutations reach elements inside open shadow roots. By default (`persistent=True`) they are also registered as an init script, so they are re-applied on every page loaded afterwards, including to elements added dynamically on those pages.
- **Reporting**: Automated mutation report showing which "mutants" were killed (detected by tests) or survived.
- **Detailed Guide**: See [TESTER_GUIDE.md](https://github.com/godhiraj-code/vandal/blob/main/TESTER_GUIDE.md) for advanced usage and customization.

## Project Structure

- `core.py`: The heart of the mutation engine (JavaScript-based strategies).
- `playwright_ext.py`: Playwright wrapper and context manager.
- `demo_vandal.py`: A demonstration script showing Vandal in action.
- `vandal_demo_app.html`: A simple demo application for testing.

## Running the Demo

The project includes a demo script that tests a simple login button.

### Headless Mode
```bash
PYTHONPATH="." python demo_vandal.py --headless
```

### Headed Mode
```bash
PYTHONPATH="." python demo_vandal.py --headed
```

In headed mode, the script includes a `slow_mo` delay and holds the browser open for 5 seconds after completion so you can see the results.

## When to use Vandal (vs code mutation testing)

| Tool | What it mutates | What it tells you |
|---|---|---|
| [mutmut](https://github.com/boxed/mutmut), [cosmic-ray](https://github.com/sixty-north/cosmic-ray) | Your Python **source code** (operators, constants, conditions) | Whether your unit/integration tests notice code changes |
| Project Vandal | The **rendered UI** in a live browser page (pointer events, visibility, text/values, click handlers, position) | Whether your Playwright end-to-end tests notice a broken UI |

They answer different questions and work well together. Use Vandal when:

- you want evidence that a critical E2E test (login, checkout, a primary CTA) actually fails when that UI breaks
- you suspect tests are "too loose", for example they click with `force=True` or never assert on the outcome
- you are reviewing a new critical test before trusting it in CI

Vandal is not a good fit if you use Selenium or Cypress (only Playwright for Python is supported today), or if you want to measure unit-test quality (use a source-code mutation tool for that).

## FAQ and Troubleshooting

**Does it work with pytest?**
Yes, with an async Playwright setup (for example `pytest-asyncio`). The [Tester's Guide](https://github.com/godhiraj-code/vandal/blob/main/TESTER_GUIDE.md) has a fixture pattern.

**Does it support Playwright's sync API?**
No. `Vandal` is an async context manager and `apply_mutation()` is a coroutine, so use `playwright.async_api`.

**Why did my test raise an exception when the mutant was killed?**
Vandal records the result but does not swallow the exception: a killed mutant means your test failed, and the failure propagates. Catch it around the `async with` block if you want the run to continue, as `demo_vandal.py` does.

**"Warning: No elements found for selector"**
The selector matched nothing on the current page when the mutation was applied. On the current page a mutation is applied once, immediately, so wait for the element first (`await page.wait_for_selector(selector)`). Alternatively, apply the mutation before `page.goto()`: persistent mutations then watch the new page and also hit elements that appear later.

**My mutant survived but the UI was clearly broken.**
Check for `force=True` on clicks. Playwright's actionability checks would otherwise catch `stealth_disable` and `ghost_element`.

**Can I undo a mutation?**
`revert_mutation()` reverts `stealth_disable`, `ghost_element`, `data_sabotage` and `ui_shift` on the current page. `logic_sabotage` and `slow_load` have no revert script. Persistent mutations are registered with `page.add_init_script()`, which Playwright can't remove, so use a fresh page or context for the next test.

## Why "Vandal"?

Unlike traditional mutation testing that modifies source code, Project Vandal sabotages the **UI layer** directly in the browser. This is particularly effective for catching:

- CSS regressions that block interactions.
- Event listener bugs.
- Data binding failures.

> [!NOTE]
> *Project Vandal is an open-source research initiative by [Dhiraj Das | Automation Architect](https://www.dhirajdas.dev).*

## License

MIT. See [LICENSE](https://github.com/godhiraj-code/vandal/blob/main/LICENSE).
