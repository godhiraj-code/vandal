# Manual public pilot: prepared, not executed

No public repository has run. The two rows in repos.csv record Dhiraj Das's explicit
review at 2026-10-21T12:20:00Z: contrail 2465e368b7658bd23f0d41f1473c114db3573005
and Platelet-Movie 14664611814b126289f291ad24ee294102efb07c. This inclusion approval
does not dispatch or authorize an unattended run now. Talkvote remains unapproved.

## Configure the human gate first

Dhiraj must create the **study-pilot** environment in repository Settings >
Environments and add himself as a required reviewer before any dispatch. Verify
the required-reviewer protection is saved and applies to the selected branch.
Do not dispatch with an absent or unprotected environment: the workflow's environment
name alone does not establish protection. No environment, setting or secret was
created by this change. No secrets are required. If self-review prevention is enabled,
a different authorized person must approve a run Dhiraj dispatches.

Review the full checked-out commit, manifest SHAs/test paths, recipes, wheel lock,
licenses and offline deviations. The GitHub manual workflow must be available on
the default branch before GitHub exposes workflow_dispatch; merging is a separate
decision and is not performed here. Restrict use to a trusted reviewed ref.

## Review preparation and obtain the exact confirmation

From the reviewed checkout, this command only reads the manifest and prints its token:

```sh
python -m study.run_study --repos study/repos.csv --print-confirm
```

The token is exactly `RUN ` followed by the first 12 hexadecimal characters of the
SHA256 of the manifest's actual bytes. Copy the printed value, including the space.
study/.gitattributes disables line-ending conversion for repos.csv so Windows and
Linux checkouts retain the same bytes. Deliberate line-ending or row changes change the token. It is an explicit confirmation, not a
credential or a replacement for the environment reviewer. The workflow checks it
before image build/download and the runner checks it again before acquisition.
The default local runner still prompts interactively; `--confirm` is opt-in.

The contrail acquisition inputs are wheelhouse/requirements-contrail.txt and
constraints.txt. The resolved requirements-contrail.lock pins all 17 direct/transitive
wheels with hashes. `bash study/wheelhouse/fetch.sh --dest wheelhouse` downloads
only CPython 3.12 Linux x86_64 binary wheels from PyPI in a clean environment;
it does not install/import them or acquire candidate code. The later hash-lock
requirement replaces the unpinned `-r requirements-contrail.txt` download argument
with `-r requirements-contrail.lock --require-hashes`, keeping the requested target
platforms and constraints. Missing or changed wheels fail; there is no source-build
fallback. MANIFEST.csv contains actual wheel filenames, SHA256 and the license
metadata retained in LOCK_METADATA.json. Wheels are not committed. Updating inputs
requires resolving and reviewing a new lock, not accepting a new hash at runtime.

Platelet-Movie's remote TMDB logo at site/index.html:142 is a known offline deviation:
network-none blocks it. It is neither stubbed nor vendored. Its effect on baseline
success remains unobserved. See [OFFLINE.md](recipes/OFFLINE.md).

## Dispatch only after explicit execution approval

This document is instructions for a future human action; this change does not trigger it.
In Actions > Manual study pilot > Run workflow, select the reviewed ref and paste
the exact token into the required `confirm` input. Review/approve the pending
study-pilot environment job. The workflow is workflow_dispatch-only, has read-only
contents permissions at both levels, SHA-pinned actions, nonpersistent checkout
credentials, a 60-minute job deadline and one shared concurrency group.

It builds the owned image from that checkout and prints/stores its immutable sha256
ID. Host acquisition uses bare pinned Git fetch/archive with no candidate checkout,
imports, installation, hooks or submodules. Dependency downloads are wheels only.
Candidate installation and tests run exclusively in the existing bounded container
with network none, read-only root, UID 10001, cap-drop ALL and no host credentials or
Docker socket. Only person-approved rows pass preflight. Missing offline dependencies
or baseline failures remain skips/incomplete outcomes; do not repair them silently.
The runner stages wheels only; MANIFEST.csv is inventory metadata, never mounted.

Ordinary PR CI remains owned-fixture-only even with approved public rows. Neither
adding these rows nor pushing this workflow runs a public repo. GitHub's actions
use their platform-provided capabilities for checkout/artifact upload; no repository
secrets or token expressions are supplied to shell commands or containers.

## Inspect and retain artifacts afterwards

The job summary lists image ID and each selected repository's status, baseline exit
result, score and sample size. Missing observations say not run/not observed/N/A.
The artifact contains public raw results/logs, regenerated REPORT.md and summary.csv,
wheelhouse/MANIFEST.csv, pilot-image-id.txt and PILOT_SUMMARY.md. No workflow step
commits, pushes or contacts candidate maintainers.

Download the artifact for the exact reviewed run/commit. Inspect its raw logs,
manifest/SHA correspondence, cleanup status and artifact_sha256 maps before accepting
numbers. Candidate code can falsify its own reports; hashes only detect later edits.
Keep failures and deviations. Copy the inspected files into the corresponding study/
paths in a separate local review checkout, preserving existing evidence rather than
overwriting another run. Recompute `python -m study.summarize`, review the diff, then
commit only the reviewed reports/raw evidence/manifest/image/summary in a separate
results commit. Do not commit wheel binaries. Any such results commit/push requires
the human's subsequent instruction; the workflow never performs it automatically.
