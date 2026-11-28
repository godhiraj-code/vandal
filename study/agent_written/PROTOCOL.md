# Prospective agent-written Playwright suite study

Protocol ID: agent-written-v1. Written 2026-10-21, before any data collection.
Status: DESIGN ONLY; collection and execution are disabled. No agent, application,
or public repository was run to prepare this design. Synthetic validator tests
are harness checks, not study observations. All app proposals are unapproved.

## Questions and population

1. How strong are suites written by coding agents, measured by Vandal score per suite?
2. How much do scores and valid-suite yield vary between agents, apps and repeated runs?
3. Which mutation strategies survive most often, and with what observed denominators?

This prospective, fixed-app design complements the existing natural-pool study,
which remains descriptive case studies. Do not combine their denominators or
make causal claims about authorship. There is no human control group.

## Freeze and approval before collection

Dhiraj must approve the exact app panel, task packets, agent/account/model panel,
terms review, budgets and offline build recipes. Approval of this design PR does
not approve execution. Keep apps.proposed.csv rows approved=no. Future approvals
belong in a separately reviewed frozen manifest; never infer them from a loader
success, repository license, or absence of a terms restriction.

Archive this protocol, prompt.md, task packets, app manifest, isolation source,
dependency and asset locks, image ID, harness commit, tool/model configuration and
terms snapshots with SHA-256 hashes before the first request. Every run records
the applicable hashes and a unique ID. A change creates a new protocol cohort;
do not quietly replace frozen inputs or pool incompatible cohorts.

## App panel

Select 5 to 10 distinct open-source web apps with permissive MIT, BSD or Apache-2.0
licenses. Each must run completely offline within the existing resource envelope,
start from a recorded local command, and be pinned to a full source commit SHA.
Stage all runtime binaries, dependency wheels/packages, fonts and assets with
licenses and hashes. No credentials, external services, CDNs or remote resets may
be necessary for the reviewed workflows. A local SQLite database and synthetic
local accounts are allowed; reset fixtures must be identical across agents.

Exclude apps written by Dhiraj. Different owners and license credits support a
proposal, but are not exhaustive authorship proof: obtain Dhiraj's no-authorship
attestation and review contributors/aliases before inclusion. Exclude unclear
licenses, unresolved asset rights, mandatory network services, and apps that
cannot fit the shared container. No app is admitted solely because its source
looks offline-friendly. Future runtime qualification needs separate permission.

APP_REVIEW.md ranks five proposals and records rejections. Offline readiness is
UNVERIFIED for all five. Select by functionality and setup feasibility before
seeing generated-suite scores. Avoid multiple implementations of the same app
as if they were independent domains. Record prior public exposure/training-data
familiarity as a limitation, not a measurable fact about any model's training.

Freeze one task packet per app: display name, loopback URL, neutral user-workflow
facts, expected outcomes, local reset instructions and starting data. Source and
local docs are available equally to every agent. Do not disclose existing tests,
scoring machinery or prior generated suites. External attribution links are not
workflows. Record any necessary app adaptation before qualification; never patch
an app differently for one agent or after seeing a score.

## Agents and terms

Candidate tools: Codex, Claude Code, GitHub Copilot, Cursor, Jules, aider and
OpenHands. TERMS.md records official sources checked on 2026-10-21 and unresolved
account/surface/publication conditions. None is cleared by this document.

Pin executable/source revision or image hash, tool version, model provider,
immutable model snapshot, endpoint, account plan, authentication route, settings,
reasoning level and sampling configuration per run. Record system prompts and
tool affordances when accessible. A hosted alias or undisclosed rollout is not an
immutable version: label it recorded_hosted and report that limitation separately;
do not silently include it in the fully pinned primary panel. Managed tools that
cannot enforce the common offline application/tool environment remain on hold.

Resolve both collection rights and publication rights before collection. Preview,
MSA, regional, provider and model terms may override general policies. If required
replication material cannot legally be shared, hold publication and omit the tool
from a public benchmark panel until the conflict is resolved. Separately review
generated-code and dependency licensing. Never treat no explicit clause found as
permission under an unidentified agreement.

## Fixed prompt, budgets and independent repetitions

prompt.md is the one template for every tool and app. Only app_name, app_url and
task_facts are substituted from the frozen app packet. The template contains no
reference to the later scoring method. Hash both raw template bytes and exact
rendered prompt bytes; preserve all visible messages and tool results.

Provisional generation budget: 1800 seconds wall time and 30 assistant turns,
whichever occurs first. One assistant response is one turn, including responses
that issue multiple tool calls; tool outputs are not extra turns. Time includes
tool execution, retries, waiting and provider latency from the first request to
the frozen suite. No manual hint or repair after the initial prompt. Tool/provider
errors consume the budget and are reported. Record token usage, known cost or
null if unavailable, elapsed time, turns, termination reason and all retries.

Run exactly three independent fresh sessions per agent per app. No shared chat,
memory, generated tests or workspace state; reset application data and browser
profile each time. Use a preregistered balanced agent/app order and recorded seed
where supported; do not select the best of three. Freeze each suite at termination.
App setup happens before timing using the same reviewed image. Any infrastructure
rerun needs a dated reason, preserves the failed attempt and cannot inspect scores
first. Do not replace missing runs with estimated values.

## Isolation and validity

Reuse study.run_study.container_command, study.process.run, study.resources and
study/pytest_entry.py. isolation.py only constructs the existing command; it does
not execute anything or provide a completed agent-written scoring adapter.
The shared limits remain network none, read-only root, uid/gid 10001, all caps
dropped, no-new-privileges, 1024 PIDs, 2 CPUs, 4 GiB memory, bounded tmpfs/logs/files,
deadlines and per-mutant descendant cleanup. Do not expose host secrets, Docker
socket or provider credentials to app/suite processes. Apps and generated suites
are untrusted and may never execute on the host.

A future generation controller may contact only its approved model endpoint;
candidate shell/browser tools still run in the offline container. A credential
broker outside that container is a design requirement, not implemented here.
Cloud agents that cannot satisfy it cannot enter the primary panel. Do not
weaken isolation to make a particular product work.

A valid suite must collect at least one test and pass its entire baseline three
consecutive times offline against fresh identical app/browser state, using the
same suite bytes and collected test IDs. All three must exit zero with no failed,
error, skipped, xfailed or xpassed tests; do not cherry-pick nodes or retry just
the failed tests. Record every attempt and hashed logs. No post-freeze fixes.
The static loader verifies consistency and file integrity only; it cannot prove
that logs are authentic or that a recorded run actually happened.

Budget for each future scoring container: 900 seconds, including installation
and its baseline/mutation work. A future adapter must also schedule the three
qualification baselines explicitly and record their budgets. Batch planning must
call study.budget.validate_run_budget: setup 600 + sum(per-repo budget + 60)
must be <=3000 seconds, at most 10 rows. Generation and scoring are separate jobs;
the legacy pilot workflow is not an executor for this design and is not dispatched.

## Outcomes, exclusions and analysis fixed in advance

Primary metric: each valid, completed suite's Vandal strength = 100 * killed /
(killed + survived), using the frozen harness version and default strategies/caps.
Report killed, survived, errors, not-applied, skipped, untested targets, cap
omissions, test count and mutant count alongside every score. Zero scored mutants
produce N/A, not zero strength. Incomplete/time-limited scoring is excluded from
the primary score. Error validity follows the existing study: errors must be at
most 10% of all recorded mutants; above that, mark invalid run and exclude it
from every score/median/rate. Preserve raw invalid outcomes in separate tables.

For each agent/app cell report all three planned repetitions, valid-suite yield,
the three scores or explicit missing/exclusion reasons, and its median of valid
scores. Do not treat repetitions as independent apps. Primary agent summary is
median and inclusive-quartile IQR across per-app medians on the common valid app
panel, with n_apps and n_valid_suites and planned denominator shown. Also show
all-app availability and per-app variation so missing cells cannot hide failures.
App cells with no valid scores remain missing and reduce the common panel; report
which apps were lost. No median/IQR/range with fewer than two app summaries.

Strategy survival is first calculated within each valid suite among killed plus
survived mutants for that strategy, then summarized within app and across apps
with equal app weight. Show n_apps, n_suites and n_mutants for every strategy and
separate zero-denominator cells. Do not silently pool by mutant. Present paired
descriptive app differences only on the same app set. With 5-10 convenience apps
and three repetitions, make no significance or population-superiority claims;
no p-values or post-hoc hypothesis tests are planned.

Report generation failures, no-suite/collection failures, each baseline failure,
resource exhaustion, invalid mutation runs, time/turn limits, missing data, cost,
provider errors, safety/terms exclusions and unfavorable scores. Publish the
predeclared selection flow, raw logs where permitted, immutable inputs, source
hashes and analysis code. Redact credentials and personal data with a retained
redaction record; preserve original outcome counts and privately retain integrity
hashes where publication is restricted. Do not suppress inconvenient results.

## Change log

| Date | Phase | Change / reason |
|---|---|---|
| 2026-10-21 | Before collection | Initial prospective design, provisional 1800-second/30-turn generation budget, three repetitions, five unapproved app proposals; no observations collected. |

After collection begins, append date, author, old/new protocol hashes, rationale,
affected runs and prospective versus retrospective status for every change.
Freeze the original protocol alongside amendments; separate affected cohorts.
