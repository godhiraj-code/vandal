# Offline preparation plans — not executed; execution approval pending

These plans refer only to the three snapshots below. They are source-derived plans,
not installation or baseline results. No candidate has been built, imported, collected
or run. Contrail and Platelet-Movie have explicit inclusion approval in repos.csv; execution remains separately gated. Talkvote is unapproved. Dependency versions/hashes and the Dockerfile must be reviewed before action-time
execution; the workflow records its freshly built immutable image ID.

Use a disposable acquisition environment without host credentials for preparation.
Download platform-compatible **wheels only** for Python dependencies; do not fall
back to source builds on the host. Retain a complete lock of transitive versions,
wheel hashes and licenses. Candidate builds/install hooks, npm lifecycle scripts
and tests are code execution and require the separately approved container action.
The runtime remains network none; missing artifacts fail installation or baseline.
Do not run the commands below as part of static discovery.

## 1. atdr/contrail

Snapshot: `2465e368b7658bd23f0d41f1473c114db3573005`.
[Declared dependencies](https://github.com/atdr/contrail/blob/2465e368b7658bd23f0d41f1473c114db3573005/pyproject.toml),
[fixture](https://github.com/atdr/contrail/blob/2465e368b7658bd23f0d41f1473c114db3573005/tests_browser/conftest.py).

Use the study image's Python 3.12/Chromium with the pinned Playwright 1.64.0 and
pytest-playwright 0.10.0. `contrail.json` installs `.[browser]` offline in the fresh
venv. Pre-provision wheels satisfying Hatchling (build backend), requests>=2.34.2,
icalendar>=7.3.0, airportsdata>=20260902 and pytest-playwright>=0.9.0, including every
transitive dependency. Resolve against the actual image interpreter/platform, retain
the chosen versions and hashes, and reject a missing binary wheel. The already
bundled harness pytest/Playwright wheels must remain compatible with that solution.

The reviewed 17-wheel lock and fetch script now live under study/wheelhouse/; hashes
were measured from binary downloads without installation/imports. See PILOT.md for
the clean, hash-enforced download and artifact procedure.

The dependency-acquisition step is equivalent to `pip download --only-binary=:all:`
for these requirements, using a constraints file matching the base image; it is not
`pip wheel .` on the candidate. Supply only the reviewed wheels via `--wheelhouse`.
The worker's existing offline pip install builds the pinned candidate **inside** the
approved container. The fixture renders synthetic CSV rows into file URLs; renderer
assets are vendored. Its request guard aborts HTTP and fails non-local requests.
No Node build, live TripIt data, airport API or credentials are needed by this selected
path. This conclusion is source inspection, not an observed passing baseline.

## 2. tegataiprime/Platelet-Movie

Snapshot: `14664611814b126289f291ad24ee294102efb07c`.
[UI fixture](https://github.com/tegataiprime/Platelet-Movie/blob/14664611814b126289f291ad24ee294102efb07c/tests/ui/conftest.py),
[project configuration](https://github.com/tegataiprime/Platelet-Movie/blob/14664611814b126289f291ad24ee294102efb07c/pyproject.toml).

Use `platelet.json`: no project installation or extra requirements. The selected
test imports only Playwright, and its conftest uses stdlib plus pytest. The owned
image already provides their pinned wheels and Chromium. No root/tests conftest was
found at this snapshot. The fixture serves the committed `site/` through a local
HTTP server and fulfills `data-*.json` from in-memory mock movie records.

Do not run the CLI/data generator, fetch TMDB data or install unrelated development
tools. If project installation becomes necessary after review, its declared wheel
requirements are click>=8.1.8, requests>=2.31.0 and poetry-core>=2,<3 plus transitives;
that would be a recipe change requiring renewed review, not an automatic fallback.

**Known offline deviation:** site/index.html:142 contains a remote themoviedb.org logo image and
external hyperlinks. The selected assertions concern local controls/movie rows;
they do not explicitly assert logo loading. Network none will block the remote
request. Whether that affects the baseline is unknown. Do not vendor,
stub or remove it; any such intervention must be recorded as a method change.

## 3. elenakulgavaya/talkvote

Snapshot: `8dc73df8b4fcd3ce6c7434a0b3793e210eb5393c` only.
[Backend manifest](https://github.com/elenakulgavaya/talkvote/blob/8dc73df8b4fcd3ce6c7434a0b3793e210eb5393c/src/backend/package.json),
[backend lock](https://github.com/elenakulgavaya/talkvote/blob/8dc73df8b4fcd3ce6c7434a0b3793e210eb5393c/src/backend/package-lock.json),
[frontend lock](https://github.com/elenakulgavaya/talkvote/blob/8dc73df8b4fcd3ce6c7434a0b3793e210eb5393c/src/frontend/package-lock.json),
[fixture](https://github.com/elenakulgavaya/talkvote/blob/8dc73df8b4fcd3ce6c7434a0b3793e210eb5393c/tests/contracts/frontend/conftest.py).

Python uses the image's pytest/pytest-playwright wheels; there is no Python app to
install. Node must satisfy Vite's locked engine range `^20.19.0 || >=22.12.0`.
Choose an official Linux Node release satisfying that range and record its archive
checksum/license in a derived immutable study image. Preserve the pinned source.

Prepare two complete Linux package trees from their separate lockfiles, including
optional platform binaries, and record every lock integrity value plus artifact
SHA256. Backend lock includes Express 4.22.2, tsx 4.23.0, TypeScript 5.9.3 and Vite
5.4.21. Frontend lock includes Vite 8.1.4, @vitejs/plugin-react 6.0.3, React 19.2.7
and TypeScript 6.0.3. These are observed lock versions, not a new resolution.

Future preparation uses each lock's `npm ci --offline --ignore-scripts --no-audit
--no-fund` with a previously reviewed complete npm cache. Review any required esbuild,
Rolldown or other lifecycle setup individually before executing it in a disposable
container; never enable network to recover a missing optional binary. The app fixture
starts `npx tsx src/backend/src/server.ts` and `npx vite src/frontend` from repository
root. There is **no root package manifest/lock**. Simply installing dependencies in
each subdirectory will not make those root npx commands reproducible.

The reviewed staging design must copy the backend package tree to
`/work/source/src/backend/node_modules`, the frontend tree to
`/work/source/src/frontend/node_modules`, and provide root command resolution for
exactly the locked tsx and frontend Vite binaries (without npx acquisition). Run
the original tsx/Vite dev servers on localhost:3001/5173; a static Vite production
build alone does not satisfy this fixture. Vite cache/output must be writable in
the bounded work tmpfs. The store is in-memory; no database or external API was
found in the inspected path.

**Remaining implementation prerequisite:** the current runner accepts wheel inputs
only and deliberately has no arbitrary asset copy/setup command. It cannot yet
stage these Node trees or root command resolution. `talkvote.plan.json` records the
required preparation, rather than masquerading as an executable worker recipe.
Before approving talkvote, implement and review a bounded, hashed asset-staging
extension (or an equally reviewed derived-image worker) and validate it with an owned
Node fixture. No candidate source or tests have been executed to prepare this plan.
