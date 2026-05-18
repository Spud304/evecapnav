"""RouteTable row coloring, pills, sov, hop-0 fallbacks."""

from __future__ import annotations

from playwright.sync_api import Page, expect

from tests.integration.helpers import (
    select_system,
    plan_route,
    set_jdc,
    set_gate_mode,
    route_data_rows,
    plan_origin_to_dest,
    plan_through_danger,
)


def _route_through_danger(page: Page, base_url: str) -> None:
    """Row-coloring assertions need both danger AND jumps weight zeroed —
    the kills/jumps scenarios all park threat data on ItgDanger and we want
    the planner to ignore all of it so the row lands on screen."""
    plan_through_danger(page, base_url, zero_jumps_weight=True)


def test_high_kills_row_paints_red(page: Page, base_url: str, reseed) -> None:
    reseed("kills_red_on_danger")  # 20 kills > 10 → red band
    _route_through_danger(page, base_url)
    danger_row = route_data_rows(page).nth(1)
    classes = danger_row.get_attribute("class") or ""
    assert "bg-red-50" in classes, classes


def test_mid_kills_row_paints_amber(page: Page, base_url: str, reseed) -> None:
    reseed("kills_amber_on_danger")  # 5 kills → (3, 10] amber band
    _route_through_danger(page, base_url)
    danger_row = route_data_rows(page).nth(1)
    classes = danger_row.get_attribute("class") or ""
    assert "bg-amber-50" in classes, classes


def test_zero_kills_row_uncolored(page: Page, base_url: str, reseed) -> None:
    reseed("empty")
    _route_through_danger(page, base_url)
    danger_row = route_data_rows(page).nth(1)
    classes = danger_row.get_attribute("class") or ""
    assert "bg-red-50" not in classes and "bg-amber-50" not in classes, classes


def test_hop_zero_renders_dash_for_distance_and_wait(
    page: Page, base_url: str, reseed
) -> None:
    reseed("empty")
    plan_origin_to_dest(page, base_url)
    origin_row = route_data_rows(page).nth(0)
    # Columns (0-indexed): 0=#, 1=System, 2=Sec, 3=LY, 4=Wait, 5=Fatigue
    assert origin_row.locator("td").nth(3).inner_text().strip() == "—"
    assert origin_row.locator("td").nth(4).inner_text().strip() == "—"


def test_dead_end_pill_renders_on_one_gate_system(
    page: Page, base_url: str, reseed
) -> None:
    """Route via Safe branch puts ItgSafeA (gate_count=1) on the route, which
    should render the 'Dead End' pill in the System column."""
    reseed("kills_on_danger")  # forces safe path at default danger_weight
    plan_origin_to_dest(page, base_url)
    safe_a_row = route_data_rows(page).filter(has_text="ItgSafeA").first
    expect(safe_a_row.get_by_text("Dead End", exact=True)).to_be_visible()


def test_dead_end_pill_absent_on_multi_gate_system(
    page: Page, base_url: str, reseed
) -> None:
    reseed("empty")  # danger path through ItgDanger (gate_count=3)
    plan_origin_to_dest(page, base_url)
    danger_row = route_data_rows(page).filter(has_text="ItgDanger").first
    expect(danger_row.get_by_text("Dead End", exact=True)).to_have_count(0)


def test_gate_pill_renders_when_route_takes_gate_hop(
    page: Page, base_url: str, reseed
) -> None:
    """With JDC=0 (Carrier range 3.5 LY < every jump edge), the only way to
    reach Dest is via stargate hops. Enabling gate_mode=all should produce a
    route through the Origin-Danger-Dest gate triangle, with Gate pills on
    each non-origin row."""
    reseed("empty")
    page.goto(base_url)
    select_system(page, "Origin", "ItgOrigin")
    select_system(page, "Destination", "ItgDest")
    set_jdc(page, 0)
    set_gate_mode(page, "all")
    plan_route(page)
    # At least one Gate pill should be rendered.
    expect(page.get_by_text("Gate", exact=True).first).to_be_visible()


def test_kills_cell_color_class_at_red_threshold(
    page: Page, base_url: str, reseed
) -> None:
    reseed("kills_red_on_danger")
    _route_through_danger(page, base_url)
    danger_row = route_data_rows(page).filter(has_text="ItgDanger").first
    kills_cell = danger_row.locator("td").nth(6)
    classes = kills_cell.get_attribute("class") or ""
    assert "color-bad" in classes, classes


def test_kills_cell_color_class_at_amber_threshold(
    page: Page, base_url: str, reseed
) -> None:
    reseed("kills_amber_on_danger")
    _route_through_danger(page, base_url)
    danger_row = route_data_rows(page).filter(has_text="ItgDanger").first
    kills_cell = danger_row.locator("td").nth(6)
    classes = kills_cell.get_attribute("class") or ""
    assert "color-warn" in classes, classes


def test_sov_owner_renders_under_system_name(
    page: Page, base_url: str, reseed, live_server
) -> None:
    """Seed a sovereignty row on ItgDanger and confirm the alliance name
    renders as the sub-text under the system name in the System column."""
    reseed("empty")
    # Inject sovereignty directly using the production helper; the danger
    # cache is already invalidated by the reseed call.
    from src.cache import save_sovereignty, _invalidate_danger_cache

    save_sovereignty(
        live_server.instance_path,
        [(90000002, 999, "TEST ALLIANCE", 0, "")],
    )
    _invalidate_danger_cache()
    # init_route_data already loaded sovereignty into _systems at app start;
    # we need to reload it. Easiest: load via the helper and patch _systems.
    from src.cache import load_sovereignty
    from src import routes as routes_mod

    sov = load_sovereignty(live_server.instance_path)
    for sid, info in sov.items():
        if sid in routes_mod._systems:
            routes_mod._systems[sid].sov_alliance_name = info["alliance_name"]

    plan_through_danger(page, base_url)
    danger_row = route_data_rows(page).filter(has_text="ItgDanger").first
    expect(danger_row.get_by_text("TEST ALLIANCE")).to_be_visible()
