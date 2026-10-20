"""Optional local stdio MCP server. Run only in a trusted test checkout."""
import json
import asyncio
from contextlib import contextmanager
from pathlib import Path
import sys
import tempfile
import threading

from .core import VandalEngine
from .reporting import survivors, write_report
from .runner import run_process

RUN_LOCK = threading.Lock()
MAX_RUN_SECONDS = 600


@contextmanager
def single_run():
    if not RUN_LOCK.acquire(blocking=False):
        raise ValueError("A Vandal run is already active; wait for its result before retrying")
    try:
        yield
    finally:
        RUN_LOCK.release()


def local_path(value, root):
    path = (root / value).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError("Path must be inside the server working directory") from exc
    if not path.exists():
        raise ValueError("Path does not exist")
    return path


def run_vandal(test_path: str, strategies: list[str] = None, max_mutants: int = 20) -> dict:
    """Run trusted local pytest tests and return their strength report.

    Review survivors as possible assertion gaps, strengthen meaningful assertions,
    then rerun. Execution is limited to 10 minutes and 30 seconds per mutant.
    """
    if isinstance(max_mutants, bool) or not isinstance(max_mutants, int) or not 1 <= max_mutants <= 100:
        raise ValueError("max_mutants must be an integer from 1 to 100 per test")
    strategies = list(VandalEngine.MUTATIONS) if strategies is None else strategies
    if not strategies or any(s not in VandalEngine.MUTATIONS for s in strategies):
        raise ValueError("strategies must contain known Vandal strategies")
    root = Path.cwd().resolve()
    filename, *node = test_path.split("::")
    target = str(local_path(filename, root))
    if node:
        target += "::" + "::".join(node)
    with single_run(), tempfile.TemporaryDirectory(prefix="vandal-mcp-") as temporary:
        output = Path(temporary) / "report.json"
        args = [
            sys.executable, "-m", "pytest", target, "--vandal",
            "--vandal-strategies=" + ",".join(strategies),
            "--vandal-max-mutants=" + str(max_mutants), "--vandal-timeout=30",
            "--vandal-report=" + str(output),
        ]
        code, log, timed_out = run_process(args, cwd=str(root), timeout=MAX_RUN_SECONDS)
        if timed_out:
            return {"error": "Vandal run exceeded 600 seconds; no completed report", "log": log}
        if not output.exists():
            return {"error": "pytest produced no report", "exit_code": code, "log": log}
        report = json.loads(output.read_text(encoding="utf-8"))
        report["execution"] = {"exit_code": code}
        write_report(report, root / "vandal_report.json")
        return report


def get_surviving_mutants(report_path: str = "vandal_report.json") -> list[dict]:
    """Return surviving mutants and review hints, not proven missing assertions."""
    path = local_path(report_path, Path.cwd().resolve())
    if path.stat().st_size > 10 * 1024 * 1024:
        raise ValueError("Report exceeds the 10 MiB read limit")
    return survivors(json.loads(path.read_text(encoding="utf-8")))


def main():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise SystemExit("Install project-vandal[mcp] using Python 3.10 or newer") from exc
    server = FastMCP("vandal")

    @server.tool(name="run_vandal", description=run_vandal.__doc__)
    async def run_tool(test_path: str, strategies: list[str] = None, max_mutants: int = 20) -> dict:
        # The SDK invokes synchronous functions on its event loop. Keep stdio
        # responsive while pytest runs and enforce the deadline in the worker.
        return await asyncio.to_thread(run_vandal, test_path, strategies, max_mutants)

    server.tool()(get_surviving_mutants)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
