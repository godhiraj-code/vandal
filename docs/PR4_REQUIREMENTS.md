# PR 4 revision evidence

This checklist covers the twelve requested follow-up changes. Version stays 0.2.1;
only CHANGELOG Unreleased changes. Existing manual async behavior is retained.

| Requirement | Implementation | Evidence |
| --- | --- | --- |
| 1 Controlled Playwright call failures | classify, before/after controls, kill_reason | test_revision controlled browser kills; existing worker error/deadline tests |
| 2 Opt-in strict errors and reasons | --vandal-strict, threshold reason line | strict/default regressions and score gate tests |
| 3 Standard package | vandal/ modules, setuptools packages, root demo | editable install; full root pytest; root demo and examples |
| 4 Discovery on use | factory wrappers removed | sync/async unused locator regression |
| 5 Usage-based defaults | candidates infers action/read strategies | planning regression and measured default example |
| 6 Reapply data sabotage | target resolution refreshes data strategy | sync/async click-then-output-assertion regression |
| 7 Interleaved cap | round-robin target candidates, skipped_by_cap | planning and real cap report regression |
| 8 Reporter isolation | worker log/html/allure destinations, no-cov and isolated coverage env | built-in logs via CLI/ini/addopts/environment; real pytest-html; existing JUnit/trace preservation |
| 9 Compatibility checks | configure validates hooks; Playwright >=1.60,<2 | missing-hook configure regression |
| 10 Bounded MCP partial reports | atomic checkpoints, deadline_seconds, restricted pytest_args, incomplete HTML notice | real deadline checkpoint and HTML tests, validation tests and stdio suite |
| 11 Counts and ordered hints | readable summary and observed assertion trace | real terminal/hint regression |
| 12 Direct checkout/platform CI | Linux full suite, Windows/macOS smoke, both score checks | workflow plus actual hosted results recorded in PR |

## Local validation

Runtime commit `581ee2f179b539a94adfc5418243a8f42e24c39e` passed these checks
on Windows with headless Chromium:

- Editable install, plain `python -m pytest -q` from the checkout: 144 passed
  in 692.97 seconds on Python 3.13 / Playwright 1.64.
- Python 3.9 / Playwright 1.60: 29 new regressions plus the legacy test, 30 passed.
- Clean wheel: exactly eight intended modules, matching source bytes; isolated
  installed-package import, pip check, 16 reporting/legacy tests passed.
- `python demo_vandal.py --headless`: passed after editable installation.
- `python -m pytest examples/test_strength.py --vandal --vandal-strategies=logic_sabotage`:
  weak 0%, strong 100%, overall 50%, no mutant errors, exit 0.
- `python -m pytest examples/test_strength.py --vandal`:
  weak 66.66666666666667%, strong 100%, overall 83.33333333333333%,
  no mutant errors, exit 0.

The higher default weak score follows the requested controlled-action-failure
classification: blocked clicks kill mutants even without an outcome assertion.
These measurements are examples, not benchmark or universal quality claims.

Exact command vectors and logs are retained in the task's pr4-revision evidence
folder. Independent review and hosted Linux/Windows/macOS CI results are recorded
in PR #4; local checks alone do not certify those hosted environments.

## Reporter repair validation

Runtime commit `15c8d9aed589e7c0e1b61a189e5ddbf41c8fe31d` fixes baseline log
overwrites and missing incomplete-run context in deadline HTML. All four log
configuration origins and the partial HTML regression failed before the fix.

- Full headless checkout suite: 150 passed in 732.76 seconds on Python 3.13.7,
  Playwright 1.64.0 and pytest 9.1.1.
- Focused reporting/revision suite: 50 passed. Python 3.9.25 / Playwright 1.60.0:
  25 affected tests passed, including all four controlled-action browser cases.
- Isolated installed wheel: eight modules match source bytes; 18 reporting/legacy
  tests passed with site-packages imports verified. An initial check from the
  workspace root imported the preserved older checkout and is excluded.
- Root legacy demo passed. Logic-only examples again measured weak 0%, strong
  100%, overall 50%; defaults measured weak 66.66666666666667%, strong 100%,
  overall 83.33333333333333%. Both exited 0 with no mutant errors.
- Independent installed-wheel repair review: 56 focused tests passed on Python
  3.13, 10 on Python 3.9, plus exact log and real MCP reproductions, visible HTML
  rendering, schema and source-byte checks. Both report-safety findings closed.

The independent prior full suite remains evidence for its own earlier commit,
not a second full run of this repair. Final repair command vectors and logs are
retained in the task's pr4-reporter-repair folder. The checklist-only successor
changes no runtime or tests. Hosted results are recorded separately in PR #4.
