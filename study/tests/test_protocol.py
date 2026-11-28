import io
import json
import sys
import tarfile
from pathlib import Path

import pytest

from study.process import clean_env
from study.protocol_run import FIELDS, confirmation, plan
from study.run_study import stage_overlay
from study.worker import execute, extract_overlay, flake_summary, validate_recipe


def junit(path, outcomes):
    cases = []
    for name, outcome in outcomes.items():
        inner = {"failed": "<failure message='x'/>", "skipped": "<skipped/>"}.get(outcome, "")
        cases.append(f"<testcase classname='t' name='{name}'>{inner}</testcase>")
    path.write_text("<testsuites><testsuite>" + "".join(cases) + "</testsuite></testsuites>")
    return path


def test_recipe_repeats_and_overlay_bounds():
    assert validate_recipe({"test_paths": ["a/test_x.py"], "repeats": 10, "overlay_root": "a"})["repeats"] == 10
    for bad in (0, 11, True, "3"):
        with pytest.raises(ValueError):
            validate_recipe({"test_paths": ["a/test_x.py"], "repeats": bad})
    with pytest.raises(ValueError):
        validate_recipe({"test_paths": ["other/test_x.py"], "overlay_root": "a"})
    with pytest.raises(ValueError):
        validate_recipe({"test_paths": ["a/test_x.py"], "overlay_root": "../a"})


def test_flake_summary_counts_mixed_results_only(tmp_path):
    runs = [junit(tmp_path / "1.xml", {"a": "passed", "b": "passed", "c": "failed"}),
            junit(tmp_path / "2.xml", {"a": "passed", "b": "failed", "c": "failed"}),
            tmp_path / "missing.xml"]
    summary = flake_summary(runs)
    assert summary["runs"] == 3 and summary["green_runs"] == 0 and summary["n_tests"] == 3
    assert summary["flaky_tests"] == ["t::a", "t::b"]
    assert summary["always_failed_tests"] == ["t::c"]
    assert summary["flake_rate"] == pytest.approx(2 / 3)
    green = flake_summary([junit(tmp_path / f"g{i}.xml", {"a": "passed"}) for i in range(3)])
    assert green["green_runs"] == 3 and green["n_flaky"] == 0 and green["flake_rate"] == 0


def overlay_tar(tmp_path, members):
    path = tmp_path / "overlay.tar"
    with tarfile.open(path, "w") as tar:
        for name, kind in members:
            info = tarfile.TarInfo(name)
            if kind == "link":
                info.type, info.linkname = tarfile.SYMTYPE, "../secret"
                tar.addfile(info)
            else:
                info.size = 2
                tar.addfile(info, io.BytesIO(b"ok"))
    return path


def test_overlay_places_regular_files_and_never_replaces_app_files(tmp_path):
    source = tmp_path / "src"
    (source / "site").mkdir(parents=True)
    assert extract_overlay(overlay_tar(tmp_path, [("test_a.py", "file"), ("conftest.py", "file")]),
                           source, "site/tests_agent") == ["conftest.py", "test_a.py"]
    assert (source / "site/tests_agent/test_a.py").read_text() == "ok"
    with pytest.raises(ValueError):
        extract_overlay(overlay_tar(tmp_path, [("x.py", "link")]), tmp_path / "s2", "tests_agent")
    with pytest.raises(FileExistsError):
        extract_overlay(overlay_tar(tmp_path, [("test_a.py", "file")]), source, "site/tests_agent")


def test_stage_overlay_is_deterministic_and_rejects_links(tmp_path):
    suite = tmp_path / "tests_agent"
    (suite / "__pycache__").mkdir(parents=True)
    (suite / "test_a.py").write_text("def test_a(): pass\n")
    (suite / "__pycache__" / "x.pyc").write_bytes(b"x")
    assert stage_overlay(suite, tmp_path / "1.tar") == ["test_a.py"]
    stage_overlay(suite, tmp_path / "2.tar")
    assert (tmp_path / "1.tar").read_bytes() == (tmp_path / "2.tar").read_bytes()
    (suite / "link.py").symlink_to(tmp_path / "1.tar")
    with pytest.raises(ValueError):
        stage_overlay(suite, tmp_path / "3.tar")


def test_repeated_baseline_records_flake_and_skips_mutation(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    counter = tmp_path / "count.txt"
    (source / "test_flip.py").write_text(
        "from pathlib import Path\n"
        f"C = Path({str(counter)!r})\n"
        "def test_stable():\n    assert True\n"
        "def test_flip():\n"
        "    n = int(C.read_text()) + 1 if C.exists() else 1\n"
        "    C.write_text(str(n))\n"
        "    assert n != 2\n")
    recipe = {"test_paths": ["test_flip.py"], "repeats": 3}
    status = execute(source, tmp_path / "out", recipe, Path(sys.executable), 120, clean_env())
    assert status["status"] == "skipped" and "mutation" not in status
    assert status["reason"].startswith("baseline not green in 1 of 3 runs")
    flake = json.loads((tmp_path / "out" / "flake.json").read_text())
    assert flake["runs"] == 3 and flake["green_runs"] == 2 and flake["n_tests"] == 2
    assert flake["flaky_tests"] == ["test_flip::test_flip"] and flake["completed_runs"] == 3
    assert (tmp_path / "out" / "baseline-3.xml").exists()


def manifest(tmp_path, approved="yes"):
    root = tmp_path / "protocol"
    (root / "recipes").mkdir(parents=True)
    (root / "recipes" / "app.json").write_text(json.dumps({"budget_seconds": 600, "repeats": 10}))
    sha = "a" * 40
    row = ["app", "owner/repo", sha, "web", "MIT", f"https://github.com/owner/repo/blob/{sha}/LICENSE",
           "recipes/app.json", approved, "Person", "2026-11-27T16:06:00Z"]
    (root / "apps.csv").write_text(",".join(FIELDS) + "\n" + ",".join(row) + "\n")
    suite = root / "suites" / "codex" / "app" / "tests_agent"
    suite.mkdir(parents=True)
    (suite / "conftest.py").write_text("")
    (suite / "test_ui.py").write_text("def test_ui(): pass\n")
    return root


def test_plan_builds_overlay_selection_and_token_binds_suite_bytes(tmp_path):
    root = manifest(tmp_path)
    row, recipe, suite = plan("codex", "app", root / "apps.csv", root / "suites")
    assert recipe["overlay_root"] == "web/tests_agent"
    assert recipe["test_paths"] == ["web/tests_agent/test_ui.py"] and recipe["repeats"] == 10
    before = confirmation("codex", "app", root / "apps.csv", root / "suites")
    (suite / "test_ui.py").write_text("def test_ui(): assert 1\n")
    assert confirmation("codex", "app", root / "apps.csv", root / "suites") != before
    with pytest.raises(ValueError):
        plan("claude-code", "app", root / "apps.csv", root / "suites")


def test_plan_rejects_unapproved_rows_and_preselected_tests(tmp_path):
    root = manifest(tmp_path, approved="no")
    with pytest.raises(ValueError, match="not approved"):
        plan("codex", "app", root / "apps.csv", root / "suites")
    root = manifest(tmp_path / "b")
    (root / "recipes" / "app.json").write_text(json.dumps({"test_paths": ["x/test_a.py"]}))
    with pytest.raises(ValueError, match="preselect"):
        plan("codex", "app", root / "apps.csv", root / "suites")


def test_committed_protocol_manifest_is_approved_and_prompt_is_fixed():
    from study.protocol_run import ROOT, app_reason, read_apps
    rows = read_apps(ROOT / "apps.csv")
    assert set(rows) == {"platelet", "contrail", "todomvc"}
    assert all(app_reason(row) is None for row in rows.values())
    prompt = (ROOT / "PROMPT.txt").read_text()
    assert "tests_agent/" in prompt and "python -m pytest tests_agent -q" in prompt


def test_export_includes_repeat_and_flake_evidence():
    from study.export import NAMES
    assert {"flake.json", "baseline-2.xml", "baseline-10.log"} <= set(NAMES)
