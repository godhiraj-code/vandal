# Project Vandal: UI Mutation Testing Engine

[![Project Vandal CI](https://github.com/godhiraj-code/vandal/actions/workflows/vandal-ci.yml/badge.svg)](https://github.com/godhiraj-code/vandal/actions/workflows/vandal-ci.yml)

Project Vandal is a lightweight, non-LLM UI mutation testing engine integrated with Playwright. It allows you to sabotage your UI in subtle ways to verify if your end-to-end tests are resilient and capable of detecting regressions.

## Features

- **Mutation Strategies**:
    - `stealth_disable`: Disables pointer events on elements, making them unclickable while remaining visually present.
    - `ghost_element`: Makes elements invisible and unclickable.
    - `data_sabotage`: Replaces text or input values with junk data.
    - `logic_sabotage`: Prevents event propagation (e.g., stopping click handlers from firing).
- **Playwright Integration**: Easy-to-use context manager (`Vandal`) for wrapping test logic.
- **Reporting**: Automated mutation report showing which "mutants" were killed (detected by tests) or survived.
- **Detailed Guide**: See [TESTER_GUIDE.md](file:///c:/vandal/TESTER_GUIDE.md) for advanced usage and customization.

## Project Structure

- `core.py`: The heart of the mutation engine (JavaScript-based strategies).
- `playwright_ext.py`: Playwright wrapper and context manager.
- `demo_vandal.py`: A demonstration script showing Vandal in action.
- `vandal_demo_app.html`: A simple demo application for testing.

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

You can use the `Vandal` class as a context manager in your Playwright tests:

```python
from vandal import Vandal

async with Vandal(page) as v:
    # Aply a mutation to an element
    await v.apply_mutation("stealth_disable", "#login-btn")
    
    # Run your test logic
    await page.click("#login-btn")
    
    # Assert the outcome
    assert await page.inner_text("#msg") == "Success"
```

## Running the Demo

The project includes a demo script that tests a simple login button.

### Headless Mode
```bash
PYTHONPATH="." python demo_vandal.py --headless
```

```bash
PYTHONPATH="." python demo_vandal.py --headed
```

In headed mode, the script includes a `slow_mo` delay and holds the browser open for 5 seconds after completion so you can see the results.

## Why "Vandal"?

Unlike traditional mutation testing that modifies source code, Project Vandal sabotages the **UI layer** directly in the browser. This is particularly effective for catching:
> [!NOTE]
> *Project Vandal is an open-source research initiative by [Dhiraj Das | Automation Architect](https://www.dhirajdas.dev).*
- CSS regressions that block interactions.
- Event listener bugs.
- Data binding failures.
```
