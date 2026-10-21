import pytest


@pytest.mark.vandal(targets=["#name", "#checkout", "#status"])
def test_checkout(page, app_url):
    # Intentionally weak example: interactions and reads without outcome assertions.
    page.goto(app_url)
    page.locator("#name").fill("Ada")
    page.locator("#name").input_value()
    page.locator("#checkout").click()
    page.locator("#status").inner_text()
    assert page.title() == "Corner Shop checkout"
