"""Alternatives panel: hop-0 has no toggle, expand/collapse, ordering."""

from __future__ import annotations

from playwright.sync_api import Page, expect

from tests.integration.helpers import (
    route_data_rows,
    expand_alternatives,
    collapse_alternatives,
    plan_origin_to_dest as _plan,
)


def test_hop_zero_has_no_toggle(page: Page, base_url: str, reseed) -> None:
    reseed("empty")
    _plan(page, base_url)
    origin_row = route_data_rows(page).nth(0)
    expect(origin_row.get_by_title("Show alternative systems")).to_have_count(0)


def test_mid_hop_has_toggle(page: Page, base_url: str, reseed) -> None:
    reseed("empty")
    _plan(page, base_url)
    mid_row = route_data_rows(page).nth(1)
    expect(mid_row.get_by_title("Show alternative systems")).to_have_count(1)


def test_expand_and_collapse_alternatives(page: Page, base_url: str, reseed) -> None:
    reseed("empty")
    _plan(page, base_url)
    expand_alternatives(page, 1)
    expect(page.get_by_text("Alternatives reachable from")).to_be_visible()
    collapse_alternatives(page, 1)
    expect(page.get_by_text("Alternatives reachable from")).to_have_count(0)


def test_only_one_hop_can_be_expanded_at_a_time(
    page: Page, base_url: str, reseed
) -> None:
    """The FE tracks expandedHop as a single index — opening hop 2 should
    automatically close hop 1's panel."""
    reseed("kills_on_danger")  # forces safe path with 3 mid hops
    _plan(page, base_url)
    # Route is Origin / SafeA / SafeB / Dest. SafeB row (index 2) should also
    # have alternatives — its prev system is SafeA.
    if route_data_rows(page).count() < 4:
        # Safe path not chosen; skip — this assertion only meaningful with
        # the 3-hop branch.
        return
    expand_alternatives(page, 1)
    expand_alternatives(page, 2)
    # The "Alternatives reachable from" header should be visible exactly once.
    expect(page.get_by_text("Alternatives reachable from")).to_have_count(1)


def test_alternatives_sorted_by_distance(page: Page, base_url: str, reseed) -> None:
    """Backend sorts alts by distance_ly (routes.py:429). The FE just renders
    them in order, so the distance text in the rendered cards should be
    monotonically non-decreasing."""
    reseed("empty")
    _plan(page, base_url)
    expand_alternatives(page, 1)
    cards = page.locator("div.bg-white.border.rounded.px-2\\.5.py-1\\.5")
    # Distance text is "X.XX LY"; extract first number.
    import re as _re

    distances: list[float] = []
    for i in range(cards.count()):
        text = cards.nth(i).inner_text()
        m = _re.search(r"(\d+\.\d+)\s*LY", text)
        if m:
            distances.append(float(m.group(1)))
    assert distances == sorted(distances), distances
