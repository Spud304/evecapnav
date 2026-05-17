"""Smoke tests: app boots, search autocomplete and ship classes load."""

from __future__ import annotations

from playwright.sync_api import Page, expect


def test_app_renders_header(page: Page, base_url: str) -> None:
    page.goto(base_url)
    expect(page.get_by_role("heading", name="EVE CapNav")).to_be_visible()


def test_ship_class_dropdown_populates(page: Page, base_url: str) -> None:
    page.goto(base_url)
    # Wait for any option to render (means /api/ship-classes finished).
    page.locator("option", has_text="Carrier (3.5 LY)").wait_for(state="attached")
    expect(page.locator("option", has_text="Carrier (3.5 LY)")).to_have_count(1)
    expect(page.locator("option", has_text="Jump Freighter")).to_have_count(1)


def test_system_search_autocomplete(page: Page, base_url: str) -> None:
    page.goto(base_url)
    origin = page.get_by_text("Origin", exact=True).locator("..").locator("input")
    origin.fill("Itg")
    # SystemSearch debounces 300ms.
    page.wait_for_timeout(500)
    expect(page.get_by_text("ItgOrigin")).to_be_visible()
    expect(page.get_by_text("ItgDanger")).to_be_visible()
    expect(page.get_by_text("ItgSafe")).to_be_visible()
    expect(page.get_by_text("ItgDest")).to_be_visible()


def test_plan_without_systems_shows_error(page: Page, base_url: str) -> None:
    page.goto(base_url)
    page.get_by_role("button", name="Plan Route").click()
    expect(
        page.get_by_text("Please select both origin and destination", exact=False)
    ).to_be_visible()
