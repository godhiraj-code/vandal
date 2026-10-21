"""The demo must fail closed rather than present a partial score as improvement."""
import importlib.util
import json
from pathlib import Path

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
