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
    # Total Wait should be a humanized "Xh Ym" / "Xm" string, not empty.
    assert summary["Total Wait"]
    # Quietest Window can be "00–06" / "—"; we just want it rendered.
    assert summary["Quietest Window"]


def test_summary_card_quiet_hours_dash_when_missing(
    page: Page, base_url: str, reseed
) -> None:
    """quiet_hours: null should produce a '—' in the Quietest Window cell."""
    reseed("empty")
    mock_route_response(page, result=two_hop_result(quiet_hours=None))
    plan_origin_to_dest(page, base_url)
    summary = read_summary_card(page)
    assert summary["Quietest Window"] == "—"


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
