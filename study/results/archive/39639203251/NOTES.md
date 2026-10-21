# Pilot 39639203251: retained evidence and static interpretation

[Run](https://github.com/godhiraj-code/vandal/actions/runs/39639203251), attempt 1,
at `8fd62837499a78f0498b1e8900f11af0ed84d7cf`. The downloaded artifact
`study-pilot-39639203251` (ID 12363714678) is 42,826 bytes, SHA-256
`22559d9fe1521d9bed8fa7c97696182c618c499ea54833d34d5188f251fdb9dc`.
All 42 extracted files (227,647 bytes) are unchanged under `artifact/` with their
original relative paths. `ARTIFACT_MANIFEST.json` records every file hash; all 35
internal status hash references also matched. The artifact's old reports and
worker statuses remain historical evidence, including their original formatting.
The repository-level REPORT.md and PILOT_SUMMARY.md are newly derived summaries.
No public code was executed while retaining or interpreting this artifact.

Retained location: `study/results/archive/39639203251/`. The live results scan and
workflow upload of `study/results/public/**` exclude this archive. Reproduce its
historical public report with `python -m study.summarize --archive-run 39639203251`;
this selects the archived public attempts instead of fresh live attempts. Original
paths inside `artifact/` and its manifest are preserved as downloaded evidence.

## Contrail: excluded baseline

At `2465e368b7658bd23f0d41f1473c114db3573005`, the baseline recorded **14 passed,
1 failed**. `test_the_ranking_dialog_opens_and_closes` failed reading `.data` from
an undefined chart. No mutation score is available. The test checks that the
dialog is visible, then immediately evaluates `Chart.getChart(...).data.labels`
([test lines 157–162](https://github.com/atdr/contrail/blob/2465e368b7658bd23f0d41f1473c114db3573005/tests_browser/test_passport_page.py#L157)).
The chart is created inside `requestAnimationFrame`, after the dialog is opened
([passport.js lines 695–696](https://github.com/atdr/contrail/blob/2465e368b7658bd23f0d41f1473c114db3573005/src/contrail/passport/passport.js#L695)).
Thus the baseline reads before the scheduled chart render; this source-level race
explains the observed failure. It was not rerun, patched, or counted as a mutant kill.

## Platelet-Movie: one valid repository, 59 scored mutants

At `14664611814b126289f291ad24ee294102efb07c`, all **8 baseline tests passed**;
mutation outcomes were **30 killed, 29 survived, 0 errors**. The unchanged score is
`100 * 30 / 59 = 50.847457627118644%` (displayed as **50.8%**). This is a
per-test mutation measure, not a count of defects surviving the entire suite.

Static reconciliation of all 29 survivors:

| Category | n mutants | Interpretation |
|---|---:|---|
| Logic sabotage of toggle, toggle-back test | 1 | Real test-local gap: two blocked clicks leave the initial state intact, which is the only state asserted. Assert the intermediate minutes-only state. |
| Logic sabotage of toggle, conversion test | 1 | Real test-local gap: hidden minute fields already contain 90/160, so reading those values does not prove a mode switch or conversion. Check mode/visibility and non-default values. |
| Data sabotage of four filter-group containers across four visibility tests | 16 | Scope/oracle mismatch: text mutation does not change the visibility property these tests guard. These are not 16 demonstrated behavioral defects. |
| Data sabotage of toggle label across eight tests | 8 | Label text is unasserted. Fixture discovery waits for the toggle in every test, including tests with no toggle interaction. This broadens mutation scope beyond each test's intended behavior. |
| Data sabotage of validation inputs | 3 | Scenario-equivalent predicate: clearing either already-zero minutes field still parses as zero; clearing max-hours from 1 to zero still leaves minimum 5 hours greater than maximum. Not globally equivalent mutants. |

Source evidence: [selected tests](https://github.com/tegataiprime/Platelet-Movie/blob/14664611814b126289f291ad24ee294102efb07c/tests/ui/test_runtime_filter_toggle.py),
[fixture](https://github.com/tegataiprime/Platelet-Movie/blob/14664611814b126289f291ad24ee294102efb07c/tests/ui/conftest.py),
[initial values](https://github.com/tegataiprime/Platelet-Movie/blob/14664611814b126289f291ad24ee294102efb07c/site/index.html),
and [application logic](https://github.com/tegataiprime/Platelet-Movie/blob/14664611814b126289f291ad24ee294102efb07c/site/app.js).
Other tests kill the blocked-toggle mutant, so the two gaps above are not evidence
that this behavioral defect survives the whole suite. These are review notes, not
changes to the target repository.

All 29 raw survivor records say the mutation was confirmed and the test passed;
the before control passed and the after control is `not_run`. Post-controls are
only run after candidate kills. No survivor DOM snapshots or value traces were
archived. The classifications above are static explanations, not replay proof;
they do not alter any status, score, or aggregate. One valid repository is too
small for median, IQR, range, strategy rates, or population conclusions.
