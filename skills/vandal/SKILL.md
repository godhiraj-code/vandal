---
name: vandal
description: Measure whether Python Playwright tests detect injected UI faults and improve meaningful assertions.
---

# Vandal assertion improvement loop

Use this skill in a trusted pytest + Playwright checkout. Tests execute project
code and may change application data. Use an isolated test environment.

1. Read the project's test instructions. Install `project-vandal` and the project's
   test dependencies, then `playwright install chromium`.
2. Run a focused baseline and mutation pass:
   `pytest tests/test_login.py --vandal --vandal-strategies=logic_sabotage,data_sabotage --vandal-max-mutants=10 --vandal-timeout=60`.
3. Read `vandal_report.json` (schema version 1). Fix baseline failures first.
   Check `error`, `not_applied`, and `skipped` counts before interpreting strength.
   These outcomes do not contribute to the score. A null score means no scored mutants.
4. Inspect each `survived` mutant and its hint. Survival is evidence to investigate,
   not proof that an assertion is missing. A shifted element can legitimately work;
   an injected fault can be irrelevant to the intended test contract. Data
   sabotage is refreshed at later observed reads and assertions.
5. Read the test and application contract. Add assertions for meaningful user-visible
   outcomes, values, navigation, or state. Do not assert Vandal's DOM markers,
   detect worker environment variables, add arbitrary sleeps, or weaken the app.
6. Rerun the ordinary tests, then rerun Vandal with the same targets and strategies.
   Compare killed/survived counts as well as the score. Do not hide errors or remove
   difficult mutants solely to raise the score. Report any justified equivalent
   mutants and unsupported targets.
7. Summarize the changed assertions, before/after measured scores, and unresolved
   survivors. Do not invent numbers or claim the score guarantees correctness.

For MCP clients, install `project-vandal[mcp]` on Python 3.10+ and launch
`vandal-mcp` with the trusted repository as its working directory. Call
`run_vandal(test_path, strategies, max_mutants, deadline_seconds, pytest_args)` and
`get_surviving_mutants(report_path)`. The server uses stdio, allows paths only
inside its working directory, and bounds each run to 600 seconds. pytest_args
permits only -k/-m expressions and local node IDs. A deadline returns completed
mutants with timed_out=true; do not compare that partial score as a full run.
Use --vandal-strict when mutant errors should fail CI. Review kill_reason:
action_failed means a controlled Playwright call failed, while assertion means
the test's assertion failed. Default strategies are inferred from observed use;
explicit strategies are preferable for a stable before/after comparison.
