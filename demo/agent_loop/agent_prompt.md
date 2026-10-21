# Prompt for a real agent run

```text
Improve demo/agent_loop/test_weak.py in this trusted checkout. It exercises the
local Corner Shop checkout: entering Ada and placing an order must preserve the
pickup name and show "Thanks, Ada! Your coffee total is $4.00.".

Run the ordinary test first, then:
python -m pytest demo/agent_loop/test_weak.py --vandal --vandal-strict --vandal-max-mutants=20 --vandal-timeout=30 --vandal-min-score=100

Read vandal_report.json. Check the passing baseline, complete candidate set,
and error/not_applied/skipped counts before interpreting its measured score.
Inspect every survived mutant's strategy, selector and hint (or use the MCP
get_surviving_mutants tool on the report). Add meaningful assertions for the
user-visible outcomes implicated by the survivors. Do not change the app,
remove targets, reduce the mutant cap, inspect Vandal markers/environment, or
skip tests to raise the score. Keep the default strategy selection unchanged.

Rerun the ordinary test and the exact mutation command until the score passes
--vandal-min-score=100. If a failure cannot be fixed with honest outcome
assertions, explain it instead of hiding it. Report the actual before/after
scores, killed/survived counts, remaining survivors, and any incomplete coverage.
```

The recorded demo runs the committed weak and fixed examples. It does not send
this prompt to an agent or edit a test at runtime. To perform a live loop, give
the prompt above to your coding agent in a disposable checkout.
