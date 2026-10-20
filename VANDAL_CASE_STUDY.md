# Case study: testing assertions with Project Vandal

**Author:** Dhiraj Das

Vandal injects UI faults into a live Playwright page and records whether tests
notice them. This case study describes the implementation and reproducible demo.
It does not report a measured production-suite improvement or performance benchmark.

## The problem

A test can click a button and pass without checking that the application changed.
The repository's example app has a button that updates a message. Its weak test
only clicks; its strong test also checks the message. Blocking the click handler
provides a concrete experiment against those two test contracts.

## Two ways to run the experiment

The original async `Vandal(page)` context manager applies explicit mutations.
Its persistence option uses init scripts and observers, and selected strategies
support manual reversion. See the test guide for the supported reverts.

The automatic pytest plugin discovers targets from observed Playwright actions,
reads, locator construction and Locator assertions. It runs a clean baseline,
then isolated mutation workers with unmutated replay controls. This mode supports
sync and async tests. Its instrumentation and lifetime rules differ from the
manual persistence mechanism.

## Reproduce the example

```bash
pip install -e ".[test]"
playwright install chromium
pytest examples/test_strength.py --vandal --vandal-strategies=logic_sabotage
```

Inspect `vandal_report.json` for the actual measured results. The strong test is
expected to detect the blocked message update; the weak test does not assert it.
The repository's browser tests check those outcomes and each strategy's effect.

## What the results mean

Strength measures killed mutants among killed and surviving mutants. It does
not prove complete test quality. Equivalent mutations may survive, errors are
excluded, and replay controls cannot guarantee deterministic external services.
Open shadow roots can be resolved by Playwright; closed roots are unsupported.
Page/frame identity is not yet part of a target, so multi-context suites require
careful review. See [TESTER_GUIDE.md](TESTER_GUIDE.md) for all supported boundaries.

Earlier versions of this document asserted a sample-suite percentage, a mutation
latency, complete shadow coverage and zero downtime without reproducible evidence.
Those claims have been removed. No runtime or production-impact benchmark is
claimed by this case study.
