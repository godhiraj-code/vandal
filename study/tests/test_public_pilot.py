import hashlib
import json
import sys
from pathlib import Path

import pytest

from study.worker import install_summary, validate_recipe


@pytest.mark.parametrize('seconds', [True, 0, 29, 3601, 900.5, '900'])
def test_recipe_rejects_invalid_budget(seconds):
    with pytest.raises(ValueError, match='seconds'):
        validate_recipe({'test_paths': ['test_ui.py'], 'seconds': seconds})


@pytest.mark.parametrize('seconds', [None, 1800])
def test_recipe_budget_reaches_runner_without_public_execution(tmp_path, monkeypatch, seconds):
    from test_harness import candidate
    from study.common import write_rows
    from study.run_study import confirmation, main
    row = candidate()
    row.update(approved='yes', reviewer='Owned test', reviewed_at='2026-10-21T00:00:00Z')
    manifest = tmp_path / 'repos.csv'
    write_rows(manifest, [row])
    (tmp_path / 'recipes').mkdir()
    recipe = {'test_paths': ['tests/test_ui.py']}
    if seconds is not None:
        recipe['seconds'] = seconds
    (tmp_path / row['recipe']).write_text(json.dumps(recipe))
    wheels = tmp_path / 'wheels'
    wheels.mkdir()
    monkeypatch.setattr(sys, 'argv', ['run_study', '--repos', str(manifest), '--confirm', confirmation(manifest),
        '--image', 'sha256:' + 'a' * 64, '--wheelhouse', str(wheels), '--results', str(tmp_path / 'out')])
    seen = []
    def fake_run(*args, **kwargs):
        seen.append(args[5])
        return {'status': 'skipped', 'reason': 'owned mock', 'cleanup': {'exit_code': 0}}
    monkeypatch.setattr('study.run_study.run_one', fake_run)
    main()
    assert seen == [seconds or 900]


@pytest.mark.parametrize('exit_code', [0, 1])
def test_harness_install_summary_records_measured_success_and_failure(tmp_path, exit_code):
    lock = tmp_path / 'harness.lock'
    lock.write_bytes(b'owned==1 --hash=sha256:abc\n')
    actual = install_summary({'exit_code': exit_code, 'seconds': 3.125, 'timed_out': False,
                              'log_limited': False, 'command': ['private/path']}, lock)
    assert actual['exit_code'] == exit_code and actual['seconds'] == 3.125
    assert actual['lock_sha256'] == hashlib.sha256(lock.read_bytes()).hexdigest()
    assert 'private' not in json.dumps(actual)


def test_archived_pilot_bytes_match_manifest():
    root = Path(__file__).resolve().parents[1] / 'results/public/39639203251'
    manifest = json.loads((root / 'ARTIFACT_MANIFEST.json').read_text(encoding='utf-8'))
    assert len(manifest['entries']) == 42
    for entry in manifest['entries']:
        data = (root / 'artifact' / entry['path']).read_bytes()
        assert len(data) == entry['size']
        assert hashlib.sha256(data).hexdigest() == entry['sha256']
    internal = 0
    for status_path in (root / 'artifact/study/results/public').glob('*/status.json'):
        status = json.loads(status_path.read_text(encoding='utf-8'))
        for name, expected in status['artifact_sha256'].items():
            assert hashlib.sha256((status_path.parent / name).read_bytes()).hexdigest() == expected
            internal += 1
    assert internal == 35


def test_static_survivor_breakdown_matches_all_raw_survivors():
    import csv
    from collections import Counter
    root = Path(__file__).resolve().parents[1] / 'results/public/39639203251'
    with (root / 'SURVIVORS.csv').open(encoding='utf-8', newline='') as stream:
        classified = list(csv.DictReader(stream))
    report = json.loads((root / 'artifact/study/results/public/tegataiprime__Platelet-Movie__14664611814b/vandal_report.json').read_text())
    actual = {(t['nodeid'], m['strategy'], m['selector']) for t in report['tests']
              for m in t['mutants'] if m['status'] == 'survived'}
    assert len(classified) == len(actual) == 29
    assert {(r['nodeid'], r['strategy'], r['selector']) for r in classified} == actual
    assert Counter(r['category'] for r in classified) == {
        'test_local_gap': 2, 'visibility_scope_oracle_mismatch': 16,
        'unasserted_label_fixture_scope': 8, 'scenario_equivalent_validation_predicate': 3}
    assert all(r['before'] == 'passed' and r['after'] == 'not_run' for r in classified)


def test_pilot_summary_rounds_display_only(tmp_path, monkeypatch):
    from study.common import read_rows
    from study.pilot import summary
    manifest = Path(__file__).resolve().parents[1] / 'repos.csv'
    identity = read_rows(manifest)[1]
    raw_score = 100 * 30 / 59
    row = dict(identity, eligible=True, score=raw_score, n_scored=59, status='completed', run_path='missing')
    monkeypatch.setattr('study.pilot.read_results', lambda _: ([row], []))
    destination = tmp_path / 'summary.md'
    summary(manifest, tmp_path, tmp_path / 'image', destination)
    assert '50.8 (n=59)' in destination.read_text() and row['score'] == raw_score
