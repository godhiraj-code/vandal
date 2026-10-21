import json
from study.redact import host_paths, redact_file


def test_host_temp_paths_redacted_in_json_text_and_docker_mounts(tmp_path):
    source = {"command": [r"C:\Users\someone\AppData\Local\Temp\vandal-study-123\deps"],
              "mount": "/run/desktop/mnt/host/c/Users/someone/AppData/Local/Temp/run/input",
              "score": 80, "killed": 4, "network": "none"}
    path = tmp_path / "isolation.json"
    path.write_text(json.dumps(source), encoding="utf-8")
    assert redact_file(path)
    assert not redact_file(path)
    value = json.loads(path.read_text())
    assert "Users" not in path.read_text()
    assert value["score"] == 80 and value["killed"] == 4 and value["network"] == "none"
    assert host_paths(json.dumps(source)).count("<HOST_TEMP>") == 2
    assert host_paths("/tmp/vandal-study-abc/input") == "<HOST_RUN>/input"
    assert host_paths("/home/person/run") == "<HOST_HOME>/run"
    assert host_paths("/Users/person/run") == "<HOST_HOME>/run"


def test_malformed_json_is_preserved_for_rejection_not_raised(tmp_path):
    path = tmp_path / "vandal_report.json"
    path.write_text('{"broken":')
    assert not redact_file(path)
    assert path.read_text() == '{"broken":'


def test_deeply_nested_json_does_not_break_terminal_status_redaction(tmp_path):
    path = tmp_path / "vandal_report.json"
    path.write_text("[" * 1200 + "0" + "]" * 1200)
    assert not redact_file(path)
