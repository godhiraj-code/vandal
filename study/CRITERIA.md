# Descriptive study of agent-written Playwright suites

This study covers agent-written suites only. There is no human control group,
comparison or causal claim about authorship. Visible evidence establishes agent
involvement, not exclusive authorship of every selected line.

A person reviews candidates.csv before approving rows in repos.csv. Discovery never
approves inclusion. repos.proposed.csv is an unapproved review proposal; repos.csv
is empty. Execution also requires action-time approval of the frozen manifest,
recipes, immutable image and dependency hashes.

## Source eligibility and execution eligibility

- Public repository pinned to one full SHA, with an OSI license verified at that
  snapshot and covering the selected tests. Public visibility alone is insufficient.
- Actual Python pytest browser tests using Playwright, with exact paths. A Python
  backend and TypeScript browser tests alone do not qualify.
- Test-specific authored evidence: a commit adding/changing the selected tests with
  agent co-authorship or an agent-authored PR containing those tests. A generic
  "generated tests" statement is weak, unresolved provenance and cannot alone
  establish agent authorship. Preserve links/diffs and disclose
  mixed authorship, including agent edits to an existing suite.
- AGENTS.md/CLAUDE.md is guidance_only provenance. It identifies review leads but
  cannot establish authored-test eligibility. Missing agent metadata establishes
  nothing about authorship. Historical control discovery is out of scope and removed.
- Proposed mutation-study replacements require at least 10 observable call sites.
  Retain positive lower-count leads without counting them toward that target;
  zero-call entries belong in rejected_candidates.csv, never candidates.csv. Static calls do not guarantee mutants or a passing baseline.
- A baseline must pass headlessly with every selected test exercised, no credentials,
  display server or external network. Partial skips/xfails, empty collection and
  missing dependencies/services are exclusions. Static qualification and executable
  baseline are separate gates. Do not selectively retry to improve a score.

## Static screening and offline risk

Read source as utf-8-sig. Select files importing Playwright, or using the pytest page
fixture with a pinned pytest-playwright declaration in supporting files. Count only
tracked Page/Locator receiver chains, locator/get_by results and imported Playwright
expect arguments. Simple fixture-returned pages and page-returning factories, aliases
and Page/Locator annotations are recognized, along with page-object self.page
fields, lexical nested helpers, frame_locator and loops over locator.all(). Selenium/Appium and ordinary Python
objects do not qualify merely by having similarly named methods.

This is conservative AST analysis, not type checking or runtime evidence. Helpers
count once; loops and parametrization are not expanded. Dynamic wrappers, factory
returns and Python shadowing may still cause misses or false positives.

Read ancestor conftest.py, pytest.ini, setup.cfg, tox.ini, pyproject.toml and
requirements files at the same SHA. Record external host literals, base_url and
--base-url, subprocess git clone, Docker use and availability checks as offline_risk.
The CLI follows statically imported repository-local Python helpers recursively
using the pinned Git tree, including relative and src-layout imports, with a 200-file
bound. Dynamic imports and application assets still require manual review. Metadata/documentation URLs and graph identifiers can be false
positives. Localhost settings are review flags, not external dependencies. An empty
risk list is not proof of offline compatibility. Never describe a source risk as an
observed baseline failure.

## Analysis and limits

Use one preregistered complete scored run per repository. Strength is
100 * killed / (killed + survived); a zero denominator is N/A. Errors, not_applied and
skipped outcomes never count as kills. Report unsupported targets, cap omissions and
action_failed kills separately. Show repository/test/mutant sample sizes, a
repository-weighted median, inclusive-quartile IQR and min-max. IQR is N/A for n<2.
Strategy survival is pooled by mutant with n_repos and n_mutants; larger suites carry
more weight. No human comparison is calculated.

Record default Vandal strategies/caps, wheel, image ID, source/dependency hashes,
recipe, commands, package freeze, baseline/mutation logs and raw reports. Host paths
are redacted in retained evidence and hashes describe sanitized bytes. Earlier failed
owned-fixture attempts remain in FIXTURE_ATTEMPTS.md and raw pilot logs, outside the
main report. Owned fixtures never enlarge the public study sample.

This bounded convenience sample has search, provenance, offline setup and survivorship
biases. App complexity, assertions, targets, strategy mix, caps and controlled action
failures limit comparability. One baseline cannot rule out flakiness. Report only
repositories actually tested, without generalizing to all AI-written tests or
implying an authorship effect.

Never contact candidate maintainers or execute their code on the host. Containers
have no network/host secrets, bounded resources and mandatory cleanup. Isolation is
defense in depth; use a disposable Docker host for public studies. Candidate code
can forge its own artifacts. Hashes detect later changes, not dishonest execution;
independent source/log review remains necessary.
