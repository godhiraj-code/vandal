import asyncio
import json
from html.parser import HTMLParser
from unittest.mock import AsyncMock

from vandal import MutationResult, Vandal


class Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def test_selectors_remain_data_in_persistent_script():
    page = AsyncMock()
    page.evaluate.return_value = 1
    selector = "button[data-name=\"O'Reilly\"]\n'; globalThis.injected = true; //"
    asyncio.run(Vandal(page).apply_mutation("stealth_disable", selector))
    script = page.add_init_script.call_args.args[0]
    serialized = script.split("const selector = ", 1)[1].split(";\n", 1)[0]
    assert json.loads(serialized) == selector
    assert page.evaluate.call_args.args[1] == selector


def test_report_escapes_all_external_fields_and_preserves_directory(tmp_path):
    directory = tmp_path / "results.json"
    directory.mkdir()
    vandal = Vandal(None)
    payload = '<img src=x onerror="alert(1)"> & café'
    vandal.mutants = [MutationResult(payload, payload, payload, details=payload)]
    vandal.save_report(str(directory / "report.json"))
    html = (directory / "report.html").read_text(encoding="utf-8")
    parser = Tags()
    parser.feed(html)
    assert not any(tag in {"img", "script"} for tag, _ in parser.tags)
    assert "&lt;img" in html
    assert "café" in html
    assert json.loads((directory / "report.json").read_text(encoding="utf-8"))[0]["details"] == payload
