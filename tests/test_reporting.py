import json
import os

import pytest

from vandal.pytest_plugin import classify
from vandal.reporting import make_report, summarize, survivors, write_report


def result(call="passed", assertion=False, applied=1):
    return {
        "applied": applied,
        "phases": {
            "setup": {"outcome": "passed"},
            "call": {"outcome": call, "assertion": assertion},
            "teardown": {"outcome": "passed"},
        },
    }


@pytest.mark.parametrize("call,assertion,applied,code,expected", [
    ("passed", False, 1, 0, "survived"),
    ("failed", True, 1, 1, "killed"),
    ("failed", False, 1, 1, "error"),
    ("failed", True, 0, 1, "error"),
    ("failed", False, 0, 1, "error"),
    ("passed", False, 0, 0, "not_applied"),
    ("skipped", False, 1, 0, "skipped"),
    ("failed", True, 1, 3, "error"),
])
def test_classification(call, assertion, applied, code, expected):
    assert classify(result(call, assertion, applied), code)[0] == expected


@pytest.mark.parametrize("phase", ["setup", "teardown"])
def test_fixture_failure_not_killed(phase):
    data = result("failed", True)
    data["phases"][phase]["outcome"] = "failed"
    assert classify(data, 1)[0] == "error"


def test_injection_failure_not_killed():
    data = result("failed", True)
    data["injection_errors"] = ["browser closed"]
    assert classify(data, 1)[0] == "error"


def test_score_and_html_escaping(tmp_path):
    mutant = dict(strategy="logic_sabotage", selector="<script>", status="survived",
                  hint="Candidate", details="<unsafe>")
    report = make_report([dict(nodeid="test.py::test_x", baseline="passed",
                              targets=["<script>"], mutants=[
                                  mutant, dict(mutant, status="killed"),
                                  dict(mutant, status="error"),
                              ])])
    assert report["schema_version"] == 1
    assert report["summary"]["score"] == 50
    assert summarize([])["score"] is None
    assert len(survivors(report)) == 1
    write_report(report, tmp_path / "report.json")
    assert json.loads((tmp_path / "report.json").read_text()) == report
    html = (tmp_path / "report.html").read_text()
    assert "<script>" not in html and "&lt;script&gt;" in html


def test_schema():
    import jsonschema
    from pathlib import Path
    schema = json.loads((Path(__file__).parents[1] / "docs/report-schema.json").read_text())
    mutant = dict(strategy="logic_sabotage", selector="#b", status="survived",
                  hint="Review", details="Passed")
    report = make_report([dict(nodeid="test.py::test", baseline="passed",
                              targets=["#b"], mutants=[mutant])])
    jsonschema.validate(report, schema)
    report["tests"][0]["mutants"][0]["status"] = "typo"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(report, schema)


@pytest.mark.parametrize("timed_out", [False, True])
def test_partial_report_discloses_deadline_without_losing_results(tmp_path, timed_out):
    mutant = dict(strategy="logic_sabotage", selector="#b", status="survived",
                  hint="Review", details="Passed")
    report = make_report([dict(nodeid="test.py::test_completed", baseline="passed",
                              targets=["#b"], mutants=[mutant])])
    report["timed_out"] = timed_out
    write_report(report, tmp_path / "report.json")
    html = (tmp_path / "report.html").read_text()
    assert ("Incomplete run: deadline reached" in html) == timed_out
    assert ("completed mutants only" in html) == timed_out
    assert "test.py::test_completed" in html and "survived" in html
    assert json.loads((tmp_path / "report.json").read_text()) == report


@pytest.mark.parametrize("filename", ["report.html", "report.HTML"])
def test_html_json_collision_is_rejected_before_writing(tmp_path, filename):
    destination = tmp_path / filename
    destination.write_text("existing report", encoding="utf-8")
    with pytest.raises(ValueError, match="distinct"):
        write_report(make_report([]), destination)
    assert destination.read_text(encoding="utf-8") == "existing report"


def test_json_temporary_creation_uses_normal_file_mode(tmp_path, monkeypatch):
    original = os.open
    modes = []
    def observe(path, flags, mode=0o777, **kwargs):
        modes.append(mode)
        return original(path, flags, mode, **kwargs)
    monkeypatch.setattr(os, "open", observe)
    write_report(make_report([]), tmp_path / "report.json")
    assert modes == [0o666]


def test_fdopen_failure_closes_descriptor_and_preserves_report(tmp_path, monkeypatch):
    descriptors = []
    original_open = os.open
    def capture(*args, **kwargs):
        descriptor = original_open(*args, **kwargs)
        descriptors.append(descriptor)
        return descriptor
    def fail_fdopen(*args, **kwargs):
        raise OSError("fdopen failed")
    path = tmp_path / "report.json"
    path.write_text("existing report")
    monkeypatch.setattr(os, "open", capture)
    monkeypatch.setattr(os, "fdopen", fail_fdopen)
    try:
        with pytest.raises(OSError, match="fdopen failed"):
            write_report(make_report([]), path)
        assert len(descriptors) == 1
        with pytest.raises(OSError) as closed:
            os.fstat(descriptors[0])
        import errno
        assert closed.value.errno == errno.EBADF
        assert path.read_text() == "existing report"
        assert not list(tmp_path.glob(".vandal-*"))
    finally:
        # Keep the fail-before reproduction from leaking an open descriptor.
        for descriptor in descriptors:
            try:
                os.close(descriptor)
            except OSError:
                pass


@pytest.mark.skipif(os.name == "nt", reason="Windows does not implement POSIX file mode/umask semantics")
@pytest.mark.parametrize("mask", [0o022, 0o027, 0o077])
def test_json_report_permissions_follow_umask(tmp_path, mask):
    import stat
    import subprocess
    import sys
    # Change the umask in a child, never in the test runner or another thread.
    source = '''
import os, sys
from pathlib import Path
from vandal.reporting import make_report, write_report
os.umask(int(sys.argv[2]))
write_report(make_report([]), Path(sys.argv[1]))
'''
    path = tmp_path / "report.json"
    for existing in (False, True):
        if existing:
            path.chmod(0o600)
        subprocess.run([sys.executable, "-c", source, str(path), str(mask)], check=True)
        assert stat.S_IMODE(path.stat().st_mode) == 0o666 & ~mask
