"""Verify seeded zkill intel renders in the row and modal."""

from __future__ import annotations

from playwright.sync_api import Page, expect

from tests.integration.helpers import (
    select_system,
    plan_route,
    open_advanced_weights,
    set_weight,
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
