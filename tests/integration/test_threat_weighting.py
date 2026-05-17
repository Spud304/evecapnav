"""End-to-end verification that threat-weighting knobs change the chosen route.

Each test reseeds `cache.sqlite` with a single threat dimension (kills, jumps,
historical activity), runs the FE pipeline twice, and asserts the mid-hop
flipped between ItgDanger (raw shortest) and ItgSafe (rerouted to avoid threat).

`activity_weight` is not exposed in the form, so we only verify the default
weight has an effect there — that still proves the activity column of
cache.sqlite is being read end-to-end.
"""

from __future__ import annotations

from playwright.sync_api import Page

from tests.integration.helpers import (
    select_system,
    plan_route,
    route_system_names,
    open_advanced_weights,
    set_weight,
)


def _plan(page: Page, base_url: str) -> list[str]:
    page.goto(base_url)
    select_system(page, "Origin", "ItgOrigin")
    select_system(page, "Destination", "ItgDest")
    plan_route(page)
    return route_system_names(page)


def test_kills_reroute_via_safe_at_default_weight(
    page: Page, base_url: str, reseed
) -> None:
    reseed("kills_on_danger")
    names = _plan(page, base_url)
    assert names[1] == "ItgSafe", f"Expected reroute around danger; got {names}"


def test_kills_pass_through_danger_when_weight_zeroed(
    page: Page, base_url: str, reseed
) -> None:
    reseed("kills_on_danger")
    page.goto(base_url)
    select_system(page, "Origin", "ItgOrigin")
    select_system(page, "Destination", "ItgDest")
    open_advanced_weights(page)
    set_weight(page, "Danger weight", 0)
    plan_route(page)
    names = route_system_names(page)
    assert names[1] == "ItgDanger", f"Expected raw shortest with dw=0; got {names}"


def test_jumps_reroute_via_safe_at_default_weight(
    page: Page, base_url: str, reseed
) -> None:
    reseed("jumps_on_danger")
    names = _plan(page, base_url)
    assert names[1] == "ItgSafe", f"Traffic should reroute via Safe; got {names}"


def test_jumps_pass_through_danger_when_weight_zeroed(
    page: Page, base_url: str, reseed
) -> None:
    reseed("jumps_on_danger")
    page.goto(base_url)
    select_system(page, "Origin", "ItgOrigin")
    select_system(page, "Destination", "ItgDest")
    open_advanced_weights(page)
    set_weight(page, "Jumps weight", 0)
    plan_route(page)
    names = route_system_names(page)
    assert names[1] == "ItgDanger", f"Expected raw shortest with jw=0; got {names}"


def test_activity_data_affects_route_at_default_weight(
    page: Page, base_url: str, reseed
) -> None:
    # Activity weight is not exposed in the form; this confirms the default
    # ACTIVITY_WEIGHT is applied to the activity column when present.
    reseed("activity_on_danger")
    names = _plan(page, base_url)
    assert names[1] == "ItgSafe", (
        f"Activity should reroute via Safe with default activity_weight; got {names}"
    )
