import json
from pathlib import Path
from study.redact import host_paths, redact_file


def test_absolute_homes_only_and_measurements_unchanged(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "actual-home"))
    unchanged = ["tests/home/test_a.py", "/work/home/.cache", "/tmp/vandal-study-abc/input", "/run/desktop/mnt/host/c/Users/person/data",
                 "/home/person/my tests/test_a.py::test_a", r"C:\Users\First Last\my tests\test_a.py::test_a", "tests/home/test_a.py::test_a", "/home/person/test_a.py::test_a"]
    for text in unchanged:
        assert host_paths(text) == text
    for text in [r"C:\Users\someone\work", "/Users/person/work", "/home/person/work", str(tmp_path / "actual-home" / "work")]:
        assert host_paths(text).startswith("<HOST_HOME>")
    assert host_paths(r"C:\Users\First Last\work") == r"<HOST_HOME>\work"
    source = {"nodeid": "/home/person/test_a.py::test_a", "score": 80, "killed": 4,
              "survived": 1, "error": 0, "path": "/home/person/work"}
    path = tmp_path / "report.json"
    path.write_text(json.dumps(source))
    assert redact_file(path)
    assert not redact_file(path)
    expected = dict(source, path="<HOST_HOME>/work")
    assert json.loads(path.read_text()) == expected


def test_actual_home_resolved_path(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path / "parent" / ".." / "actual"))
    assert host_paths(str(tmp_path / "actual" / "file")) == "<HOST_HOME>" + str(tmp_path / "actual" / "file")[len(str(tmp_path / "actual")):]


def test_baseline_hostname_only_metadata_changes(tmp_path):
    import xml.etree.ElementTree as ET
    path = tmp_path / "baseline.xml"
    path.write_text('<testsuite hostname="dhiraj" tests="2" failures="0"><testcase name="tests/home/test_a.py::test_a"/></testsuite>')
    before = ET.fromstring(path.read_text())
    assert redact_file(path)
    after = ET.fromstring(path.read_text())
    assert after.attrib == dict(before.attrib, hostname="runner")
    assert after[0].attrib == before[0].attrib


def test_malformed_json_is_preserved_for_rejection_not_raised(tmp_path):
    path = tmp_path / "vandal_report.json"
    path.write_text('{"broken":')
    assert not redact_file(path)
    assert path.read_text() == '{"broken":'


def test_deeply_nested_json_does_not_break_terminal_status_redaction(tmp_path):
    path = tmp_path / "vandal_report.json"
    path.write_text("[" * 1200 + "0" + "]" * 1200)
    assert not redact_file(path)
