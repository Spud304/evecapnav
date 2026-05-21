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


def test_high_kills_row_marked_high_threat(page: Page, base_url: str, reseed) -> None:
    """kills > 10 → row carries data-row-threat='high' (red overlay).
    Switched from asserting the Tailwind class string to a stable data
    attribute so the test doesn't break when palette colors change."""
    reseed("kills_red_on_danger")  # 20 kills > 10 → high band
    _route_through_danger(page, base_url)
    danger_row = route_data_rows(page).nth(1)
    assert danger_row.get_attribute("data-row-threat") == "high"


def test_mid_kills_row_marked_mid_threat(page: Page, base_url: str, reseed) -> None:
    reseed("kills_amber_on_danger")  # 5 kills → (3, 10] mid band
    _route_through_danger(page, base_url)
    danger_row = route_data_rows(page).nth(1)
    assert danger_row.get_attribute("data-row-threat") == "mid"


def test_zero_kills_row_no_threat(page: Page, base_url: str, reseed) -> None:
    reseed("empty")
    _route_through_danger(page, base_url)
    danger_row = route_data_rows(page).nth(1)
    assert danger_row.get_attribute("data-row-threat") == "none"


def test_sec_band_pill_renders_NS_for_null_sec(
    page: Page, base_url: str, reseed
) -> None:
    """Every system in the integration topology is null-sec — each route row
    should carry a `data-sec-band='NS'` pill."""
    reseed("empty")
    plan_origin_to_dest(page, base_url)
    pills = page.locator('[data-testid="sec-band-pill"]')
    assert pills.count() >= 2
    for i in range(pills.count()):
        assert pills.nth(i).get_attribute("data-sec-band") == "NS"


def test_sec_band_pill_renders_LS_HS_from_mock(
    page: Page, base_url: str
) -> None:
    """Mock a route with low-sec and hi-sec steps to exercise the LS/HS
    branches of the secBand() function. The hi-sec pill is intentionally
    rendered with a hard-red warning palette (capital ships can't gate-jump
    into HS) — that styling lives in secBandStyle()."""
    from tests.integration.helpers import (
        mock_route_response,
        plan_origin_to_dest,
        step_dict,
        two_hop_result,
    )

    result = two_hop_result()
    result["steps"] = [
        step_dict(system_id=1, system_name="LowSec1", security=0.3),
        step_dict(system_id=2, system_name="HiSec1", security=0.7),
    ]
    mock_route_response(page, result=result)
    plan_origin_to_dest(page, base_url)
    pills = page.locator('[data-testid="sec-band-pill"]')
    bands = [pills.nth(i).get_attribute("data-sec-band") for i in range(pills.count())]
    assert "LS" in bands
    assert "HS" in bands


def test_safe_au_subtext_renders_warp_and_nearest(
    page: Page, base_url: str, reseed
) -> None:
    """The 'warp X-Y' / 'near Z' subtitles render as muted spans below the AU
    number so a pilot can see HOW to make the safe spot without hovering.
    A duplicate `title` tooltip on the cell makes the info screen-reader-
    friendly too."""
    reseed("empty")
    plan_origin_to_dest(page, base_url)
    origin_row = route_data_rows(page).nth(0)
    safe_cell = origin_row.locator("td").last
    # Visible subtitle spans must be present (integration topology seeds two
    # planets per system so the `warp X-Y` text always populates).
    from playwright.sync_api import expect

    expect(safe_cell.locator(".text-\\[10\\.5px\\]").first).to_be_visible()
    # And the cell's `title` attribute still carries the same info.
    title = safe_cell.get_attribute("title") or ""
    assert "warp" in title or "near" in title, title


def test_moons_column_hidden_in_safe_mode(
    page: Page, base_url: str, reseed
) -> None:
    """In safe (default) routing mode the Moons column is hidden — pilots
    don't care about moon count unless they're POS-hopping."""
    from playwright.sync_api import expect

    reseed("empty")
    plan_origin_to_dest(page, base_url)
    expect(page.get_by_role("columnheader", name="Moons")).to_have_count(0)


def test_column_headers_render_info_icons_with_titles(
    page: Page, base_url: str, reseed
) -> None:
    """Every column header should carry a hoverable ⓘ icon whose `title`
    attribute explains the column. The Hour-of-day column header must
    explicitly call out that the sparkline is a weekly average."""
    from playwright.sync_api import expect

    reseed("empty")
    plan_origin_to_dest(page, base_url)
    icons = page.get_by_test_id("header-info")
    # At least 9 columns get an info icon (System, Sec, LY, Wait, Fatigue,
    # Kills/h, Hour-of-day, Threat, Safe AU). Moons is only present in POS
    # mode so this lower bound is mode-agnostic.
    assert icons.count() >= 9

    # Hour-of-day's tooltip must explicitly mention the weekly averaging
    # window — that's the bit users were missing from the label alone.
    hour_header = page.get_by_role("columnheader", name="Hour-of-day", exact=False)
    expect(hour_header).to_be_visible()
    hour_info = hour_header.get_by_test_id("header-info")
    title = hour_info.get_attribute("title") or ""
    assert "7" in title or "week" in title.lower(), title


def test_hour_of_day_column_label_says_weekly_avg(
    page: Page, base_url: str, reseed
) -> None:
    """The visible column header itself (not just the tooltip) should say
    `weekly avg` so users don't have to hover to learn the window."""
    from playwright.sync_api import expect

    reseed("empty")
    plan_origin_to_dest(page, base_url)
    header = page.get_by_role("columnheader", name="Hour-of-day", exact=False)
    expect(header).to_contain_text("weekly avg")


def test_wait_cell_renders_two_tone_bar_when_breakdown_present(
    page: Page, base_url: str
) -> None:
    """When a step has a nonzero wait_cooldown_minutes + wait_decay_minutes
    breakdown, the Wait cell should render a small two-segment bar
    (red = cooldown, blue = decay) underneath the time."""
    from tests.integration.helpers import mock_route_response, step_dict, two_hop_result

    result = two_hop_result()
    result["steps"] = [
        step_dict(system_id=1, system_name="Origin", security=-0.5),
        step_dict(
            system_id=2,
            system_name="Dest",
            security=-0.5,
            distance_ly=5,
            wait_minutes=60,
            wait_cooldown_minutes=10,
            wait_decay_minutes=50,
            edge_type="jump",
        ),
    ]
    mock_route_response(page, result=result)
    plan_origin_to_dest(page, base_url)

    bar = page.get_by_test_id("wait-bar")
    expect(bar).to_have_count(1)
    cd = page.get_by_test_id("wait-bar-cooldown")
    dc = page.get_by_test_id("wait-bar-decay")
    # cooldown 10/60 = 16.67%; decay 50/60 = 83.33%.
    cd_w = cd.evaluate("el => el.style.width")
    dc_w = dc.evaluate("el => el.style.width")
    assert cd_w.startswith("16") or cd_w.startswith("17"), cd_w
    assert dc_w.startswith("83") or dc_w.startswith("84"), dc_w


def test_wait_cell_no_bar_when_breakdown_zero(
    page: Page, base_url: str
) -> None:
    """No bar should render when both cooldown and decay are zero (e.g. on
    a gate hop or origin row). Just the time text."""
    from tests.integration.helpers import mock_route_response, two_hop_result

    mock_route_response(page, result=two_hop_result())
    plan_origin_to_dest(page, base_url)
    expect(page.get_by_test_id("wait-bar")).to_have_count(0)


def test_wait_cell_no_bar_on_gate_hops(page: Page, base_url: str) -> None:
    """Gate hops have travel-time + pre-jump decay rolled together but no
    red-timer cooldown — the two-tone bar would be misleading. Suppress it
    on gate edges even if wait_decay_minutes is nonzero."""
    from tests.integration.helpers import mock_route_response, step_dict, two_hop_result

    result = two_hop_result()
    result["steps"] = [
        step_dict(system_id=1, system_name="Origin", security=-0.5),
        step_dict(
            system_id=2,
            system_name="GateDest",
            security=-0.5,
            distance_ly=0,
            wait_minutes=31,
            # The search emits decay for the pre-JD wait at this system, but
            # because the inbound edge was a gate the row shouldn't show the
            # red/blue bar at all.
            wait_cooldown_minutes=0,
            wait_decay_minutes=31,
            edge_type="gate",
        ),
    ]
    mock_route_response(page, result=result)
    plan_origin_to_dest(page, base_url)
    expect(page.get_by_test_id("wait-bar")).to_have_count(0)


def test_row_carries_sov_color_for_known_alliance(
    page: Page, base_url: str, reseed
) -> None:
    """When a route step's sov_owner is a known alliance, the row's
    `data-sov-color` attribute should carry the expected color so the
    4-pixel inset left border renders. Empty when no sov."""
    from tests.integration.helpers import mock_route_response, step_dict, two_hop_result

    result = two_hop_result()
    result["steps"] = [
        step_dict(
            system_id=1,
            system_name="GoonStaging",
            security=-0.5,
            sov_owner="Goonswarm Federation",
        ),
        step_dict(
            system_id=2,
            system_name="BraveStaging",
            security=-0.5,
            sov_owner="Brave Collective",
        ),
    ]
    mock_route_response(page, result=result)
    plan_origin_to_dest(page, base_url)
    rows = route_data_rows(page)
    goon = rows.nth(0)
    brave = rows.nth(1)
    assert goon.get_attribute("data-sov-color") == "#ff7733"
    assert brave.get_attribute("data-sov-color") == "#a26ad8"


def test_moons_column_visible_in_pos_mode(
    page: Page, base_url: str, reseed
) -> None:
    """POS-hopping mode brings the Moons column back."""
    from playwright.sync_api import expect
    from tests.integration.helpers import (
        select_routing_mode,
        select_system,
        plan_route,
    )

    reseed("empty")
    page.goto(base_url)
    select_system(page, "Origin", "ItgOrigin")
    select_system(page, "Destination", "ItgDest")
    select_routing_mode(page, "pos")
    plan_route(page)
    expect(page.get_by_role("columnheader", name="Moons")).to_be_visible()


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
