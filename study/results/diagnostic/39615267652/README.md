# Failed pilot, not results

Retained evidence from workflow run 39615267652 at main 9303d11. The workflow
concluded success, but its repository outcomes do not qualify as study results.
No repository was rerun to prepare this archive. This directory and its diagnostic
marker are excluded by summarize.py, including when passed directly as its root.

- Contrail: archive extraction rejected a nonregular entry before its baseline.
  Pinned tree inspection identifies CLAUDE.md -> AGENTS.md (blob
  47dc3e3d863cfb5727b87d785d09abf9743c0a72); the old extractor
  rejected all links. The recorded error did not identify an individual member.
- Platelet-Movie: baseline passed; 59 mutants contain 24 errors (40.677966%),
  14 killed and 21 survived. Its historical 40% score is not a valid study score
  under the new error ceiling. The container command used --pids-limit=256;
  error details include pthread_create / Resource temporarily unavailable.
  These observations are consistent with process/thread exhaustion, but no
  sampled process census exists for this old run to establish the leak's cause.

artifact/ preserves the downloaded files, including the old report and summary;
those are historical evidence, not accepted aggregates. PROVENANCE.json records
the original ZIP hash and original/retained hash for every entry. Original status
integrity maps are retained as provenance, not rewritten to conceal redaction.
Private home paths were screened with the study redactor; no entries required
changes. All 32 retained files match the downloaded bytes. Pytest identities and
measured outcomes are preserved. Raw report metrics were checked before/after screening.
