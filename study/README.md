# Reproducible Playwright mutation study

Run commands from the repository root. Python 3.9+ runs the host harness; the Docker
image uses the Python/runtime bundled in Playwright's noble image. Study code and
results are excluded from the wheel by the existing explicit `packages = ["vandal"]`.

## Discover and review

```sh
python -m study.find_repos
```

Read-only GitHub Search API discovery uses `GITHUB_TOKEN` from the host environment.
It searches commit evidence, checks changed Python browser tests and a pinned
license, and writes unapproved leads plus an audit of queries/errors. Bounded search
is not exhaustive. No test import, collection or repository setup happens here.
For manual evidence sources see `candidate-evidence.json` and `CANDIDATE_REVIEW.md`.
Run discovery to a separate `--output` to avoid replacing reviewed candidate work.

A **person** checks `CRITERIA.md`, source/evidence and recipes, reviews dependency
wheels, and copies selected rows to `repos.csv` with `approved=yes`, reviewer and
UTC `reviewed_at`. Keep unapproved/rejected candidates in the discovery audit.
Human cohort discovery is deliberately manual until affirmative authorship evidence
is available; missing agent metadata never assigns that group automatically.

## Container execution

Build only the owned harness/package image; `.dockerignore` allows just required
source files and excludes credentials, `.git`, venvs and results:

```sh
docker build -f study/Dockerfile -t vandal-study .
docker image inspect vandal-study --format '{{.Id}}'
python -m study.run_study --image sha256:REPLACE_WITH_INSPECTED_ID --wheelhouse /path/to/reviewed-wheels
python -m study.summarize
```

Record the build log and image ID; the upstream base tag and unconstrained package
dependencies can change between builds. For reproducibility retain the immutable
image and dependency wheels, not merely the Dockerfile. The worker pins Playwright
1.64.0/pytest-playwright 0.10.0 to its browser image; it installs Vandal from this
checkout's wheel, never an independently published release.

The runner prints the exact frozen manifest and recipes and asks for action-time
approval. **Do not automate the answer.** Approval in CSV alone is insufficient for
an assistant to execute unknown repository code. There is no noninteractive bypass.

Source acquisition uses a bounded bare Git fetch of the exact SHA in a temporary
directory, with global/system configuration and credentials disabled; no checkout,
hooks, filters or submodules execute. Archive extraction rejects links, devices,
path escapes, duplicates and oversized trees. The source hash is retained.

Install and tests run in a fresh venv inside the container, entirely offline. Supply
reviewed, platform-compatible dependency wheels (including project build backends
and transitives) in a dedicated directory containing only regular `.whl` files.
The runner copies and hashes these, never mounts an incidental user directory.
It does not run pip/build from the candidate on the host. Missing wheels cause an
honest installation exclusion. No dependency/download fallback enables networking.

Resource policy: unprivileged UID, read-only root, no capabilities or privilege
escalation, no network, no host IPC/PID sharing, no Docker socket, two CPUs, 4 GiB
RAM/no additional swap, 256 PIDs, 3 GiB work tmpfs, 256 MiB temporary tmpfs and shared
memory, file-size/descriptor limits, bounded logs and per-repository deadline.
Only read-only source/recipe and dependency inputs are mounted. No host credentials
or `GITHUB_TOKEN` enter a container, and no candidate output is written through a
host bind mount. Whitelisted regular artifacts are exported through bounded tar
data; the entire container is forcibly removed after collection. Cleanup failures
remain in status/logs and require operator attention.

The standalone baseline disables Vandal. Both phases clear repository `addopts`,
use identical reviewed `-m`/`-k` selection, and pass only explicit test files.
This avoids hidden parallelism/strategy/reporter options and is a disclosed method
change. Project fixtures handle local app startup. No application-specific secrets,
external services or arbitrary setup shell commands are accepted. Install, baseline
and mutation output, environment freeze and raw report are retained. All skipped
tests invalidate the baseline; this deliberately favors fully runnable selections.

## Validation without Docker

```sh
python -m pip install -e '.[test]' build
python -m pytest study/tests -q
python -m study.fixture_smoke
python -m study.summarize
python -m build --wheel
```

`fixture_smoke` executes only the small owned fixture hardwired in this repository,
in a newly initialized local fixture Git repository, using the task venv. It has no
arbitrary source/path execution option. Its scores are real harness measurements
and always excluded from public cohort analysis. It exercises the same real pytest
baseline/mutation/report path, **not** Docker acquisition, installation, namespace
isolation or container export. A successful fixture is not a successful public pilot.
Never use this host-only fallback for a third-party candidate.

`summary.csv` is machine-readable; `REPORT.md` includes all skipped/incomplete/invalid
runs and method limitations. Existing output directories are never overwritten by a
run. Choose a new results directory for repeat validation; do not combine repeat
runs of the same repository into a larger apparent sample.
