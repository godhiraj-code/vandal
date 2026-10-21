# Study protocol and results

Public agent-suite sample: n=1 repositories. Public attempts: n=2.

This is a descriptive study of agent-written suites only. No comparison population or causal claim is defined.

Completed owned-fixture validations: n=6 attempts of one fixture; not study subjects. Earlier failed fixture attempts are retained in [FIXTURE_ATTEMPTS.md](FIXTURE_ATTEMPTS.md).

Results are limited to the repositories and selected tests actually executed. No population or causal inference is justified.

## Per repository

Counts below are observed mutants, with n_tests and n_mutants shown per row. Score is 100 × killed / n_scored; n_scored = killed + survived. N/A means no observation, not zero.


### Public repositories (n=2 runs)

| Repository / artifact directory / pinned SHA | Status | Score % (n_scored) | n_tests / n_mutants | Killed | Survived | Error | Untested mutants | Unsupported targets | Cap omissions |
|---|---|---|---|---|---|---|---|---|---|
| atdr/contrail / public/atdr__contrail__2465e368b765 / 2465e368b7658bd23f0d41f1473c114db3573005  | skipped | N/A (n=N/A) | N/A / N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| tegataiprime/Platelet-Movie / public/tegataiprime__Platelet-Movie__14664611814b / 14664611814b126289f291ad24ee294102efb07c  | completed | 40.0000 (n=35) | 8 / 59 | 14 | 21 | 24 | 0 | 0 | 0 |

### Host-only owned fixture validation (n=1 runs)

| Repository / artifact directory / pinned SHA | Status | Score % (n_scored) | n_tests / n_mutants | Killed | Survived | Error | Untested mutants | Unsupported targets | Cap omissions |
|---|---|---|---|---|---|---|---|---|---|
| owned-local-fixture / pilot/owned-fixture-corrected / e886c215ebb550c2e26780008c42ea7e87560e9f  | completed | 80.0000 (n=5) | 2 / 5 | 4 | 1 | 0 | 0 | 0 | 0 |

### Container owned fixture validation (n=5 runs)

| Repository / artifact directory / pinned SHA | Status | Score % (n_scored) | n_tests / n_mutants | Killed | Survived | Error | Untested mutants | Unsupported targets | Cap omissions |
|---|---|---|---|---|---|---|---|---|---|
| owned-local-fixture / pilot/owned-container-06 / d5cbb81a67350c6c228bf517e66af24ebc5fec78  | completed | 80.0000 (n=5) | 2 / 5 | 4 | 1 | 0 | 0 | 0 | 0 |
| owned-local-fixture / pilot/owned-container-07 / 2ca7cfe098fa65b0e123ba7c2f78bb888d36a9da  | completed | 80.0000 (n=5) | 2 / 5 | 4 | 1 | 0 | 0 | 0 | 0 |
| owned-local-fixture / pilot/owned-container-08 / c34637afac674437101cf90b7a67423c86fc8732 (repeat runs at this SHA: n=3) | completed | 80.0000 (n=5) | 2 / 5 | 4 | 1 | 0 | 0 | 0 | 0 |
| owned-local-fixture / pilot/owned-container-09 / c34637afac674437101cf90b7a67423c86fc8732 (repeat runs at this SHA: n=3) | completed | 80.0000 (n=5) | 2 / 5 | 4 | 1 | 0 | 0 | 0 | 0 |
| owned-local-fixture / pilot/owned-container-10 / c34637afac674437101cf90b7a67423c86fc8732 (repeat runs at this SHA: n=3) | completed | 80.0000 (n=5) | 2 / 5 | 4 | 1 | 0 | 0 | 0 | 0 |

Untested mutants = not_applied + skipped. Unsupported targets and cap omissions are separate units and are not added to that count or score denominator.

## Descriptive agent-suite results

One complete, scored observation per repository; repository-weighted median, inclusive-quartile IQR and min-max spread. Guidance-only provenance, incomplete runs, invalid reports and owned fixtures are excluded. IQR is N/A below two repositories.

| n repositories | Median % | IQR percentage points | Min-max % |
|---|---|---|---|
| 1 | 40.0000 | N/A | 40.0000-40.0000 |

## Strategy survival

Pooled by mutant, ranked by survivors; larger suites contribute more weight. Survival rate is among killed + survived. Both n_repos and n_mutants are shown. Error/untested outcomes remain outside the rate.

| Strategy | n_repos | n_mutants | Survived / n scored | Survival % | Errors | Untested mutants |
|---|---|---|---|---|---|---|
| data_sabotage | 1 | 38 | 20 / 25 | 80.0000 | 13 | 0 |
| logic_sabotage | 1 | 7 | 1 / 3 | 33.3333 | 4 | 0 |
| ghost_element | 1 | 7 | 0 / 3 | 0.0000 | 4 | 0 |
| stealth_disable | 1 | 7 | 0 / 4 | 0.0000 | 3 | 0 |

## Exclusions and limitations

- owned-local-fixture: owned fixture excluded (n runs=1).
- owned-local-fixture: owned fixture excluded (n runs=1).
- owned-local-fixture: owned fixture excluded (n runs=1).
- owned-local-fixture: owned fixture excluded (n runs=1).
- owned-local-fixture: owned fixture excluded (n runs=1).
- owned-local-fixture: owned fixture excluded (n runs=1).
- atdr/contrail: ValueError: archive contains duplicate or nonregular entry (n runs=1).

Selection is a convenience sample from bounded GitHub search, not a random sample. Visible co-authorship is evidence of agent involvement, not exclusive agent authorship. Only test-specific agent involvement is in scope; guidance alone cannot establish authorship.

Offline, no-secret execution selects for self-contained suites; external CDNs, services and complex install requirements can cause exclusions. All-skip and partially skipped baselines are excluded. A single baseline cannot establish lack of flakiness.

Default Vandal strategies and its per-test cap depend on observed interactions. Scores across different apps, assertions, targets and strategy mixes are not directly comparable. Controlled action failures count as kills and need not imply an outcome assertion. Mutant errors remain visible but outside the score denominator.

Candidate processes can tamper with their own in-container reports. Stored hashes detect later changes, not dishonest execution. Independently inspect raw logs and source before publication. The host-only validation row exercises the owned baseline and mutation run without a container. The separately labelled container rows exercise the Docker harness; repeated runs of the same fixture are not independent study subjects. Neither category is a public repository result.
