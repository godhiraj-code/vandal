"""The demo must fail closed rather than present a partial score as improvement."""
import importlib.util
import io
import json
import os
from pathlib import Path
import sys

import pytest

SPEC = importlib.util.spec_from_file_location(
    "agent_loop_demo", Path(__file__).parents[1] / "demo/agent_loop/run_demo.py",
)
demo = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(demo)


def report():
    return {
        "schema_version": 1, "summary": {"score": 0.0},
        "tests": [{"baseline": "passed", "mutants": [
            {"strategy": "logic_sabotage", "selector": "#checkout", "status": "survived"},
        ]}],
    }


@pytest.mark.parametrize("fault", [
    "timed_out", "baseline", "cap", "untested", "error", "not_applied",
    "skipped", "empty", "null_score", "wrong_score",
])
def test_reject_incomplete_measurement(tmp_path, fault):
    data = report()
    test = data["tests"][0]
    if fault == "timed_out":
        data["timed_out"] = True
    elif fault == "baseline":
        test["baseline"] = "failed"
    elif fault == "cap":
        test["skipped_by_cap"] = 1
    elif fault == "untested":
        test["untested_targets"] = ["#name"]
    elif fault in ("error", "not_applied", "skipped"):
        test["mutants"][0]["status"] = fault
    elif fault == "empty":
        test["mutants"] = []
    else:
        data["summary"]["score"] = None if fault == "null_score" else 100
    path = tmp_path / "vandal_report.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        demo.read_measurement(path)


@pytest.mark.parametrize("fixed,candidates,expected", [
    (0, {("logic_sabotage", "#checkout")}, 1),
    (100, {("data_sabotage", "#status")}, 1),
    (100, {("logic_sabotage", "#checkout")}, 0),
])
def test_improvement_requires_same_candidates(tmp_path, monkeypatch, fixed, candidates, expected):
    monkeypatch.setattr(demo, "HERE", tmp_path)
    monkeypatch.setattr(demo, "ROOT", tmp_path)
    measurements = iter([(0, {("logic_sabotage", "#checkout")}), (fixed, candidates)])
    monkeypatch.setattr(demo, "measure", lambda *args: next(measurements))
    assert demo.main() == expected


def test_live_stream_preserves_log_and_exit_code(tmp_path, capsys):
    """The child cannot finish until its first line has reached the log sink."""
    acknowledgement = tmp_path / "streamed"

    class Log(io.StringIO):
        def flush(self):
            if self.getvalue():
                acknowledgement.touch()
            super().flush()

    script = """
import pathlib, sys, time
print('. [100%]Vandal: test_cart.py::test_checkout | custom_strategy | [data-label="a | b"]', flush=True)
deadline = time.monotonic() + 10
while not pathlib.Path(sys.argv[1]).exists():
    if time.monotonic() >= deadline:
        raise SystemExit(99)
    time.sleep(0.01)
print('diagnostic from stderr', file=sys.stderr, flush=True)
print('Vandal: unsupported target', flush=True)
raise SystemExit(7)
"""
    log = Log()
    code = demo.stream_pytest([sys.executable, "-u", "-c", script, str(acknowledgement)],
                             dict(os.environ), log)
    assert code == 7
    output = capsys.readouterr().out
    assert output.startswith('. [100%]\n  mutating')
    assert 'mutating [data-label="a | b"] with custom_strategy...' in output
    assert "diagnostic from stderr" in output
    assert "Vandal: unsupported target" in output
    assert log.getvalue().startswith(". [100%]Vandal: test_cart.py::test_checkout | custom_strategy | ")
    assert "diagnostic from stderr" in log.getvalue()
    assert "mutating" not in log.getvalue()
