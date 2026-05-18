"""Form-control behavior: mode toggles, conditionals, sliders, reset."""

from __future__ import annotations

from playwright.sync_api import Page, expect

from tests.integration.helpers import (
    select_system,
    plan_route,
    route_system_names,
    route_data_rows,
    open_advanced_weights,
    set_weight,
    select_routing_mode,
    set_ship_class,
    set_jdc,
    set_jfc,
    set_initial_fatigue,
    set_gate_mode,
    click_reset_weights,
)


def test_advanced_weights_hidden_in_direct_mode(
    page: Page, base_url: str, reseed
) -> None:
    reseed("empty")
    page.goto(base_url)
    expect(page.get_by_text("Advanced cost weights")).to_be_visible()
    select_routing_mode(page, "direct")
    # Toggle button is conditionally rendered alongside the Plan Route button.
    expect(page.get_by_text("Advanced cost weights")).to_have_count(0)
    select_routing_mode(page, "pos")
    expect(page.get_by_text("Advanced cost weights")).to_be_visible()


def test_jf_skill_field_conditional_on_ship_class(page: Page, base_url: str) -> None:
    page.goto(base_url)
    # Default ship class is Carrier — JF skill field is hidden.
    expect(page.get_by_text("JF skill", exact=True)).to_have_count(0)
    set_ship_class(page, "Jump Freighter")
    expect(page.get_by_text("JF skill", exact=True)).to_be_visible()
    set_ship_class(page, "Carrier")
    expect(page.get_by_text("JF skill", exact=True)).to_have_count(0)


def test_jdc_zero_drops_range_below_jump_edge(
    page: Page, base_url: str, reseed
) -> None:
    """JDC=0 makes Carrier range = 3.5 LY, below every 5-LY edge in the
    topology. With gate_mode=off the planner returns no route and the FE
    renders the gate-suggestion error."""
    reseed("empty")
    page.goto(base_url)
    select_system(page, "Origin", "ItgOrigin")
    select_system(page, "Destination", "ItgDest")
    set_jdc(page, 0)
    page.get_by_role("button", name="Plan Route").click()
    expect(page.get_by_text("No route found at this ship", exact=False)).to_be_visible(
        timeout=15_000
    )


def test_initial_fatigue_carries_over_to_first_hop(
    page: Page, base_url: str, reseed
) -> None:
    reseed("empty")
    page.goto(base_url)
    select_system(page, "Origin", "ItgOrigin")
    select_system(page, "Destination", "ItgDest")
    set_initial_fatigue(page, 60)
    plan_route(page)
    # Origin row's Fatigue cell should reflect the carry-over (not "0m").
    fatigue_cell = (
        route_data_rows(page).nth(0).locator("td").nth(5).inner_text().strip()
    )
    assert "1h" in fatigue_cell or "60" in fatigue_cell, fatigue_cell


def test_jfc_sent_in_request_url(page: Page, base_url: str, reseed) -> None:
    reseed("empty")
    page.goto(base_url)
    select_system(page, "Origin", "ItgOrigin")
    select_system(page, "Destination", "ItgDest")
    set_jfc(page, 3)
    with page.expect_request("**/api/route?**") as info:
        plan_route(page)
    assert "jfc_level=3" in info.value.url


def test_gate_mode_reveals_gate_cost_input(page: Page, base_url: str) -> None:
    page.goto(base_url)
    expect(page.get_by_text("Gate cost (= N jumps)")).to_have_count(0)
    set_gate_mode(page, "interregional")
    expect(page.get_by_text("Gate cost (= N jumps)")).to_be_visible()
    set_gate_mode(page, "all")
    expect(page.get_by_text("Gate cost (= N jumps)")).to_be_visible()
    set_gate_mode(page, "off")
    expect(page.get_by_text("Gate cost (= N jumps)")).to_have_count(0)


def test_reset_weights_restores_defaults(page: Page, base_url: str, reseed) -> None:
    reseed("empty")
    page.goto(base_url)
    open_advanced_weights(page)
    set_weight(page, "Danger weight", 9999)
    set_weight(page, "Jumps weight", 1)
    click_reset_weights(page)
    danger = (
        page.get_by_text("Danger weight", exact=True).locator("..").locator("input")
    )
    jumps = page.get_by_text("Jumps weight", exact=True).locator("..").locator("input")
    expect(danger).to_have_value("600")
    expect(jumps).to_have_value("60")


def test_direct_mode_takes_shortest_path_ignoring_kills(
    page: Page, base_url: str, reseed
) -> None:
    """In direct mode the planner ignores `extra_cost` entirely (see
    src/pathfinder.py:259), so even high kills on ItgDanger don't reroute."""
    reseed("kills_on_danger")
    page.goto(base_url)
    select_system(page, "Origin", "ItgOrigin")
    select_system(page, "Destination", "ItgDest")
    select_routing_mode(page, "direct")
    plan_route(page)
    names = route_system_names(page)
    assert "ItgDanger" in names, names
