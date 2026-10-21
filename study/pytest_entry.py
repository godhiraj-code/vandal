"""Owned mutation entrypoint; candidate code is executed only in its allowed runtime."""
import os
import sys
from pathlib import Path

script_folder = Path(__file__).resolve().parent
runtime_paths = sys.path[1:]
sys.path.insert(0, str(script_folder.parent))
from study.resources import install_guard

# Bootstrap the owned guard without exposing its import roots to repository code.
# `python -m pytest` starts with CWD, rather than the entrypoint's script folder.
sys.path[:] = [os.getcwd()] + [p for p in runtime_paths
                             if Path(p).resolve() not in {script_folder, Path('/opt').resolve()}]


if __name__ == '__main__':
    import pytest
    install_guard(os.environ['STUDY_RESOURCE_LOG'])
    raise SystemExit(pytest.main(sys.argv[1:]))
