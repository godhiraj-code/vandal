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
