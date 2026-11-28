import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest

SITE = Path(__file__).resolve().parents[1] / "site"


class SiteHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


@pytest.fixture(scope="session")
def app_url():
    handler = partial(SiteHandler, directory=SITE)
    with ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}"
        finally:
            server.shutdown()
            thread.join()


@pytest.fixture(scope="session")
def catalogs():
    return {
        region: json.loads((SITE / f"data-{region}.json").read_text(encoding="utf-8"))
        for region in ("us", "gb", "in")
    }


@pytest.fixture(autouse=True)
def block_external_requests(context, app_url):
    def local_only(route):
        if route.request.url.startswith(f"{app_url}/"):
            route.continue_()
        else:
            route.abort()

    context.route("**/*", local_only)
