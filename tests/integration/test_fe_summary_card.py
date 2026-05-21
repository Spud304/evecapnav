"""Summary card / tab strip / Copy / Open in Dotlan."""

from __future__ import annotations

from playwright.sync_api import Page

from tests.integration.helpers import (
    read_summary_card,
    mock_route_response,
    read_clipboard,
    install_window_open_recorder,
    last_opened_url,
    plan_origin_to_dest,
    two_hop_result,
)


def test_summary_card_renders_jumps_fuel_wait_quiet(
    page: Page, base_url: str, reseed
) -> None:
    reseed("empty")
    plan_origin_to_dest(page, base_url)
    summary = read_summary_card(page)
    assert summary["Total Hops"] == "2"
    # Fuel is route-dependent but always > 0 for a 2-hop carrier route.
    assert summary["Fuel"] not in {"0", "—"}, summary
    # Total LY sums the distance of jump-drive hops only (gate hops contribute 0).
    assert summary["Total LY"] not in {"0.0", "—"}, summary
    # Total Wait should be a humanized "Xh Ym" / "Xm" string, not empty.
    assert summary["Total Wait"]
    # Both quiet-window cells (merged into one card with two lines) render;
    # their value can be "HH–HH" or "—".
    assert summary["Quietest · Jumps"]
    assert summary["Quietest · Kills"]


def test_summary_card_total_ly_sums_jump_hops(
    page: Page, base_url: str, reseed
) -> None:
    """Total LY adds up only edge_type='jump' hops. The integration topology's
    canonical 2-hop route is Origin → Danger (5 LY) → Dest (5 LY) = 10 LY."""
    reseed("empty")
    plan_origin_to_dest(page, base_url)
    summary = read_summary_card(page)
    ly_value = float(summary["Total LY"])
    # Floating-point distance after coords→LY→meters→back to LY: allow tolerance.
    assert 9.5 <= ly_value <= 10.5, summary


def test_summary_card_arrival_time_renders_when_wait_positive(
    page: Page, base_url: str, reseed
) -> None:
    """When total wait > 0, the Total Wait cell's sub-line shows an arrival
    time projection (`arrive ~HH:MM UTC`). Pin Date.now() via init script so
    the assertion is deterministic across runs."""
    from playwright.sync_api import expect

    # Freeze the page's clock to 2026-05-20T12:00:00Z so arrival = noon + wait.
    page.add_init_script(
        "Date.now = () => new Date('2026-05-20T12:00:00Z').getTime();"
    )
    reseed("empty")
    plan_origin_to_dest(page, base_url)
    badge = page.get_by_test_id("arrival-time")
    expect(badge).to_be_visible()
    text = badge.inner_text()
    # Format is "arrive ~HH:MM UTC"; just sanity-check the prefix + UTC suffix.
    assert text.startswith("arrive ~"), text
    assert text.endswith(" UTC"), text


def test_summary_card_quiet_hours_dash_when_missing(
    page: Page, base_url: str, reseed
) -> None:
    """quiet_hours: null and quiet_jumps: null → both cells render '—'."""
    reseed("empty")
    mock_route_response(
        page, result=two_hop_result(quiet_hours=None, quiet_jumps=None)
    )
    plan_origin_to_dest(page, base_url)
    summary = read_summary_card(page)
    assert summary["Quietest · Jumps"] == "—"
    assert summary["Quietest · Kills"] == "—"


def test_summary_card_renders_risk_score(
    page: Page, base_url: str, reseed
) -> None:
    """Risk cell renders a 0–100% value and carries a `data-risk-band` band
    attribute that drives the green/amber/red coloring."""
    from playwright.sync_api import expect

    reseed("empty")
    plan_origin_to_dest(page, base_url)
    risk = page.get_by_test_id("risk-score")
    expect(risk).to_be_visible()
    text = risk.inner_text()
    assert text.endswith("%"), text
    band = risk.get_attribute("data-risk-band")
    assert band in {"low", "mid", "high"}


def test_summary_card_quiet_jumps_independent_of_quiet_hours(
    page: Page, base_url: str, reseed
) -> None:
    """A backend that returns jump-based quiet but no kill-based quiet (or vice
    versa) should render each cell independently — one falls back to '—', the
    other shows the window."""
    reseed("empty")
    mock_route_response(
        page,
        result=two_hop_result(
            quiet_hours=None,
            quiet_jumps={"start": 23, "end": 3, "hourly": [0.0] * 24},
        ),
    )
    plan_origin_to_dest(page, base_url)
    summary = read_summary_card(page)
    assert summary["Quietest · Kills"] == "—"
    assert "23" in summary["Quietest · Jumps"] and "03" in summary["Quietest · Jumps"]


def test_copy_as_text_writes_clipboard(page: Page, base_url: str, reseed) -> None:
    reseed("empty")
    plan_origin_to_dest(page, base_url)
    page.get_by_role("button", name="Copy as text").click()
    clip = read_clipboard(page)
    assert "ItgOrigin" in clip
    assert "ItgDanger" in clip
    assert "ItgDest" in clip
    assert "Total: 2 hops" in clip


def test_open_in_dotlan_builds_url(page: Page, base_url: str, reseed) -> None:
    reseed("empty")
    install_window_open_recorder(page)
    plan_origin_to_dest(page, base_url)
    page.get_by_role("button", name="Open in Dotlan").click()
    url = last_opened_url(page)
    # Carrier (label "Carrier") isn't in the FE's dotlanShipMap → falls back
    # to "Archon". Defaults from RouteControls: jdc=5, jfc=4, jfSkill=4.
    assert url is not None
    assert "evemaps.dotlan.net/jump/Archon,544/" in url
    assert "ItgOrigin" in url and "ItgDanger" in url and "ItgDest" in url
