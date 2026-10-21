"""Version 1 of the automatic runner's report (separate from Vandal.save_report)."""
import html
import json
import os
import uuid
from pathlib import Path

SCHEMA_VERSION = 1
STATUSES = ("killed", "survived", "error", "not_applied", "skipped")


def summarize(mutants):
    counts = {status: sum(m["status"] == status for m in mutants) for status in STATUSES}
    denominator = counts["killed"] + counts["survived"]
    return dict(counts, score=100 * counts["killed"] / denominator if denominator else None)


def make_report(tests):
    for test in tests:
        test["summary"] = summarize(test["mutants"])
    return {
        "schema_version": SCHEMA_VERSION,
        "summary": summarize([m for test in tests for m in test["mutants"]]),
        "tests": tests,
    }


def survivors(report):
    if report.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported vandal report schema_version")
    return [
        dict(test=test["nodeid"], **mutant)
        for test in report["tests"]
        for mutant in test["mutants"]
        if mutant["status"] == "survived"
    ]


def score_text(score):
    return "N/A" if score is None else f"{score:.1f}%"


def report_paths(path):
    path = Path(path)
    html_path = path.with_suffix(".html")
    # Case-insensitive filesystems also alias report.HTML to report.html.
    if path.suffix.lower() == ".html" or path.resolve() == html_path.resolve():
        raise ValueError("JSON and HTML reports need distinct paths; use a .json destination")
    return path, html_path


def write_report(report, path):
    path, html_path = report_paths(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Readers always see a complete checkpoint, even if the process is killed.
    temporary = None
    try:
        # Let the OS apply the current umask without changing the process-wide
        # mask. NamedTemporaryFile would give the replaced report mode 0600.
        candidate = path.parent / (".vandal-" + uuid.uuid4().hex)
        descriptor = os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
        temporary = candidate
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(report, indent=2) + "\n")
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
    esc = lambda value: html.escape(str(value))
    incomplete = (
        "<p role='status'><strong>Incomplete run: deadline reached.</strong> "
        "Strength covers completed mutants only. Unfinished candidates are not "
        "included; do not interpret this as the full suite's strength.</p>"
        if report.get("timed_out") else ""
    )
    rows = []
    for test in report["tests"]:
        rows.append("<tr><th colspan='5'>" + esc(test["nodeid"]) + " | baseline: "
                    + esc(test["baseline"]) + " | strength: "
                    + score_text(test["summary"]["score"]) + "</th></tr>")
        for mutant in test["mutants"]:
            rows.append("<tr>" + "".join(
                "<td>" + esc(mutant[key]) + "</td>"
                for key in ("strategy", "selector", "status", "hint", "details")
            ) + "</tr>")
    html_path.write_text(
        "<!doctype html><html lang='en'><meta charset='utf-8'>"
        "<title>Vandal strength report</title><style>"
        "body{font-family:system-ui;margin:2rem}table{border-collapse:collapse;width:100%}"
        "td,th{border:1px solid #ccc;padding:.6rem;text-align:left;overflow-wrap:anywhere}"
        "</style><h1>Vandal strength: " + score_text(report["summary"]["score"]) +
        "</h1>" + incomplete + "<p>Survivors are candidates for review, not proof of missing assertions. "
        "Errors and unapplied mutations do not contribute to strength.</p><pre>" +
        esc(json.dumps(report["summary"], indent=2)) + "</pre><table>"
        "<tr><th>Strategy</th><th>Selector</th><th>Status</th><th>Hint</th><th>Details</th></tr>"
        + "".join(rows) + "</table></html>", encoding="utf-8",
    )
