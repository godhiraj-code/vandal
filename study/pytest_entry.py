"""Owned mutation entrypoint; candidate code is executed only in its allowed runtime."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from study.resources import install_guard


if __name__ == '__main__':
    # Match baseline `python -m pytest`: root helpers remain importable.
    sys.path.insert(0, os.getcwd())
    import pytest
    install_guard(os.environ['STUDY_RESOURCE_LOG'])
    raise SystemExit(pytest.main(sys.argv[1:]))
