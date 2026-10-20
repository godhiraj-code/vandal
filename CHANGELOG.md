# Changelog

## Unreleased

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
