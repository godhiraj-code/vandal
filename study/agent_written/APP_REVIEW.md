# App proposals: static review, no executions

Reviewed 2026-10-21. Five proposals, zero approved apps, zero runtime-qualified
apps. The ranks order preparation risk, not expected scores. All start commands
in `apps.proposed.csv` are proposed future commands, never executed during this
review. Exact source URLs and inspected paths are recorded in
`app_review_evidence.json`; the CSV contains full commit SHAs and license URLs.
The selected workflow and its assets must pass a future, separately approved
offline qualification before the app can enter the frozen cohort.

Different repository owners and original license credits are visible. This does
not prove that Dhiraj never contributed. The available GitHub read connector
rejected the author-only commit-search endpoint as unsupported (HTTP 400,
INVALID_ARGUMENT). No complete author-search coverage is claimed. Dhiraj must
confirm no authorship for each selected app before inclusion. No substitute
credentials or execution were used.

## Ranked proposals

1. **[TodoMVC](https://github.com/tastejs/todomvc/tree/ff43b02e59dfa604386bb382034b2cd07c2bcd8a), MIT.**
   Select `examples/javascript-es5/`, not the absent `examples/vanillajs/`.
   The HTML references local JS and local `node_modules/todomvc-common` and
   `todomvc-app-css` assets. Stage these at reviewed versions and audit their
   asset closure before collection; do not install dynamically during a run.
   Serve that directory with the Python HTTP server on loopback. Proposed task
   facts: add, edit, complete, filter and delete todos, and local persistence.
   Reset localStorage per baseline. The source credits Oscar Godson,
   Christoph Burgmer and the TodoMVC team. Repository license metadata says
   NOASSERTION, but the inspected `license.md` explicitly supplies MIT terms
   unless otherwise stated; dependency notices still need review.
2. **[2048](https://github.com/gabrielecirulli/2048/tree/478b6ec346e3787f589e4af751378d06ded4cbbc), MIT.**
   The HTML references local scripts/styles; external attribution anchors are
   outside the selected workflow. Audit the stylesheet/font closure and serve
   the repository with the same loopback static server. Proposed task facts:
   start/restart, keyboard movement, score and tile-state invariants, persistence.
   Random tile placement makes a fixed winning trajectory inappropriate. Record
   this stochastic limitation rather than modifying the game for an agent.
   Keyboard-heavy interaction may offer fewer observable mutation sites; report
   the actual denominator if later scored. License credits Gabriele Cirulli.
3. **[impress.js](https://github.com/impress/impress.js/tree/b44b9694b41fd2c076c3d1ad7a0c3e0cea9eb262), MIT.**
   Select `examples/3D-positions/index.html`, served from the repository root.
   It references local CSS and committed `js/impress.js`; the README says the
   runtime does not require Node/npm. Proposed task facts: navigate steps,
   active-step state, overview, hash navigation and returning to a step. Verify
   transitions and keyboard behavior offline. The alternative 2D-navigation
   demo has Flickr image credits whose reuse scope was not established and is
   not selected. This is a narrow presentation app, not an independent content
   editor. License credits Bartek Szopka.
4. **[TiddlyWiki](https://github.com/TiddlyWiki/TiddlyWiki5/tree/999763abb080adc68595dbee7526f315da28a044), BSD-3-Clause.**
   Stage a pinned Node runtime and a reviewed copy of `editions/server` at
   `/work/wiki`; run the repository's `tiddlywiki.js` on loopback. The selected
   edition declares local tiddlyweb/filesystem/highlight plugins and local
   themes. Proposed task facts: create/edit/search/tag/delete tiddlers and local
   persistence. Reset the writable wiki tree between baselines. No remote
   plugins, synchronization or online imports belong in the task. Metadata is
   NOASSERTION; the inspected `license` text supplies BSD-3-Clause terms and
   credits Jeremy Ruston/UnaMesa. Offline dependency/plugin closure remains
   unverified.
5. **[Memos](https://github.com/usememos/memos/tree/334925a5f10c58e17b66dbc67fd4b27ed0d3fa8e), MIT.**
   Highest preparation risk: stage a hash-pinned Go binary plus its built local
   frontend. The inspected Dockerfile requires Go 1.27.2 and frontend build
   steps; no build occurred. CLI source confirms `--addr`, `--port`, `--driver`
   and `--data`; choose loopback, SQLite and `/work/memos-data`. Do not reuse the
   upstream root/chown entrypoint: the existing harness requires uid 10001.
   Proposed task facts: local account setup, memo CRUD, search, tags and local
   visibility controls. Use synthetic credentials and fresh local SQLite state.
   Disable external integrations by selecting the local workflow, not by
   stubbing app behavior. SSO, email, remote storage and webhooks are out of
   scope. License credits Memos; build closure and startup remain unverified.

## Rejected or deferred leads

| Lead and inspected snapshot | Decision and evidence limit |
| --- | --- |
| [excalidraw/excalidraw](https://github.com/excalidraw/excalidraw/tree/1d4dc2c0e6e476911d0760e9c3cf3694f2d43384), MIT | Deferred: inspected app HTML has external font preconnects, SimpleAnalytics and a conditional app-domain redirect. The local build/config/asset closure was not established. These are source risks, not observed runtime failures. |
| [hakimel/reveal.js](https://github.com/hakimel/reveal.js/tree/e240e175232fa2de660a02bc0d7bf5f655b159bb), MIT metadata | Deferred as a second presentation family to avoid overstating diversity. No deeper source or offline qualification claimed. |
| [jgraph/drawio](https://github.com/jgraph/drawio/tree/17b367b91dbab91804f852645788d7ffb46dcb79), Apache-2.0 metadata | Deferred: editor/build/service preparation is larger than the initial shortlist; dependency closure was not reviewed. |
| [chvin/react-tetris](https://github.com/chvin/react-tetris/tree/89435b72f127b67f95870c515a130cbff38fd7cf) | Hold: metadata supplied no recognized license, and source licensing/build closure were not established. Absence of metadata is not a claim that no license exists. |

## Review before collection

Dhiraj chooses the final 5–10 apps, confirms no authorship, approves exact task
facts and reset rules, and authorizes future preparation/qualification. If a
proposal fails offline or license qualification, replace it and date the
protocol amendment **before** collecting agent suites. Do not drop apps after
seeing scores. Freeze the approved cohort and all setup hashes separately from
this unapproved proposal CSV. App licensing, third-party asset licensing and
agent service terms are separate reviews.
