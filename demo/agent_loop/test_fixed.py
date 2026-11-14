import pytest
from playwright.sync_api import expect


@pytest.mark.vandal(targets=["#name", "#checkout", "#status"])
def test_checkout(page, app_url):
    # Scripted example of the assertions an agent could add after reading survivors.
    page.goto(app_url)
    page.locator("#name").fill("Ada")
    expect(page.locator("#name")).to_have_value("Ada", timeout=1000)
    page.locator("#checkout").click()
    expect(page.locator("#status")).to_have_text(
        "Thanks, Ada! Your coffee total is $4.00.", timeout=1000,
    )
    assert page.title() == "Corner Shop checkout"
