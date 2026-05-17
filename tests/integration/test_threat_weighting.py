"""End-to-end verification that threat-weighting knobs change the chosen route.

Each test reseeds `cache.sqlite` with a single threat dimension (kills, jumps,
historical activity), runs the FE pipeline, and asserts whether the route
includes ItgDanger (raw shortest) or detours through ItgSafeA/ItgSafeB to
avoid the threat. The safe branch is 3 hops on purpose — see
`tests/seeds/topology.py` — so the cost margin between branches stays well
above any heap tie-break / float rounding noise that can differ between
local macOS and CI Linux.

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


def _assert_danger_path(names: list[str]) -> None:
    assert "ItgDanger" in names and "ItgSafeA" not in names, (
        f"Expected raw shortest path through ItgDanger; got {names}"
    )


def _assert_safe_path(names: list[str]) -> None:
    assert "ItgSafeA" in names and "ItgSafeB" in names and "ItgDanger" not in names, (
        f"Expected detour via ItgSafeA → ItgSafeB; got {names}"
    )


def test_kills_reroute_via_safe_at_default_weight(
    page: Page, base_url: str, reseed
) -> None:
    reseed("kills_on_danger")
    _assert_safe_path(_plan(page, base_url))


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
    _assert_danger_path(route_system_names(page))


def test_jumps_reroute_via_safe_at_default_weight(
    page: Page, base_url: str, reseed
) -> None:
    reseed("jumps_on_danger")
    _assert_safe_path(_plan(page, base_url))


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
    _assert_danger_path(route_system_names(page))


def test_activity_data_affects_route_at_default_weight(
    page: Page, base_url: str, reseed
) -> None:
    # Activity weight is not exposed in the form; this confirms the default
    # ACTIVITY_WEIGHT is applied to the activity column when present.
    reseed("activity_on_danger")
    _assert_safe_path(_plan(page, base_url))
