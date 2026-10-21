# Changelog

## Unreleased

- Add a local, headless scripted agent-loop demo with measured weak/fixed scores,
  survivor output, an agent prompt, a VHS tape and a CI improvement check.
- Stream demo mutation progress, use realistic shallow checks in the weak test,
  and exclude its checkout-only runner tests from source distributions.

- Avoid ineffective pointer/click defaults for press, type, select_option, focus,
  dispatch_event and set_input_files. Keep data_sabotage for type; infer
  stealth_disable and ghost_element for hover, backed by browser kill tests.
- Report actions without defaults as untested separately from cap omissions,
  respect umask for JSON reports, and close the descriptor if fdopen fails.
- Remove redundant adapter diagnostics and unused locator factory code; refresh
  the module overview and remove the internal PR checklist.

- Preserve baseline pytest file logs across mutation workers and label deadline
  HTML reports as incomplete while retaining completed mutant results.

- Count controlled Playwright call errors as action_failed kills; add optional
  kill_reason, skipped_by_cap and MCP timed_out report fields within schema v1.
- Make mutant-error exit failures opt-in with --vandal-strict and explain gates.
- Use a standard vandal/ package with editable installs and root-level tests.
- Discover targets on use, infer default strategies, alternate targets before
  the cap, refresh data sabotage and make terminal counts and hints readable.
- Isolate worker reporter outputs and validate private Playwright hooks; bound
  Playwright below version 2 while retaining the manual async API.
- Return completed MCP mutants on deadlines and validate restricted pytest_args.
- Run checkout-based CI and add Windows/macOS smoke coverage and score assertions.

- Keep native mutation receipts outside the document so navigation preserves
  killed/survived accounting and the CI score gate.
- Apply mutations during native Playwright selector retries, including replacement
  nodes in actions and scalar/array assertions, without adding attachment waits.
- Require Playwright 1.60 or newer for the tested selector retry adapter.
- Resolve relative explicit targets inside nested FrameLocators and preserve
  `to_be_attached(attached=False)` absence semantics.
- Treat copied DOM markers as new node identities: cloned buttons get their own
  click blocker, and cloned slow-load targets get their own restoration timer.
- Document the independently demonstrated limit of clean controls for periodic
  external application state. Passing controls cannot prove mutation causality.

- Fix mutation ordering for auto-waited elements in sync and async tests.
- Resolve configured targets independently of the test's locator spelling.
- Track mutated nodes independently of temporary strategy markers so `slow_load`
  restores visibility once without being reapplied on later reads.
- Reject JSON/HTML report path collisions before executing tests or writing files.
- Observe assertion-only Locator access through both Playwright APIs.
- Preserve confirmed mutation counts when async operations run concurrently.
- Require bounded unmutated replay controls before mutation and after a possible
  kill; classify failed controls as errors instead of inflating strength.
- Remove historical performance claims that have no reproducible benchmark evidence.

- Add automatic pytest mutation runs with sync and async Playwright target discovery.
- Separate assertion kills from failing baselines, fixture failures, timeouts, and unapplied mutations.
- Add per-test and overall strength, versioned JSON and HTML reports, survivor hints, and a CI score gate.
- Add optional stdio MCP tools, an agent skill, and weak/strong example tests.
- Add headless browser regression coverage to CI. Keep the manual async Vandal API.
- Fix UTF-8 report writes and console output in the legacy Windows demo.
- Isolate worker pytest caches and preserve last-failed baseline selection.
- Treat worker failures before confirmed injection as errors.
- Preserve baseline temporary directories, JUnit XML, and Playwright artifacts during replay.
