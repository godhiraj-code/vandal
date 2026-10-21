"""Self-contained local server and headless browser; no pytest-playwright needed."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import sync_playwright


@pytest.fixture(scope="session")
def app_url():
    document = Path(__file__).with_name("app.html").read_bytes()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != "/":
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(document)))
            self.end_headers()
            self.wfile.write(document)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.fixture
def page(app_url):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(service_workers="block")
        # Browser requests may only reach this fixture's loopback server.
        origin = urlsplit(app_url).netloc
        context.route("**/*", lambda route: route.continue_()
                      if urlsplit(route.request.url).netloc == origin else route.abort())
        page = context.new_page()
        page.set_default_timeout(1000)
        try:
            yield page
        finally:
            context.close()
            browser.close()
