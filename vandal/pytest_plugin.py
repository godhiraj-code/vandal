"""Automatic, isolated pytest mutation runs. Inactive for ordinary pytest runs."""
import json
import math
import os
from pathlib import Path
import sys
import tempfile

import pytest

from .core import VandalEngine
from .instrumentation import Instrumentation, CLICK_OPERATIONS, READ_OPERATIONS, check_compatibility
from .reporting import make_report, report_paths, score_text, survivors, write_report
from .runner import run_process

WORKER_ENV = "_VANDAL_WORKER"


def pytest_addoption(parser):
    group = parser.getgroup("vandal")
    group.addoption("--vandal", action="store_true", help="Measure Playwright test strength")
    group.addoption("--vandal-strategies", default=None, help="Explicit strategies; otherwise infer from target usage")
    group.addoption("--vandal-strict", action="store_true", help="Fail when mutant errors are recorded")
    group.addoption("--vandal-max-mutants", type=int, default=20, help="Maximum mutants per test")
    group.addoption("--vandal-timeout", type=float, default=60, help="Seconds per worker, including fixtures")
    group.addoption("--vandal-min-score", type=float, default=None)
    group.addoption("--vandal-report", default="vandal_report.json")


def pytest_configure(config):
    config.addinivalue_line("markers", "vandal(targets): explicit Playwright selectors to mutate")
    if not config.getoption("vandal"):
        return
    try:
        report_paths(config.getoption("vandal_report"))
    except ValueError as exc:
        raise pytest.UsageError(str(exc)) from exc
    try:
        check_compatibility()
    except (ValueError, ImportError, AttributeError) as exc:
        raise pytest.UsageError(f"{exc} (adapter tested on Playwright 1.60.0 and 1.64.0)") from exc
    option = config.getoption("vandal_strategies")
    strategies = list(dict.fromkeys(option.split(","))) if option is not None else None
    if strategies is not None and (not strategies or any(s not in VandalEngine.MUTATIONS for s in strategies)):
        raise pytest.UsageError("Unknown or empty --vandal-strategies")
    if config.getoption("vandal_max_mutants") < 1:
        raise pytest.UsageError("--vandal-max-mutants must be positive")
    timeout = config.getoption("vandal_timeout")
    if not math.isfinite(timeout) or timeout <= 0:
        raise pytest.UsageError("--vandal-timeout must be finite and positive")
    minimum = config.getoption("vandal_min_score")
    if minimum is not None and (not math.isfinite(minimum) or not 0 <= minimum <= 100):
        raise pytest.UsageError("--vandal-min-score must be between 0 and 100")
    if getattr(config.option, "numprocesses", 0) or getattr(config.option, "dist", "no") != "no":
        raise pytest.UsageError("--vandal currently requires serial pytest (no xdist)")
    if getattr(config.option, "reruns", 0):
        raise pytest.UsageError("--vandal cannot be combined with pytest-rerunfailures")
    state = VandalPlugin(config, strategies)
    config.pluginmanager.register(state, "vandal-runner")


def classify(result, returncode, controls=None):
    phases = result.get("phases", {})
    if returncode not in (0, 1) or result.get("injection_errors"):
        return "error", "Worker or mutation injection failed: " + "; ".join(result.get("injection_errors", []))
    if any(phases.get(p, {}).get("outcome") != "passed" for p in ("setup", "teardown")):
        return "error", "Setup or teardown did not pass: " + "\n".join(
            phases.get(p, {}).get("details", "") for p in ("setup", "teardown")
        )
    call = phases.get("call", {})
    if call.get("xfail") or call.get("outcome") == "skipped":
        return "skipped", "Skipped or expected-failure test is not scored"
    if call.get("outcome") not in ("passed", "failed"):
        return "error", "Missing or incomplete test call"
    detected = call.get("assertion") or call.get("playwright_error")
    if call["outcome"] == "failed" and (not detected or not result.get("applied")):
        return "error", call.get("details", "Test failed without a confirmed assertion kill")
    if call["outcome"] == "passed" and returncode != 0:
        return "error", "Worker exited unsuccessfully despite a passing test call"
    if not result.get("applied"):
        return "not_applied", "No target was confirmed mutated during the test call"
    if call.get("outcome") == "passed" and returncode == 0:
        return "survived", "Test passed after confirmed mutation"
    if call.get("outcome") == "failed" and detected and returncode == 1:
        if call.get("playwright_error") and (not controls or any(controls.get(p) != "passed" for p in ("before", "after"))):
            return "error", "Playwright call failed without both passing unmutated controls"
        return "killed", call.get("details", "Assertion failed")
    return "error", call.get("details", "Non-assertion failure or incomplete worker")


class VandalPlugin:
    def __init__(self, config, strategies):
        self.config = config
        self.strategies = strategies
        self.worker = json.loads(os.environ[WORKER_ENV]) if WORKER_ENV in os.environ else None
        self.tests = {}
        self.current = None
        self.phase = None
        self.applied = 0
        self.injection_errors = []
        self.report = None
        self.instrumentation = Instrumentation(self)
        self.instrumentation.install()

    @pytest.hookimpl(trylast=True)
    def pytest_collection_modifyitems(self, session, config, items):
        if self.worker:
            selected = [item for item in items if item.nodeid == self.worker["nodeid"]]
            config.hook.pytest_deselected(items=[item for item in items if item not in selected])
            items[:] = selected

    def pytest_collection_finish(self, session):
        # Some normal pytest selectors (notably --lf) finish in collection hook
        # wrappers. Record only the final selection, after those wrappers unwind.
        for item in session.items:
            marker = item.get_closest_marker("vandal")
            targets = marker.kwargs.get("targets") if marker else None
            if targets is not None and (
                not isinstance(targets, (list, tuple))
                or any(not isinstance(t, str) or not t for t in targets)
            ):
                raise pytest.UsageError("vandal targets must be a list of nonempty selectors")
            self.tests[item.nodeid] = {
                "nodeid": item.nodeid, "explicit": targets, "targets": {}, "phases": {},
            }

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_protocol(self, item, nextitem):
        self.current = self.tests[item.nodeid]
        yield
        self.current = None
        self.phase = None

    def pytest_runtest_setup(self, item):
        self.phase = "setup"

    def pytest_runtest_call(self, item):
        self.phase = "call"

    def pytest_runtest_teardown(self, item):
        self.phase = "teardown"

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item, call):
        outcome = yield
        report = outcome.get_result()
        from playwright._impl._errors import Error
        self.tests[item.nodeid]["phases"][report.when] = {
            "outcome": report.outcome,
            "assertion": bool(call.excinfo and isinstance(call.excinfo.value, AssertionError)),
            "playwright_error": bool(call.excinfo and isinstance(call.excinfo.value, Error)),
            "xfail": hasattr(report, "wasxfail"),
            "details": str(report.longrepr)[-3000:] if report.failed else "",
        }

    def run_worker(self, test, strategy, selector, directory, control=False):
        worker_dir = Path(tempfile.mkdtemp(prefix="worker-", dir=directory))
        destination = worker_dir / "result.json"
        worker = dict(nodeid=test["nodeid"], strategy=strategy, selector=selector,
                      output=str(destination), control=control)
        env = dict(os.environ, **{WORKER_ENV: json.dumps(worker)})
        for key in list(env):
            if key.startswith("COV_CORE_") or key == "COVERAGE_PROCESS_START":
                env.pop(key)
        env["COVERAGE_FILE"] = str(worker_dir / ".coverage")
        # Preserve the original options and replay the exact selected nodeid.
        # Mutation failures must never poison the real suite's --lf cache.
        command = [sys.executable, "-m", "pytest", *self.config.invocation_params.args]
        command.append(f"--basetemp={worker_dir / 'pytest-temp'}")
        if getattr(self.config.option, "xmlpath", None):
            command.append(f"--junitxml={worker_dir / 'junit.xml'}")
        if self.config.pluginmanager.hasplugin("playwright"):
            command.append(f"--output={worker_dir / 'playwright'}")
        # Override options from CLI, addopts and config without touching the
        # baseline's output. Each worker owns its reporter destinations.
        if self.config.pluginmanager.hasplugin("logging"):
            # A final CLI override also wins over ini and PYTEST_ADDOPTS paths.
            command.append(f"--log-file={worker_dir / 'pytest.log'}")
        if getattr(self.config.option, "htmlpath", None):
            command.append(f"--html={worker_dir / 'report.html'}")
        if self.config.pluginmanager.hasplugin("pytest_cov"):
            command.append("--no-cov")
        if getattr(self.config.option, "allure_report_dir", None):
            command.append(f"--alluredir={worker_dir / 'allure'}")
        if self.config.pluginmanager.hasplugin("cacheprovider"):
            # Baseline --lf selection is already resolved. A worker's empty,
            # isolated cache must not deselect it after the baseline now passes.
            command.extend(["-o", f"cache_dir={worker_dir / 'cache'}", "--lfnf=all"])
        try:
            code, output, timeout = run_process(
                command, cwd=str(self.config.invocation_params.dir),
                timeout=self.config.getoption("vandal_timeout"), env=env,
            )
            if timeout:
                return None, code, "Worker timeout (including setup/teardown)"
            if not destination.exists():
                return None, code, "Worker produced no result: " + output
            result = json.loads(destination.read_text(encoding="utf-8"))
            return result, code, None
        except (OSError, ValueError) as exc:
            return None, None, str(exc)

    def clean_replay(self, test, strategy, selector, directory):
        result, code, error = self.run_worker(test, strategy, selector, directory, control=True)
        if error:
            return error
        phases = result.get("phases", {})
        if code != 0 or any(
            phases.get(phase, {}).get("outcome") != "passed"
            or phases.get(phase, {}).get("xfail")
            for phase in ("setup", "call", "teardown")
        ):
            details = "\n".join(phases.get(p, {}).get("details", "")
                                for p in ("setup", "call", "teardown"))
            return f"Unmutated worker exited {code} without three passing phases. {details}"
        return None

    def run_mutant(self, test, strategy, selector, directory):
        # A fresh Python process does not reset files, databases or services.
        # Require a clean replay before every mutant, and again after a putative
        # kill, to exclude reproducible replay/state failures from the score.
        controls = {"before": "passed", "after": "not_run"}
        result = None
        error = self.clean_replay(test, strategy, selector, directory)
        if error:
            controls["before"] = "error"
            status, details = "error", "Clean replay before mutation failed: " + error
        else:
            result, code, error = self.run_worker(test, strategy, selector, directory)
            call = (result or {}).get("phases", {}).get("call", {})
            candidate = (not error and result.get("applied") and not result.get("injection_errors")
                         and code == 1 and call.get("outcome") == "failed"
                         and (call.get("assertion") or call.get("playwright_error")))
            if candidate:
                error = self.clean_replay(test, strategy, selector, directory)
                controls["after"] = "error" if error else "passed"
                if error:
                    error = "Clean replay after mutation failed: " + error
            status, details = ("error", error) if error else classify(result, code, controls)
        event = test["targets"].get(selector, {})
        if event.get("force"):
            hint = "Uses force=True; review actionability and assert the user-visible outcome."
        elif any(op in event.get("operations", []) for op in CLICK_OPERATIONS):
            trace = test.get("trace", [])
            last_click = max((i for i, (target, op) in enumerate(trace)
                              if target == selector and op in CLICK_OPERATIONS), default=-1)
            asserted = any(op.startswith("expect:") for _, op in trace[last_click + 1:])
            hint = (f"A Playwright assertion ran after clicking {selector}; review its outcome checks."
                    if asserted else f"No Playwright assertion ran after clicking {selector}; review Python assertions and the outcome.")
        else:
            hint = f"Used {selector}; check assertions about its value, state, or resulting behavior."
        mutant = dict(strategy=strategy, selector=selector, status=status, hint=hint,
                      details=details, controls=controls)
        if status == "killed":
            mutant["kill_reason"] = "assertion" if result["phases"]["call"].get("assertion") else "action_failed"
        return mutant

    def candidates(self, test, targets):
        choices = {}
        for target in targets:
            operations = test["targets"].get(target, {}).get("operations", [])
            # Explicit aliases (e.g. CSS marker with a role operation) use the
            # observed test operations when their spelling has no exact match.
            if not operations and test["explicit"] is not None:
                operations = [op for e in test["targets"].values() for op in e["operations"]]
            inferred = []
            if any(op in CLICK_OPERATIONS for op in operations):
                inferred += ["stealth_disable", "ghost_element", "logic_sabotage"]
            if any(op in READ_OPERATIONS or op.startswith("expect:") for op in operations):
                inferred.append("data_sabotage")
            choices[target] = self.strategies if self.strategies is not None else inferred
        # Round-robin targets: a small cap must not exhaust one target first.
        return [(choices[t][i], t) for i in range(max(map(len, choices.values()), default=0))
                for t in targets if i < len(choices[t])]

    @pytest.hookimpl(trylast=True)
    def pytest_sessionfinish(self, session, exitstatus):
        if self.worker:
            test = self.tests.get(self.worker["nodeid"], {})
            Path(self.worker["output"]).write_text(json.dumps({
                "phases": test.get("phases", {}), "applied": self.applied,
                "injection_errors": self.injection_errors,
            }), encoding="utf-8")
            return
        if self.config.option.collectonly:
            return
        tests = []
        terminal = self.config.pluginmanager.get_plugin("terminalreporter")
        with tempfile.TemporaryDirectory(prefix="vandal-") as temporary:
            for test in self.tests.values():
                phases = test["phases"]
                baseline = "passed"
                if any(p.get("outcome") == "failed" for p in phases.values()):
                    baseline = "baseline failing"
                elif any(phases.get(p, {}).get("outcome") != "passed" or
                         phases.get(p, {}).get("xfail") for p in ("setup", "call", "teardown")):
                    baseline = "skipped"
                targets = test["explicit"] if test["explicit"] is not None else list(test["targets"])
                entry = dict(nodeid=test["nodeid"], baseline=baseline, targets=targets, mutants=[])
                tests.append(entry)
                if baseline != "passed" or exitstatus not in (0, 1):
                    continue
                candidates = self.candidates(test, targets)
                entry["skipped_by_cap"] = max(0, len(candidates) - self.config.getoption("vandal_max_mutants"))
                # Atomic checkpoints let a bounded MCP caller recover completed
                # mutants even when it must terminate the active worker tree.
                write_report(make_report(tests), self.config.getoption("vandal_report"))
                for strategy, selector in candidates[:self.config.getoption("vandal_max_mutants")]:
                    if terminal:
                        terminal.write_line(f"Vandal: {test['nodeid']} | {strategy} | {selector}")
                    entry["mutants"].append(self.run_mutant(test, strategy, selector, Path(temporary)))
                    write_report(make_report(tests), self.config.getoption("vandal_report"))
        self.report = make_report(tests)
        write_report(self.report, self.config.getoption("vandal_report"))
        minimum = self.config.getoption("vandal_min_score")
        score = self.report["summary"]["score"]
        reasons = []
        if self.config.getoption("vandal_strict") and self.report["summary"]["error"]:
            reasons.append(f"{self.report['summary']['error']} mutant errors with --vandal-strict")
        if minimum is not None and (score is None or score < minimum):
            reasons.append(f"strength {score_text(score)} is below --vandal-min-score {minimum:g}"
                           if score is not None else f"no scored mutants for --vandal-min-score {minimum:g}")
        if exitstatus == 0 and reasons:
            session.exitstatus = pytest.ExitCode.TESTS_FAILED
            if terminal:
                terminal.write_line("Vandal: " + "; ".join(reasons))

    def pytest_terminal_summary(self, terminalreporter):
        if not self.report:
            return
        terminalreporter.section("Vandal strength")
        summary = self.report["summary"]
        terminalreporter.write_line(score_text(summary["score"]) + " | " + ", ".join(
            f"{summary[key]} {key.replace('_', ' ')}" for key in ("killed", "survived", "error", "not_applied", "skipped")))
        for test in self.report["tests"]:
            terminalreporter.write_line(
                f"{test['nodeid']}: {test['baseline']}, {score_text(test['summary']['score'])}, "
                f"{test.get('skipped_by_cap', 0)} skipped by cap"
            )
        for mutant in survivors(self.report):
            terminalreporter.write_line(
                f"SURVIVED {mutant['test']} | {mutant['strategy']} | {mutant['selector']} | {mutant['hint']}"
            )

    def pytest_unconfigure(self, config):
        self.instrumentation.restore()
