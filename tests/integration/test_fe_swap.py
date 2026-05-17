"""Click a swap alternative in the route table; the table should update."""

from __future__ import annotations

from playwright.sync_api import Page, expect

from tests.integration.helpers import select_system, plan_route, route_system_names


def test_swap_replaces_mid_hop(page: Page, base_url: str, reseed) -> None:
    # With no kills the planner picks the 2-hop route via ItgDanger. The
    # alternatives panel for hop 1 should include ItgSafeA, which is the
    # only other 1-jump-from-origin null system reachable from ItgOrigin.
    reseed("empty")
    page.goto(base_url)
    select_system(page, "Origin", "ItgOrigin")
    select_system(page, "Destination", "ItgDest")
    plan_route(page)
    assert route_system_names(page)[1] == "ItgDanger"

    # The "▸" toggle next to hop 1's index opens the alternatives table.
    page.locator("tbody tr").nth(1).get_by_title("Show alternative systems").click()
    expect(page.get_by_text("Alternatives reachable from")).to_be_visible()

    # The alternatives panel renders ItgSafeA as a clickable card.
    alt = page.locator("div.cursor-pointer", has_text="ItgSafeA").first
    alt.click()

    # After the swap the new route detours via ItgSafeA → ItgSafeB → Dest.
    page.wait_for_function(
        "() => Array.from(document.querySelectorAll('tbody tr td:nth-child(2) .font-semibold'))"
        ".some(el => el.textContent.includes('ItgSafeB'))"
    )
    names = route_system_names(page)
    assert names[1] == "ItgSafeA" and "ItgSafeB" in names, names
