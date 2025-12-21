# Automation Tester's Guide to Project Vandal

The easiest way to get started is via PyPI:

```bash
pip install project-vandal
```

### Manual Installation (Development)
If you want to contribute or customize the engine:
```bash
git clone https://github.com/godhiraj-code/vandal.git
cd vandal
pip install .
```

Welcome to the advanced guide for Project Vandal. This document explains how to integrate, customize, and master UI mutation testing in your automation framework.

---

## 1. Quick Integration

Project Vandal is designed to be framework-agnostic but pairs perfectly with **Playwright**.

### Using as a Context Manager
The simplest way to use Vandal is via the `Vandal` context manager. This ensures that the mutation is applied, the test runs, and the result is captured automatically.

```python
from vandal import Vandal

async def test_login_resilience(page):
    async with Vandal(page) as v:
        # 1. Apply Mutation
        await v.apply_mutation("stealth_disable", "#submit-button")
        
        # 2. Run Test Steps
        await page.fill("#user", "test")
        await page.click("#submit-button")
        
        # 3. Assert (This is where you "Kill" the mutant)
        # If the mutation worked, the message below should NOT appear.
        assert await page.is_visible(".success-msg")
```

---

## 2. Advanced Integration Patterns

### Pytest Fixture (Recommended)
For large projects, wrap Vandal in a pytest fixture for cleaner tests.

```python
import pytest
from vandal import Vandal

@pytest.fixture
async def vandal(page):
    async with Vandal(page) as v:
        yield v
    v.report()

async def test_feature_x(page, vandal):
    await vandal.apply_mutation("data_sabotage", ".input-field")
    # ... test logic ...
```

---

## 3. Customizing Mutation Strategies

Vandal allows you to define your own "sabotage" logic. All mutations are JavaScript functions injected into the browser.

### Adding a New Strategy
1. Open `core.py`.
2. Add your strategy to the `MUTATIONS` dictionary.

Example: **"Color Blindness" Sabotage**
This mutation makes all text the same color as the background.

```python
# core.py
"invisible_text": """
    (selector) => {
        const elements = document.querySelectorAll(selector);
        elements.forEach(el => {
            el.style.color = window.getComputedStyle(el).backgroundColor;
            el.setAttribute('data-vandalized', 'invisible_text');
        });
        return elements.length;
    }
"""
```

---

## 4. Best Practices for Testers

### Target Selection
Don't vandalize everything. Target **High-Impact UI Elements**:
- Primary Call-to-Action (CTA) buttons.
- Form inputs that trigger validation.
- Critical navigation links.
- Elements that rely on complex event listeners (e.g., drag-and-drop).

### "Killing" the Mutant
A mutant is **KILLED** if your test fails. If your test passes despite the UI being broken, the mutant has **SURVIVED**.
- **Killed**: Great! Your test is sensitive to UI failures.
- **Survived**: Warning! Your test might be too "loose" or your assertions aren't checking the right things.

### When to Run Vandal?
UI Mutation testing is computationally expensive. Use it:
1. During **Nightly CI Runs**.
2. When creating a **New Critical Test Case** (to verify the test's own quality).
3. During **Regression Sprints**.

---

## 5. Troubleshooting

- **No Elements Found**: Ensure your selector is correct and the element is present in the DOM when `apply_mutation` is called. Use `await page.wait_for_selector(selector)` before applying.
- **Mutant Survived Unnecessarily**: Check if your test is using `force=True` on clicks. Playwright's default click checks for visibility and pointer-events; if you bypass these, you might "miss" a `stealth_disable`.

---

---

## 6. Advanced Features (v0.2.0)

Project Vandal v0.2.0 addresses several major limitations found in traditional UI automation:

1. **Navigation Survival**: Mutations now persist across page reloads and navigations using a combination of `add_init_script` and deep `MutationObserver`.
2. **Shadow DOM Support**: The engine now penetrates Shadow DOM boundaries recursively, ensuring that even elements hidden inside shadow roots are vandalized.
3. **Automatic Revert**: Most mutations can be reverted on-the-fly without a page reload using the `revert_mutation()` method.
4. **Resilient Monitoring**: Mutations are applied even to elements added dynamically to the page after initial load.
5. **JSON/HTML Reporting**: Reports are automatically saved to disk in both machine-readable (JSON) and human-readable (HTML) formats.

---

## 7. Known Limitations

1. **Limited Library Support**: Currently, only **Playwright** (Python) is supported. Selenium and Cypress integrations are planned.
2. **Infinite Mutation Loops**: While Vandal tries to avoid re-mutating elements, complex page structures might occasionally trigger multiple observer fires.
3. **Revert Limitations**: Some complex CSS-based mutations might take more effort to revert perfectly.
