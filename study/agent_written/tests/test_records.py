import csv
import json
import os
import re
from pathlib import Path
from string import Template

import pytest

from study.agent_written import records
from study.agent_written.isolation import scoring_envelope
from study.run_study import container_command


@pytest.fixture
def bundle(tmp_path):
    root = tmp_path / 'bundle'
    root.mkdir()
    manifest = tmp_path / 'apps.csv'
    manifest.write_text('repo,commit_sha,approved\nowned/probe,' + 'a' * 40 + ',no\n')
    def write(name, data):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return {'path': name, 'sha256': records.sha256(data)}
    suite = [write('suite/test_owned.py', b'raise RuntimeError("MUST NEVER IMPORT THIS SYNTHETIC SUITE")\n')]
    packet = {'app_name': 'Synthetic app', 'app_url': 'http://127.0.0.1:8080/', 'task_facts': 'Owned fixture facts only.'}
    prompt = records.render_prompt(packet)
    write('prompt.txt', prompt)
    data = {
        'schema_version': 1, 'run_id': 'owned-1', 'replicate': 1,
        'app': {'repo': 'owned/probe', 'commit_sha': 'a' * 40},
        'agent': {'name': 'synthetic', 'version': '1.0', 'version_pin': 'immutable',
                  'artifact_sha256': 'b' * 64, 'surface': 'synthetic', 'provider': 'owned',
                  'model': 'none', 'model_snapshot': 'synthetic-v1', 'account_plan': 'none',
                  'auth_route': 'none', 'config': write('config.json', b'{}\n')},
        'protocol_sha256': records.sha256((records.HERE / 'PROTOCOL.md').read_bytes()),
        'prompt_template_sha256': records.sha256((records.HERE / 'prompt.md').read_bytes()),
        'prompt_sha256': records.sha256(prompt), 'task_packet': packet,
        'harness': {'commit_sha': 'c' * 40, 'image_id': 'sha256:' + 'd' * 64},
        'started_at': '2026-10-21T00:00:00Z', 'ended_at': '2026-10-21T00:05:00Z',
        'generation': {'status': 'completed', 'turns': 3, 'budget_seconds': 1800,
                       'budget_turns': 30, 'cost_usd': None, 'input_tokens': None,
                       'output_tokens': None, 'failure_reason': ''},
        'suite_files': suite,
        'baseline_runs': [
            {'exit_code': 0, 'collected': 1, 'passed': 1, 'failed': 0, 'errors': 0,
             'skipped': 0, 'xfailed': 0, 'xpassed': 0, 'nodeids': ['test_owned.py::test_one'],
             'offline': True, 'suite_sha256': records.suite_digest(suite),
             'log': write('logs/baseline-' + str(i) + '.txt', b'synthetic evidence, not an actual run\n')}
            for i in range(3)]}
    def load():
        (root / 'run.json').write_text(json.dumps(data), encoding='utf-8')
        return records.load_run(root, apps_manifest=manifest)
    return root, data, manifest, load


def test_static_valid_record_never_imports_suite_or_authorizes_execution(bundle, monkeypatch):
    import subprocess
    import socket
    def forbidden(*args, **kwargs):
        raise AssertionError('validator must not execute or connect')
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    result = bundle[3]()
    assert result['baseline_valid'] is True
    assert result['execution_authorized'] is False
    assert result['version_limitation'] is False


@pytest.mark.parametrize('field,value', [('exit_code', 1), ('passed', 0), ('failed', 1),
                                      ('errors', 1), ('skipped', 1), ('xfailed', 1),
                                      ('xpassed', 1), ('offline', False)])
def test_failed_baseline_is_retained_but_not_valid(bundle, field, value):
    bundle[1]['baseline_runs'][1][field] = value
    assert bundle[3]()['baseline_valid'] is False


def test_requires_three_identical_baseline_collections(bundle):
    data, load = bundle[1], bundle[3]
    data['baseline_runs'][1]['nodeids'] = ['test_owned.py::different']
    assert 'baseline collection changed' in load()['reasons']
    data['baseline_runs'].pop()
    assert 'three consecutive baselines required' in load()['reasons']


def test_failed_generation_and_missing_suite_are_retained(bundle):
    root, data, _, load = bundle
    data['generation'].update(status='no_suite', turns=0, failure_reason='synthetic timeout')
    data['suite_files'] = []
    data['baseline_runs'] = []
    (root / 'suite/test_owned.py').unlink()
    result = load()
    assert not result['baseline_valid']
    assert 'no suite' in result['reasons']
    data['generation']['failure_reason'] = ''
    with pytest.raises(ValueError, match='needs a reason'):
        load()


def test_budget_and_zero_turn_completion_not_valid(bundle):
    data, load = bundle[1], bundle[3]
    data['ended_at'] = '2026-10-21T00:30:01Z'
    assert 'generation time budget exceeded' in load()['reasons']
    data['generation']['turns'] = 0
    assert 'completed generation recorded no assistant turns' in load()['reasons']


@pytest.mark.parametrize('key,value', [('replicate', True), ('replicate', 1.0), ('replicate', 4),
                                    ('schema_version', 2), ('ended_at', '2026-02-30T00:01:00Z'),
                                    ('ended_at', '2026-10-20T23:59:00Z')])
def test_rejects_malformed_scalar_fields(bundle, key, value):
    bundle[1][key] = value
    with pytest.raises(ValueError):
        bundle[3]()


def test_rejects_missing_unknown_fields_and_wrong_types(bundle):
    data, load = bundle[1], bundle[3]
    data['extra'] = True
    with pytest.raises(ValueError, match='unknown fields'):
        load()
    del data['extra']
    del data['run_id']
    with pytest.raises(ValueError, match='missing fields'):
        load()


@pytest.mark.parametrize('raw', [b'{"x":1,"x":2}', b'{"x":NaN}', b'\xff', b'[' * 1500])
def test_rejects_duplicate_nonfinite_and_invalid_json(raw):
    with pytest.raises(ValueError):
        records._json(raw)


@pytest.mark.parametrize('field', ['protocol_sha256', 'prompt_template_sha256', 'prompt_sha256'])
def test_rejects_frozen_hash_changes(bundle, field):
    bundle[1][field] = '0' * 64
    with pytest.raises(ValueError, match='mismatch'):
        bundle[3]()


def test_rejects_file_hash_and_app_snapshot_changes(bundle):
    root, data, _, load = bundle
    original = (root / 'config.json').read_bytes()
    (root / 'config.json').write_bytes(b'changed')
    with pytest.raises(ValueError, match='hash mismatch'):
        load()
    (root / 'config.json').write_bytes(original)
    data['app']['commit_sha'] = 'f' * 40
    with pytest.raises(ValueError, match='not uniquely listed'):
        load()


def test_baseline_digest_and_node_ids_are_validated(bundle):
    data, load = bundle[1], bundle[3]
    baseline = data['baseline_runs'][0]
    baseline['suite_sha256'] = '0' * 64
    with pytest.raises(ValueError, match='different suite bytes'):
        load()
    baseline['suite_sha256'] = records.suite_digest(data['suite_files'])
    baseline['nodeids'] *= 2
    baseline['collected'] = 2
    with pytest.raises(ValueError, match='test identities'):
        load()


def test_version_pin_limitations(bundle):
    data, load = bundle[1], bundle[3]
    data['agent']['artifact_sha256'] = None
    with pytest.raises(ValueError, match='pin is incomplete'):
        load()
    data['agent']['version_pin'] = 'recorded_hosted'
    assert load()['version_limitation'] is True
    assert load()['execution_authorized'] is False


@pytest.mark.parametrize('name', ['../secret', '/etc/passwd', 'C:/secret', 'suite/../secret',
                                'suite\\test.py', 'suite/test.py:stream', 'suite//x.py',
                                './suite/x.py', 'suite/NUL.py', 'suite/a. ', '~/.ssh/key'])
def test_rejects_unsafe_paths(bundle, name):
    bundle[1]['agent']['config']['path'] = name
    with pytest.raises(ValueError, match='unsafe'):
        bundle[3]()


def test_rejects_casefold_duplicate_and_unlisted_suite_files(bundle):
    root, data, _, load = bundle
    data['suite_files'].append(dict(data['suite_files'][0], path='SUITE/TEST_OWNED.PY'))
    with pytest.raises(ValueError, match='duplicate'):
        load()
    data['suite_files'].pop()
    (root / 'suite/unlisted.py').write_text('sentinel')
    with pytest.raises(ValueError, match='unlisted'):
        load()


@pytest.mark.parametrize('kind', ['file', 'suite_root', 'parent'])
def test_rejects_symlinks(bundle, tmp_path, kind):
    root, data, _, load = bundle
    target = tmp_path / 'target'
    try:
        if kind == 'file':
            path = root / 'config.json'
            path.rename(target)
            path.symlink_to(target)
        elif kind == 'suite_root':
            path = root / 'suite'
            path.rename(target)
            path.symlink_to(target, target_is_directory=True)
            # No listed suite paths: verify root itself is checked before traversal.
            data['suite_files'] = []
            data['baseline_runs'] = []
        else:
            path = root / 'logs'
            path.rename(target)
            path.symlink_to(target, target_is_directory=True)
    except OSError as exc:
        pytest.skip('symlink creation unavailable: ' + str(exc))
    with pytest.raises(ValueError, match='symlink|reparse'):
        load()


def test_rejects_hardlinks(bundle, tmp_path):
    root, _, _, load = bundle
    try:
        os.link(root / 'config.json', tmp_path / 'linked-config')
    except OSError as exc:
        pytest.skip('hardlink creation unavailable: ' + str(exc))
    with pytest.raises(ValueError, match='hardlinks'):
        load()


def test_rejects_oversize_files(bundle):
    root, _, _, load = bundle
    (root / 'config.json').write_bytes(b'x' * (records.MAX_FILE_BYTES + 1))
    with pytest.raises(ValueError, match='bounded'):
        load()


@pytest.mark.parametrize('url', ['https://127.0.0.1:8080/', 'http://example.com:8080/',
                               'http://user:pass@127.0.0.1:8080/', 'http://127.0.0.1/',
                               'http://127.0.0.1:8080/?token=x', 'http://[invalid'])
def test_prompt_rejects_remote_or_credential_urls(url):
    with pytest.raises(ValueError):
        records.render_prompt({'app_name': 'probe', 'app_url': url, 'task_facts': 'facts'})


def test_isolation_is_existing_factory_not_execution(tmp_path):
    image = 'sha256:' + '1' * 64
    actual = scoring_envelope(image, tmp_path / 'inputs', tmp_path / 'wheels')
    expected = container_command(image, 'agent-written-plan', tmp_path / 'inputs', tmp_path / 'wheels', 900)
    assert actual == expected
    command = ' '.join(actual)
    for flag in ['--network=none', '--read-only', '--user=10001:10001', '--cap-drop=ALL', '--pids-limit=1024']:
        assert flag in command
    with pytest.raises(ValueError):
        scoring_envelope(image, tmp_path, tmp_path, 3600)


def test_proposals_and_prompt_are_precollection_only():
    with (records.HERE / 'apps.proposed.csv').open(newline='', encoding='utf-8') as stream:
        apps = list(csv.DictReader(stream))
    assert 5 <= len(apps) <= 10
    assert all(app['approved'] == 'no' and re.fullmatch('[0-9a-f]{40}', app['commit_sha']) for app in apps)
    assert all(app['license'] in {'MIT', 'BSD-3-Clause', 'Apache-2.0'} for app in apps)
    assert all(app['repo'].split('/')[0].lower() != 'godhiraj-code' for app in apps)
    prompt = (records.HERE / 'prompt.md').read_text()
    assert 'mutation' not in prompt.lower() and 'vandal' not in prompt.lower()
    identifiers = {m.group('named') or m.group('braced') for m in Template.pattern.finditer(prompt)}
    assert identifiers == {'app_name', 'app_url', 'task_facts'}


def test_suite_digest_is_order_independent():
    files = [{'path': 'suite/a.py', 'sha256': 'a' * 64}, {'path': 'suite/b.py', 'sha256': 'b' * 64}]
    assert records.suite_digest(files) == records.suite_digest(list(reversed(files)))
