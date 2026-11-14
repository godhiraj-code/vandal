"""Measure a scripted before/after example with real, isolated Vandal runs."""
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def stream_pytest(command, env, log):
    """Tee live pytest output, shortening only the plugin's mutant-start lines."""
    with subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                          errors="replace", bufsize=1) as process:
        for line in process.stdout:
            log.write(line)
            log.flush()
            # Pytest can leave its baseline progress on the same line as the
            # first mutant. Preserve that prefix and still announce the mutant.
            prefix, marker, message = line.rstrip("\r\n").partition("Vandal: ")
            parts = message.split(" | ", 2)
            if marker and len(parts) == 3:
                if prefix:
                    print(prefix, flush=True)
                _, strategy, selector = parts
                print(f"  mutating {selector} with {strategy}...", flush=True)
            else:
                print(line, end="", flush=True)
        return process.wait()


def read_measurement(path):
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("schema_version") != 1 or report.get("timed_out"):
        raise ValueError("Unsupported or incomplete report")
    tests = report["tests"]
    if len(tests) != 1 or tests[0]["baseline"] != "passed":
        raise ValueError("Expected one passing baseline")
    test = tests[0]
    mutants = test["mutants"]
    if test.get("skipped_by_cap") or test.get("untested_targets") or not mutants:
        raise ValueError("Expected complete mutation coverage for the selected targets")
    if any(m["status"] not in ("killed", "survived") for m in mutants):
        raise ValueError("Errors, skipped or unapplied mutants invalidate this comparison")
    score = report["summary"]["score"]
    calculated = 100 * sum(m["status"] == "killed" for m in mutants) / len(mutants)
    if not isinstance(score, (int, float)) or not math.isfinite(score) or score != calculated:
        raise ValueError("Missing or inconsistent measured score")
    return score, mutants


def measure(label, test_file, destination):
    destination.mkdir()
    report_path = destination / "vandal_report.json"
    command = [
        sys.executable, "-m", "pytest", str(HERE / test_file), "-q",
        "-p", "vandal.pytest_plugin", "--vandal", "--vandal-strict",
        "--vandal-max-mutants=20", "--vandal-timeout=30",
        f"--vandal-report={report_path}",
    ]
    if label == "Fixed":
        command.append("--vandal-min-score=100")
    # Keep unrelated installed plugins and user addopts out of this reproducible run.
    env = dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", PYTEST_ADDOPTS="",
               PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
    print(f"\n{label}: pytest --vandal {test_file}", flush=True)
    started = time.perf_counter()
    with (destination / "pytest.log").open("w", encoding="utf-8") as log:
        returncode = stream_pytest(command, env, log)
    if returncode:
        raise RuntimeError(f"pytest exited {returncode}; see {destination / 'pytest.log'}")
    score, mutants = read_measurement(report_path)
    killed = sum(m["status"] == "killed" for m in mutants)
    print(f"Strength: {score:.1f}% ({killed}/{len(mutants)} killed)", flush=True)
    survivors = [m for m in mutants if m["status"] == "survived"]
    for mutant in survivors:
        print(f"  SURVIVED {mutant['strategy']} on {mutant['selector']}", flush=True)
    if not survivors:
        print("  No surviving mutants.", flush=True)
    print(f"Measured pass time: {time.perf_counter() - started:.1f}s", flush=True)
    return score, {(m["strategy"], m["selector"]) for m in mutants}


def main():
    started = time.perf_counter()
    artifacts = HERE / "artifacts"
    artifacts.mkdir(exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix="run-", dir=artifacts))
    print("VANDAL | scripted agent-loop before / after", flush=True)
    print("Prewritten tests; no live agent is invoked.", flush=True)
    try:
        weak, weak_candidates = measure("Weak", "test_weak.py", output / "weak")
        print("\nRead survivors -> assert pickup name and order confirmation.", flush=True)
        fixed, fixed_candidates = measure("Fixed", "test_fixed.py", output / "fixed")
        if weak_candidates != fixed_candidates:
            raise ValueError("Before/after mutation candidates differ")
        if fixed <= weak:
            raise ValueError("Fixed strength must be higher than weak strength")
        print(f"\nPASS: {weak:.1f}% -> {fixed:.1f}%", flush=True)
        return 0
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        print(f"\nFAIL: {exc}", file=sys.stderr, flush=True)
        return 1
    finally:
        print(f"Elapsed: {time.perf_counter() - started:.1f}s", flush=True)
        print(f"Reports and logs: {output.relative_to(ROOT)}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
