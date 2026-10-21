"""Owned pilot preflight and artifact summary; never execute candidate code."""
import argparse
import html
import json
from pathlib import Path

from study.common import approval_reason, paths, read_rows
from study.run_study import confirmation
from study.summarize import read_results
from study.worker import validate_recipe


def preflight(manifest, confirm):
    if confirm != confirmation(manifest):
        raise ValueError("confirm must exactly match the manifest RUN token")
    rows = read_rows(manifest)
    if not rows:
        raise ValueError("manifest has no approved rows")
    for row in rows:
        reason = approval_reason(row)
        if reason:
            raise ValueError(row["repo"] + ": " + reason)
        recipe_path = (manifest.parent / row["recipe"]).resolve()
        if manifest.parent.resolve() not in recipe_path.parents:
            raise ValueError("recipe escapes manifest directory")
        recipe = validate_recipe(json.loads(recipe_path.read_text()))
        if recipe["test_paths"] != paths(row["test_paths"]):
            raise ValueError("recipe differs from reviewed selection")
    return rows


def safe(value):
    return html.escape(str(value)).replace("|", "&#124;").replace("\n", " ").replace("\r", " ")


def summary(manifest, results, image_file, destination):
    rows, _ = read_results(results)
    by_identity = {(r["repo"], r["commit_sha"]): r for r in rows}
    image = image_file.read_text().strip() if image_file.exists() else "not built"
    lines = ["# Study pilot", "", "Image ID: " + safe(image), "", "Manifest confirmation: " + confirmation(manifest), "",
             "| Repository / SHA | Status | Baseline | Score % (n scored) | Reason |", "|---|---|---|---|---|"]
    for selected in read_rows(manifest):
        row = by_identity.get((selected["repo"], selected["commit_sha"]), {})
        baseline = "not observed"
        if row:
            try:
                status = json.loads((results / row["run_path"] / "status.json").read_text())
                worker = status.get("worker", status)
                record = worker.get("baseline", {})
                if not isinstance(record, dict):
                    raise ValueError("invalid baseline record")
                if record:
                    baseline = "exit=" + str(record.get("exit_code", "unknown")) + "; timeout=" + str(record.get("timed_out", "unknown"))
            except (OSError, ValueError, TypeError, AttributeError, RecursionError):
                baseline = "unavailable: malformed evidence"
        score = f"{row['score']:.1f}" if row.get("eligible") and row.get("score") is not None else "N/A"
        values = [selected["repo"] + " / " + selected["commit_sha"], row.get("status", "not run"), baseline,
                  score + " (n=" + str(row.get("n_scored", "N/A")) + ")", row.get("reason", "no recorded attempt")]
        lines.append("| " + " | ".join(safe(v) for v in values) + " |")
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["preflight", "summary"])
    parser.add_argument("--repos", type=Path, default=Path("study/repos.csv"))
    parser.add_argument("--confirm")
    parser.add_argument("--results", type=Path, default=Path("study/results/public"))
    parser.add_argument("--image", type=Path, default=Path("study/pilot-image-id.txt"))
    parser.add_argument("--output", type=Path, default=Path("study/PILOT_SUMMARY.md"))
    args = parser.parse_args()
    if args.action == "preflight":
        print("Validated approved rows:", len(preflight(args.repos, args.confirm)))
    else:
        summary(args.repos, args.results, args.image, args.output)


if __name__ == "__main__":
    main()
