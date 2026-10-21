# Automatic runner report, version 1

`pytest --vandal` writes UTF-8 `vandal_report.json` and a sibling HTML file.
`--vandal-report=path.json` changes their location. Colliding `.html` destinations
are rejected before tests run. The formal
[JSON Schema](report-schema.json) validates the report. This format is separate
from the existing manual `Vandal.save_report()` list format, which is unchanged.

The root object contains:

| Field | Meaning |
| --- | --- |
| `schema_version` | Integer `1`. Incompatible changes require a new version. |
| `summary` | Overall outcome counts and percentage strength. |
| `tests` | Tests in selected pytest collection order, including failed/skipped baselines. |
| `execution` | Optional MCP metadata, currently `exit_code` from pytest. |
| `timed_out` | Optional MCP boolean. True means only completed candidates are reported. |

Each test contains `nodeid` (including parametrization), `baseline` (`passed`,
`baseline failing`, or `skipped`), `targets` (ordered selectors), `mutants`, and
`summary`. Optional `skipped_by_cap` counts candidate mutants omitted by the cap. Tests not reached because of pytest early stopping appear as skipped.

Each mutant contains `strategy`, `selector`, `status`, `hint`, and `details`.
Optional `kill_reason` is `assertion` or `action_failed` on a killed mutant. Older
reports may omit it; consumers must not assume an omitted reason is an assertion.
The optional `controls` object records unmutated replay outcomes: `before` is
`passed` or `error`; `after` is `passed`, `error`, or `not_run`. The second control
runs only for a possible kill. These optional fields keep version 1 compatible
with earlier reports.
Hints describe observed Playwright assertion order and remain review hypotheses;
Python assert statements are not traced.
Details may include a truncated pytest failure message; do not publish reports
containing private test data.

| Status | Meaning |
| --- | --- |
| `killed` | Confirmed injection, clean setup/teardown, an AssertionError or Playwright Error/TimeoutError in the test call, and passing unmutated controls before and after. |
| `survived` | Confirmed injection, all three phases passed, worker exited successfully. |
| `error` | Failed unmutated control, injection error, setup/teardown failure, worker deadline, other infrastructure exception, failure before confirmed injection, incomplete worker, or abnormal exit. |
| `not_applied` | A passing worker with no matching element confirmed mutated during the test call. |
| `skipped` | The mutant call was skipped or treated as an expected failure. |

Every summary has integer counts for the five statuses and `score`.
The score is `100 * killed / (killed + survived)`, with no rounding in JSON.
It is `null` if the denominator is zero. Baseline failures produce no mutants.
The HTML and terminal round scores to one decimal place.

Consumers should check the version, tolerate new optional fields within version 1,
and inspect excluded outcomes before comparing scores. Baseline failures retain
pytest status. Mutant errors fail only with --vandal-strict; they never enter the
score denominator. A score threshold also fails if there are no scored mutants.
When Vandal changes the exit status, a clear reason line names the strict-error
or threshold condition. A timed_out report is partial even if its score is high.
The companion HTML labels this state as an incomplete run and explains that its
strength covers completed mutants only.
