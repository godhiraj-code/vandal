import json
import sys

import psutil

from vandal.runner import run_process


def test_timeout_terminates_nested_process(tmp_path):
    script = tmp_path / "parent.py"
    pid_file = tmp_path / "child.json"
    script.write_text(
        "import subprocess, sys, time, json\n"
        "from pathlib import Path\n"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], "
        "start_new_session=True)\n"
        f"Path({str(pid_file)!r}).write_text(json.dumps(child.pid))\n"
        "time.sleep(60)\n"
    )
    _, _, timed_out = run_process([sys.executable, str(script)], cwd=tmp_path, timeout=3)
    assert timed_out
    pid = json.loads(pid_file.read_text())
    assert not psutil.pid_exists(pid) or psutil.Process(pid).status() == psutil.STATUS_ZOMBIE


def test_output_is_bounded(tmp_path):
    code, log, timed_out = run_process(
        [sys.executable, "-c", "print('x' * 20000)"], cwd=tmp_path, timeout=10
    )
    assert code == 0 and not timed_out
    assert len(log) == 8000
