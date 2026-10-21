# Preregistered eligibility and provenance

A person reviews `candidates.csv` before copying approved rows into `repos.csv`.
Discovery never writes approvals. An assistant must not impersonate that person.
There are currently **no approved public repositories**. Execution additionally
requires action-time approval of the frozen manifest, image and dependency wheels.

## Inclusion

- Public GitHub repository, pinned to a full commit SHA. Preserve the exact license
  at that SHA and verify an OSI-approved license covers the selected test files.
  `common.py` recognizes a conservative subset; other OSI licenses need a reviewed
  code change. Public visibility without a license is insufficient.
- Python tests collected by pytest and using Playwright for actual browser end to
  end behavior. A Python backend plus TypeScript Playwright tests does not qualify.
- Record precise test file paths, evidence links, group, evidence strength and an
  installation/selection recipe. Review imports, fixtures and application startup.
  The selected E2E suite, not unrelated unit tests, is the unit of execution.
- Baseline must pass headlessly, with all selected tests exercised, no credentials,
  no display server and no external network. Partial skips, xfails, empty collection,
  missing browsers, missing dependencies and failed startup are explicit exclusions.
  Eligibility for review does not guarantee an executable baseline.

## Agent cohort

Prefer **test-specific** commits adding/changing selected tests with visible Claude,
Codex, Copilot, Cursor, Devin or Jules co-authorship, an agent-authored PR containing
the tests, or an explicit statement that those tests were generated. Save the exact
commit diff/evidence and link; a random agent commit elsewhere is insufficient.
These signals establish agent involvement, not that every line was agent-written.
Mixed authorship is disclosed, not silently relabeled as exclusively AI-written.

An AGENTS.md/CLAUDE.md instruction to write tests is **guidance_only** provenance:
it can identify a candidate, but is weaker than evidence of the tests actually being
authored by an agent. Keep it in a separate stratum, excluded from the primary
agent/human comparison. Mere presence of a guidance filename is insufficient.

## Human control cohort

Use the same public/license/stack/execution rules. Require affirmative provenance:
a linked author/maintainer statement about the selected tests, or documented
historical test authorship with original commit/PR and date, plus a person's review
of that history. Record limitations of historical evidence and possible later
agent edits. **Absence of agent labels or guidance files is not proof of human
authorship.** Unresolved/mixed provenance remains unresolved rather than becoming
a convenient control. No eligible control has yet been approved for this pilot.

Match or stratify on app domain/complexity, E2E suite size, assertion style, maturity,
browser/runtime versions, dependencies and target/strategy exposure. Do not choose
controls after seeing their scores. Use one preregistered run per repository and
publish exclusions before looking for replacement repositories.

## Analysis and limitations

Default strategies, per-test cap and worker timeout come from the installed Vandal
version. Record the immutable container image ID, wheel/dependency hashes, source
SHA, selection recipe, command vectors, package freeze, baseline and mutation logs,
raw report and terminal status. Retain incomplete raw reports but exclude them from
complete-run comparisons. Do not retry selectively to improve scores.

Strength = 100 * killed / (killed + survived); zero denominator is N/A. Error,
not_applied and skipped outcomes never count as kills. Report untested mutants
(not_applied + skipped), unsupported targets, cap omissions and action_failed kills
separately. Show repository/test/mutant sample sizes, repository-weighted median,
inclusive-quartile IQR and min–max. Strategy survival rates use killed + survived
for that strategy. Every number is calculated from raw observations.

This is a bounded convenience sample, subject to search, provenance, installation,
offline-service and survivorship bias. A single baseline does not eliminate flaky
tests. App/target/strategy differences, caps and controlled action failures can
make cross-repository scores misleading. Report only the repositories tested;
do not claim agent authorship caused a difference or generalize to all AI tests.

Never push, comment, open issues or contact candidate repositories. Do not execute
their code on the host. A container is defense in depth, not a proof against hostile
code; use a disposable Docker host for public studies. Candidate code can forge its
own artifacts, so raw evidence still needs independent review before publication.

## Static screening and discovery strata

`observable_calls` is a read-only AST call-site heuristic at the pinned SHA, not a
mutation score or proof of runtime observability. For proposed replacements require
at least 10 matching calls plus fixture/application review for local-only runtime
behavior. Record low/zero counts and rejected leads rather than silently dropping
them. A source finding about CDN/setup access is not an observed baseline failure.

Discovery includes test commits, generated-tests commits, agent PRs, AGENTS.md and
CLAUDE.md guidance, and a historical-control lead mode. The historical cutoff is
2021-01-01: repository creation, author date and committer date must all precede it.
This is a conservative lead filter, not a claim that all earlier tests are human.
Historical and guidance-only rows retain unresolved authorship for person review.
Search totals, sampled hits, candidate rows and approved study subjects are different
counts. Report evidence-type counts and missing licenses in the audit.
