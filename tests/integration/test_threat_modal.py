"""Verify seeded zkill intel renders in the row and modal."""

from __future__ import annotations

from playwright.sync_api import Page, expect

from tests.integration.helpers import (
    select_system,
    plan_route,
    open_advanced_weights,
    set_weight,
    close_threat_modal,
    plan_through_danger as _plan_through_danger,
)


def test_zkill_intel_renders_in_row_and_modal(
    page: Page, base_url: str, reseed
) -> None:
    # Seed kills + zkill intel on ItgDanger but tell the planner to ignore the
    # kills (danger_weight = 0) so the route still passes through that system
    # and the threat cell has data to render.
    reseed("zkill_intel")
    page.goto(base_url)
    select_system(page, "Origin", "ItgOrigin")
    select_system(page, "Destination", "ItgDest")
    open_advanced_weights(page)
    set_weight(page, "Danger weight", 0)
    plan_route(page)

    # Row-level threat cell shows the "PVPers" count from the seeded zkill.
    expect(page.get_by_text("17 PVPers")).to_be_visible()
    expect(page.get_by_text("Gang: 63%")).to_be_visible()

    # Click into the Threat cell to open the modal.
    page.get_by_text("17 PVPers").click()
    # Modal headings — "Active PVPers" + "Active Corps" only appear inside it.
    expect(page.get_by_text("Active PVPers", exact=True)).to_be_visible()
    expect(page.get_by_text("Active Corps", exact=True)).to_be_visible()
    # Distinguishing values: 17 active chars, 4 corps, 88 ships destroyed.
    modal = page.locator("div.fixed.inset-0")
    expect(modal).to_contain_text("17")
    expect(modal).to_contain_text("4")
    expect(modal).to_contain_text("88")


def test_hourly_bar_chart_renders_24_bars(page: Page, base_url: str, reseed) -> None:
    """ThreatModal renders the chart only when hourly.length === 24."""
    reseed("varied_hourly_zkill")
    _plan_through_danger(page, base_url)
    page.get_by_text("25 PVPers").click()
    chart = page.locator("div.flex.items-end.gap-px")
    expect(chart).to_be_visible()
    bars = chart.locator("> div")
    expect(bars).to_have_count(24)


def test_hourly_bar_chart_colors_span_threshold_bands(
    page: Page, base_url: str, reseed
) -> None:
    """The bar at hour 0 (count=10/100 → 10%, green band), hour 8 (50/100 →
    50%, amber), and hour 20 (100/100 → 100%, red) should each render with
    the matching CSS variable color. Reading computed style is robust to
    threshold tuning."""
    reseed("varied_hourly_zkill")
    _plan_through_danger(page, base_url)
    page.get_by_text("25 PVPers").click()
    bars = page.locator("div.flex.items-end.gap-px > div").locator("> div")

    def color_at(hour: int) -> str:
        return bars.nth(hour).evaluate("el => getComputedStyle(el).backgroundColor")

    green = color_at(0)
    amber = color_at(8)
    red = color_at(20)
    # The three colors must be distinct — exact RGB is theme-dependent but
    # the three CSS variables map to three different values.
    assert len({green, amber, red}) == 3, (green, amber, red)


def test_zkillboard_link_in_modal_targets_system(
    page: Page, base_url: str, reseed
) -> None:
    reseed("zkill_intel")
    _plan_through_danger(page, base_url)
    page.get_by_text("17 PVPers").click()
    link = page.get_by_role("link", name="View on zKillboard →")
    href = link.get_attribute("href")
    assert href == "https://zkillboard.com/system/90000002/", href


def test_modal_closes_on_close_button(page: Page, base_url: str, reseed) -> None:
    reseed("zkill_intel")
    _plan_through_danger(page, base_url)
    page.get_by_text("17 PVPers").click()
    close_threat_modal(page, method="button")
    expect(page.get_by_text("Active PVPers", exact=True)).to_have_count(0)


def test_modal_closes_on_backdrop_click(page: Page, base_url: str, reseed) -> None:
    reseed("zkill_intel")
    _plan_through_danger(page, base_url)
    page.get_by_text("17 PVPers").click()
    close_threat_modal(page, method="backdrop")
    expect(page.get_by_text("Active PVPers", exact=True)).to_have_count(0)


# NOTE: the "true zkill-missing" branch (z is undefined, threat cell shows
# the dash) is covered in test_fe_response_shape_robustness.py. When the real
# backend can't find zkill data it inserts an empty dict `{}` per system —
# truthy in JS, so the threat cell renders empty without opening the modal.
# That's an FE oversight worth knowing about, but the dash-fallback assertion
# requires fully mocking the response.
