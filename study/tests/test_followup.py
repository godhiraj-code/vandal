import io
import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

from study.common import digest
from study.resources import classify_resource_error, monitor
from study.summarize import read_results, summarize
from study.worker import extract_source
from test_harness import candidate, report

ROOT = Path(__file__).resolve().parents[2]


def archive(tmp_path, name, target, kind=tarfile.SYMTYPE, files=None):
    path = tmp_path / 'source.tar'
    with tarfile.open(path, 'w') as tar:
        for file in files or ['AGENTS.md']:
            item = tarfile.TarInfo(file); item.size = 3
            tar.addfile(item, io.BytesIO(b'own'))
        item = tarfile.TarInfo(name); item.type = kind; item.linkname = target
        tar.addfile(item)
    return path


def test_documentation_link_skipped_and_listed_without_materializing(tmp_path):
    path = archive(tmp_path, 'CLAUDE.md', 'AGENTS.md')
    result = extract_source(path, tmp_path / 'out', {'test_paths': ['tests/test_ui.py']})
    assert result == [{'path': 'CLAUDE.md', 'target': 'AGENTS.md',
                       'reason': 'documentation outside recipe runtime scope'}]
    assert (tmp_path / 'out/AGENTS.md').read_bytes() == b'own'
    assert not (tmp_path / 'out/CLAUDE.md').exists()
    with pytest.raises(ValueError):
        extract_source(path, tmp_path / 'strict-export')


@pytest.mark.parametrize('name,target,files,recipe', [
    ('CLAUDE.md', '../outside.md', ['AGENTS.md'], {}),
    ('CLAUDE.md', '/etc/passwd', ['AGENTS.md'], {}),
    ('tests/CLAUDE.md', '../AGENTS.md', ['AGENTS.md'], {}),
    ('CLAUDE.md', 'app.py', ['app.py'], {}),
    ('docs/link.md', '../site/content.md', ['site/content.md'], {}),
    ('docs/link.md', '../custom/content.md', ['custom/content.md'], {'source_paths': ['custom']}),
    ('CLAUDE.md', 'missing.md', ['AGENTS.md'], {}),
])
def test_unsafe_or_runtime_symlink_rejected(tmp_path, name, target, files, recipe):
    path = archive(tmp_path, name, target, files=files)
    with pytest.raises(ValueError):
        extract_source(path, tmp_path / 'out', {'test_paths': ['tests/test_ui.py'], **recipe})


def test_hardlink_still_rejected(tmp_path):
    with pytest.raises(ValueError):
        extract_source(archive(tmp_path, 'CLAUDE.md', 'AGENTS.md', tarfile.LNKTYPE),
                       tmp_path / 'out', {'test_paths': ['test_ui.py']})


@pytest.mark.parametrize('text', ['pthread_create failed', 'Resource temporarily unavailable'])
def test_resource_exhaustion_class_preserves_error_status(text):
    mutant = {'status': 'error', 'details': text}
    assert classify_resource_error(mutant)['error_class'] == 'resource_exhausted'
    assert mutant['status'] == 'error' and mutant['details'] == text
    assert 'error_class' not in classify_resource_error({'status': 'survived', 'details': text})


def test_monitor_reaps_owned_child_and_preserves_preexisting_process(tmp_path):
    # Only owned sleeping Python processes; no browser or candidate source.
    prior = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
    leaked = []
    try:
        def call():
            leaked.append(subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)']))
            return {'status': 'survived', 'details': 'owned mock'}
        output = tmp_path / 'resources.jsonl'
        result = monitor(call, output, {'nodeid': 'owned::test'}, subreaper=False)
        assert result['resources']['before_cleanup'] > result['resources']['before']
        assert result['resources']['reaped'] and result['resources']['remaining_new'] == 0
        assert result['resources']['after'] == result['resources']['before']
        assert prior.poll() is None
        assert json.loads(output.read_text())['cleanup_attempted'] == 1
    finally:
        for process in [prior, *leaked]:
            if process.poll() is None: process.kill()
            process.wait(timeout=5)


def add_result(root, name, errors):
    out = root / name; out.mkdir(parents=True)
    row = candidate(); row.update(repo='owner/' + name, approved='yes', reviewer='Person',
                                  reviewed_at='2026-10-21T12:20:00Z')
    row['evidence_url'] = row['evidence_url'].replace('owner/repo', row['repo'])
    row['license_url'] = row['license_url'].replace('owner/repo', row['repo'])
    raw = out / 'vandal_report.json'; raw.write_text(json.dumps(report(['killed'] * (10-errors) + ['error'] * errors)))
    status = {'repo': row['repo'], 'commit_sha': row['commit_sha'], 'kind': 'public', 'group': 'agent',
              'status': 'completed', 'reason': '', 'manifest': row,
              'artifact_sha256': {'vandal_report.json': digest(raw)}}
    (out / 'status.json').write_text(json.dumps(status))


def test_error_ceiling_boundary_and_invalid_exclusion(tmp_path):
    add_result(tmp_path, 'valid', 1); add_result(tmp_path, 'invalid', 2)
    rows, strategies = read_results(tmp_path)
    valid = next(r for r in rows if r['repo'] == 'owner/valid')
    invalid = next(r for r in rows if r['repo'] == 'owner/invalid')
    assert valid['eligible'] and valid['error_rate'] == 10
    assert invalid['status'] == 'invalid run' and invalid['score'] is None
    assert invalid['error'] == 2 and invalid['error_rate'] == 20 and not invalid['eligible']
    assert all(c['n_repos'] == 1 for c in strategies.values())
    path = tmp_path / 'REPORT.md'; summarize(tmp_path, path)
    text = path.read_text()
    assert '| 1 | N/A | N/A |' in text and 'no median, IQR or strategy rates' in text
    assert text.count('owned fixture excluded') == 1 and 'Error %' in text
    strategy_table = text.split('## Strategy survival')[1].split('## Exclusions')[0]
    assert 'N/A' in strategy_table
    add_result(tmp_path, 'second', 0)
    summarize(tmp_path, path)
    assert '| 2 | 100.0000 | 0.0000 |' in path.read_text()


def test_diagnostic_evidence_never_becomes_results(tmp_path):
    root = tmp_path / 'diagnostic' / 'old'
    add_result(root, 'evidence', 0)
    assert read_results(tmp_path) == ([], {})
    assert read_results(root) == ([], {})
    root2 = tmp_path / 'marked'; add_result(root2, 'evidence', 0)
    (root2 / '.diagnostic-only').touch()
    assert read_results(root2) == ([], {})


@pytest.mark.parametrize('path,ignored', [
    ('study/results/public/owner/status.json', False),
    ('study/results/public/owner/baseline.log', False),
    ('study/results/public/owner/resources.jsonl', False),
    ('study/results/public/owner/.pytest_cache/state', True),
    ('study/results/public/owner/__pycache__/x.pyc', True),
    ('study/results/public/owner/tmp/x', True),
    ('study/results/public/owner/scratch.tmp', True),
])
def test_git_ignore_allows_public_evidence_but_not_caches(path, ignored):
    result = subprocess.run(['git', 'check-ignore', '--no-index', '-q', path], cwd=ROOT)
    assert result.returncode == (0 if ignored else 1)


def test_hash_locked_harness_and_artifact_export():
    from study.harness_lock import WHEELS, requirements
    from study.export import NAMES
    assert {'harness.lock', 'resources.jsonl', 'harness-install.log'} <= set(NAMES)
    assert len(WHEELS) == 21 and all(len(w['sha256']) == 64 for w in WHEELS)
    names = {w['name'].lower().replace('_','-') for w in WHEELS}
    assert {'pytest', 'psutil', 'setuptools', 'playwright', 'pip', 'virtualenv'} <= names
    assert requirements().count('--hash=sha256:') == len(WHEELS)
    docker = (ROOT / 'study/Dockerfile').read_text()
    assert docker.count('--require-hashes') == 2 and 'apt-get' not in docker
    assert '--no-build-isolation' in docker and '--no-deps' in docker


def test_failed_baseline_resource_class_does_not_invent_mutants(tmp_path):
    from study.worker import classify_failed_run
    (tmp_path / 'baseline.log').write_text('browser: pthread_create: Resource temporarily unavailable')
    status = classify_failed_run({'status': 'skipped', 'reason': 'baseline failed'}, tmp_path)
    assert status['error_class'] == 'resource_exhausted' and 'score' not in status


def test_cleanup_failure_aborts_after_durable_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr('study.resources.snapshot', lambda: {})
    monkeypatch.setattr('study.resources.reap_new', lambda before: {
        'before': 0, 'before_cleanup': 1, 'after': 1, 'remaining_new': 1, 'reaped': False})
    output = tmp_path / 'resources.jsonl'
    with pytest.raises(RuntimeError, match='process_cleanup_failed'):
        monitor(lambda: {'status': 'survived'}, output, {'nodeid': 'owned::test'}, subreaper=False)
    assert json.loads(output.read_text())['error_class'] == 'process_cleanup_failed'


def test_guard_launcher_preserves_baseline_root_helper_imports(tmp_path):
    from study.process import clean_env
    (tmp_path / 'owned_helper.py').write_text('VALUE = 3\n')
    (tmp_path / 'tests').mkdir()
    (tmp_path / 'tests/test_owned.py').write_text(
        'from owned_helper import VALUE\ndef test_owned():\n    assert VALUE == 3\n')
    env = clean_env()
    env['STUDY_RESOURCE_LOG'] = str(tmp_path / 'resources.jsonl')
    args = ['--collect-only', '-q', '-p', 'no:vandal']
    for launcher in [['-m', 'pytest'], [str(ROOT / 'study/pytest_entry.py')]]:
        result = subprocess.run([sys.executable, *launcher, *args], cwd=tmp_path,
                                env=env, capture_output=True, text=True, timeout=20)
        assert result.returncode == 0, result.stdout + result.stderr
        assert 'tests/test_owned.py::test_owned' in result.stdout
