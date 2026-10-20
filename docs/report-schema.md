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

Each test contains `nodeid` (including parametrization), `baseline` (`passed`,
`baseline failing`, or `skipped`), `targets` (ordered selectors), `mutants`, and
`summary`. Tests not reached because of pytest early stopping appear as skipped.

Each mutant contains `strategy`, `selector`, `status`, `hint`, and `details`.
The optional `controls` object records unmutated replay outcomes: `before` is
`passed` or `error`; `after` is `passed`, `error`, or `not_run`. The second control
runs only for a possible kill. These optional fields keep version 1 compatible
with earlier reports.
Hints are hypotheses for review, never a claim that an assertion is absent.
Details may include a truncated pytest failure message; do not publish reports
containing private test data.

| Status | Meaning |
| --- | --- |
| `killed` | Confirmed injection, clean setup/teardown, an AssertionError in the test call, and passing unmutated controls before and after. |
| `survived` | Confirmed injection, all three phases passed, worker exited successfully. |
| `error` | Failed unmutated control, injection error, setup/teardown failure, timeout, browser/infrastructure exception, failure before confirmed injection, incomplete worker, or abnormal exit. |
| `not_applied` | A passing worker with no matching element confirmed mutated during the test call. |
| `skipped` | The mutant call was skipped or treated as an expected failure. |

Every summary has integer counts for the five statuses and `score`.
The score is `100 * killed / (killed + survived)`, with no rounding in JSON.
It is `null` if the denominator is zero. Baseline failures produce no mutants.
The HTML and terminal round scores to one decimal place.

Consumers should check the version, tolerate new optional fields within version 1,
and inspect excluded outcomes before comparing scores. Baseline failures and worker
errors fail pytest. A score threshold also fails if there are no scored mutants.
