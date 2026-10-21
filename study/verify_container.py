"""Fail CI unless the owned fixture exercised the isolated container pipeline."""
import json
import sys
from pathlib import Path
from study.run_study import cleanup_confirmed
from study.summarize import metrics


def verify(root):
    status = json.loads((root / "status.json").read_text())
    isolation = json.loads((root / "isolation.json").read_text())
    measured, _ = metrics(json.loads((root / "vandal_report.json").read_text()))
    assert status["kind"] == "fixture" and status["status"] == "completed"
    assert cleanup_confirmed(status)
    assert isolation["host_config"]["NetworkMode"] == "none"
    assert isolation["host_config"]["ReadonlyRootfs"] is True
    assert isolation["host_config"]["Privileged"] is False
    assert isolation["user"] == "10001:10001"
    assert not isolation["github_token_present"] and isolation["proxy_values_empty"]
    binds = [m for m in isolation["mounts"] if m["Type"] == "bind"]
    assert {m["Destination"] for m in binds} == {"/input", "/deps"}
    assert all(not m["RW"] for m in binds)
    assert measured["n_scored"] > 0 and measured["error"] == 0
    assert status["worker"]["baseline"]["exit_code"] == 0
    assert isolation["host_config"]["PidsLimit"] == 1024
    resources = [json.loads(line) for line in (root / "resources.jsonl").read_text().splitlines()]
    assert len(resources) == measured["n_mutants"]
    assert all(r["reaped"] and r["remaining_new"] == 0 and r["subreaper"] for r in resources)
    assert "--hash=sha256:" in (root / "harness.lock").read_text()
    print(json.dumps(measured, sort_keys=True))


if __name__ == "__main__":
    verify(Path(sys.argv[1]))
