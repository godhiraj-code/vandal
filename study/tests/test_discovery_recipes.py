import os
import subprocess
import sys

from study.worker import validate_recipe


def test_explicit_file_selection_passes_owned_directory_collection_guard(tmp_path):
    """Probe the candidate's collection pattern with owned code, not its tests."""
    (tmp_path / 'tests/browser').mkdir(parents=True)
    (tmp_path / 'tests/conftest.py').write_text('''from pathlib import Path
def pytest_addoption(parser): parser.addoption('--browser-smoke', action='store_true')
def pytest_ignore_collect(collection_path, config):
    if collection_path == Path(__file__).parent / 'browser' and not config.getoption('--browser-smoke'):
        return True
''')
    (tmp_path / 'tests/browser/test_owned.py').write_text('def test_owned(): assert True\n')
    env = {k: v for k, v in os.environ.items() if k not in {'PYTHONPATH', 'PYTEST_ADDOPTS'}}
    env['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
    result = subprocess.run([sys.executable, '-m', 'pytest', '-q', 'tests/browser/test_owned.py'],
                            cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '1 passed' in result.stdout


def test_new_proposed_recipe_is_valid_without_execution():
    import json
    from pathlib import Path
    recipe = json.loads((Path(__file__).resolve().parents[1] / 'recipes/meow-now.json').read_text())
    assert validate_recipe(recipe)['seconds'] == 1800
