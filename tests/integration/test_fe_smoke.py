"""Smoke tests: app boots, search autocomplete and ship classes load."""

from __future__ import annotations

from playwright.sync_api import Page, expect


def test_app_renders_header(page: Page, base_url: str) -> None:
    page.goto(base_url)
    expect(page.get_by_role("heading", name="EVE CapNav")).to_be_visible()


def test_ship_picker_loads_cap_ships(page: Page, base_url: str) -> None:
    """The typeahead replaces the old dropdown — clearing the input and
    focusing it should fetch /api/cap-ships and render every seeded ship as
    a selectable option. (With the default Archon selection the input filters
    to just Archon, so we clear first to see the full unfiltered list.)"""
    page.goto(base_url)
    inp = page.get_by_test_id("ship-picker-input")
    # Wait for the auto-select to populate the input, then clear it to see all.
    expect(inp).not_to_have_value("", timeout=5_000)
    inp.click()
    inp.fill("")
    expect(
        page.locator('[data-testid="ship-picker-option"][data-ship-name="Archon"]')
    ).to_have_count(1)
    expect(
        page.locator('[data-testid="ship-picker-option"][data-ship-name="Rhea"]')
    ).to_have_count(1)


def test_system_search_autocomplete(page: Page, base_url: str) -> None:
    page.goto(base_url)
    origin = page.get_by_text("Origin", exact=True).locator("..").locator("input")
    origin.fill("Itg")
    # SystemSearch debounces 300ms.
    page.wait_for_timeout(500)
    expect(page.get_by_text("ItgOrigin")).to_be_visible()
    expect(page.get_by_text("ItgDanger")).to_be_visible()
    expect(page.get_by_text("ItgSafeA")).to_be_visible()
    expect(page.get_by_text("ItgSafeB")).to_be_visible()
    expect(page.get_by_text("ItgDest")).to_be_visible()


def test_plan_without_systems_shows_error(page: Page, base_url: str) -> None:
    page.goto(base_url)
    page.get_by_role("button", name="Plan Route").click()
    expect(
        page.get_by_text("Please select both origin and destination", exact=False)
    ).to_be_visible()
