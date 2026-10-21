"""Bounded command execution for harness tools and the container worker."""
import os
import signal
import subprocess
import threading
import time
from pathlib import Path

MAX_LOG = 8 * 1024 * 1024


def clean_env(*, docker_client=False):
    # Deliberate allowlist: no GitHub/cloud/SSH credentials, proxies, Python hooks,
    # pip configuration, pytest options, or inherited display/server variables.
    env = {k: os.environ[k] for k in ("PATH", "SYSTEMROOT", "WINDIR", "COMSPEC",
           "TEMP", "TMP", "LOCALAPPDATA") if k in os.environ}
    if docker_client:
        # Client routing/config only. Never use this environment for candidate code.
        env.update({k: os.environ[k] for k in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_CONFIG", "HOME") if k in os.environ})
    env.update(PYTHONUTF8="1", PIP_CONFIG_FILE=os.devnull,
               PIP_DISABLE_PIP_VERSION_CHECK="1", GIT_CONFIG_NOSYSTEM="1",
               GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0")
    return env


def kill_tree(proc):
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if proc.poll() is None:
        proc.kill()


def run(cmd, cwd, log, seconds, env=None, max_bytes=MAX_LOG, disk_root=None):
    """No shell; bound elapsed time and retained bytes, including a noisy child."""
    started = time.monotonic()
    proc = subprocess.Popen(cmd, cwd=cwd, env=env or clean_env(),
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            start_new_session=os.name != "nt")
    overflow = threading.Event()
    def drain():
        retained = 0
        with Path(log).open("wb") as stream:
            while True:
                chunk = proc.stdout.read(65536)
                if not chunk:
                    break
                room = max(0, max_bytes - retained)
                stream.write(chunk[:room])
                retained += len(chunk)
                if retained > max_bytes:
                    overflow.set()
    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    timed_out = False
    disk_limited = False
    while proc.poll() is None:
        if disk_root is not None:
            try:
                disk_limited = sum(p.stat().st_size for p in Path(disk_root).rglob("*")
                                   if p.is_file()) > 256 * 1024 * 1024
            except OSError:
                pass
        if time.monotonic() - started >= seconds or overflow.is_set() or disk_limited:
            timed_out = not overflow.is_set()
            kill_tree(proc)
            break
        time.sleep(0.05)
    proc.wait(timeout=10)
    reader.join(timeout=2)
    if reader.is_alive():
        kill_tree(proc)
        reader.join(timeout=2)
    return {"command": cmd, "exit_code": proc.returncode, "timed_out": timed_out,
            "log_limited": overflow.is_set(), "disk_limited": disk_limited,
            "seconds": round(time.monotonic() - started, 3)}
