![Project Vandal Cover](./vandal_project_cover.png)

# Stop Shipping "Zombie Tests": Introducing Project Vandal v0.2.0 🤘

Have you ever looked at a 100% green test suite and wondered: *"Is this actually testing anything, or is it just passing because the happy path hasn't changed?"*

In the world of Test Automation, we often suffer from **test rot**—tests that remain green even when the application logic is broken. These are **Zombie Tests**. They give you a false sense of security, and they are the reason bugs slip into production despite your massive automation suite.

Today, we are elevating **Project Vandal**: A runtime UI Mutation Testing engine for Playwright that forces your tests to earn their keep.

---

## What is Project Vandal?

**Vandal** is a deterministic chaos engineering tool for frontends. Unlike traditional mutation testing that modifies source code (slow and rebuild-heavy), Vandal sabotages the **live DOM** inside your browser during test execution.

### The "Aha!" Moment
Traditional tools change your `if` statements to `else` in React/Vue source.
**Vandal** changes the **browser's reality**. It strips click listeners, shifts UI elements, and sabotages form state *while the test is running*.

---

## Vandal v0.2.0: What's New?

We've listened to the community and packed the v0.2.0 release with "world-class" features designed for high-scale enterprise apps.

### 1. Persistent Chaos (Navigation Survival) ⚓
The biggest challenge with UI mutation is navigation. Traditional scripts disappear on reload. Vandal v0.2.0 uses a combination of `add_init_script` and a deep `MutationObserver` to ensure your sabotages survive page reloads and transitions.

### 2. Recursive Shadow DOM Support 🕵️‍♂️
Modern apps are built with Web Components. Vandal now recursively penetrates Shadow DOM boundaries, ensuring that even elements hidden inside multiple shadow roots can be targeted and vandalized.

### 3. Automatic Revert (Live Healing) 🩹
Want to test a "broken" state and then "fix" it without reloading the page? Vandal v0.2.0 caches the original state of elements, allowing you to restore them on-the-fly with `await v.revert_mutation()`.

---

## The "Vandalism" Playbook

Vandal comes with high-impact strategies designed to mimic real-world regressions:

*   **Stealth Disable:** Sets `pointer-events: none`. The button looks perfect, but it's "dead" to user interaction.
*   **UI Shift:** Translates elements by 100px. Perfect for testing if your automation relies on hardcoded coordinates or if layout shifts break your assertions.
*   **Slow Load:** Simulates a 5-second UI hang by hiding elements temporarily. Does your test wait properly, or does it time out?
*   **Data Sabotage:** Replaces critical labels and input values with junk data to verify your data-validation logic.

---

## Pro Usage: The Resilience Fixture

Integrating Vandal into your framework (like Pytest) makes it a seamless part of your developer experience.

```python
from vandal import Vandal

async def test_critical_path(page):
    async with Vandal(page) as v:
        # 1. Apply a persistent mutation
        await v.apply_mutation("stealth_disable", "#checkout-btn")
        
        # 2. Navigate - The mutation survives!
        await page.goto("https://myapp.com/cart")
        
        # 3. This SHOULD fail if your test is resilient
        try:
            await page.click("#checkout-btn", timeout=2000)
            print("🧟 MUTANT SURVIVED: Test is a Zombie!")
        except:
            print("💀 MUTANT KILLED: Test is Robust.")

    # Generate a beautiful HTML report
    v.save_report("ci_resilience_report.html")
```

---

## Reporting: From Console to HTML 📊

Vandal v0.2.0 now exports structured **JSON** and beautiful **HTML reports**. No more digging through console logs. You get a visual scorecard of your test suite's effectiveness, ready for your CI/CD dashboard.

---

## High-Impact Use Cases

1.  **CI/CD Gatekeeping:** Fail builds where more than 10% of UI mutants survive.
2.  **Shadow DOM Validation:** Finally test those elusive Web Components with confidence.
3.  **Assertion Benchmarking:** Quantify the "Kill Ratio" of your automation suite.

---

## Join the Vandalism Movement

Stop counting lines of code coverage. Start measuring **assertion effectiveness**. 

**Project Vandal** is the tool that makes "green checkmarks" mean something again. 

---
> [!NOTE]
> *Project Vandal is an open-source research initiative by [Dhiraj Das | Automation Architect](https://www.dhirajdas.dev).*
