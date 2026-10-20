import json

import pytest

from vandal import mcp_server
from vandal.reporting import make_report


def test_paths_and_arguments_are_validated(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError):
        mcp_server.run_vandal("../outside.py")
    with pytest.raises(ValueError):
        mcp_server.run_vandal(".", max_mutants=101)
    with pytest.raises(ValueError):
        mcp_server.run_vandal(".", strategies=["oops"])
    with pytest.raises(ValueError):
        mcp_server.run_vandal("--help")


def test_bounded_argument_vector_and_returned_report(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "test space.py"
    target.write_text("")
    report = make_report([])
    calls = []

    def execute(args, **kwargs):
        calls.append((args, kwargs))
        destination = next(a.split("=", 1)[1] for a in args if a.startswith("--vandal-report="))
        with open(destination, "w") as stream:
            json.dump(report, stream)
        return 0, "", False

    monkeypatch.setattr(mcp_server, "run_process", execute)
    returned = mcp_server.run_vandal(target.name, ["logic_sabotage"], 3)
    assert returned["schema_version"] == 1
    assert calls[0][0][3] == str(target)
    assert calls[0][1]["timeout"] == 600
    assert "--vandal-timeout=30" in calls[0][0]
    assert mcp_server.get_surviving_mutants() == []


def test_timeout_does_not_return_stale_report(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "vandal_report.json").write_text('{"stale":true}')
    monkeypatch.setattr(mcp_server, "run_process", lambda *a, **k: (1, "log", True))
    assert "error" in mcp_server.run_vandal(".")


@pytest.mark.asyncio
async def test_real_stdio_tools(tmp_path):
    import sys
    from datetime import timedelta
    pytest.importorskip("mcp")
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    # Shell metacharacters are literal filename characters, never commands.
    filename = "test_app & semi;.py"
    (tmp_path / filename).write_text('''
import pytest
@pytest.mark.vandal(targets=["#b"])
def test_weak(page):
    page.set_content('<button id="b">Go</button>')
    page.click("#b")
''')
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "vandal.mcp_server"], cwd=str(tmp_path)
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=60)) as session:
            await session.initialize()
            names = {t.name for t in (await session.list_tools()).tools}
            assert names == {"run_vandal", "get_surviving_mutants"}
            for invalid in [
                {"test_path": "../outside.py"},
                {"test_path": filename, "max_mutants": 101},
                {"test_path": filename, "max_mutants": 0},
                {"test_path": filename, "strategies": ["logic_sabotage; echo bad"]},
            ]:
                response = await session.call_tool("run_vandal", invalid)
                assert response.isError
                assert not (tmp_path / "vandal_report.json").exists()
            response = await session.call_tool("run_vandal", {
                "test_path": filename, "strategies": ["logic_sabotage"], "max_mutants": 1,
            })
            assert not response.isError
            report = json.loads((tmp_path / "vandal_report.json").read_text())
            assert report["summary"]["survived"] == 1
            response = await session.call_tool("get_surviving_mutants", {})
            assert not response.isError
            assert "test_weak" in response.content[0].text
            response = await session.call_tool("get_surviving_mutants", {"report_path": "../outside.json"})
            assert response.isError


def test_concurrent_run_does_not_queue_without_bound(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with mcp_server.single_run():
        with pytest.raises(ValueError, match="already active"):
            mcp_server.run_vandal(".")


def test_report_read_limits_and_schema_version(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "report.json"
    path.write_text('{"schema_version":999}')
    with pytest.raises(ValueError, match="schema_version"):
        mcp_server.get_surviving_mutants(path.name)
    with path.open("wb") as stream:
        stream.seek(10 * 1024 * 1024)
        stream.write(b"x")
    with pytest.raises(ValueError, match="10 MiB"):
        mcp_server.get_surviving_mutants(path.name)
