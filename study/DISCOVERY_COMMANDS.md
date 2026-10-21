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

## Review corrections: new connector search pass

The corrected Jules author is `author:app/google-labs-jules`: 100 of 249 returned in the first page, replacing the old incorrectly scoped zero-hit observation. Historical searches above are retained as history, not reused as corrected coverage.

Copilot was read through pages 1-10 at 100/page: **1000 of 1636** results, the GitHub API cap. Devin pages 1-5 returned **all 482** results. This goes beyond the old three-page sample. Returned records overlap and are not qualified repositories.

| Query | Pages / returned |
|---|---|
| `is:pr author:app/google-labs-jules playwright pytest` | page 1, 100 / total 249 |
| `is:pr is:merged "Generated with Claude Code" in:body pytest-playwright` | page 1, 100 / total 7762 |
| `is:pr is:merged "Generated with Claude Code" in:body playwright pytest` | page 1, 100 / total 34731 |
| `is:pr head:cursor/ playwright pytest` | page 1, 100 / total 2584 |
| `is:pr "aider" playwright pytest` | page 1, 100 / total 261 |
| `is:pr "OpenHands" playwright pytest` | page 1, 100 / total 312 |
| `is:pr author:app/copilot-swe-agent playwright pytest` | page 1, 100 / total 1636 |
| `is:pr author:app/copilot-swe-agent playwright pytest` | page 2, 100 / total 1636 |
| `is:pr author:app/copilot-swe-agent playwright pytest` | page 3, 100 / total 1636 |
| `is:pr author:app/copilot-swe-agent playwright pytest` | page 4, 100 / total 1636 |
| `is:pr author:app/copilot-swe-agent playwright pytest` | page 5, 100 / total 1636 |
| `is:pr author:app/copilot-swe-agent playwright pytest` | page 6, 100 / total 1636 |
| `is:pr author:app/copilot-swe-agent playwright pytest` | page 7, 100 / total 1636 |
| `is:pr author:app/copilot-swe-agent playwright pytest` | page 8, 100 / total 1636 |
| `is:pr author:app/copilot-swe-agent playwright pytest` | page 9, 100 / total 1636 |
| `is:pr author:app/copilot-swe-agent playwright pytest` | page 10, 100 / total 1636 |
| `is:pr author:app/devin-ai-integration playwright pytest` | page 1, 100 / total 482 |
| `is:pr author:app/devin-ai-integration playwright pytest` | page 2, 100 / total 482 |
| `is:pr author:app/devin-ai-integration playwright pytest` | page 3, 100 / total 482 |
| `is:pr author:app/devin-ai-integration playwright pytest` | page 4, 100 / total 482 |
| `is:pr author:app/devin-ai-integration playwright pytest` | page 5, 82 / total 482 |
| `language:Python "playwright.sync_api"` | page 1, 100 / total 271872 |
| `language:Python "playwright.sync_api" path:tests` | page 1, 100 / total 65408 |

This pass made 26 search request attempts: 23 successful pages with **2282 overlapping records**, two rate-limit failures and one internal-error failure. Copilot page 9 and Devin page 1 each returned a secondary-rate-limit 403; one retry per denied request after the server-requested cooldown succeeded. The page-fixture query `language:Python "def test_" "page" "pytest" path:tests` returned connector internal error -32603; no results or coverage are claimed for that query. Python import searches succeeded. No alternate credentials were acquired.

The live CLI was actually attempted again: `.venv\Scripts\python.exe -m study.find_repos --mode agent-prs --pages 10 --output ../revision-live-candidates.csv`; argparse exited 2 before network for absent GITHUB_TOKEN. No live output file was produced. The searches above came from the connector; actual local static_screen/pr_provenance functions analyzed the cached pinned sources.

The token-based CLI now supports corrected Jules, merged Claude-footer PRs (including Markdown-linked Claude Code), Cursor branches, aider/OpenHands PR and co-author signals, and a code mode. Default pagination is 10 pages at 100/page, capped at 1000; a 403/429 stops all discovery without automatic retry. Branch/keyword/code-only hits remain unresolved guidance, not agent-authorship proof. A selected test diff plus verified agent PR/body evidence is still required. Call counts, permissive licensing and offline feasibility must pass person review before inclusion.

A token holder can reproduce with `python -m study.find_repos --mode all --pages 10 --output study/candidates.review.csv`; this writes unapproved review leads, not approvals or an execution manifest. See discovery-review-corrections.json for all returned identities, failures, sampled PR changes and source hashes.
