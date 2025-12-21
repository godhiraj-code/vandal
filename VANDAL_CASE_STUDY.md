# Case Study: Eliminating "Zombie Tests" with Project Vandal
**Author:** Dhiraj Das | Automation Architect

## Project Context
Project Vandal is a runtime UI mutation testing engine built with Python and Playwright. It is designed to sabotage the live DOM during test execution to verify that automation suites are truly capable of detecting regressions. Unlike traditional tools that modify source code, Vandal injects deterministic "vandalism" scripts into the browser context to simulate high-impact UI failures on-the-fly.

## Key Objectives
- **Verify Assertion Sensitivity:** Ensure that tests fail when the UI is broken.
- **Quantify Test Quality:** Provide a "Kill Ratio" metric to identify weak automation scripts.
- **Zero-Rebuild Mutation:** Enable high-speed testing without modifying or rebuilding the application source.
- **Shadow DOM Resiliency:** Target modern web components that are often invisible to standard testing tools.
- **CI/CD Integration:** Automated reporting for continuous quality gatekeeping.

## Stakeholders/Users
- **SDETs & Automation Engineers:** Scaling test suites while ensuring multi-environment robustness.
- **QA Managers:** Quantifying the ROI of automation and identifying "green-washing" in test reports.
- **Frontend Developers:** Ensuring that UI changes are adequately covered by unit and E2E tests.

## Technical Background
- **Engine:** Playwright (Python wrapper).
- **Distribution:** Hosted on PyPI as `project-vandal`.
- **Core logic:** Async JavaScript injection via the Chrome DevTools Protocol (CDP) bridge.
- **Key Techniques:** Deep `MutationObserver` for persistence, monkey-patching `attachShadow` for Web Components, and data-attribute caching for non-destructive reverts.

---

## 1. Problem
### The "Zombie Test" Phenomenon
The largest risk in modern automation is not a failing test, but a **passing test that should have failed**. 

Engineering teams often optimize for **Code Coverage**, assuming that if a line of code is executed, it is "tested." This leads to an inefficiency where test suites remain green even if the application's visual or logic layer is sabotaged. Existing approaches, like source-code mutation (e.g., Stryker), were insufficient for UIs because:
- **Speed:** Rebuilding large frontend bundles for every mutation is too slow for E2E cycles.
- **Scope:** They focus on logic branches in the code but ignore how those branches manifest in the DOM (e.g., a button that is logic-active but visually unclickable).

**Risks:** High maintenance costs for "green-washed" suites that fail to catch production bugs, leading to a false sense of security and ultimate deployment failures.

---

## 2. Challenges
### Technical & Operational Constraints
- **Navigation Survival:** Standard JS injections are wiped the moment a page navigates or reloads. Ensuring a "vandalized" state persists across a user journey was a significant technical hurdle.
- **Shadow DOM Isolation:** Modern frameworks (Lit, Salesforce LWC) hide elements inside Shadow Roots. Traditional `document.querySelectorAll` cannot see these elements, leaving them immune to mutation.
- **Non-Destructive Sabotage:** In a multi-test suite, mutations must be reversible to avoid "test pollution," where one failing mutant breaks all subsequent tests.
- **Zero Configuration:** The solution needed to be a "drop-in" wrapper that required no changes to the application under test (AUT).

---

## 3. Solution
### The Architecture of Chaos
The approach involved creating a deterministic "Vandal Engine" that sits between the test script and the browser.

#### Step-by-Step Approach:
1. **The Context Manager:** Implemented an `async with` context manager in Python that automatically wraps a Playwright `page` object.
2. **Deep Selection Engine:** Developed a recursive `DEEP_SELECT` JavaScript helper that penetrates all levels of Shadow DOM to find targets.
3. **Persistence Mechanism:** Leveraged `page.add_init_script` combined with a specialized `MutationObserver` and an `attachShadow` monkey-patch. This ensures that even if an element is created 10 seconds after a navigation, it is immediately vandalized.
4. **State Caching:** Before mutating (e.g., changing text or disabling pointer-events), the engine caches original values in `data-vandal-original-*` attributes, enabling a 1-click **Automatic Revert**.

#### Tools Used:
- **Playwright:** For orchestration and CDP interaction.
- **MutationObserver API:** for DOM resilience.
- **JSON/HTML Template Engine:** For persistent reporting.

---

## 4. Outcome/Impact
### Quantifiable Quality Gains
Project Vandal transformed how we viewed test success:
- **Kill Ratio Visibility:** We could suddenly see that ~15% of tests in a sample suite were "Zombies"—they passed even when the primary "Submit" button was invisibly disabled.
- **Speed to Feedback:** Mutations occur in **<20ms**, meaning a full mutation suite can run in parallel with standard E2E tests without significant overhead.
- **Shadow DOM Coverage:** Achieved 100% targetability of elements inside Shadow Roots, a feat previously requiring manual, brittle CSS selectors.
- **Stability:** By implementing the Audit-Mode (Automatic Revert), we reduced test environment downtime caused by stale mutations to zero.

---

## Summary
Project Vandal v0.2.0 is a world-class UI mutation testing tool that solves the "Zombie Test" problem by bringing deterministic chaos to the browser runtime. By combining deep Shadow DOM penetration with intelligent navigation survival and automated reporting, Vandal empowers engineering teams to build automation suites that are not just green, but **resilient**. It moves the quality focus from simple "Execution Coverage" to "Assertion Effectiveness."
