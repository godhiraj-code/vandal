# Study protocol and results (no public runs yet)

Public agent-suite sample: n=0 repositories. Public attempts: n=0.

This is a descriptive study of agent-written suites only. No comparison population or causal claim is defined.

Completed owned-fixture validations: n=6 attempts of one fixture; not study subjects. Earlier failed fixture attempts are retained in [FIXTURE_ATTEMPTS.md](FIXTURE_ATTEMPTS.md).

Results are limited to the repositories and selected tests actually executed. No population or causal inference is justified.

## Per repository

Counts below are observed mutants, with n_tests and n_mutants shown per row. Score is 100 × killed / n_scored; n_scored = killed + survived. N/A means no observation, not zero.

| Repository / kind / group | Status | Score % (n_scored) | n_tests / n_mutants | Killed | Survived | Error | Untested mutants | Unsupported targets | Cap omissions |
|---|---|---|---|---|---|---|---|---|---|
| owned-local-fixture / fixture / fixture | completed | 80.0000 (n=5) | 2 / 5 | 4 | 1 | 0 | 0 | 0 | 0 |
| owned-local-fixture / fixture / fixture | completed | 80.0000 (n=5) | 2 / 5 | 4 | 1 | 0 | 0 | 0 | 0 |
| owned-local-fixture / fixture / fixture | completed | 80.0000 (n=5) | 2 / 5 | 4 | 1 | 0 | 0 | 0 | 0 |
| owned-local-fixture / fixture / fixture | completed | 80.0000 (n=5) | 2 / 5 | 4 | 1 | 0 | 0 | 0 | 0 |
| owned-local-fixture / fixture / fixture | completed | 80.0000 (n=5) | 2 / 5 | 4 | 1 | 0 | 0 | 0 | 0 |
| owned-local-fixture / fixture / fixture | completed | 80.0000 (n=5) | 2 / 5 | 4 | 1 | 0 | 0 | 0 | 0 |

Untested mutants = not_applied + skipped. Unsupported targets and cap omissions are separate units and are not added to that count or score denominator.

## Descriptive agent-suite results

One complete, scored observation per repository; repository-weighted median, inclusive-quartile IQR and min-max spread. Guidance-only provenance, incomplete runs, invalid reports and owned fixtures are excluded. IQR is N/A below two repositories.

| n repositories | Median % | IQR percentage points | Min-max % |
|---|---|---|---|
| 0 | N/A | N/A | N/A-N/A |

No eligible public results exist. No strength estimate is reported for agent-written suites.

## Strategy survival

Pooled by mutant, ranked by survivors; larger suites contribute more weight. Survival rate is among killed + survived. Both n_repos and n_mutants are shown. Error/untested outcomes remain outside the rate.

| Strategy | n_repos | n_mutants | Survived / n scored | Survival % | Errors | Untested mutants |
|---|---|---|---|---|---|---|

No eligible strategy observations (n repositories=0).

## Exclusions and limitations

- owned-local-fixture: owned fixture excluded (n runs=1).
- owned-local-fixture: owned fixture excluded (n runs=1).
- owned-local-fixture: owned fixture excluded (n runs=1).
- owned-local-fixture: owned fixture excluded (n runs=1).
- owned-local-fixture: owned fixture excluded (n runs=1).
- owned-local-fixture: owned fixture excluded (n runs=1).

Selection is a convenience sample from bounded GitHub search, not a random sample. Visible co-authorship is evidence of agent involvement, not exclusive agent authorship. Only test-specific agent involvement is in scope; guidance alone cannot establish authorship.

Offline, no-secret execution selects for self-contained suites; external CDNs, services and complex install requirements can cause exclusions. All-skip and partially skipped baselines are excluded. A single baseline cannot establish lack of flakiness.

Default Vandal strategies and its per-test cap depend on observed interactions. Scores across different apps, assertions, targets and strategy mixes are not directly comparable. Controlled action failures count as kills and need not imply an outcome assertion. Mutant errors remain visible but outside the score denominator.

Candidate processes can tamper with their own in-container reports. Stored hashes detect later changes, not dishonest execution. Independently inspect raw logs and source before publication. No claim that container isolation or its Docker integration has been validated follows from a host-only fixture test.
