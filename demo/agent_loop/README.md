# A measured agent-loop example

An intentionally weak checkout test fills an input, clicks **Place order**, and
reads the result, but only asserts the page title. Vandal exposes surviving
faults. The fixed test asserts the pickup name and order confirmation.

**This is a scripted before/after example using two prewritten test files. No
live coding agent is invoked.** [agent_prompt.md](agent_prompt.md) contains the
exact prompt for trying the improvement loop with your own agent.

## Run from a fresh clone

With Python 3.9+ available, in the repository root (prefer an activated virtual
environment):

```sh
pip install -e .
playwright install chromium
python demo/agent_loop/run_demo.py
```

The three-command setup targets under two minutes on a machine with fast package
and browser downloads. Download time and missing OS browser libraries can exceed
that budget; on a minimal Linux host use `playwright install --with-deps chromium`.
No extra pytest fixture package is needed. After installation the demo serves
only `app.html` on an ephemeral loopback port and blocks off-origin browser
requests. It uses headless Chromium and requires no service or credentials.

Each run writes separate `weak/vandal_report.json`, `fixed/vandal_report.json`,
HTML reports and pytest logs under the printed `artifacts/run-*` directory.
Scores, survivors and elapsed times come from the actual run, never constants.
The runner exits nonzero on pytest failures, incomplete/unscored/error results,
different mutation candidates, or a fixed score no higher than the weak score.
The fixed pass also enforces `--vandal-min-score=100`.

Both tests select `#name`, `#checkout`, and `#status`. Default strategies produce
data sabotage on the input and result, and three click mutations on the button.
Both tests may already kill click-blocking faults through action failures;
the new outcome assertions are what detect the silent survivors. A strength
score describes this selected fault set; it does not prove application correctness.
The runner disables unrelated pytest plugins and user addopts for repeatability.

For ordinary tests or manual reports:

```sh
python -m pytest demo/agent_loop/test_weak.py demo/agent_loop/test_fixed.py
python -m pytest demo/agent_loop/test_weak.py --vandal --vandal-strict
python -m pytest demo/agent_loop/test_fixed.py --vandal --vandal-strict --vandal-min-score=100
```

## Record the terminal

Install [VHS and its ttyd/FFmpeg prerequisites](https://github.com/charmbracelet/vhs#installation).
With the same Python environment activated:

```sh
cd demo/agent_loop
vhs demo.tape
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1 demo.mp4
```

The tape produces `demo.mp4` and `demo.gif` at 1600 × 1000 with large text. It
targets a roughly 60-second social video, waits for measured completion, then
holds the final output for six seconds. It does not truncate a slower run or
invent a 60-second runtime. Measure the output with `ffprobe` before publishing;
adjust the final hold for your machine if needed. The recording tools are
optional and are not project dependencies. Generated videos and reports are
git-ignored; do not commit them.

The CI job runs the headless demo and enforces the improvement check. The wheel
uses the existing explicit `packages = ["vandal"]` allowlist, so this entire demo
folder is excluded from the installed package.
