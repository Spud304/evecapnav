"""Verify the route table and summary card render after a plan request."""

from __future__ import annotations

from playwright.sync_api import Page, expect

from tests.integration.helpers import select_system, plan_route, route_system_names


def test_basic_route_renders_table_and_summary(
    page: Page, base_url: str, reseed
) -> None:
    reseed("empty")
    page.goto(base_url)

    select_system(page, "Origin", "ItgOrigin")
    select_system(page, "Destination", "ItgDest")
    plan_route(page)

    names = route_system_names(page)
    assert names[0] == "ItgOrigin"
    assert names[-1] == "ItgDest"
    # Origin -> mid -> Dest = 3 rows; with empty threat data the mid is ItgDanger.
    assert len(names) == 3
    assert names[1] == "ItgDanger"

    # Summary card shows total jumps = 2.
    expect(page.get_by_text("Total Hops", exact=True)).to_be_visible()
    summary = page.get_by_text("Total Hops", exact=True).locator("..")
    expect(summary).to_contain_text("2")
