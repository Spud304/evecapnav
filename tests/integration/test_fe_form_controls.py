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
    set_ship,
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
    """Picking a Jump Freighter (Rhea) should reveal the JF-skill field;
    picking a Carrier (Archon) should hide it. The picker maps the chosen
    ship's class_label to the internal shipClass state that gates this field."""
    page.goto(base_url)
    # No ship selected yet — JF skill field is hidden.
    expect(page.get_by_text("JF skill", exact=True)).to_have_count(0)
    set_ship(page, "Rhea")
    expect(page.get_by_text("JF skill", exact=True)).to_be_visible()
    set_ship(page, "Archon")
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
    """Verify the initial_fatigue form field is sent in the API request.

    The multi-label search inserts a fatigue-decay wait at the origin before
    the first JD, so the origin row's Fatigue cell now shows the post-wait
    value (10m) rather than the entered 60m. The form control itself is
    still doing its job — we assert that by inspecting the outgoing request
    URL contains `initial_fatigue=60`."""
    reseed("empty")
    page.goto(base_url)
    select_system(page, "Origin", "ItgOrigin")
    select_system(page, "Destination", "ItgDest")
    set_initial_fatigue(page, 60)

    seen_urls: list[str] = []
    page.on(
        "request", lambda r: seen_urls.append(r.url) if "/api/route" in r.url else None
    )

    plan_route(page)

    assert any("initial_fatigue=60" in u for u in seen_urls), seen_urls
    # First hop should include a wait > 0 — the search decayed the entered
    # fatigue before the first jump rather than burning it into a worse cooldown.
    first_hop_wait = (
        route_data_rows(page).nth(1).locator("td").nth(4).inner_text().strip()
    )
    assert first_hop_wait not in {"—", "0m"}, first_hop_wait


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


def test_initial_fatigue_accepts_hh_mm_syntax(
    page: Page, base_url: str, reseed
) -> None:
    """`1h 30m` syntax should parse to 90 minutes and round-trip into the
    /api/route request as `initial_fatigue=90`."""
    reseed("empty")
    page.goto(base_url)
    select_system(page, "Origin", "ItgOrigin")
    select_system(page, "Destination", "ItgDest")
    set_initial_fatigue(page, "1h 30m")

    with page.expect_request("**/api/route?**") as info:
        plan_route(page)
    assert "initial_fatigue=90" in info.value.url, info.value.url


def test_initial_fatigue_invalid_input_blocks_plan(
    page: Page, base_url: str, reseed
) -> None:
    """A garbage fatigue input should show the validation hint and refuse
    to fire /api/route."""
    reseed("empty")
    page.goto(base_url)
    select_system(page, "Origin", "ItgOrigin")
    select_system(page, "Destination", "ItgDest")
    set_initial_fatigue(page, "definitely not a duration")
    expect(page.get_by_text("Unrecognized format", exact=False)).to_be_visible()
    # Clicking Plan Route now surfaces the same complaint via onError; the
    # planRouteSSE call never fires. The integration assertion is that the
    # validation hint stays visible (no plan-success summary card appears).
    page.get_by_role("button", name="Plan Route").click()
    expect(page.get_by_text("Total Hops", exact=True)).to_have_count(0)


def test_route_preference_slider_renders_tick_marks(
    page: Page, base_url: str
) -> None:
    """The slider has a `<datalist>` with three labeled stops (Quickest /
    Balanced / Least jumps). Browsers render small tick marks at the
    datalist option positions."""
    page.goto(base_url)
    datalist = page.locator("datalist#wait-weight-stops")
    expect(datalist).to_have_count(1)
    options = datalist.locator("option")
    expect(options).to_have_count(3)


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
