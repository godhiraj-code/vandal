# Tester's guide to Vandal

Vandal measures which injected UI faults cause assertions in your pytest +
Playwright suite to fail. It supports the sync and async APIs automatically.
The manual `Vandal` async context manager remains available.

## Install and run

```bash
pip install project-vandal pytest-playwright
playwright install chromium
pytest --vandal
```

For development, clone the repository and run `pip install -e ".[test,mcp]"`.
The MCP extra needs Python 3.10+. Run `python -m pytest -q` for the regression
suite and `python demo_vandal.py --headless` for the original demo.

Normal pytest paths, node IDs, parametrization, `-k`, and `-m` select tests.
Without `--vandal`, this plugin does not instrument Playwright or write reports.
A normal baseline runs first, with the suite's usual fixtures and configuration.
Failed baselines are reported as `baseline failing` and are not mutated.

```bash
pytest tests/test_login.py --vandal --vandal-strategies=logic_sabotage,data_sabotage --vandal-max-mutants=10 --vandal-timeout=60
pytest -m vandal --vandal --vandal-min-score=80
```

| Option | Default | Meaning |
| --- | --- | --- |
| `--vandal` | off | Enable baseline discovery and mutation workers. |
| `--vandal-strategies` | infer from usage | Explicit comma-separated strategy names override inference. |
| `--vandal-strict` | off | Fail when any mutant has an error outcome. |
| `--vandal-max-mutants` | 20 | Maximum mutants per test, positive integer. |
| `--vandal-timeout` | 60 | Worker wall time in seconds, including startup, collection, fixtures and test. |
| `--vandal-min-score` | unset | Fail if strength is below this percentage, or if no mutants were scored. |
| `--vandal-report` | `vandal_report.json` | JSON destination; HTML uses the same stem. An `.html` destination is rejected before running tests. |

Candidates alternate across first-seen targets, taking each target's first
strategy before its second. The cap truncates that list; each test reports
`skipped_by_cap` in JSON and the terminal. Restrict strategies and explicit targets for focused, comparable runs.
The CLI bounds individual workers; the ordinary baseline retains pytest's normal
runtime behavior. Use your CI job deadline for a suite-wide bound.

## Targets and discovery limits

```python
import pytest
from playwright.sync_api import expect

@pytest.mark.vandal(targets=["#submit"])
def test_submit(page):
    page.goto("http://localhost:8000")
    page.locator("#submit").click()
    expect(page.locator("#message")).to_have_text("Saved")
```

The optional marker supplies selectors. It does not exclude unmarked tests;
`-m vandal` does that. An empty target list deliberately schedules no mutants.
Selectors support Playwright syntax, including role and text selectors.

Without explicit targets, Vandal records common Page, Frame, and Locator operations
(click, fill, check, press, hover, text/value reads and others). Locator and
`get_by_*` construction alone never records a target. Chained locators and `nth()` preserve their Playwright
selector. Locator assertions through `expect(locator)` are observed too, including
locators constructed by fixtures. Replay currently uses Playwright's private
locator selector/frame representation, assertion dispatch and selector composition;
this is covered by browser tests but may require updates for future Playwright versions.
The package requires Playwright 1.60 or newer, the oldest selector implementation
covered by the compatibility tests for this adapter.

Mutations are applied to currently matched elements before observed operations and
after `goto`/`set_content`. A registered selector engine also applies the mutation
each time Playwright resolves a supported operation or Locator assertion. This
includes native retries: replacement nodes are mutated before the assertion reads
them or an action acts on them. Playwright retains its own waits and assertion
semantics. Vandal adds no attachment wait to immediate reads, absence assertions,
negative assertions or array assertions.
Applications during native retries send receipts to the Python worker immediately,
so navigation cannot erase a confirmed mutation or remove it from the score.
Configured targets are resolved in the operation's frame independently of whether
the test uses a CSS, role or chained locator, including nested FrameLocators.
Except for data sabotage, each matching element is changed once, tracked by node
identity independently of the DOM marker. Data sabotage is reapplied on target
resolution, including reads and assertion retries after application text changes. In particular, reading a restored `slow_load` target does not hide
it again. A cloned marker does not suppress mutation of a new node: event handlers
and restoration timers are installed for the clone when it is observed.
Replacement nodes are considered on subsequent native resolutions,
including retries within an operation. Injection occurs only in the test call,
not setup or teardown. A target used only during setup may therefore be unapplied.
A locator constructed but never used is not a candidate. This is deliberately
observable target discovery, not a full trace of every DOM access.

Raw JavaScript interactions, ElementHandle operations, direct mouse/keyboard actions,
and operations outside the observed method set may be missed.
No background mutation observer is installed by the automatic runner. Open shadow
roots work through Playwright locator resolution; closed shadow roots are unsupported.
Frame operations are observed, but selectors are not qualified by page/frame identity,
so identical selectors in multiple frames or pages may be mutated together. Use
unique selectors and inspect reports for multi-page/frame tests.
An explicitly qualified target in a different frame from the current operation
can be injected before the operation, but cannot participate in that operation's
native retry resolution. This cross-frame case remains outside complete coverage.

Each mutant gets a fresh pytest process and fresh Python fixtures. The worker
recollects the original selection and runs only the exact selected node ID.
Before each mutant, a separate unmutated control must pass setup, call and
teardown. A possible kill also requires a passing unmutated control afterward.
A failed, skipped, crashed or timed-out control records an `error` and excludes
that mutant from strength. These controls catch non-replayable tests such as a
baseline that leaves a file which makes the next run fail. Each control has the
same `--vandal-timeout` bound as a mutant. A candidate uses at most three bounded
workers: control, mutant and, only for a possible kill, a second control.
Each worker uses an isolated pytest cache, so mutation failures do not pollute
ordinary `--lf` runs. Baseline cache-based selection is resolved before replay.
Collection must be deterministic. Session fixtures execute again for every worker.
Processes and controls do not reset external databases, services, or files.
Controls detect reproducible replay failures, not every intermittent service or
application-state change. For example, an external counter that fails every third
execution can pass both controls and fail the mutant independently of the mutation.
Such a failure can still appear as killed. Passing controls do not prove causality.
They are additional executions and can have side effects.
Use repeatable fixtures and isolated application state. Tests that require another test to run first are
not suitable for isolated replay. Serial execution is required; xdist and
pytest-rerunfailures are rejected. Other plugins that rewrite outcomes or perform
retries may be incompatible. Worker temporary directories, JUnit XML, and
pytest-playwright artifacts are redirected to isolated worker directories and
discarded after the run. Baseline artifacts retain their configured destinations.
Other reporting plugins may need their own output isolation; use Vandal's report
as the mutation record.

The baseline uses your usual fixture lifetimes. A session-scoped sync Playwright
driver can conflict with pytest-asyncio's event loop in a mixed suite. Close sync
drivers in function-scoped fixtures before async tests start, or run those suites
separately. Vandal supports replay of either API but does not rewrite fixture lifetimes.

## Outcomes and strength

AssertionError and Playwright Error (including TimeoutError) in the test call
count as killed after confirmed mutation, clean setup/teardown, and passing
unmutated controls before and after. The optional `kill_reason` is `assertion`
or `action_failed`. A blocked click can therefore kill a mutant even in a weak
test. This is detection evidence, not proof of a meaningful outcome assertion.
Injection errors, worker deadlines, setup/teardown failures, and failed controls
remain errors. Skipped/xfail calls, unmatched targets and collection failures
are excluded. Failed baselines prevent mutation of that test.
Any failing worker without a confirmed injection is an error, including assertion
failures before injection. Failures caused by unrelated intermittent state after
injection can still be misattributed; the repeatable-state requirement above applies.

Strength is `100 * killed / (killed + survived)`, overall and per test. With no
scored mutants it is `N/A` (JSON `null`), never 100%. A minimum-score gate fails
when there is no score, even with a threshold of zero. Mutant errors are informational by
default; `--vandal-strict` makes them fail the command. Baseline failures retain
pytest's exit status. Whenever Vandal changes an exit status for strict errors or
a threshold, it prints one reason line, for example
`Vandal: strength 50.0% is below --vandal-min-score 51`.
Unapplied and skipped mutants are visible but do not independently fail a run.
A run can have a high score and many excluded outcomes, so inspect the counts.

Survivors are candidates for review, not proven missing assertions. A shifted
button may still behave correctly. Data sabotage is refreshed before later reads.
Read the hint and test contract before adding assertions. Prefer checking the
resulting UI, navigation, or state. Do not assert Vandal's own DOM marker.

See [report schema version 1](docs/report-schema.md) for machine-readable details.
The HTML report escapes test names, selectors and failure text.

## Strategies

- `stealth_disable`: disables pointer events while retaining visual appearance.
- `ghost_element`: sets opacity to zero and disables pointer events.
- `data_sabotage`: changes input values or visible text to junk data.
- `logic_sabotage`: blocks click propagation and default behavior.
- `ui_shift`: translates an element 100 pixels right and down.
- `slow_load`: hides an element for five seconds before restoring visibility.

Start with `logic_sabotage` for a click-and-assert flow. Default strategies follow observed usage: click/dblclick/tap/check/uncheck
(and set_checked) use stealth_disable, ghost_element and logic_sabotage; reads,
Locator assertions, fill and type use data_sabotage. Hover uses stealth_disable
and ghost_element, verified to block the browser's hover action. Press,
select_option, focus, dispatch_event and set_input_files have no inferred
strategies because pointer blocking and click handlers do not reliably sabotage those
operations. Targets used only through these actions remain untested, even when
their outcome assertions pass. A target used multiple ways gets the combined set
without duplicates. Explicit marker aliases inherit observed test usage if there
is no exact selector match. Observed targets without supported defaults appear
in untested_targets and a terminal warning, separately from skipped_by_cap.
ui_shift and slow_load require explicit --vandal-strategies selection.
Do not compare scores from different strategy/target sets as if they were identical.

## Weak and strong example

```bash
pytest examples/test_strength.py --vandal --vandal-strategies=logic_sabotage
```

The local app needs no web server. The weak test only clicks, while the strong
test also asserts the message. Both baselines pass; the mutation prevents the
message change, exposing the difference. The generated report contains measured
results for your environment.

## Agent workflow and MCP

Use [skills/vandal/SKILL.md](skills/vandal/SKILL.md) for the assertion improvement
loop. On Python 3.10+, install `project-vandal[mcp]` and launch `vandal-mcp` in a
trusted repository. Configure it as a stdio server in your MCP client.

`run_vandal(test_path, strategies, max_mutants, deadline_seconds, pytest_args)` returns the JSON report, including
pytest's exit code, and saves the JSON/HTML pair in the server working directory.
It limits each worker to 30 seconds, each call to deadline_seconds (default and maximum 600), and accepts 1 to 100
mutants per test. A deadline returns a partial report with `timed_out: true`,
retaining completed mutants rather than reading a stale report.
`get_surviving_mutants(report_path)` returns survivors with hypotheses for an agent
to inspect. Paths must stay within the working directory; report reads are capped
at 10 MiB. Arguments are passed directly to a subprocess without shell interpolation.
The server executes trusted project code and is not a sandbox for unknown tests.

## Manual API and original demo

```python
from vandal import Vandal

async with Vandal(page) as v:
    await v.apply_mutation("logic_sabotage", "#submit")
    await page.click("#submit")
    assert await page.inner_text("#message") == "Saved"
```

The existing manual API is unchanged: exceptions inside the block are recorded
as killed and propagate to the caller. Its accounting is broader than the automatic
plugin's controlled assertion/Playwright-error rule. Catch exceptions around the block if you want to
continue, as the original demo does:

```bash
python demo_vandal.py --headless
python demo_vandal.py --headed
```

`v.report()` prints manual results. `v.save_report()` writes its original JSON
list and HTML formats, separate from the automatic runner's versioned schema.

Manual `apply_mutation(..., persistent=True)` registers an init script for later
navigation and dynamic nodes, including open shadow roots. On the current page
it applies immediately; wait for the element first if necessary. `persistent=False`
only applies on the current page. Use a fresh page/context to discard init scripts.
`revert_mutation()` supports stealth_disable, ghost_element, data_sabotage and
ui_shift; logic_sabotage and slow_load have no revert script. Avoid mixing manual
mutations with automatic runs because they confound the measured mutation.

To add a custom strategy, add a JavaScript function to `VandalEngine.MUTATIONS` in
`core.py`, following the existing selector and `data-vandalized` conventions.
The automatic plugin validates strategy names against that dictionary.

## Worker reports and bounded MCP calls

Workers redirect built-in pytest file logs, pytest-html, JUnit, Allure and Playwright artifacts into their
own temporary folders, and disable pytest-cov collection so they cannot overwrite
the baseline report or coverage files. Other third-party reporters may need
project-specific configuration.

MCP `pytest_args` accepts only -k/-m expressions and local node IDs. Arguments
are passed as an array without shell interpolation. Invalid flags, outside paths,
non-finite deadlines, and deadlines above 600 seconds are rejected before pytest.
The plugin atomically checkpoints reports after completed mutants. On a deadline,
MCP terminates the process tree and returns the latest checkpoint with
`timed_out: true`; a deadline during the baseline may return an empty report.
The partial score covers only completed mutants, so never treat it as a full run.
The saved HTML visibly labels deadline reports as incomplete and retains the
completed mutant results.

Hints use observed Playwright assertions in event order. Python assert statements
are not traced, so a no-Playwright-assertion hint is a review prompt, not proof
that the test contains no assertions.

The adapter validates its required private hooks at --vandal configuration time.
It has been exercised with Playwright 1.60.0 and 1.64.0; the dependency range is
>=1.60,<2, not a claim that every intervening or future version was tested.
