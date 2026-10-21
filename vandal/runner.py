"""Bounded subprocess execution shared by pytest and the MCP server."""
import os
import subprocess
import tempfile

import psutil


def terminate_tree(process):
    """Include nested Vandal workers even when they create their own session."""
    try:
        root = psutil.Process(process.pid)
        descendants = root.children(recursive=True)
    except psutil.NoSuchProcess:
        return
    # Stop the parent first so it cannot start another worker during cleanup.
    for child in [root, *descendants]:
        try:
            child.kill()
        except psutil.NoSuchProcess:
            pass
    psutil.wait_procs([root, *descendants], timeout=5)


def run_process(args, *, cwd, timeout, env=None):
    """Return (exit code, bounded output, timed out); terminate descendants on timeout."""
    options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {
        "start_new_session": True
    }
    # Spool output instead of retaining unbounded test output in memory.
    with tempfile.TemporaryFile() as output:
        process = subprocess.Popen(
            args, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
            stdout=output, stderr=subprocess.STDOUT, **options
        )
        timed_out = False
        try:
            process.wait(timeout=timeout)
        except (subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
            timed_out = True
            terminate_tree(process)
            process.wait(timeout=10)
            # Do not swallow an operator's interruption.
            if isinstance(exc, KeyboardInterrupt):
                raise
        output.seek(0, 2)
        output.seek(max(0, output.tell() - 8000))
        return process.returncode, output.read().decode("utf-8", errors="replace"), timed_out
