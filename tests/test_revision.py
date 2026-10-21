"""Regressions for PR 4's requested usability and scoring changes."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_plugin import APP, run_suite
from test_native_retry import fixture
from test_reporting import result
from vandal.pytest_plugin import VandalPlugin, classify
from vandal import instrumentation, mcp_server


@pytest.mark.parametrize("controls,expected", [
    (None, "error"), ({"before": "passed", "after": "error"}, "error"),
    ({"before": "error", "after": "passed"}, "error"),
    ({"before": "passed", "after": "passed"}, "killed"),
])
def test_action_failure_requires_both_controls(controls, expected):
    data = result("failed")
    data["phases"]["call"]["playwright_error"] = True
    assert classify(data, 1, controls)[0] == expected
    data["injection_errors"] = ["injection failed"]
    assert classify(data, 1, controls)[0] == "error"


@pytest.mark.parametrize("api", ["sync", "async"])
@pytest.mark.parametrize("strategy", ["stealth_disable", "ghost_element"])
def test_blocked_browser_actions_are_controlled_kills(tmp_path, api, strategy):
    wait = "await " if api == "async" else ""
    source = f'''
import pytest
{"@pytest.mark.asyncio" if api == "async" else ""}
@pytest.mark.vandal(targets=["#b"])
{"async " if api == "async" else ""}def test_click(ready):
    {wait}ready.locator("#b").click(timeout=1500)
'''
    run, report = run_suite(tmp_path, source, "--vandal", "--vandal-strategies=" + strategy,
                           conftest=fixture(api))
    assert run.returncode == 0, run.stdout + run.stderr
    assert report and report["tests"][0]["baseline"] == "passed", run.stdout + run.stderr
    assert report["tests"][0]["mutants"], report
    mutant = report["tests"][0]["mutants"][0]
    assert mutant["status"] == "killed"
    assert mutant["kill_reason"] == "action_failed"
    assert mutant["controls"] == {"before": "passed", "after": "passed"}


@pytest.mark.parametrize("strict", [False, True])
def test_mutant_errors_are_opt_in_failures(tmp_path, strict):
    source = f'''
import pytest
@pytest.mark.vandal(targets=["["])
def test_bad_target(page):
    page.set_content({APP!r})
    page.click("#b")
'''
    run, report = run_suite(tmp_path, source, "--vandal", "--vandal-strategies=logic_sabotage",
                           *( ["--vandal-strict"] if strict else []))
    assert run.returncode == int(strict), run.stdout + run.stderr
    assert report["summary"]["error"] == 1
    assert ("Vandal: 1 mutant errors with --vandal-strict" in run.stdout) == strict


@pytest.mark.parametrize("api", ["sync", "async"])
def test_discovery_ignores_unused_locators_and_reapplies_changed_text(tmp_path, api):
    wait = "await " if api == "async" else ""
    source = f'''
import pytest
from playwright.{api}_api import expect
{"@pytest.mark.asyncio" if api == "async" else ""}
{"async " if api == "async" else ""}def test_flow(ready):
    ready.locator("#unused")
    {wait}ready.locator("#b").click()
    {wait}expect(ready.locator("#result")).to_have_text("done", timeout=150)
'''
    run, report = run_suite(tmp_path, source, "--vandal", "--vandal-strategies=data_sabotage",
                           conftest=fixture(api))
    assert run.returncode == 0, run.stdout + run.stderr
    test = report["tests"][0]
    assert test["targets"] == ["#b", "#result"]
    out = next(m for m in test["mutants"] if m["selector"] == "#result")
    assert out["status"] == "killed" and out["kill_reason"] == "assertion"


def test_default_planning_and_cap_are_balanced():
    planner = SimpleNamespace(strategies=None)
    test = {"explicit": None, "targets": {
        "#button": {"operations": ["click"]},
        "#input": {"operations": ["fill", "input_value"]},
        "#out": {"operations": ["expect:to.have.text"]},
    }}
    pairs = VandalPlugin.candidates(planner, test, list(test["targets"]))
    assert pairs == [("stealth_disable", "#button"), ("data_sabotage", "#input"),
                     ("data_sabotage", "#out"), ("ghost_element", "#button"),
                     ("logic_sabotage", "#button")]
    planner.strategies = ["ui_shift", "slow_load"]
    assert VandalPlugin.candidates(planner, test, list(test["targets"]))[:3] == [
        ("ui_shift", "#button"), ("ui_shift", "#input"), ("ui_shift", "#out")]


def test_cap_metadata_hints_and_readable_summary(tmp_path):
    source = '''
def test_flow(page):
    page.set_content('<button id="a">A</button><button id="b">B</button>')
    page.click("#a")
    page.click("#b")
'''
    run, report = run_suite(tmp_path, source, "--vandal", "--vandal-max-mutants=2",
                           "--vandal-strategies=logic_sabotage,ui_shift")
    test = report["tests"][0]
    assert [m["selector"] for m in test["mutants"]] == ["#a", "#b"]
    assert test["skipped_by_cap"] == 2
    assert "No Playwright assertion ran after clicking #a" in test["mutants"][0]["hint"]
    assert "2 skipped by cap" in run.stdout
    assert "0 killed, 2 survived, 0 error" in run.stdout
    assert "{'killed'" not in run.stdout


def test_html_report_is_not_overwritten_by_workers(tmp_path):
    source = f'''
def test_flow(page):
    page.set_content({APP!r})
    page.click("#b")
    assert page.inner_text("#result") == "done"
'''
    run, report = run_suite(tmp_path, source, "--vandal", "--vandal-strategies=logic_sabotage",
                           "--html=baseline.html", "--self-contained-html")
    assert run.returncode == 0, run.stdout + run.stderr
    assert report["summary"]["killed"] >= 1
    html = (tmp_path / "baseline.html").read_text(encoding="utf-8")
    # pytest-html serializes results into its data-jsonblob attribute.
    from html import unescape
    import re
    data = json.loads(unescape(re.search(r'data-jsonblob="([^"]+)"', html).group(1)))
    outcomes = [item["result"] for items in data["tests"].values() for item in items]
    assert outcomes == ["Passed"]


@pytest.mark.parametrize("origin", ["cli", "ini", "ini_addopts", "environment"])
def test_builtin_log_preserves_baseline(tmp_path, origin):
    import os
    import subprocess
    import sys

    (tmp_path / "test_log.py").write_text('''
import logging
def test_label(page):
    page.set_content('<button id="b">Go</button>')
    logging.warning("AUDIT_LABEL=%s", page.locator("#b").inner_text())
''', encoding="utf-8")
    options = "--log-file=baseline.log --log-file-level=WARNING"
    env = dict(os.environ)
    env.pop("_VANDAL_WORKER", None)
    env.pop("PYTEST_ADDOPTS", None)
    args = [sys.executable, "-m", "pytest", "test_log.py", "-q", "--vandal",
            "--vandal-strategies=data_sabotage"]
    if origin == "cli":
        args.extend(options.split())
    elif origin == "ini":
        (tmp_path / "pytest.ini").write_text(
            "[pytest]\nlog_file = baseline.log\nlog_file_level = WARNING\n")
    elif origin == "ini_addopts":
        (tmp_path / "pytest.ini").write_text("[pytest]\naddopts = " + options + "\n")
    else:
        env["PYTEST_ADDOPTS"] = options
    run = subprocess.run(args, cwd=tmp_path, env=env, text=True,
                         capture_output=True, timeout=120)
    assert run.returncode == 0, run.stdout + run.stderr
    report = json.loads((tmp_path / "vandal_report.json").read_text())
    assert report["summary"]["survived"] == 1, report
    log = (tmp_path / "baseline.log").read_text()
    assert "AUDIT_LABEL=Go" in log and "VANDALIZED_TEXT" not in log, log


def test_missing_private_adapter_fails_at_configure(tmp_path):
    conftest = '''
from playwright._impl._frame import Frame
Frame._click = None
'''
    run, report = run_suite(tmp_path, "def test_never(): assert False", "--vandal", conftest=conftest)
    assert run.returncode == 4
    assert "Frame._click" in run.stderr and "1.60.0 and 1.64.0" in run.stderr
    assert run.stderr.count("1.60.0 and 1.64.0") == 1
    assert report is None


def test_applied_mutant_worker_deadline_stays_error(tmp_path):
    source = f'''
import os, json, time, pytest
from pathlib import Path
@pytest.mark.vandal(targets=["#b"])
def test_deadline(page):
    page.set_content({APP!r})
    page.locator("#b").count()
    worker = json.loads(os.environ.get("_VANDAL_WORKER", "{{}}"))
    if worker and not worker.get("control"):
        assert page.locator("#b").get_attribute("data-vandalized") == "logic_sabotage"
        Path("injected.txt").write_text("confirmed")
        time.sleep(30)
'''
    run, report = run_suite(tmp_path, source, "--vandal", "--vandal-timeout=8",
                           "--vandal-strategies=logic_sabotage")
    assert (tmp_path / "injected.txt").read_text() == "confirmed"
    assert run.returncode == 0
    assert report["summary"]["error"] == 1 and report["summary"]["killed"] == 0
    assert "timeout" in report["tests"][0]["mutants"][0]["details"].lower()


def test_page_assertion_after_click_is_observed_for_hint(tmp_path):
    source = f'''
from playwright.sync_api import expect
def test_flow(page):
    page.set_content({APP!r})
    page.click("#b")
    expect(page).to_have_url("about:blank")
'''
    run, report = run_suite(tmp_path, source, "--vandal", "--vandal-strategies=logic_sabotage")
    assert run.returncode == 0
    assert "A Playwright assertion ran after clicking #b" in report["tests"][0]["mutants"][0]["hint"]


@pytest.mark.parametrize("arguments", [["--html=x"], ["-p", "evil"], ["../outside.py::test"], ["-k"], ["-m="]])
def test_mcp_rejects_unbounded_pytest_options(tmp_path, arguments):
    with pytest.raises(ValueError):
        mcp_server.pytest_selection(arguments, tmp_path)


@pytest.mark.parametrize("deadline", [0, 601, float("nan"), True, "1"])
def test_mcp_deadline_validation(tmp_path, monkeypatch, deadline):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError):
        mcp_server.run_vandal(".", deadline_seconds=deadline)


def test_mcp_deadline_preserves_completed_mutants(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "test_partial.py").write_text('''
import time, pytest
@pytest.mark.vandal(targets=["#b"])
def test_first(page):
    page.set_content('<button id="b">Go</button>')
    page.click("#b")
@pytest.mark.vandal(targets=["#b"])
def test_slow(page):
    page.set_content('<button id="b">Go</button>')
    page.click("#b")
    time.sleep(12)
''')
    # Baselines plus first candidate finish before a bounded later worker.
    report = mcp_server.run_vandal("test_partial.py", ["logic_sabotage"],
                                   deadline_seconds=30, pytest_args=["-k", "first or slow"])
    assert report["timed_out"] is True, report
    assert report["summary"]["survived"] >= 1, report
    assert report["tests"][0]["mutants"][0]["status"] == "survived"
    assert json.loads((tmp_path / "vandal_report.json").read_text()) == report
    html = (tmp_path / "vandal_report.html").read_text()
    assert "Incomplete run: deadline reached" in html
    assert "completed mutants only" in html
    assert "test_partial.py::test_first" in html and "survived" in html


@pytest.mark.parametrize("operation", ["press", "type", "select_option", "hover",
                                       "focus", "dispatch_event", "set_input_files"])
def test_remaining_action_defaults(operation):
    planner = SimpleNamespace(strategies=None)
    test = {"explicit": None, "targets": {"#q": {"operations": [operation]}}}
    expected = (["data_sabotage"] if operation == "type" else
                ["stealth_disable", "ghost_element"] if operation == "hover" else [])
    assert VandalPlugin.candidates(planner, test, ["#q"]) == [(s, "#q") for s in expected]
    assert test["untested_targets"] == ([] if expected else ["#q"])
    test["targets"]["#q"]["operations"] += ["click", "fill"]
    pairs = VandalPlugin.candidates(planner, test, ["#q"])
    assert len(pairs) == len(set(pairs))


@pytest.mark.parametrize("api", ["sync", "async"])
def test_asserted_select_option_and_press_are_untested_by_default(tmp_path, api):
    html = '''<select id="s" onchange="document.querySelector('#selected').textContent=this.value">
    <option value="a">A</option><option value="b">B</option></select>
    <input id="q" onkeydown="if(event.key==='Enter') document.querySelector('#searched').textContent='searched'">
    <p id="selected">waiting</p><p id="searched">waiting</p>'''
    wait = "await " if api == "async" else ""
    source = f'''
import pytest
from playwright.{api}_api import expect
{"@pytest.mark.asyncio" if api == "async" else ""}
{"async " if api == "async" else ""}def test_input(ready):
    {wait}ready.locator("#s").select_option("b", timeout=1500)
    {wait}expect(ready.locator("#selected")).to_have_text("b", timeout=500)
    {wait}ready.locator("#q").press("Enter", timeout=1500)
    {wait}expect(ready.locator("#searched")).to_have_text("searched", timeout=500)
'''
    run, report = run_suite(tmp_path, source, "--vandal", conftest=fixture(api, html))
    assert run.returncode == 0, run.stdout + run.stderr
    test = report["tests"][0]
    assert test["baseline"] == "passed", report
    assert test["untested_targets"] == ["#s", "#q"]
    assert report["summary"]["survived"] == 0, report
    assert report["summary"]["error"] == 0, report
    assert [(m["strategy"], m["selector"]) for m in test["mutants"]] == [
        ("data_sabotage", "#selected"), ("data_sabotage", "#searched")]
    assert all(m["status"] == "killed" for m in test["mutants"]), report
    for selector in ("#s", "#q"):
        assert f"Vandal: {selector} was used but no default strategy applies; pass --vandal-strategies" in run.stdout


@pytest.mark.parametrize("api", ["sync", "async"])
@pytest.mark.parametrize("strategy", ["stealth_disable", "ghost_element"])
def test_hover_strategy_blocks_real_hover(tmp_path, api, strategy):
    html = '''<button id="b" onmouseover="document.querySelector('#result').textContent='hovered'">Hover</button>
    <p id="result">waiting</p>'''
    wait = "await " if api == "async" else ""
    source = f'''
import pytest
from playwright.{api}_api import expect
{"@pytest.mark.asyncio" if api == "async" else ""}
@pytest.mark.vandal(targets=["#b"])
{"async " if api == "async" else ""}def test_hover(ready):
    {wait}ready.locator("#b").hover(timeout=1500)
    {wait}expect(ready.locator("#result")).to_have_text("hovered", timeout=500)
'''
    run, report = run_suite(tmp_path, source, "--vandal", "--vandal-strategies=" + strategy,
                           conftest=fixture(api, html))
    assert run.returncode == 0, run.stdout + run.stderr
    test = report["tests"][0]
    assert test["baseline"] == "passed", report
    assert len(test["mutants"]) == 1, report
    mutant = test["mutants"][0]
    assert mutant["status"] == "killed", report
    assert mutant["kill_reason"] == "action_failed", report
    assert mutant["controls"] == {"before": "passed", "after": "passed"}


@pytest.mark.parametrize("explicit", [False, True])
def test_untested_defaults_are_separate_from_cap(tmp_path, explicit):
    # Simulate an observed extension operation without a default policy.
    conftest = '''
from vandal.instrumentation import Instrumentation
original_record = Instrumentation.record
def record(self, selector, operation, kwargs):
    original_record(self, selector, "extension_read" if selector == "#q" else operation, kwargs)
Instrumentation.record = record
'''
    source = '''
def test_flow(page):
    page.set_content('<input id="q"><button id="b">Go</button>')
    page.locator("#q").count()
    page.locator("#b").click(timeout=1500)
'''
    args = ["--vandal", "--vandal-max-mutants=1"]
    if explicit:
        args.append("--vandal-strategies=logic_sabotage")
    run, report = run_suite(tmp_path, source, *args, conftest=conftest)
    assert run.returncode == 0, run.stdout + run.stderr
    test = report["tests"][0]
    assert test["untested_targets"] == ([] if explicit else ["#q"])
    assert test["skipped_by_cap"] == (1 if explicit else 2)
    warning = "Vandal: #q was used but no default strategy applies; pass --vandal-strategies"
    assert (warning in run.stdout) == (not explicit)
    assert "Vandal: #b was used but no default strategy applies" not in run.stdout
    import jsonschema
    schema = json.loads((Path(__file__).parents[1] / "docs/report-schema.json").read_text())
    jsonschema.validate(report, schema)
    test["untested_targets"] = [1]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(report, schema)
