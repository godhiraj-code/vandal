# Validation record — 2026-10-21

Base: current remote main `685988050d7dd899c6a67b4488c735934b04f55b`, verified
again with `git ls-remote origin refs/heads/main`. PR #5 was squash-merged at this
commit; its reviewed head was `e7ce1ef314b3e42904ca3a42883aa7c8c17f950e`.
Separate checkout and branch: `study/reproducible-playwright-agent-study`.
No demo checkout/branch was used. No Vandal package source or version changed.

## Actual local checks

- Windows, Python 3.13.7, fresh task venv with the owned editable package and declared
  test dependencies. `python -m pytest study/tests -q`: **30 passed in 0.74s**.
- `python -m build --wheel`: successfully built
  `project_vandal-0.2.1-py3-none-any.whl`; inspected ZIP members: **14 entries**,
  eight `vandal/*.py` modules and distribution metadata/license, no `study/` entry.
  Build backend resolved to setuptools 84.2.1. The explicit existing package list
  already excludes the study; no package configuration change was needed.
- Three candidate manifest rows validate structurally; all remain `approved=no`.
  `repos.csv` contains only the header. No public source was executed.
- `git diff --check` passed.

## Independent review and repairs

Frozen candidate `05f2b4cf7010f1038559c0e895a4ceedd06e915e` received an independent
read-only review, including an independent **30 passed in 0.62s** unit run and owned
mock reproductions. Four P2 issues were found: malformed container exports/cleanup
exceptions could lose status records; malformed JSON could abort summarization;
public results did not bind the repository identity to approval; and staged wheels
incorrectly consumed the source-fetch disk allowance. All four were corrected with
regressions. The expanded local suite passed **37 tests in 0.78s**. The corrected
browser fixture's execution function did not change in this repair.

A final isolation review added explicit empty proxy environment values to prevent
Docker CLI configuration from injecting host proxy credentials, and made uncertain
container cleanup mark the result incomplete and halt subsequent repositories.
The first new regression setup failed because its mock evidence URLs referenced
the wrong repository; after correcting that setup, **38 tests passed in 0.98s**.
These are command/policy checks; the unavailable engine still prevents validation
of actual container isolation. No public code was executed.

Independent review of that frozen correction passed 38 tests in 0.89s but found
one further P2: a malformed worker reason combined with cleanup failure could
prevent durable status writing. Worker reason types are now validated before
adoption. The combined regression and full local suite passed **39 tests in 1.00s**.

Raw artifact hashes were also verified against committed Git blobs. `.gitattributes`
preserves evidence bytes and generated whitespace across platforms; all eight wheel
module contents match the unchanged owned package source. The actual CLI rejects
`candidates.csv` with “not approved by a person” before acquisition or execution.

## Owned fixture attempts (not public study observations)

Raw reports, status, command vectors, package freeze and logs are retained under
`results/pilot/`. The same owned fixture source was used throughout; these are
debugging/validation attempts, not three independent study subjects.

| Directory | Actual outcome |
|---|---|
| owned-fixture | Restricted execution baseline timed out at 180.076s; no mutation score or report. |
| owned-fixture-elevated | Headless baseline passed, but the initial harness `--` delimiter prevented Vandal's appended worker flags from parsing. Five clean replay errors, no scored mutants, score N/A. |
| owned-fixture-corrected | After removing the delimiter and retaining validated file paths, baseline and mutation pass completed. Two tests, five mutants: four killed, one survived, zero error/not_applied/skipped, strength **80%**. |

This is a real baseline → mutation → raw report → summary check using the same
worker execution function. The fixture-only entry point has no arbitrary repository
path input. Vandal itself needed no fix; its appended worker flags require the
harness to omit the end-of-options delimiter. CI checks the owned fixture produces
scored mutants without replay errors, so exit zero alone cannot mask this problem.

## Docker and network evidence

GitHub read-only API discovery succeeded. Restricted Git/PyPI networking failed
with `getaddrinfo` errors; permitted elevated clone/install operations succeeded.
This is **not** a claim that all network access is unavailable.

Docker client 28.4.0 is installed. Initial `docker version` reported:
`open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified.`
`docker desktop status` reported it could not retrieve status and suggested normal
startup. `docker desktop start` and the installed Docker Desktop application's
ordinary startup were attempted; no engine/settings installation or alteration was
performed. A subsequent sandbox probe reported pipe access denied; the permitted
elevated version/status probe again returned the missing engine pipe and no server
version. No running Docker process remained at inspection.

Therefore Docker image build, real container acquisition/export/resource controls,
and public pilot execution are **not validated here**. Unit tests inspect command
construction and safe parsing but cannot prove runtime isolation. Public execution
also remains blocked on person review/action-time approval and reviewed dependency
wheel provisioning. The three selected candidates may fail offline baselines,
particularly pyvista-js's explicit unpkg CDN check.

No public agent/human comparison is available: n_agent=0, n_human=0.

## Container validation and expanded protocol (2026-10-21)

Docker Desktop's earlier runtime-directory startup blocker was repaired using the
separately authorized reversible runtime-directory rename. The backup was preserved.
The Linux engine is now available; the earlier missing-pipe observations above are
historical, not a current blocker.

Retained build attempts: `container-build-01` failed before building because an empty
Docker configuration could not find Buildx and the fallback rejected `--progress`.
`container-build-02` succeeded in 98.644s after specifying the installed plugin
location without credentials. Builds 03, 04 and 05 succeeded in 2.330s, 22.456s and
2.577s respectively. Each build record lists the exact allowlisted context hashes,
immutable image ID, bounded command/log result and empty-proxy/credential policy.

| Owned container attempt | Actual result |
|---|---|
| 01 | Docker logging driver rejected compression with max-file=1. No worker or baseline. Cleanup succeeded. Fixed by disabling compression for this bounded single log. |
| 02 | Worker venv creation failed with PermissionError. No baseline. Cleanup succeeded. Manual inspection after cleanup failed; its isolation record explicitly says unavailable. |
| 03 | Same venv failure; captured mount evidence showed `/work` was noexec. Fixed by explicitly permitting execution on bounded work tmpfs; `/tmp` stays noexec. |
| 04 | Container exited before mount inspection. No baseline/export evidence. Cleanup succeeded. Root cause of this specific attempt was not captured. |
| 05 | Console explicitly reported ensurepip unavailable; container exited 1. Harness reached its deadline and recorded incomplete with no score; cleanup succeeded. Fixed by adding python3.12-venv to the owned image. |
| 06 | Real container pipeline completed: baseline 2 passed, 4 killed, 1 survived, 0 errors, 80% (n_scored=5, n_tests=2). Export and cleanup passed. |
| 07 | Rebuilt bounded-venv worker repeated the real container pipeline: baseline 2 passed, 4 killed, 1 survived, 0 errors, 80% (n_scored=5, n_tests=2). Export and cleanup passed. |

Attempt 07 image ID and source/context provenance are retained in build-05 and the
run's status. `python -m study.verify_container` passed for both successful runs:
network none, read-only root, UID 10001, no privileged mode, read-only input/dependency
binds only, no GITHUB_TOKEN, empty injected proxies and confirmed cleanup. These are
repeated checks of **one owned fixture**, never public study subjects. Two kills are
controlled action failures, not necessarily assertion detection.

The venv step now runs as a bounded subprocess so ensurepip/SystemExit failures
produce durable worker status and a whitelisted `venv.log`. Docker client routing
variables and HOME are retained only for Docker CLI subprocesses; candidate process
environments do not inherit them. The final worker was rebuilt and actually tested.

Independent source review at `2ca7cfe098fa65b0e123ba7c2f78bb888d36a9da`
passed **51 study tests in 1.06s** and verified attempt 06 from raw evidence with no
new blocking finding. Local study tests passed **51 in 1.30s**. Final publication
checks and current-head hosted CI are recorded in the PR description after completion.

Static screening now retains seven unapproved test-commit leads and explicitly marks
pyvista-js/debim expected unscoreable. Contrail (66 calls) and talkvote (100) are
proposed replacements; their dependency preparation and person approval remain pending.
The full authenticated discovery CLI was not run: GITHUB_TOKEN is absent. Read-only
connector search and source inspection are documented in the discovery audit; one
Devin author query returned HTTP 422, preserved honestly. No public pilot occurred.
