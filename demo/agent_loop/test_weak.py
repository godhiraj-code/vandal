import pytest


@pytest.mark.vandal(targets=["#name", "#checkout", "#status"])
def test_checkout(page, app_url):
    # Intentionally weak example: visibility and title do not verify the order.
    page.goto(app_url)
    page.locator("#name").fill("Ada")
    page.locator("#checkout").click()
    assert page.locator("#status").is_visible()
    assert page.title() == "Corner Shop checkout"
