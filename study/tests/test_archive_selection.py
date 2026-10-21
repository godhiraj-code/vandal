import json
import shutil
from pathlib import Path

import pytest

from study.summarize import read_results, summarize

STUDY = Path(__file__).resolve().parents[1]
RUN = '39639203251'
PLATELET = 'tegataiprime__Platelet-Movie__14664611814b'


def test_fresh_public_rerun_excludes_archive_and_history_is_explicit(tmp_path):
    root = tmp_path / 'results'
    archive = root / 'archive' / RUN
    shutil.copytree(STUDY / 'results/archive' / RUN, archive)
    live = root / 'public' / PLATELET
    # Copy retained data as an owned simulation; no repository code is executed.
    shutil.copytree(archive / 'artifact/study/results/public' / PLATELET, live)
    status = json.loads((live / 'status.json').read_text())
    status['reason'] = 'owned simulated fresh rerun'
    (live / 'status.json').write_text(json.dumps(status))
    rows = summarize(root, tmp_path / 'live.md')
    assert len(rows) == 1 and rows[0]['eligible'] and rows[0]['status'] == 'completed'
    assert rows[0]['reason'] == 'owned simulated fresh rerun'
    assert rows[0]['run_path'] == 'public/' + PLATELET
    assert 'duplicate' not in (tmp_path / 'live.md').read_text()
    history = summarize(root, tmp_path / 'history.md', archive_run=RUN)
    assert len(history) == 2 and sum(row['eligible'] for row in history) == 1
    platelet = next(row for row in history if row['eligible'])
    assert platelet['killed'] == 30 and platelet['survived'] == 29 and platelet['error'] == 0
    assert platelet['score'] == 100 * 30 / 59
    assert all(row['run_path'].startswith('archive/' + RUN + '/') for row in history)
    assert 'owned simulated fresh rerun' not in (tmp_path / 'history.md').read_text()


def test_default_canonical_scan_and_public_upload_exclude_archive():
    rows, _ = read_results(STUDY / 'results')
    assert not any(row['kind'] == 'public' for row in rows)
    assert read_results(STUDY / 'results/archive' / RUN) == ([], {})
    workflow = (STUDY.parent / '.github/workflows/study-pilot.yml').read_text()
    assert 'study/results/public/**' in workflow and 'study/results/archive' not in workflow
    uploaded = {p.resolve() for p in (STUDY / 'results/public').rglob('*') if p.is_file()}
    archived = {p.resolve() for p in (STUDY / 'results/archive' / RUN).rglob('*') if p.is_file()}
    assert archived and not uploaded.intersection(archived)
    assert not (STUDY / 'results/public' / RUN).exists()


def test_unrelated_nested_archive_directory_is_not_hidden(tmp_path):
    from test_followup import add_result
    add_result(tmp_path / 'case/archive', 'owned', 0)
    rows, _ = read_results(tmp_path)
    assert len(rows) == 1 and rows[0]['eligible']


@pytest.mark.parametrize('run', ['../public', 'missing', '999999'])
def test_historical_selection_fails_closed_for_invalid_or_missing_run(tmp_path, run):
    with pytest.raises(ValueError, match='archive'):
        read_results(tmp_path, archive_run=run)
