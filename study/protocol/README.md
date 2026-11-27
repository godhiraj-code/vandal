# Agent protocol track

Every coding agent gets the same task on the same pinned apps, so suites can be compared.
This sits beside the natural pool in `study/repos.csv`, which stays unchanged.

## Fixed inputs
- Apps: `apps.csv` (pinned SHAs, licenses, approval by Dhiraj Das on 2026-11-27).
  `app_path` is where the agent's working folder sits inside the repository.
- Prompt: `PROMPT.txt`, used word for word for every agent. Do not edit it between agents.
- Working folder given to the agent: a plain file snapshot of the pinned SHA with no `.git`
  history. Existing agent tests are removed first (Platelet-Movie `tests/ui/`,
  contrail `tests_browser/`). For TodoMVC the folder is `examples/javascript-es5/dist`.
- Time limit: 30 minutes wall clock per app. Standard speed, one pinned model per agent,
  recorded with the suite.
- The agent runs with no network. Python, Playwright 1.64.0, pytest-playwright 0.10.0 and
  Chromium are prepared before it starts.

## Committing a suite
Copy the agent's `tests_agent/` folder, unchanged, to
`suites/<agent>/<app>/tests_agent/`, plus `suites/<agent>/<app>/run.json` with model,
CLI version, start and end time and exit status. Raw agent logs stay outside the repo.

## Scoring
`python -m study.protocol_run print-confirm --agent <agent> --app <app>` prints the RUN token.
The `Protocol suite scoring` workflow (manual, reviewer gated) then:
1. fetches the pinned SHA and places the suite under `<app_path>/tests_agent`;
2. runs the suite 10 times on the unchanged app (`flake.json`: green runs, flaky tests,
   tests that failed every time);
3. runs Vandal mutation scoring only if all 10 runs were green.

A test is flaky when it both passed and failed across the 10 runs. Flake rate is flaky
tests divided by all tests. A suite that is not green 10 of 10 gets no mutation score.
