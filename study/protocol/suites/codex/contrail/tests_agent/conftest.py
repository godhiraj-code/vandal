from datetime import UTC, datetime
from pathlib import Path

import pytest
from playwright.sync_api import expect

NOW = datetime(2026, 8, 14, 12, tzinfo=UTC)


def flight(day, number, kg, hours=None, **fields):
    return {
        "flight_date": day,
        "carrier_code": "BA",
        "flight_number": str(number),
        "origin": "JFK",
        "destination": "LHR",
        "departure_time": f"{day}T08:00:00+00:00",
        "arrival_time": f"{day}T{8 + hours:02d}:00:00+00:00" if hours else "",
        "emissions_source": "exact" if kg is not None else "no_data",
        "emissions_kg_actual": str(kg) if kg is not None else "",
        **fields,
    }


@pytest.fixture
def flights():
    return [
        flight("2025-01-06", 101, 120, 2, flight_reason="leisure"),
        flight(
            "2025-02-04", 102, 300, 3,
            origin="LHR", destination="JFK", cabin_class_known="business",
            flight_reason="business", emissions_source="typical_route_average",
        ),
        flight("2025-02-11", 103, 60, origin="ZZZ"),
        flight("2025-02-18", 104, None, 4),
        flight("2025-04-03", 999, 5000, 2, status="cancelled"),
        flight("2026-12-03", 201, 900, 2),
        *[
            flight(f"2024-03-{index:02d}", 300 + index, index * 10, 2,
                   origin="SFO", destination="LAX")
            for index in range(1, 5)
        ],
    ]


@pytest.fixture
def open_passport(page, tmp_path, monkeypatch):
    # Exercise the checkout, even when the environment has a wheel installed.
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "src"))
    from contrail.passport import render

    errors = []
    external_requests = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    def block_external(route):
        external_requests.append(route.request.url)
        route.abort()

    page.context.route("http*://**/*", block_external)

    def open_rows(rows):
        document = render(rows, tmp_path / "passport.html", now=NOW)
        page.goto(document.as_uri())
        expect(page.get_by_role("heading", name="Carbon Passport")).to_be_visible()
        expect(page.locator("#hero-value")).not_to_be_empty()
        return page

    yield open_rows
    assert not errors, errors
    assert not external_requests, external_requests


@pytest.fixture
def browser_context_args(browser_context_args):
    return {**browser_context_args, "locale": "en-US", "timezone_id": "America/Los_Angeles"}


@pytest.fixture
def passport(open_passport, flights):
    return open_passport(flights)
