# Study protocol (no valid public results)

Public agent-suite sample: n=0 repositories. Included public attempts: n=0.

Diagnostic archives are omitted from all tables and sample sizes; see results/diagnostic/ for failed-pilot evidence.

This is a descriptive study of agent-written suites only. No comparison population or causal claim is defined.

Completed owned-fixture validations: n=6 attempts of one fixture; not study subjects. Earlier failed fixture attempts are retained in [FIXTURE_ATTEMPTS.md](FIXTURE_ATTEMPTS.md).

Results are limited to the repositories and selected tests actually executed. No population or causal inference is justified.

## Per repository

Counts below are observed mutants, with n_tests and n_mutants shown per row. Score is 100 × killed / n_scored; n_scored = killed + survived. Error rate is 100 x errors / all mutants. Runs above 10% errors are invalid and have no score. N/A means no observation, not zero.


### Public repositories (n=0 runs)

| Repository / artifact directory / pinned SHA | Status | Score % (n_scored) | n_tests / n_mutants | Killed | Survived | Error | Error % | Untested mutants | Unsupported targets | Cap omissions |
|---|---|---|---|---|---|---|---|---|---|---|

### Host-only owned fixture validation (n=1 runs)

| Repository / artifact directory / pinned SHA | Status | Score % (n_scored) | n_tests / n_mutants | Killed | Survived | Error | Error % | Untested mutants | Unsupported targets | Cap omissions |
|---|---|---|---|---|---|---|---|---|---|---|
| owned-local-fixture / pilot/owned-fixture-corrected / e886c215ebb550c2e26780008c42ea7e87560e9f  | completed | 80.0000 (n=5) | 2 / 5 | 4 | 1 | 0 | 0.0000 | 0 | 0 | 0 |

### Container owned fixture validation (n=5 runs)

| Repository / artifact directory / pinned SHA | Status | Score % (n_scored) | n_tests / n_mutants | Killed | Survived | Error | Error % | Untested mutants | Unsupported targets | Cap omissions |
|---|---|---|---|---|---|---|---|---|---|---|
| owned-local-fixture / pilot/owned-container-06 / d5cbb81a67350c6c228bf517e66af24ebc5fec78  | completed | 80.0000 (n=5) | 2 / 5 | 4 | 1 | 0 | 0.0000 | 0 | 0 | 0 |
| owned-local-fixture / pilot/owned-container-07 / 2ca7cfe098fa65b0e123ba7c2f78bb888d36a9da  | completed | 80.0000 (n=5) | 2 / 5 | 4 | 1 | 0 | 0.0000 | 0 | 0 | 0 |
| owned-local-fixture / pilot/owned-container-08 / c34637afac674437101cf90b7a67423c86fc8732 (repeat runs at this SHA: n=3) | completed | 80.0000 (n=5) | 2 / 5 | 4 | 1 | 0 | 0.0000 | 0 | 0 | 0 |
| owned-local-fixture / pilot/owned-container-09 / c34637afac674437101cf90b7a67423c86fc8732 (repeat runs at this SHA: n=3) | completed | 80.0000 (n=5) | 2 / 5 | 4 | 1 | 0 | 0.0000 | 0 | 0 | 0 |
| owned-local-fixture / pilot/owned-container-10 / c34637afac674437101cf90b7a67423c86fc8732 (repeat runs at this SHA: n=3) | completed | 80.0000 (n=5) | 2 / 5 | 4 | 1 | 0 | 0.0000 | 0 | 0 | 0 |

Untested mutants = not_applied + skipped. Unsupported targets and cap omissions are separate units and are not added to that count or score denominator.

## Descriptive agent-suite results

One complete, scored observation per repository; repository-weighted median, inclusive-quartile IQR and min-max spread. Guidance-only provenance, incomplete runs and invalid reports are excluded; owned fixture excluded. Median, IQR and strategy rates require at least two valid repositories.

| n repositories | Median % | IQR percentage points | Min-max % |
|---|---|---|---|
| 0 | N/A | N/A | N/A |

No eligible public results exist. No strength estimate is reported for agent-written suites.

## Strategy survival

Pooled by mutant, ranked by survivors; larger suites contribute more weight. Survival rate is among killed + survived. Both n_repos and n_mutants are shown. Error/untested outcomes remain outside the rate.

| Strategy | n_repos | n_mutants | Survived / n scored | Survival % | Errors | Untested mutants |
|---|---|---|---|---|---|---|

No eligible strategy observations (n repositories=0).

Insufficient valid repositories (n=0); no median, IQR or strategy rates are reported.

## Exclusions and limitations


Selection is a convenience sample from bounded GitHub search, not a random sample. Visible co-authorship is evidence of agent involvement, not exclusive agent authorship. Only test-specific agent involvement is in scope; guidance alone cannot establish authorship.

Offline, no-secret execution selects for self-contained suites; external CDNs, services and complex install requirements can cause exclusions. All-skip and partially skipped baselines are excluded. A single baseline cannot establish lack of flakiness.

Default Vandal strategies and its per-test cap depend on observed interactions. Scores across different apps, assertions, targets and strategy mixes are not directly comparable. Controlled action failures count as kills and need not imply an outcome assertion. Mutant errors remain visible but outside the score denominator.

Candidate processes can tamper with their own in-container reports. Stored hashes detect later changes, not dishonest execution. Independently inspect raw logs and source before publication. The host-only validation row exercises the owned baseline and mutation run without a container. The separately labelled container rows exercise the Docker harness; repeated runs of the same fixture are not independent study subjects. Neither category is a public repository result.
