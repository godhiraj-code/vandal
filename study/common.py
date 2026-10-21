"""Manifest validation shared by discovery and execution. No project imports."""
import csv
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path, PurePosixPath

FIELDS = ["repo", "commit_sha", "group", "evidence_kind", "evidence_url",
          "evidence_detail", "test_paths", "license", "license_url",
          "approved", "reviewer", "reviewed_at", "recipe", "observable_calls", "offline_risk"]
REPO = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")
# Conservative recognized subset, not a claim to enumerate all OSI licenses.
LICENSES = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC",
            "MPL-2.0", "GPL-2.0-only", "GPL-3.0-only", "AGPL-3.0-only"}


def safe_path(value):
    p = PurePosixPath(value)
    if (not value or not p.parts or p.is_absolute() or str(p) != value or
            any(x in {"..", "."} for x in p.parts) or
            any(c in value for c in "\\:\x00\r\n") or value.startswith("-")):
        raise ValueError("expected normalized relative POSIX path")
    return value


def paths(value):
    result = json.loads(value)
    if not isinstance(result, list) or not result or len(result) > 100:
        raise ValueError("test_paths must be a nonempty JSON list")
    for p in result:
        safe_path(p)
        if not p.endswith(".py"):
            raise ValueError("test selections must be Python files")
    return result


def candidate_reason(row):
    if not REPO.fullmatch(row.get("repo", "")):
        return "invalid repository identity"
    if not SHA.fullmatch(row.get("commit_sha", "")):
        return "commit must be a full lowercase SHA"
    if row.get("license") not in LICENSES:
        return "license requires explicit OSI verification/support"
    if row.get("group") != "agent":
        return "authorship is unresolved"
    allowed = {"agent": {"test_commit", "agent_pr"}}
    if row.get("evidence_kind") not in allowed[row["group"]]:
        return "authorship evidence does not support group"
    for key in ("evidence_url", "license_url"):
        if not row.get(key, "").startswith("https://github.com/" + row["repo"] + "/"):
            return "evidence/license URL must reference this repository"
    try:
        paths(row.get("test_paths", ""))
        safe_path(row.get("recipe", ""))
    except (ValueError, TypeError):
        return "invalid test paths or recipe path"
    return None


def approval_reason(row):
    problem = candidate_reason(row)
    if problem:
        return problem
    if row.get("approved") != "yes" or not row.get("reviewer", "").strip():
        return "not approved by a person"
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", row.get("reviewed_at", "")):
        return "missing UTC review timestamp"
    try:
        datetime.strptime(row["reviewed_at"], "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return "invalid UTC review timestamp"
    return None


def read_rows(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != FIELDS:
            raise ValueError("manifest columns must match study/common.py FIELDS")
        rows = list(reader)
    if any(None in r or None in r.values() for r in rows):
        raise ValueError("malformed CSV row")
    identities = [(r["repo"].lower(), r["commit_sha"]) for r in rows]
    if len(identities) != len(set(identities)):
        raise ValueError("duplicate repository/commit")
    return rows


def write_rows(path, rows):
    with Path(path).open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
