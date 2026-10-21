"""Owned synthetic fixture, created for harness validation; never a study subject."""
from playwright.sync_api import expect


def test_counter(page):
    page.set_default_timeout(600)
    page.set_content('''<button id="increment" onclick="document.querySelector('#count').textContent='1'">Add</button>
                        <output id="count">0</output>''')
    page.locator("#increment").click()
    expect(page.locator("#count")).to_have_text("1", timeout=500)


def test_label_without_assertion(page):
    page.set_default_timeout(600)
    page.set_content('<p id="label">Ready</p>')
    page.locator("#label").inner_text()
