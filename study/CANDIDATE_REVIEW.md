# Public candidates for one bundled person review

Read-only inspection on 2026-10-21. **None is approved or executed.** These meet the
public/license/Python pytest/Playwright/test-authorship evidence criteria; runtime
eligibility remains unverified. Stored commit patches and license blobs are in
`candidate-evidence.json`. Recipes are proposals for review, not execution approval.

| Repository and pinned SHA | Exact test evidence | License at SHA | Execution caveats |
|---|---|---|---|
| dodjango/tasmota-auto-updater — `f08e6c7236a0f3e9ba3e3a111037677192566688` | [Commit adds tests/e2e/test_smoke.py and its local fake-device server fixture; Claude Opus co-author](https://github.com/dodjango/tasmota-auto-updater/commit/f08e6c7236a0f3e9ba3e3a111037677192566688). Test navigates app UI and checks heading, cards and navbar. | [MIT](https://github.com/dodjango/tasmota-auto-updater/blob/f08e6c7236a0f3e9ba3e3a111037677192566688/LICENSE) | App dependencies and any CDN assets need inspection; offline behavior unknown. No real devices or secrets will be supplied. |
| tkoyama010/pyvista-js — `0a1492943dbf50e379bffa8ed1794e603ccdcc44` | [Commit adds tests/test_browser_rendering.py, pytest browser fixtures and dependencies; anthropic-code-agent co-author](https://github.com/tkoyama010/pyvista-js/commit/0a1492943dbf50e379bffa8ed1794e603ccdcc44). Browser renders generated plots. Mixed human/agent authorship is visible. | [BSD-3-Clause](https://github.com/tkoyama010/pyvista-js/blob/0a1492943dbf50e379bffa8ed1794e603ccdcc44/LICENSE) | Test explicitly checks unpkg CDN and skips without access. Expected offline exclusion unless a separately reviewed protocol supplies pinned assets; no network relaxation is proposed. Requires Python >=3.12. |
| PRIDA-TAKON/debim — `1d3b18e827cab56fc4376649f11c46d0415e09cd` | [Commit adds browser transform tests in tests/test_docs_viewer.py and Playwright benchmark; google-labs-jules co-author](https://github.com/PRIDA-TAKON/debim/commit/1d3b18e827cab56fc4376649f11c46d0415e09cd). Selected tests launch headless Chromium against generated class-directory HTML. | [MIT](https://github.com/PRIDA-TAKON/debim/blob/1d3b18e827cab56fc4376649f11c46d0415e09cd/LICENSE) | Heavy geometry dependencies, generated web assets and mutation applicability require baseline validation. Recipe selects only the two added browser tests with -k. |

Bundled review scope: choose candidate identities/SHAs and test selections, confirm
the evidence interpretation and license, approve exact install recipes plus reviewed
dependency wheel hashes and immutable image ID, then approve executing that concrete
manifest inside the offline container. These candidates may yield only exclusions;
do not substitute successful-looking scores or enable external networking silently.

Other inspected leads were rejected: brianroberg/regression-kit,
Ak79p/playwright-automation-playground and barouu78-wq/teranga-ai lacked a verifiable
license in the inspected state. Backend pytest plus TypeScript Playwright projects,
dependency-only bot commits, and agent changes unrelated to browser tests were not
accepted as test-authorship evidence. No human control is inferred from absent tags.
