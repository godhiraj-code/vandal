"""Recompute results from raw reports; never estimate missing observations."""
import argparse
import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from study.common import approval_reason, digest

STATUSES = ("killed", "survived", "error", "not_applied", "skipped")


def counts(mutants):
    if not isinstance(mutants, list) or any(not isinstance(m, dict) for m in mutants):
        raise ValueError("mutants must be a list of objects")
    if any(m.get("status") not in STATUSES for m in mutants):
        raise ValueError("unknown mutant status")
    result = {s: sum(m["status"] == s for m in mutants) for s in STATUSES}
    n = result["killed"] + result["survived"]
    result["score"] = 100 * result["killed"] / n if n else None
    return result


def validate_summary(recorded, actual):
    for key, value in actual.items():
        other = recorded.get(key)
        if key == "score" and value is not None:
            if not isinstance(other, (float, int)) or isinstance(other, bool) or not math.isfinite(other) or not math.isclose(other, value):
                raise ValueError("summary score disagrees with mutants")
        elif other != value or (key != "score" and type(other) is not int):
            raise ValueError("summary counts disagree with mutants")


def metrics(report):
    if not isinstance(report, dict) or report.get("schema_version") != 1 or not isinstance(report.get("tests"), list):
        raise ValueError("unsupported or invalid report schema")
    mutants, nodeids = [], set()
    untested_targets, capped = 0, 0
    for test in report["tests"]:
        if not isinstance(test, dict):
            raise ValueError("test records must be objects")
        if not isinstance(test.get("nodeid"), str) or test["nodeid"] in nodeids:
            raise ValueError("missing or duplicate test identity")
        nodeids.add(test["nodeid"])
        if test.get("baseline") not in {"passed", "baseline failing", "skipped"}:
            raise ValueError("invalid baseline status")
        validate_summary(test["summary"], counts(test["mutants"]))
        mutants.extend(test["mutants"])
        targets = test.get("untested_targets", [])
        cap = test.get("skipped_by_cap", 0)
        if (not isinstance(targets, list) or any(not isinstance(t, str) for t in targets)
                or type(cap) is not int or cap < 0):
            raise ValueError("invalid untested target/cap metadata")
        untested_targets += len(set(targets))
        capped += cap
    result = counts(mutants)
    validate_summary(report["summary"], result)
    result.update(n_tests=len(nodeids), n_mutants=len(mutants),
                  n_scored=result["killed"] + result["survived"],
                  untested=result["not_applied"] + result["skipped"],
                  untested_targets=untested_targets, skipped_by_cap=capped,
                  action_failed_kills=sum(m.get("status") == "killed" and m.get("kill_reason") == "action_failed" for m in mutants))
    strategies = defaultdict(Counter)
    for m in mutants:
        if not isinstance(m.get("strategy"), str):
            raise ValueError("invalid strategy")
        strategies[m["strategy"]][m["status"]] += 1
    return result, strategies


def spread(values):
    if not values:
        return {"n": 0, "median": None, "min": None, "max": None, "iqr": None}
    q = statistics.quantiles(values, n=4, method="inclusive") if len(values) > 1 else None
    return {"n": len(values), "median": statistics.median(values),
            "min": min(values), "max": max(values), "iqr": q[2] - q[0] if q else None}


def read_results(root):
    rows, strategies, seen = [], defaultdict(Counter), set()
    for path in sorted(root.rglob("status.json")):
        row = {"repo": str(path.parent.relative_to(root)), "commit_sha": "", "kind": "unknown",
               "group": "unknown", "status": "invalid", "reason": "", "eligible": False}
        try:
            status = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(status, dict):
                raise ValueError("status must be an object")
            row.update({k: status[k] for k in ("repo", "commit_sha", "kind", "group", "status", "reason")})
            if any(not isinstance(row[k], str) for k in ("repo", "commit_sha", "kind", "group", "status", "reason")):
                raise ValueError("invalid status field types")
            identity = row["repo"].lower()
            if row["kind"] == "public" and identity in seen:
                for previous in rows:
                    if previous["repo"].lower() == identity:
                        previous.update(status="invalid", reason="duplicate repository runs", eligible=False)
                raise ValueError("duplicate run; select one preregistered run per repository")
            if row["kind"] == "public":
                seen.add(identity)
            for name, sha in status.get("artifact_sha256", {}).items():
                from study.common import safe_path
                safe_path(name)
                file = path.parent / name
                if file.is_symlink() or path.parent.resolve() not in file.resolve().parents or digest(file) != sha:
                    raise ValueError("artifact hash mismatch: " + name)
            report_path = path.parent / "vandal_report.json"
            if report_path.exists():
                report = json.loads(report_path.read_text(encoding="utf-8"))
                calculated, per_strategy = metrics(report)
                row.update(calculated)
                if report.get("timed_out") or report.get("execution", {}).get("exit_code", 0) != 0:
                    row.update(status="incomplete", reason="raw report is incomplete or has failing execution")
                elif any(t["baseline"] != "passed" for t in report["tests"]):
                    row.update(status="incomplete", reason="mutation baseline did not exercise every selected test")
                if row["status"] == "completed" and not row["n_scored"]:
                    row.update(status="unscored", reason="no killed/survived mutants")
                kind = status.get("manifest", {}).get("evidence_kind")
                row["eligible"] = (row["status"] == "completed" and row["kind"] == "public"
                                   and row["group"] == "agent" and kind != "guidance_only"
                                   and approval_reason(status.get("manifest", {})) is None)
                if row["kind"] == "public" and row["status"] == "completed":
                    if approval_reason(status.get("manifest", {})):
                        raise ValueError("public completed run lacks valid person approval")
                    if "vandal_report.json" not in status.get("artifact_sha256", {}):
                        raise ValueError("public report lacks integrity hash")
                    if any(row[k] != status["manifest"][k] for k in ("repo", "group", "commit_sha")):
                        raise ValueError("result differs from reviewed repository/group/SHA")
                row["_strategies"] = per_strategy
            elif row["status"] == "completed":
                raise ValueError("completed run is missing its raw report")
        except (OSError, ValueError, KeyError, TypeError, AttributeError, RecursionError) as exc:
            row.update(status="invalid", reason=str(exc), eligible=False)
        rows.append(row)
    for row in rows:
        per_strategy = row.pop("_strategies", {})
        if row["eligible"]:
            for strategy, counter in per_strategy.items():
                strategies[(row["group"], strategy)].update(counter)
                strategies[(row["group"], strategy)]["n_repos"] += 1
    return rows, strategies


def cell(value):
    if value is None or value == "":
        return "N/A"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value).replace("|", "\\|").replace("\n", " ")


def summarize(root, report_path):
    rows, strategies = read_results(root)
    failures = [r for r in rows if r["kind"] == "fixture" and r["status"] != "completed"]
    visible = [r for r in rows if r not in failures]
    failure_path = report_path.with_name("FIXTURE_ATTEMPTS.md")
    failure_lines = ["# Earlier owned-fixture attempts", "", "Historical validation failures; excluded from the descriptive public study.", ""]
    failure_lines += [f"- {cell(r['repo'])}: {cell(r['status'])}; {cell(r['reason'])} (n attempts=1)." for r in failures]
    failure_lines += ["", f"Failed/incomplete owned-fixture attempts: n={len(failures)}. Raw artifacts remain under results/pilot/; see VALIDATION.md for the chronological record.", ""]
    failure_path.write_text("\n".join(failure_lines), encoding="utf-8")
    columns = ["repo", "commit_sha", "kind", "group", "status", "eligible", "score",
               "n_tests", "n_mutants", "n_scored", *STATUSES, "untested", "untested_targets",
               "skipped_by_cap", "action_failed_kills", "reason"]
    root.mkdir(parents=True, exist_ok=True)
    with (root / "summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    title = "Study protocol and results" if any(r["kind"] == "public" for r in rows) else "Study protocol and results (no public runs yet)"
    lines = ["# " + title, "",
             f"Public agent-suite sample: n={sum(r['eligible'] for r in rows)} repositories. Public attempts: n={sum(r['kind'] == 'public' for r in rows)}.", "",
             "This is a descriptive study of agent-written suites only. No comparison population or causal claim is defined.", "",
             f"Completed owned-fixture validations: n={sum(r['kind'] == 'fixture' for r in visible)} attempts of one fixture; not study subjects. Earlier failed fixture attempts are retained in [FIXTURE_ATTEMPTS.md](FIXTURE_ATTEMPTS.md).", "",
             "Results are limited to the repositories and selected tests actually executed. No population or causal inference is justified.", "",
             "## Per repository", "",
             "Counts below are observed mutants, with n_tests and n_mutants shown per row. Score is 100 × killed / n_scored; n_scored = killed + survived. N/A means no observation, not zero.", "",
             "| Repository / kind / group | Status | Score % (n_scored) | n_tests / n_mutants | Killed | Survived | Error | Untested mutants | Unsupported targets | Cap omissions |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for r in visible:
        lines.append("| " + " | ".join(map(cell, [f"{r['repo']} / {r['kind']} / {r['group']}", r["status"],
            f"{cell(r.get('score'))} (n={cell(r.get('n_scored'))})", f"{cell(r.get('n_tests'))} / {cell(r.get('n_mutants'))}",
            *[r.get(k) for k in ("killed", "survived", "error", "untested", "untested_targets", "skipped_by_cap")]])) + " |")
    lines += ["", "Untested mutants = not_applied + skipped. Unsupported targets and cap omissions are separate units and are not added to that count or score denominator.", "",
              "## Descriptive agent-suite results", "",
              "One complete, scored observation per repository; repository-weighted median, inclusive-quartile IQR and min-max spread. Guidance-only provenance, incomplete runs, invalid reports and owned fixtures are excluded. IQR is N/A below two repositories.", "",
              "| n repositories | Median % | IQR percentage points | Min-max % |", "|---|---|---|---|"]
    data = spread([r["score"] for r in rows if r["eligible"]])
    lines.append(f"| {data['n']} | {cell(data['median'])} | {cell(data['iqr'])} | {cell(data['min'])}-{cell(data['max'])} |")
    if not data["n"]:
        lines += ["", "No eligible public results exist. No strength estimate is reported for agent-written suites."]
    lines += ["", "## Strategy survival", "",
              "Pooled by mutant, ranked by survivors; larger suites contribute more weight. Survival rate is among killed + survived. Both n_repos and n_mutants are shown. Error/untested outcomes remain outside the rate.", "",
              "| Strategy | n_repos | n_mutants | Survived / n scored | Survival % | Errors | Untested mutants |", "|---|---|---|---|---|---|---|"]
    for (group, strategy), c in sorted(strategies.items(), key=lambda item: (-item[1]["survived"], item[0])):
        n = c["killed"] + c["survived"]
        rate = c["survived"] * 100 / n if n else None
        lines.append(f"| {cell(strategy)} | {c['n_repos']} | {sum(c[s] for s in STATUSES)} | {c['survived']} / {n} | {cell(rate)} | {c['error']} | {c['skipped'] + c['not_applied']} |")
    if not strategies:
        lines += ["", "No eligible strategy observations (n repositories=0)."]
    lines += ["", "## Exclusions and limitations", ""]
    for r in visible:
        if not r["eligible"]:
            lines.append(f"- {cell(r['repo'])}: {cell(r['reason'] or ('owned fixture excluded' if r['kind'] == 'fixture' else 'provenance or group ineligible'))} (n runs=1).")
    lines += ["", "Selection is a convenience sample from bounded GitHub search, not a random sample. Visible co-authorship is evidence of agent involvement, not exclusive agent authorship. Only test-specific agent involvement is in scope; guidance alone cannot establish authorship.", "",
              "Offline, no-secret execution selects for self-contained suites; external CDNs, services and complex install requirements can cause exclusions. All-skip and partially skipped baselines are excluded. A single baseline cannot establish lack of flakiness.", "",
              "Default Vandal strategies and its per-test cap depend on observed interactions. Scores across different apps, assertions, targets and strategy mixes are not directly comparable. Controlled action failures count as kills and need not imply an outcome assertion. Mutant errors remain visible but outside the score denominator.", "",
              "Candidate processes can tamper with their own in-container reports. Stored hashes detect later changes, not dishonest execution. Independently inspect raw logs and source before publication. No claim that container isolation or its Docker integration has been validated follows from a host-only fixture test.", ""]
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return rows


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results", type=Path, default=Path("study/results"))
    p.add_argument("--report", type=Path, default=Path("study/REPORT.md"))
    args = p.parse_args()
    summarize(args.results, args.report)


if __name__ == "__main__":
    main()
