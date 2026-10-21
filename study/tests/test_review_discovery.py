import json
import urllib.error
from pathlib import Path

import pytest

from study.find_repos import PR_AUTHORS, QUERIES, discover, pr_provenance, search_specs


def test_corrected_and_additional_queries_are_rerunnable():
    specs = list(search_specs('all', QUERIES))
    queries = '\n'.join(q for _, q, _ in specs)
    assert 'app/google-labs-jules' in PR_AUTHORS
    for term in ('author:app/google-labs-jules', 'Generated with Claude Code', 'is:merged',
                 'head:cursor/', 'aider', 'OpenHands', 'playwright.sync_api', '"page"'):
        assert term in queries
    assert len(list(search_specs('code', []))) == 2


@pytest.mark.parametrize('pr,expected', [
    ({'head': {'ref': 'cursor/tests'}, 'body': 'Testing with pytest'}, 'guidance_only'),
    ({'body': 'Discuss OpenHands and aider'}, 'guidance_only'),
    ({'body': 'Generated with Claude Code', 'merged_at': '2026-10-21'}, 'agent_pr'),
    ({'body': 'Generated with [Claude Code](https://claude.com/claude-code)', 'merged_at': '2026-10-21'}, 'agent_pr'),
    ({'body': 'Generated with Claude Code', 'merged_at': None}, 'guidance_only'),
    ({'user': {'login': 'google-labs-jules[bot]'}}, 'agent_pr'),
    ({'body': 'Co-authored-by: aider <bot@example.invalid>'}, 'agent_pr'),
])
def test_search_keyword_or_branch_is_not_alone_authorship(pr, expected):
    assert pr_provenance(pr)[0] == expected


def test_search_paginates_beyond_three_pages_and_records_cap():
    calls = []
    class API:
        def get(self, endpoint, **kw):
            if endpoint == 'search/commits':
                calls.append(kw)
                return {'items': [{}] * 100, 'total_count': 1200}
            raise AssertionError(endpoint)
    rows, audit = discover(API(), ['owned query'], 10)
    assert rows == []
    assert [c['page'] for c in calls] == list(range(1, 11))
    assert all(c['per_page'] == 100 for c in calls)
    assert any('1000-result' in r.get('reason', '') for r in audit)


@pytest.mark.parametrize('code', [403, 429])
def test_discovery_stops_when_candidate_read_is_rate_limited(code):
    calls = []
    class API:
        def get(self, endpoint, **kw):
            calls.append(endpoint)
            if endpoint == 'search/commits':
                return {'items': [{'repository': {'full_name': 'owned/probe'}, 'sha': 'a' * 40}] * 2}
            raise urllib.error.HTTPError('https://api.github.com/' + endpoint, code, 'limited', {}, None)
    rows, audit = discover(API(), ['first', 'second'], 10)
    assert rows == []
    assert calls == ['search/commits', 'repos/owned/probe']
    assert 'no automatic retries' in audit[-1]['reason']


@pytest.mark.parametrize('routes', [
    [('code_only', 'conftest.py'), ('code_only', 'tests/test_app.py')],
    [('code_only', 'tests/test_app.py'), ('guidance_only', 'AGENTS.md')],
    [('guidance_only', 'CLAUDE.md'), ('code_only', 'tests/test_app.py')],
])
def test_each_code_file_and_provenance_mode_is_screened(monkeypatch, routes):
    from study import find_repos
    sha = 'a' * 40
    sources = {
        'conftest.py': 'from playwright.sync_api import Page\n',
        'tests/test_app.py': 'from playwright.sync_api import Page\ndef test_app(page: Page): page.locator("button").click()\n',
        'AGENTS.md': 'Write browser tests.',
        'CLAUDE.md': 'Write browser tests.',
    }
    screened = []
    parse = find_repos.parse_candidate
    def record_screen(*args, **kwargs):
        screened.append(kwargs['evidence_url'])
        return parse(*args, **kwargs)
    specs = [('code', str(i), kind) for i, (kind, _) in enumerate(routes)]
    monkeypatch.setattr(find_repos, 'search_specs', lambda *_: iter(specs))
    monkeypatch.setattr(find_repos, 'parse_candidate', record_screen)
    monkeypatch.setattr(find_repos, 'pinned_license', lambda *_: {
        'license': {'spdx_id': 'MIT'}, 'html_url': f'https://github.com/owned/probe/blob/{sha}/LICENSE'})
    monkeypatch.setattr(find_repos, 'sources_at', lambda api, repo, pin, paths: {p: sources[p] for p in paths})
    monkeypatch.setattr(find_repos, 'supporting_at', lambda *_: {})
    monkeypatch.setattr(find_repos, 'tree_tests', lambda *_: ['tests/test_app.py'])
    class API:
        def get(self, endpoint, **kw):
            if endpoint == 'search/code':
                path = routes[int(kw['q'])][1]
                return {'items': [{'repository': {'full_name': 'owned/probe'}, 'path': path}]}
            if endpoint == 'repos/owned/probe':
                return {'full_name': 'owned/probe', 'private': False, 'default_branch': 'main'}
            if endpoint.startswith('repos/owned/probe/commits/'):
                return {'sha': sha, 'commit': {'message': ''}, 'files': []}
            raise AssertionError(endpoint)
    rows, audit = discover(API(), [], 1, mode='all')
    assert screened == [f'https://github.com/owned/probe/blob/{sha}/{path}' for _, path in routes]
    assert len(rows) == (1 if routes[0][1] == 'conftest.py' else 2)
    assert all(json.loads(row['test_paths']) == ['tests/test_app.py'] for row in rows)
    assert not any('error' in entry for entry in audit)


def test_meow_fetch_uses_reviewed_profile_without_credentials(tmp_path, monkeypatch):
    from study.wheelhouse import fetch
    monkeypatch.setenv('GITHUB_TOKEN', 'owned sentinel')
    def fake_run(command, **kw):
        assert any(c.endswith('requirements-meow-now.lock') for c in command)
        assert any(c.endswith('constraints-meow-now.txt') for c in command)
        assert '--require-hashes' in command and '--only-binary=:all:' in command
        assert 'GITHUB_TOKEN' not in kw['env'] and 'install' not in command
    monkeypatch.setattr(fetch.subprocess, 'run', fake_run)
    monkeypatch.setattr(fetch, 'manifest', lambda directory, metadata: metadata)
    metadata = fetch.download(tmp_path/'wheels', 'meow-now')
    assert len(metadata) == 31
    root = Path(fetch.__file__).parent
    lock = (root/'requirements-meow-now.lock').read_text()
    for wheel in metadata:
        assert f"{wheel['name']}=={wheel['version']} --hash=sha256:{wheel['sha256']}" in lock
        assert wheel['license'] != 'UNKNOWN'


def test_code_mode_writes_combined_paths_counts_and_risks(tmp_path, monkeypatch):
    import sys
    from study import find_repos
    from study.common import read_rows
    sha = 'a' * 40
    sources = {
        'tests/test_a.py': 'from playwright.sync_api import Page\nfrom helpers import Login\ndef test_a(page: Page):\n Login(page).submit()\n page.locator("input").fill("a")\n',
        'tests/test_b.py': 'from playwright.sync_api import Page\nfrom helpers import Login\ndef test_b(page: Page):\n Login(page).submit()\n page.get_by_text("ok").click()\n page.goto("https://example.invalid")\n',
    }
    support = {'helpers.py': 'import shutil\nfrom playwright.sync_api import Page\nclass Login:\n def __init__(self, page: Page): self.page = page\n def submit(self):\n  shutil.which("docker")\n  self.page.get_by_role("button").click()\n'}
    class API:
        def get(self, endpoint, **kw):
            if endpoint == 'search/code':
                return {'items': [{'repository': {'full_name': 'owned/probe'}, 'path': p} for p in sources]}
            if endpoint == 'repos/owned/probe':
                return {'full_name': 'owned/probe', 'private': False, 'default_branch': 'main'}
            if endpoint.startswith('repos/owned/probe/commits/'):
                return {'sha': sha, 'commit': {'message': ''}, 'files': []}
            raise AssertionError(endpoint)
    monkeypatch.setattr(find_repos, 'GitHub', lambda _: API())
    monkeypatch.setattr(find_repos, 'search_specs', lambda *_: iter([('code', 'owned query', 'code_only')]))
    monkeypatch.setattr(find_repos, 'pinned_license', lambda *_: {
        'license': {'spdx_id': 'MIT'}, 'html_url': f'https://github.com/owned/probe/blob/{sha}/LICENSE'})
    monkeypatch.setattr(find_repos, 'sources_at', lambda api, repo, pin, paths: {p: sources[p] for p in paths})
    monkeypatch.setattr(find_repos, 'supporting_at', lambda *_: support)
    monkeypatch.setenv('GITHUB_TOKEN', 'owned fake transport sentinel')
    output = tmp_path / 'candidates.csv'
    monkeypatch.setattr(sys, 'argv', ['find_repos', '--mode', 'code', '--pages', '1', '--output', str(output)])
    find_repos.main()
    rows = read_rows(output)
    assert len(rows) == 1
    assert json.loads(rows[0]['test_paths']) == sorted(sources)
    assert rows[0]['observable_calls'] == '6'  # Shared page object counted once, not 4 + 4.
    assert json.loads(rows[0]['offline_risk']) == find_repos.static_screen(sources, support)['offline_risk']
    assert len(json.loads(rows[0]['offline_risk'])) == 2
    assert all(path in rows[0]['evidence_detail'] for path in sources)
    assert rows[0]['approved'] == 'no' and rows[0]['group'] == 'unresolved'
