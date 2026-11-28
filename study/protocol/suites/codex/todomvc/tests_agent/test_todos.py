import re

import pytest
from playwright.sync_api import Page, expect


def new_todo(page: Page):
    return page.get_by_placeholder("What needs to be done?")


def add_todo(page: Page, title: str):
    field = new_todo(page)
    field.fill(title)
    field.press("Enter")
    expect(field).to_have_value("")


def rows(page: Page):
    return page.locator(".todo-list > li")


def todo(page: Page, title: str):
    return rows(page).filter(has=page.get_by_text(title, exact=True))


def expect_titles(page: Page, *titles: str):
    if titles:
        expect(rows(page).locator("label")).to_have_text(list(titles))
    else:
        expect(rows(page)).to_have_count(0)


def expect_remaining(page: Page, count: int):
    noun = "item" if count == 1 else "items"
    expect(page.locator(".todo-count")).to_have_text(f"{count} {noun} left")


def expect_filter(page: Page, name: str):
    expect(page.locator(".filters a.selected")).to_have_text(name)


def show_filter(page: Page, name: str):
    page.get_by_role("link", name=name, exact=True).click()
    expect_filter(page, name)


def revisit_all(page: Page):
    show_filter(page, "Completed")
    show_filter(page, "All")


def test_add_todos_from_empty_list(todo_page: Page):
    page = todo_page
    expect_titles(page)
    expect(page.locator(".footer")).to_be_hidden()
    expect(new_todo(page)).to_be_focused()

    new_todo(page).fill("   ")
    new_todo(page).press("Enter")
    expect_titles(page)
    expect(page.locator(".footer")).to_be_hidden()

    add_todo(page, "  Buy milk  ")
    expect_titles(page, "Buy milk")
    expect_remaining(page, 1)
    expect(page.locator(".clear-completed")).to_be_hidden()

    title = 'Read <em>notes</em> & "ideas"'
    add_todo(page, title)
    expect_titles(page, "Buy milk", title)
    expect(rows(page).locator("label em")).to_have_count(0)
    expect_remaining(page, 2)

    revisit_all(page)
    expect_titles(page, "Buy milk", title)


def test_filter_routes_and_toggle_items(todo_page: Page):
    page = todo_page
    add_todo(page, "Book train")
    add_todo(page, "Pack bag")
    packed = todo(page, "Pack bag")

    packed.get_by_role("checkbox").click()
    expect(packed.get_by_role("checkbox")).to_be_checked()
    expect(packed).to_have_class("completed")
    expect_remaining(page, 1)

    page.get_by_role("link", name="Active", exact=True).click()
    expect(page).to_have_url(re.compile(r"#/active$"))
    expect_filter(page, "Active")
    expect_titles(page, "Book train")
    expect_remaining(page, 1)

    page.get_by_role("link", name="Completed", exact=True).click()
    expect(page).to_have_url(re.compile(r"#/completed$"))
    expect_filter(page, "Completed")
    expect_titles(page, "Pack bag")

    page.go_back()
    expect_filter(page, "Active")
    expect_titles(page, "Book train")
    page.go_forward()
    expect_filter(page, "Completed")
    expect_titles(page, "Pack bag")

    expect(packed.get_by_role("checkbox")).to_be_checked()
    packed.get_by_role("checkbox").click()
    expect_titles(page)
    expect_remaining(page, 2)

    page.get_by_role("link", name="All", exact=True).click()
    expect_filter(page, "All")
    expect_titles(page, "Book train", "Pack bag")
    expect(packed.get_by_role("checkbox")).not_to_be_checked()


@pytest.mark.parametrize("save_with", ["enter", "blur"])
def test_edit_saves_trimmed_title(todo_page: Page, save_with: str):
    page = todo_page
    add_todo(page, "Draft report")
    add_todo(page, "Send invoice")
    todo(page, "Draft report").get_by_text("Draft report", exact=True).dblclick()
    editor = rows(page).locator(".edit")
    expect(editor).to_be_focused()
    expect(editor).to_have_value("Draft report")
    editor.fill("  Review report  ")
    if save_with == "enter":
        editor.press("Enter")
    else:
        new_todo(page).click()

    expect(editor).to_have_count(0)
    expect_titles(page, "Review report", "Send invoice")
    expect_remaining(page, 2)
    revisit_all(page)
    expect_titles(page, "Review report", "Send invoice")


def test_escape_cancels_edit_and_blank_edit_removes_item(todo_page: Page):
    page = todo_page
    add_todo(page, "Call dentist")
    add_todo(page, "Water plants")
    label = todo(page, "Call dentist").get_by_text("Call dentist", exact=True)
    label.dblclick()
    editor = rows(page).locator(".edit")
    editor.fill("Cancel appointment")
    editor.press("Escape")

    expect(editor).to_have_count(0)
    expect_titles(page, "Call dentist", "Water plants")
    revisit_all(page)
    expect_titles(page, "Call dentist", "Water plants")

    label.dblclick()
    editor.fill("   ")
    editor.press("Enter")
    expect_titles(page, "Water plants")
    expect_remaining(page, 1)
    revisit_all(page)
    expect_titles(page, "Water plants")


def test_delete_one_of_two_identical_todos(todo_page: Page):
    page = todo_page
    add_todo(page, "Refill prescription")
    add_todo(page, "Refill prescription")
    expect_titles(page, "Refill prescription", "Refill prescription")
    rows(page).last.get_by_role("checkbox").click()

    rows(page).first.hover()
    rows(page).first.get_by_role("button").click()
    expect_titles(page, "Refill prescription")
    expect(rows(page).get_by_role("checkbox")).to_be_checked()
    expect_remaining(page, 0)
    revisit_all(page)
    expect_titles(page, "Refill prescription")
    expect(rows(page).get_by_role("checkbox")).to_be_checked()

    rows(page).hover()
    rows(page).get_by_role("button").click()
    expect_titles(page)
    expect(page.locator(".footer")).to_be_hidden()


def test_toggle_all_completes_and_reopens_todos(todo_page: Page):
    page = todo_page
    add_todo(page, "Wash dishes")
    add_todo(page, "Sweep floor")
    todo(page, "Wash dishes").get_by_role("checkbox").click()
    toggle_all = page.get_by_text("Mark all as complete", exact=True)

    toggle_all.click()
    expect_titles(page, "Wash dishes", "Sweep floor")
    for checkbox in rows(page).get_by_role("checkbox").all():
        expect(checkbox).to_be_checked()
    expect_remaining(page, 0)
    expect(page.get_by_role("button", name="Clear completed")).to_be_visible()

    toggle_all.click()
    expect_titles(page, "Wash dishes", "Sweep floor")
    for checkbox in rows(page).get_by_role("checkbox").all():
        expect(checkbox).not_to_be_checked()
    expect_remaining(page, 2)
    expect(page.locator(".clear-completed")).to_be_hidden()


def test_clear_completed_preserves_active_todo(todo_page: Page):
    page = todo_page
    add_todo(page, "Pay bill")
    add_todo(page, "Walk dog")
    add_todo(page, "Send parcel")
    for title in ("Pay bill", "Send parcel"):
        todo(page, title).get_by_role("checkbox").click()

    page.get_by_role("link", name="Completed", exact=True).click()
    expect_titles(page, "Pay bill", "Send parcel")
    page.get_by_role("button", name="Clear completed").click()
    expect_titles(page)
    expect_filter(page, "Completed")
    expect_remaining(page, 1)
    expect(page.locator(".clear-completed")).to_be_hidden()

    page.get_by_role("link", name="All", exact=True).click()
    expect_titles(page, "Walk dog")
    expect(todo(page, "Walk dog").get_by_role("checkbox")).not_to_be_checked()
