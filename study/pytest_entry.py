"""Owned mutation entrypoint; candidate code is executed only in its allowed runtime."""
import os
import sys
import importlib.util
from pathlib import Path

script_folder = Path(__file__).resolve().parent
runtime_paths = sys.path[1:]
guard_spec = importlib.util.spec_from_file_location('_vandal_study_resources', script_folder / 'resources.py')
if guard_spec is None or guard_spec.loader is None:
    raise ImportError('cannot load the owned study resource guard')
resource_guard = importlib.util.module_from_spec(guard_spec)
sys.modules[guard_spec.name] = resource_guard
guard_spec.loader.exec_module(resource_guard)

# Bootstrap the owned guard without exposing its import roots to repository code.
# `python -m pytest` starts with CWD, rather than the entrypoint's script folder.
sys.path[:] = [os.getcwd()] + [p for p in runtime_paths
                             if Path(p).resolve() not in {script_folder, Path('/opt').resolve()}]


if __name__ == '__main__':
    import pytest
    resource_guard.install_guard(os.environ['STUDY_RESOURCE_LOG'])
    for name in tuple(sys.modules):
        if name == 'study' or name.startswith('study.'):
            del sys.modules[name]
    raise SystemExit(pytest.main(sys.argv[1:]))
