from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest
from playwright.sync_api import Page


@pytest.fixture(scope="session")
def app_url():
    app_dir = Path(__file__).resolve().parents[1]
    handler = partial(SimpleHTTPRequestHandler, directory=str(app_dir))
    with ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}/index.html"
        finally:
            server.shutdown()
            thread.join()


@pytest.fixture
def todo_page(page: Page, app_url: str) -> Page:
    page.goto(app_url, wait_until="load")
    return page
