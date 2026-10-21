# Discovery transport and coverage

Actual live CLI attempt (before connector discovery):

```powershell
.venv\Scripts\python.exe -m study.find_repos --mode agent-prs --pages 1 --output study/discovery-live-candidates.csv
```

It exited through argparse (exit 2) before network because GITHUB_TOKEN was absent. No candidate output was written by that command. No credentials were acquired. This is not a successful authenticated CLI crawl.

The actual find_repos.test_files, parse_candidate, static_screen and local_import_paths functions were then run locally against cached, pinned source text returned by the GitHub connector. Target code was never imported or executed. This separately verifies parser execution, not live CLI transport.

Read-only connector calls: `github_search_commits(query=..., topn=...)`; `github_fetch(url="https://api.github.com/search/issues?q=<URL-encoded-query>&per_page=30&page=N")` for PR searches, and pinned commit/tree/raw-file reads. Generic commit-search/license fetch endpoint shapes returned unsupported-operation errors; supported search and pinned file reads supplied the data. Missing licenses are not treated as authenticated API successes.

| Search | Route / page | Returned records |
|---|---|---:|
| `playwright pytest "Co-Authored-By: Claude"` | commit topn=30 | 30 |
| `playwright pytest "Co-authored-by: Cursor"` | commit topn=30 | 30 |
| `playwright pytest "Co-authored-by: Copilot"` | commit topn=30 | 30 |
| `playwright "set_content" "Co-Authored-By: Claude"` | commit topn=25 | 25 |
| `playwright "offline" "Co-Authored-By: Claude"` | commit topn=25 | 25 |
| `playwright "Co-authored-by: Cursor" "test" "html"` | commit topn=25 | 25 |
| `playwright pytest "offline" "Co-Authored-By: Claude"` | commit topn=20 | 20 |
| `playwright pytest "set_content"` | commit topn=20 | 20 |
| `playwright pytest "Co-Authored-By: Claude Code"` | commit topn=20 | 20 |
| `playwright pytest "file://"` | commit topn=20 | 20 |
| `playwright pytest "Co-authored-by: Claude" "static"` | commit topn=20 | 20 |
| `playwright pytest "Co-authored-by: Cursor" "local"` | commit topn=20 | 20 |
| `playwright pytest "Co-authored-by: Copilot" "offline"` | commit topn=20 | 20 |
| `playwright pytest "Co-authored-by: Claude" "browser tests"` | commit topn=20 | 20 |
| `is:pr author:app/copilot-swe-agent playwright pytest` | PR page=1, per_page=30 | 30 |
| `is:pr author:app/devin-ai-integration playwright pytest` | PR page=1, per_page=30 | 30 |
| `is:pr author:google-labs-jules playwright pytest` | PR page=1, per_page=30 | 0 |
| `playwright pytest "Co-authored-by: Claude" "MIT"` | commit topn=30 | 30 |
| `playwright pytest "Co-authored-by: Cursor" "offline"` | commit topn=30 | 30 |
| `playwright pytest "Co-authored-by: Copilot" "static"` | commit topn=30 | 30 |
| `playwright pytest "Co-authored-by: Claude" "no network"` | commit topn=30 | 30 |
| `repo:straussbastian/ai_flashcards_for_school "Co-Authored-By" "browser"` | commit topn=10 | 9 |
| `repo:tolgaguensal-lab/tatilvakti "Co-Authored-By" "e2e"` | commit topn=10 | 10 |
| `repo:hibbertda/lego_manager "Co-Authored-By" "Playwright"` | commit topn=10 | 5 |
| `is:pr author:app/devin-ai-integration playwright pytest` | PR page=2, per_page=30 | 30 |
| `is:pr author:app/devin-ai-integration playwright pytest` | PR page=3, per_page=30 | 30 |
| `is:pr author:app/copilot-swe-agent playwright pytest` | PR page=2, per_page=30 | 30 |
| `is:pr author:app/copilot-swe-agent playwright pytest` | PR page=3, per_page=30 | 30 |

Claude, explicit Claude Code, Cursor, Copilot, corrected `author:app/devin-ai-integration`, and Jules were all searched. The commit connector exposes topn, not page; broader targeted queries and repository-specific follow-ups were used. The PR connector fetch was paged through three pages for Copilot and Devin.

Totals are returned records with overlap, not unique repositories or samples. The audit stores every hit and the sampled metadata/source gates. Further hits remain unreviewed; no completeness or absence-of-suitable-repositories claim is made. One new proposal satisfies the current static filter; its installation and baseline remain unvalidated.
