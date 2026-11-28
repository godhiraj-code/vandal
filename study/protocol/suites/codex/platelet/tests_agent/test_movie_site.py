import re
from collections import Counter

import pytest
from playwright.sync_api import expect


def button(page, name):
    return page.get_by_role("button", name=name, exact=True)


def runtime_input(page, name):
    return page.get_by_role("spinbutton", name=name, exact=True)


def movie_rows(page):
    return page.locator("#movies-tbody tr").filter(has=page.locator(".movie-title"))


def movie_titles(page):
    return movie_rows(page).locator(".movie-title")


def runtime_cells(page):
    return movie_rows(page).locator("td:nth-child(3)")


def by_runtime(movies):
    return sorted(movies, key=lambda movie: movie["runtime_minutes"])


def hours_and_minutes(minutes):
    hours, remainder = divmod(minutes, 60)
    return " ".join(part for part in (
        f"{hours} h" if hours else "",
        f"{remainder} m" if remainder or not hours else "",
    ) if part)


def expect_movies(page, movies, total, *, minutes_only=False):
    expect(page.locator("#filter-results")).to_have_text(f"Showing {len(movies)} of {total} movies")
    if movies:
        expect(movie_titles(page)).to_have_text([movie["title"] for movie in movies])
        format_runtime = (lambda value: f"{value} m") if minutes_only else hours_and_minutes
        expect(runtime_cells(page)).to_have_text([
            format_runtime(movie["runtime_minutes"]) for movie in movies
        ])
    else:
        expect(movie_rows(page)).to_have_count(0)
        expect(page.get_by_text("No movies found matching the filter criteria.")).to_be_visible()


@pytest.fixture
def movie_page(page, app_url, catalogs):
    page.goto(app_url)
    movies = by_runtime(catalogs["us"]["movies"])
    expect_movies(page, movies, len(movies))
    return page, movies


@pytest.mark.parametrize("target", ["gb", "in"])
def test_region_changes_catalog_and_commentary_and_survives_reload(movie_page, catalogs, target):
    page, us_movies = movie_page
    region = page.get_by_role("combobox", name="Select Netflix Region")
    expect(region).to_have_value("us")
    expect(button(page, "Show Favorites Only")).to_be_visible()
    expect(page.locator("#commentary p")).to_have_text(
        catalogs["us"]["commentary"].strip().split("\n\n")
    )

    region.select_option(target)
    regional_movies = by_runtime(catalogs[target]["movies"])
    expect_movies(page, regional_movies, len(regional_movies))
    expect(page.locator("#commentary p")).to_have_text(
        catalogs[target]["commentary"].strip().split("\n\n")
    )
    expect(page.locator("#generated-at")).to_have_text(re.compile(r"^Last updated: .+"))
    expect(button(page, "Show Favourites Only")).to_be_visible()

    page.reload()
    expect(region).to_have_value(target)
    expect_movies(page, regional_movies, len(regional_movies))
    region.select_option("us")
    expect_movies(page, us_movies, len(us_movies))


def test_sort_changes_order_and_accessible_indicator(movie_page):
    page, movies = movie_page
    runtime = page.get_by_role("columnheader", name="Runtime")
    title = page.get_by_role("columnheader", name="Title")
    expect(runtime).to_have_attribute("aria-sort", "ascending")
    runtime.click()
    expect(runtime).to_have_attribute("aria-sort", "descending")
    expect_movies(page, sorted(movies, key=lambda movie: -movie["runtime_minutes"]), len(movies))

    title.press("Enter")
    expect(title).to_have_attribute("aria-sort", "ascending")
    expect(runtime).to_have_attribute("aria-sort", "none")
    alphabetical = sorted(movies, key=lambda movie: movie["title"].lower())
    expect(movie_titles(page)).to_have_text([movie["title"] for movie in alphabetical])
    title.press("Space")
    expect(title).to_have_attribute("aria-sort", "descending")
    expect(movie_titles(page)).to_have_text([movie["title"] for movie in reversed(alphabetical)])


def test_runtime_bounds_validation_empty_results_and_reset(movie_page):
    page, movies = movie_page
    runtimes = sorted({movie["runtime_minutes"] for movie in movies})
    lower, upper = runtimes[len(runtimes) // 3], runtimes[2 * len(runtimes) // 3]
    minimum = runtime_input(page, "Minimum Runtime (minutes):")
    maximum = runtime_input(page, "Maximum Runtime (minutes):")
    apply = button(page, "Apply Filters")
    button(page, "Show Runtime in Minutes").click()
    minimum.fill(str(lower))
    maximum.fill(str(upper))
    apply.click()
    filtered = [movie for movie in movies if lower <= movie["runtime_minutes"] <= upper]
    expect_movies(page, filtered, len(movies), minutes_only=True)

    minimum.fill(str(upper + 1))
    apply.click()
    expect(page.get_by_role("alert")).to_have_text(
        "Minimum runtime cannot be greater than maximum runtime."
    )
    expect_movies(page, filtered, len(movies), minutes_only=True)

    minimum.fill(str(runtimes[-1] + 1))
    maximum.fill("")
    apply.click()
    expect(page.get_by_role("alert")).to_be_hidden()
    expect_movies(page, [], len(movies))

    button(page, "Reset").click()
    expect(minimum).to_have_value("90")
    expect(maximum).to_have_value("160")
    expect_movies(page, movies, len(movies), minutes_only=True)
    page.reload()
    expect_movies(page, movies, len(movies), minutes_only=True)
    expect(minimum).to_have_value("90")
    expect(maximum).to_have_value("160")


def test_runtime_format_preserves_applied_range_and_blank_maximum(movie_page):
    page, movies = movie_page
    min_hours = runtime_input(page, "Minimum runtime hours")
    min_minutes = runtime_input(page, "Minimum runtime minutes")
    max_hours = runtime_input(page, "Maximum runtime hours")
    max_minutes = runtime_input(page, "Maximum runtime minutes")
    min_hours.fill("2")
    min_minutes.fill("05")
    max_hours.fill("")
    max_minutes.fill("")
    button(page, "Apply Filters").click()
    filtered = [movie for movie in movies if movie["runtime_minutes"] >= 125]
    expect_movies(page, filtered, len(movies))

    button(page, "Show Runtime in Minutes").click()
    minimum = runtime_input(page, "Minimum Runtime (minutes):")
    maximum = runtime_input(page, "Maximum Runtime (minutes):")
    expect(min_hours).to_have_count(0)
    expect(minimum).to_have_value("125")
    expect(maximum).to_have_value("")
    expect_movies(page, filtered, len(movies), minutes_only=True)

    page.reload()
    expect_movies(page, filtered, len(movies), minutes_only=True)
    expect(minimum).to_have_value("125")
    expect(maximum).to_have_value("")

    button(page, "Show Runtime in Hrs & Mins").click()
    expect(min_hours).to_have_value("2")
    expect(min_minutes).to_have_value("5")
    expect(max_hours).to_have_value("")
    expect(max_minutes).to_have_value("")
    expect_movies(page, filtered, len(movies))


def test_favorites_persist_and_removal_updates_filtered_list(movie_page):
    page, movies = movie_page
    id_counts = Counter(movie["tmdb_id"] for movie in movies)
    first_index, second_index = [
        index for index, movie in enumerate(movies) if id_counts[movie["tmdb_id"]] == 1
    ][:2]
    first = movie_rows(page).nth(first_index)
    second = movie_rows(page).nth(second_index)
    first.get_by_role("button", name="Add to favorites", exact=True).press("Space")
    second.get_by_role("button", name="Add to favorites", exact=True).click()
    expect(first.get_by_role("button", name="Remove from favorites", exact=True)).to_be_visible()
    page.reload()
    expect(page.get_by_role("button", name="Remove from favorites", exact=True)).to_have_count(2)

    button(page, "Show Favorites Only").click()
    expect_movies(page, [movies[first_index], movies[second_index]], len(movies))
    movie_rows(page).first.get_by_role("button", name="Remove from favorites", exact=True).click()
    expect_movies(page, [movies[second_index]], len(movies))
    button(page, "Clear All Favorites").click()
    expect(button(page, "Show Favorites Only")).to_be_visible()
    expect_movies(page, movies, len(movies))
    page.reload()
    expect(page.get_by_role("button", name="Add to favorites", exact=True)).to_have_count(len(movies))
    button(page, "Show Favorites Only").click()
    expect_movies(page, [], len(movies))


def test_description_expands_with_keyboard_and_collapses_with_click(movie_page):
    page, _ = movie_page
    row = movie_rows(page).and_(page.locator('[aria-expanded="false"]')).first
    expect(row).to_be_visible()
    # Keep the same row locator after aria-expanded changes.
    title = row.locator(".movie-title").inner_text()
    row = movie_rows(page).filter(has=page.get_by_text(title, exact=True)).first
    description = row.locator(".movie-description")
    expect(description).to_be_visible()
    collapsed_height = description.evaluate("(element) => element.clientHeight")

    row.press("Enter")
    expect(row).to_have_attribute("aria-expanded", "true")
    assert description.evaluate("(element) => element.clientHeight") > collapsed_height

    row.locator(".movie-title").click()
    expect(row).to_have_attribute("aria-expanded", "false")
    assert description.evaluate("(element) => element.clientHeight") == collapsed_height


def test_theme_updates_appearance_and_persists(movie_page):
    page, _ = movie_page
    theme = button(page, "Toggle theme")
    initial_background = page.locator("body").evaluate(
        "(element) => getComputedStyle(element).backgroundColor"
    )
    expect(theme).to_have_text("🌙")
    theme.click()
    expect(theme).to_have_text("☀️")
    expect(page.locator("body")).not_to_have_css("background-color", initial_background)
    page.reload()
    expect(theme).to_have_text("☀️")
    expect(page.locator("body")).not_to_have_css("background-color", initial_background)
    theme.click()
    expect(theme).to_have_text("🌙")
    expect(page.locator("body")).to_have_css("background-color", initial_background)


def test_catalog_failure_shows_message_and_refresh_recovers(page, app_url, catalogs):
    page.route("**/data-us.json?*", lambda route: route.fulfill(status=503), times=1)
    page.goto(app_url)
    message = "Failed to load movie data. Please try refreshing the page."
    expect(page.locator("#commentary")).to_have_text(message)
    expect(page.get_by_role("cell", name=message)).to_be_visible()
    expect(movie_rows(page)).to_have_count(0)

    page.reload()
    movies = by_runtime(catalogs["us"]["movies"])
    expect_movies(page, movies, len(movies))
    expect(page.locator("#commentary")).not_to_have_text(message)
