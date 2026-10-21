import argparse
import json
import shutil
import sys
from pathlib import Path

import pytest

from study.budget import cli_seconds, recipe_seconds, validate_run_budget, validate_seconds
from study.common import paths, write_rows
from study.pilot import preflight
from study.run_study import confirmation, main
from study.worker import validate_recipe


@pytest.mark.parametrize('value', [True, False, 900.0, 29, 3601, '900'])
def test_shared_seconds_reject_invalid_types_and_range(value):
    with pytest.raises(ValueError, match='integer'):
        validate_seconds(value)
    for key in ('seconds', 'budget_seconds'):
        with pytest.raises(ValueError, match='integer'):
            validate_recipe({'test_paths': ['test_owned.py'], key: value})


@pytest.mark.parametrize('value', ['True', '900.0', '29', '3601', True, 900.0])
def test_cli_fallback_uses_same_integer_bounds(value):
    with pytest.raises(argparse.ArgumentTypeError):
        cli_seconds(value)


@pytest.mark.parametrize('value', ['30', '900', '3600'])
def test_cli_fallback_accepts_valid_integers(value):
    assert cli_seconds(value) == int(value)


def test_recipe_alias_is_compatible_but_not_ambiguous():
    assert recipe_seconds({'seconds': 1200}) == recipe_seconds({'budget_seconds': 1200}) == 1200
    assert recipe_seconds({}, 800) == 800
    with pytest.raises(ValueError, match='not both'):
        recipe_seconds({'seconds': 900, 'budget_seconds': 900})


@pytest.mark.parametrize('seconds,allowed', [(1200, True), (1201, False)])
def test_preflight_and_runner_check_whole_budget_before_any_run(tmp_path, monkeypatch, seconds, allowed):
    from test_harness import candidate
    rows = []
    (tmp_path / 'recipes').mkdir()
    for i in range(2):
        row = candidate()
        row.update(repo=f'owned/repo{i}', approved='yes', reviewer='Owned mock', reviewed_at='2026-10-21T00:00:00Z',
                   recipe=f'recipes/repo{i}.json', evidence_url=f'https://github.com/owned/repo{i}/commit/'+ 'a'*40,
                   license_url=f'https://github.com/owned/repo{i}/blob/'+ 'a'*40+'/LICENSE')
        (tmp_path / row['recipe']).write_text(json.dumps({'test_paths': paths(row['test_paths']), 'budget_seconds': seconds}))
        rows.append(row)
    manifest = tmp_path / 'repos.csv'
    write_rows(manifest, rows)
    token = confirmation(manifest)
    if allowed:
        assert len(preflight(manifest, token)) == 2
    else:
        with pytest.raises(ValueError, match='total run budget'):
            preflight(manifest, token)
    calls = []
    monkeypatch.setattr('study.run_study.run_one', lambda *a, **k: calls.append(a) or {'status': 'skipped', 'reason': 'mock', 'cleanup': {'exit_code': 0}})
    monkeypatch.setattr('study.run_study.wheel_hashes', lambda _: {})
    monkeypatch.setattr(sys, 'argv', ['run_study', '--repos', str(manifest), '--confirm', token,
        '--image', 'sha256:'+'a'*64, '--wheelhouse', str(tmp_path), '--results', str(tmp_path/'out')])
    if allowed:
        main()
        assert len(calls) == 2 and all(c[5] == seconds for c in calls)
    else:
        with pytest.raises(SystemExit):
            main()
        assert calls == [] and not (tmp_path/'out').exists()


def test_total_budget_includes_fallback_and_setup():
    assert validate_run_budget([{}, {}]) == 2400
    assert validate_run_budget([{}, {}], 1200) == 3000
    with pytest.raises(ValueError, match='3000'):
        validate_run_budget([{}, {}], 1201)


def test_committed_summary_regenerates_byte_exact_with_lf(tmp_path):
    from study.summarize import summarize
    source = Path(__file__).resolve().parents[1] / 'results'
    destination = tmp_path / 'results'
    shutil.copytree(source, destination)
    summarize(destination, tmp_path/'REPORT.md')
    actual = (destination/'summary.csv').read_bytes()
    assert b'\r' not in actual
    assert actual == (source/'summary.csv').read_bytes()
