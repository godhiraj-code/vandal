# We ran mutation testing on AI written Playwright test suites

Study protocol and observed results. This title is a research question, not evidence that a public pilot ran.

Recorded runs: n=3. Public runs: n=0. Owned fixture runs: n=3. Fixtures never enter the study comparison.

Results are limited to the repositories and selected tests actually executed. No population or causal inference is justified.

## Per repository

Counts below are observed mutants, with n_tests and n_mutants shown per row. Score is 100 × killed / n_scored; n_scored = killed + survived. N/A means no observation, not zero.

| Repository / kind / group | Status | Score % (n_scored) | n_tests / n_mutants | Killed | Survived | Error | Untested mutants | Unsupported targets | Cap omissions |
|---|---|---|---|---|---|---|---|---|---|
| owned-local-fixture / fixture / fixture | skipped | N/A (n=N/A) | N/A / N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| owned-local-fixture / fixture / fixture | completed | 80.0000 (n=5) | 2 / 5 | 4 | 1 | 0 | 0 | 0 | 0 |
| owned-local-fixture / fixture / fixture | unscored | N/A (n=0) | 2 / 5 | 0 | 0 | 5 | 0 | 0 | 0 |

Untested mutants = not_applied + skipped. Unsupported targets and cap omissions are separate units and are not added to that count or score denominator.

## Agent versus human comparison

One complete, scored observation per repository; repository-weighted median, inclusive-quartile IQR and min–max spread. Guidance-only provenance, incomplete runs, invalid reports and fixtures are excluded.

| Group | n repositories | Median % | IQR percentage points | Min–max % |
|---|---|---|---|---|
| agent | 0 | N/A | N/A | N/A–N/A |
| human | 0 | N/A | N/A | N/A–N/A |

No between-group difference can be calculated: at least one group has no eligible observations.

## Strategy survival

Ranked by survivors, with survival rate among killed + survived and repository sample sizes. Error/untested outcomes remain outside the rate.

| Group / strategy | n repos | Survived / n scored | Survival % | Errors | Untested mutants |
|---|---|---|---|---|---|

No eligible strategy observations (n repositories=0).

## Exclusions and limitations

- owned-local-fixture: baseline timeout (n runs=1).
- owned-local-fixture: owned fixture excluded (n runs=1).
- owned-local-fixture: no killed/survived mutants (n runs=1).

Selection is a convenience sample from bounded GitHub search, not a random sample. Visible co-authorship is evidence of agent involvement, not exclusive agent authorship. Human provenance requires affirmative evidence; missing agent labels prove nothing.

Offline, no-secret execution selects for self-contained suites; external CDNs, services and complex install requirements can cause exclusions. All-skip and partially skipped baselines are excluded. A single baseline cannot establish lack of flakiness.

Default Vandal strategies and its per-test cap depend on observed interactions. Scores across different apps, assertions, targets and strategy mixes are not directly comparable. Controlled action failures count as kills and need not imply an outcome assertion. Mutant errors remain visible but outside the score denominator.

Candidate processes can tamper with their own in-container reports. Stored hashes detect later changes, not dishonest execution. Independently inspect raw logs and source before publication. No claim that container isolation or its Docker integration has been validated follows from a host-only fixture test.
