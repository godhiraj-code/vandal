from pathlib import Path

import pytest
from playwright.sync_api import expect

APP = Path(__file__).with_name("app.html").as_uri()


@pytest.mark.vandal(targets=["#login"])
def test_weak(page):
    page.set_default_timeout(1000)
    page.goto(APP)
    page.locator("#login").click()


@pytest.mark.vandal(targets=["#login"])
def test_strong(page):
    page.set_default_timeout(1000)
    page.goto(APP)
    page.locator("#login").click()
    expect(page.locator("#status")).to_have_text("Welcome back", timeout=500)
