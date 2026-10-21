"""Study-only per-mutant descendant accounting and bounded cleanup."""
import ctypes
import json
import sys
from pathlib import Path

import psutil


def enable_subreaper():
    # Adopt orphaned browser/site children even if they detach from their session.
    if sys.platform != 'linux':
        return False
    if ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), 'cannot enable study child subreaper')
    return True


def snapshot():
    result = {}
    for process in psutil.Process().children(recursive=True):
        try:
            result[(process.pid, process.create_time())] = process
        except psutil.NoSuchProcess:
            pass
    return result


def reap_new(before):
    pending = snapshot()
    newcomers = [p for key, p in pending.items() if key not in before]
    for process in newcomers:
        try:
            process.terminate()
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs(newcomers, timeout=2)
    for process in alive:
        try:
            process.kill()
        except psutil.NoSuchProcess:
            pass
    psutil.wait_procs(alive, timeout=3)
    after = snapshot()
    return {'before': len(before), 'before_cleanup': len(pending), 'after': len(after),
            'cleanup_attempted': len(newcomers), 'remaining_new': len(set(after) - set(before)),
            'reaped': not (set(after) - set(before))}


def classify_resource_error(mutant):
    if mutant.get('status') == 'error' and any(token in json.dumps(mutant).lower()
            for token in ('pthread_create', 'resource temporarily unavailable')):
        mutant['error_class'] = 'resource_exhausted'
    return mutant


def monitor(call, destination, identity, *, subreaper):
    before = snapshot()
    mutant = None
    try:
        mutant = call()
    finally:
        evidence = reap_new(before)
        evidence.update(identity, subreaper=subreaper)
        if not evidence['reaped']:
            evidence['error_class'] = 'process_cleanup_failed'
        with Path(destination).open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(evidence) + '\n')
    if not evidence['reaped']:
        raise RuntimeError('process_cleanup_failed: new browser/site descendants remain after bounded cleanup')
    mutant['resources'] = evidence
    return classify_resource_error(mutant)


def install_guard(destination):
    from vandal.pytest_plugin import VandalPlugin
    subreaper = enable_subreaper()
    original = VandalPlugin.run_mutant
    def guarded(self, test, strategy, selector, directory):
        return monitor(lambda: original(self, test, strategy, selector, directory), destination,
                       {'nodeid': test['nodeid'], 'strategy': strategy, 'selector': selector},
                       subreaper=subreaper)
    VandalPlugin.run_mutant = guarded
