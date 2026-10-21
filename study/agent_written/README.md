# Agent-written suite design and static validator

This prospective design is separate from the natural-pool descriptive case studies.
No observations have been collected. No executor, agent adapter or app launcher is
implemented or enabled. Start with PROTOCOL.md, TERMS.md and APP_REVIEW.md.

`apps.proposed.csv` is an unapproved shortlist, not a runnable manifest.
The existing study/repos.csv and its approvals are untouched. App offline readiness
and no-Dhiraj-authorship attestation remain approval gates.

Run only the owned validator tests:

```sh
python -m pytest study/agent_written/tests -q
python -m pytest study/tests -q
```

The minimal study/tests/test_agent_written.py collection bridge includes these
tests in existing Study CI without changing workflows. Tests create synthetic
files and mock evidence; they never run a candidate suite, app or coding agent.

Future frozen bundle layout (not sample results): run.json, prompt.txt, suite/*.py,
artifacts/agent-config.json and artifacts/baseline-1.log through baseline-3.log.
run.schema.json defines record fields. records.load_run reads bounded regular files,
rejects malformed/duplicate JSON fields, unsafe paths, links, unlisted suite files,
hash mismatches and app snapshot mismatches, and compares prompt/protocol hashes.
All supporting Python fixtures belong in suite/ and must be listed; v1 does not
allow extra suite data files. Pass a frozen protocol/template/manifest explicitly
when validating an older cohort; defaults use this design's checked-in inputs.

```sh
python -m study.agent_written.records /path/to/frozen-bundle
```

This command only validates data. A valid record can describe a failed run.
baseline_valid requires three consistent offline passing baseline records and a
completed in-budget generation. It is not proof those runs happened; independently
review logs. execution_authorized is always false. No automatic approval, scoring,
imports, subprocesses or network requests occur. Read only immutable bundles;
the loader is not a sandbox for a concurrently mutating hostile filesystem.

Suite digest is SHA-256 of UTF-8 JSON for suite_files sorted by path, with keys
sorted and separators (comma, colon), without whitespace. Each baseline references
that same digest. Each listed file and exact rendered prompt has its own SHA-256.
Run start/end timestamps refer to generation; baseline logs must retain their own
observed timing and ordered attempts. Missing usage/cost is null, never estimated.

isolation.scoring_envelope is pure construction of the existing container command;
it does not start Docker and is not a completed scoring adapter. A future approved
adapter must handle app setup/reset, three qualification baselines, suite overlay,
budget accounting, resource monitoring and artifact export within that envelope.
