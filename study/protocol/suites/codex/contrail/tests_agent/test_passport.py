import re

from playwright.sync_api import expect


def select_year(page, label):
    periods = page.get_by_role("navigation", name="Reporting period")
    selected = periods.get_by_role("button", name=label, exact=True)
    selected.click()
    expect(periods.get_by_role("button", pressed=True)).to_have_text(label)


def test_period_filter_updates_summary_quality_and_extremes(passport):
    page = passport
    periods = page.get_by_role("navigation", name="Reporting period")
    expect(periods.get_by_role("button")).to_have_text(["All time", "2026", "2025", "2024"])
    expect(page.locator("#hero-value")).to_have_text("580 kg CO₂e")
    expect(page.locator("#flight-count")).to_have_text("8")
    expect(page.locator("#planned-total")).to_have_text("900 kg CO₂e")

    select_year(page, "2025")
    expect(page.locator("#hero-value")).to_have_text("480 kg CO₂e")
    expect(page.locator("#flight-count")).to_have_text("4")
    expect(page.locator("#planned-total")).to_have_text("0 kg CO₂e")
    expect(page.locator("#lightest-total")).to_contain_text("60 kg CO₂e · BA103")
    expect(page.locator("#heaviest-total")).to_contain_text("300 kg CO₂e · BA102")
    for field, count in {
        "exact-count": "2 · 50%",
        "typical-count": "1 · 25%",
        "missing-count": "1 · 25%",
        "duration-missing": "1 · 25%",
        "distance-missing": "1 · 25%",
        "cabin-assumed": "3 · 75%",
    }.items():
        expect(page.locator(f"#{field}")).to_have_text(count)

    select_year(page, "2026")
    expect(page.locator("#flight-count")).to_have_text("0")
    expect(page.locator("#hero-value")).to_have_text("0 kg CO₂e")
    expect(page.locator("#planned-total")).to_have_text("900 kg CO₂e")
    expect(page.locator("#heaviest-total")).to_contain_text("Needs the required source data.")
    select_year(page, "All time")
    expect(page.locator("#hero-value")).to_have_text("580 kg CO₂e")


def test_intensity_uses_only_flights_with_both_inputs(passport):
    page = passport
    select_year(page, "2025")
    page.get_by_role("button", name="Per hour", exact=True).click()
    # (120 + 300) / (2 + 3). The summary also includes the unpriced four-hour flight.
    expect(page.locator("#hero-value")).to_have_text("84 kg CO₂e / block hour")
    expect(page.locator("#duration-total")).to_have_text("9 h")
    expect(page.locator("#lightest-duration")).to_contain_text("60 kg CO₂e / block hour · BA101")
    expect(page.locator("#heaviest-duration")).to_contain_text("100 kg CO₂e / block hour · BA102")

    per_km = page.get_by_role("button", name="Per km", exact=True)
    per_km.click()
    # Two priced JFK–LHR legs, about 5,540 km each.
    expect(page.locator("#hero-value")).to_have_text("37.9 g CO₂e / passenger-km")
    select_year(page, "2026")
    expect(per_km).to_have_attribute("aria-pressed", "true")
    expect(page.locator("#hero-value")).to_have_text("Not available")
    page.get_by_role("button", name="Per hour", exact=True).click()
    expect(page.locator("#hero-value")).to_have_text("Needs arrival times")


def test_charts_regroup_without_losing_scope_or_upcoming_impact(passport):
    page = passport
    select_year(page, "2025")
    pattern = page.locator("#pattern-chart")
    trend = page.locator("#trend-chart")
    expect(pattern).to_have_accessible_name(re.compile(r"Jan: 120 kg CO₂e, Feb: 360 kg CO₂e"))
    expect(trend).to_have_accessible_name(
        "2024: 100 kg completed, 2025: 480 kg completed, 2026: 0 kg completed, 900 kg upcoming"
    )

    page.get_by_role("button", name="Weekday", exact=True).click()
    page.get_by_role("group", name="Break down carbon patterns").get_by_role(
        "button", name="Cabin"
    ).click()
    expect(pattern).to_have_accessible_name(
        re.compile(r"Mon: 120 kg CO₂e; [^:]*Economy 120 kg[^:]*Tue: 360 kg CO₂e; [^:]*Business 300 kg")
    )
    page.get_by_role("group", name="Break down annual impact").get_by_role(
        "button", name="Reason"
    ).click()
    expect(trend).to_have_accessible_name(re.compile(r"2025: 480 kg completed; [^:]*Leisure 120 kg"))
    expect(pattern).to_have_accessible_name(re.compile(r"Mon: 120 kg CO₂e"))

    select_year(page, "2024")
    expect(pattern).to_have_accessible_name(re.compile(r"Mon: 40 kg CO₂e; Economy 40 kg"))
    expect(page.locator("#trend-note-value")).to_have_text("100 kg CO₂e")
    expect(trend).to_have_accessible_name(re.compile(r"900 kg upcoming"))


def test_map_updates_and_shows_aggregated_airport_impact(passport):
    page = passport
    select_year(page, "2025")
    markers = page.locator("#route-map .leaflet-airports-pane path")
    expect(markers).to_have_count(2)
    expect(page.locator("#route-map .leaflet-routes-pane path")).to_have_count(1)
    markers.first.hover()
    expect(page.get_by_role("tooltip")).to_have_text(re.compile(r"(JFK|LHR).*420 kg CO₂e connected"))

    select_year(page, "2026")
    expect(markers).to_have_count(0)
    expect(page.get_by_text("No priced routes in this period")).to_be_visible()


def test_ranking_dialog_expands_reorders_and_closes(passport):
    page = passport
    see_all = page.locator(".ranking").filter(
        has=page.get_by_role("heading", name="Highest impact flights")
    ).get_by_role("button", name="See all")
    preview = page.locator("#flights")
    expect(preview).to_have_accessible_name(re.compile(r"^BA102.*BA302"))
    expect(preview).not_to_have_accessible_name(re.compile("BA301"))

    see_all.click()
    dialog = page.get_by_role("dialog", name="All flights by impact · total CO₂e")
    expect(dialog).to_be_visible()
    expect(dialog.get_by_role("img")).to_have_accessible_name(re.compile(r"^BA102.*BA301"))
    expect(dialog.get_by_role("img")).not_to_have_accessible_name(re.compile("BA201|BA104|BA999"))
    page.keyboard.press("Escape")
    expect(dialog).to_be_hidden()

    page.get_by_role("button", name="Avg / hr", exact=True).click()
    page.get_by_role("group", name="Break down contributor rankings").get_by_role(
        "button", name="Cabin"
    ).click()
    expect(preview).to_have_accessible_name(re.compile(r"^BA102.*Business.*BA101.*Economy"))
    expect(preview).not_to_have_accessible_name(re.compile("BA103"))
    # Six flights have both time and emissions, so the preview now fits them all.
    expect(see_all).to_be_hidden()

    page.get_by_role("button", name="Total CO₂e", exact=True).click()
    see_all.click()
    dialog = page.get_by_role("dialog", name="All flights by impact · total CO₂e by cabin")
    expect(dialog.get_by_role("img")).to_have_accessible_name(re.compile(r"^BA102.*BA301"))
    dialog.get_by_role("button", name="Close").click()
    expect(dialog).to_be_hidden()


def test_empty_passport_has_working_controls_and_empty_states(open_passport):
    page = open_passport([])
    expect(page.get_by_role("navigation").get_by_role("button")).to_have_text(["All time"])
    expect(page.locator("#hero-value")).to_have_text("0 kg CO₂e")
    expect(page.locator("#trend-note-value")).to_have_text("No flights")
    expect(page.get_by_text("No priced routes in this period")).to_be_visible()
    expect(page.locator("#missing-count")).to_have_text("0 · 0%")
    expect(page.locator("#flights")).to_have_accessible_name(
        "No flights with the data required for total impact in this period"
    )
    page.get_by_role("button", name="Per km", exact=True).click()
    expect(page.locator("#hero-value")).to_have_text("Not available")
