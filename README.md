# Project Vandal

[![PyPI version](https://img.shields.io/pypi/v/project-vandal.svg)](https://pypi.org/project/project-vandal/)
[![Python versions](https://img.shields.io/pypi/pyversions/project-vandal.svg)](https://pypi.org/project/project-vandal/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/godhiraj-code/vandal/blob/main/LICENSE)
[![Project Vandal CI](https://github.com/godhiraj-code/vandal/actions/workflows/vandal-ci.yml/badge.svg)](https://github.com/godhiraj-code/vandal/actions/workflows/vandal-ci.yml)

**Proof that your AI written end to end tests actually catch bugs.**

Vandal runs your pytest + Playwright tests against injected UI faults and measures
which faults trigger assertions or Playwright action failures. Passing tests can still miss broken behavior.
Vandal gives you a strength score and candidates for better assertions, including
reports that coding agents can read. A score describes the mutations exercised;
it is not a guarantee that a test catches every bug.

## Two minute quick start

In your existing Python test project:

```bash
pip install project-vandal pytest-playwright
playwright install chromium
pytest --vandal
```

The `page` fixture from pytest-playwright works with the sync API. Custom sync and
async Playwright tests work too; async tests need their usual async pytest plugin.
Normal `pytest` runs are unchanged when `--vandal` is absent.

Vandal first runs the selected tests without mutations. For each passing baseline,
it reruns the test in a fresh pytest process for each selected mutant, up to 20 per
test by default. It writes `vandal_report.json` and `vandal_report.html`, and prints
survivors and review hints.
Each candidate also requires a passing unmutated replay before injection.
Potential kills require another passing control afterward. Failed controls are
reported as errors and excluded from strength. Controls cannot prove causality:
intermittent external-state failures can still be mistaken for mutation kills.
Use repeatable fixtures and isolated application state.

```bash
pytest tests/test_login.py --vandal --vandal-strategies=logic_sabotage,data_sabotage --vandal-max-mutants=10 --vandal-timeout=60
pytest -k login --vandal --vandal-min-score=80
```

Strength is `100 * killed / (killed + survived)`, overall and per test. Assertion
failures and Playwright `Error`/`TimeoutError` in the test call count as killed
only after confirmed mutation and passing unmutated controls. Reports distinguish
`kill_reason: assertion` from `action_failed`. Worker deadlines, injection errors,
setup/teardown failures, and failed controls remain errors and are excluded.
Mutant errors do not fail the command by default; add `--vandal-strict` to fail
for them. Baseline failures retain pytest's status. No scored
mutants means `null` in JSON and `N/A` in the terminal; a minimum score gate fails
in that case, including a gate of zero.

Targets are discovered when actions, reads or Locator assertions run. Constructing
an unused locator does not create a target. By default, clicks, double-clicks, taps
and checks use `stealth_disable`, `ghost_element`, and `logic_sabotage`; reads,
assertions and fills use `data_sabotage`. `ui_shift` and `slow_load` require explicit
selection. Candidates alternate across targets before the cap; `skipped_by_cap`
reports candidates omitted by that cap. Data sabotage is refreshed when targets
are resolved again, so later app text changes do not silently undo it.
For focused runs, specify targets with normal Playwright selectors:

```python
import pytest

@pytest.mark.vandal(targets=["#login-btn"])
def test_login(page):
    page.goto("http://localhost:8000")
    page.locator("#login-btn").click()
    assert page.locator("#message").inner_text() == "Logged in"
```

The marker supplies targets; use normal pytest paths, `-k`, or `-m vandal` to select
tests. See [limits and outcome rules](TESTER_GUIDE.md) before treating a survivor
as a missing assertion.

## See a weak and strong test

From this repository after `pip install -e ".[test]"`:

```bash
pytest examples/test_strength.py --vandal --vandal-strategies=logic_sabotage
```

Both tests click the same button in a local HTML app. The weak test only clicks.
The strong test asserts the resulting message, so it detects the swallowed click.
Use the generated report to compare their measured scores.

## Coding agents and MCP

On Python 3.10 or newer:

```bash
pip install "project-vandal[mcp]"
vandal-mcp
```

Configure your MCP client to launch `vandal-mcp` with the trusted test repository
as its working directory. The stdio server exposes:

- `run_vandal(test_path, strategies, max_mutants, deadline_seconds, pytest_args)`: runs pytest and returns the JSON
  report, with an optional `deadline_seconds` (maximum 600), 30 seconds per
  worker, and a maximum of 100 mutants per test. `pytest_args` permits only `-k`,
  `-m`, and node IDs inside the working folder. A deadline returns completed
  mutants in a partial report with `timed_out: true`.
- `get_surviving_mutants(report_path)`: reads survivors and review hints from a
  report inside that working directory.

Tests and conftest files execute project code. Run the server only in trusted
checkouts, against isolated test data. Paths cannot escape the working directory;
commands use argument arrays without shell interpolation. See the
[agent skill](skills/vandal/SKILL.md) and [versioned report schema](docs/report-schema.md).

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

- `vandal/core.py`: The heart of the mutation engine (JavaScript-based strategies).
- `vandal/playwright_ext.py`: Playwright wrapper and context manager.
- `demo_vandal.py`: A demonstration script showing Vandal in action.
- `vandal_demo_app.html`: A simple demo application for testing.

## Running the Demo

The project includes a demo script that tests a simple login button.

### Headless Mode
```bash
python demo_vandal.py --headless
```

### Headed Mode
```bash
python demo_vandal.py --headed
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
Yes. Install the package and use `pytest --vandal` for automatic baseline and
mutation runs. Normal pytest selection still applies.

**Does it support Playwright's sync API?**
The automatic pytest plugin supports sync and async Playwright, including the
pytest-playwright `page` fixture. The existing manual `Vandal` context manager
remains async and fully compatible with its previous API.

**Why did my test raise an exception when the mutant was killed?**
Vandal records the result but does not swallow the exception: a killed mutant means your test failed, and the failure propagates. Catch it around the `async with` block if you want the run to continue, as `demo_vandal.py` does.

**"Warning: No elements found for selector"**
The selector matched nothing on the current page when the mutation was applied. On the current page a mutation is applied once, immediately, so wait for the element first (`await page.wait_for_selector(selector)`). Alternatively, apply the mutation before `page.goto()`: persistent mutations then watch the new page and also hit elements that appear later.

**My mutant survived but the UI was clearly broken.**
Check the hint, `force=True`, and assertions about the visible outcome. A survivor
is a candidate for review, not proof that an assertion is missing. The automatic
runner records controlled Playwright call failures as `action_failed` kills;
worker deadlines and infrastructure failures remain excluded errors.

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
