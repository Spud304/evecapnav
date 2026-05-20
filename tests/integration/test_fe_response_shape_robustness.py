"""FE robustness to malformed / sparse backend responses.

All tests here use `mock_route_response` to inject a hand-crafted /api/route
payload. The goal is to lock in graceful behavior for backend changes that
could otherwise silently break the FE — missing keys, empty containers,
unexpected enum values.
"""

from __future__ import annotations

from playwright.sync_api import Page, expect

from tests.integration.helpers import (
    select_system,
    mock_route_response,
    route_data_rows,
    read_summary_card,
    plan_origin_to_dest,
    two_hop_result,
)


def test_zkill_empty_dict_does_not_open_modal(page: Page, base_url: str) -> None:
    """When `zkill` is `{}` (real backend behavior when no stats found),
    the threat cell is empty (not '—') and clicking it must not open the
    modal. This documents an FE branch that's currently lenient."""
    mock_route_response(page, result=two_hop_result(zkill={}))
    plan_origin_to_dest(page, base_url)
    threat_cell = route_data_rows(page).nth(1).locator("td").nth(9)
    threat_cell.click()
    expect(page.get_by_text("Active PVPers", exact=True)).to_have_count(0)


def test_alternatives_empty_renders_no_toggles(page: Page, base_url: str) -> None:
    mock_route_response(page, result=two_hop_result(alternatives={}))
    plan_origin_to_dest(page, base_url)
    expect(page.get_by_title("Show alternative systems")).to_have_count(0)


def test_optimized_missing_hides_tab_strip(page: Page, base_url: str) -> None:
    """`optimized` key absent → Minimum Wait / Optimized tabs not rendered."""
    mock_route_response(page, result=two_hop_result())  # no optimized
    plan_origin_to_dest(page, base_url)
    expect(page.get_by_role("button", name="Minimum Wait")).to_have_count(0)


def test_quiet_hours_null_renders_dash(page: Page, base_url: str) -> None:
    mock_route_response(page, result=two_hop_result(quiet_hours=None))
    plan_origin_to_dest(page, base_url)
    summary = read_summary_card(page)
    assert summary["Quietest Window"] == "—", summary


def test_jump_data_window_24h_renders_header_label(page: Page, base_url: str) -> None:
    """The Jumps column header reads `Jumps/24h` instead of `Jumps/h` when the
    backend declares 24h data."""
    mock_route_response(page, result=two_hop_result(jump_data_window="24h"))
    plan_origin_to_dest(page, base_url)
    expect(page.get_by_text("Jumps/24h", exact=False)).to_be_visible()


def test_edge_type_jump_omits_gate_pill(page: Page, base_url: str) -> None:
    """No step has edge_type=='gate' → no Gate pill rendered anywhere."""
    mock_route_response(page, result=two_hop_result())
    plan_origin_to_dest(page, base_url)
    expect(page.get_by_text("Gate", exact=True)).to_have_count(0)


def test_gate_count_greater_than_one_omits_dead_end_pill(
    page: Page, base_url: str
) -> None:
    result = two_hop_result()
    for step in result["steps"]:
        step["gate_count"] = 3
    mock_route_response(page, result=result)
    plan_origin_to_dest(page, base_url)
    expect(page.get_by_text("Dead End", exact=True)).to_have_count(0)


def test_zero_total_jumps_with_empty_steps_hides_summary(
    page: Page, base_url: str
) -> None:
    """App.tsx guards summary + table on `result.steps.length > 0`. An empty
    steps array (e.g. degenerate same-origin-as-dest response) should not
    render the summary card."""
    mock_route_response(
        page,
        result={
            "steps": [],
            "total_jumps": 0,
            "total_fuel": 0,
            "total_wait_minutes": 0,
            "alternatives": {},
            "zkill": {},
            "quiet_hours": None,
            "jump_data_window": "1h",
        },
    )
    page.goto(base_url)
    select_system(page, "Origin", "ItgOrigin")
    select_system(page, "Destination", "ItgDest")
    # Don't use plan_route — it waits on Total Hops which we expect NOT to render.
    page.get_by_role("button", name="Plan Route").click()
    # Give the SSE handler a moment to settle; if Total Hops was going to
    # appear, it would by now.
    page.wait_for_timeout(500)
    expect(page.get_by_text("Total Hops", exact=True)).to_have_count(0)


def test_sov_owner_empty_string_omits_subtext(page: Page, base_url: str) -> None:
    """`sov_owner: ""` → no <div> with alliance text in the System cell."""
    result = two_hop_result()
    for step in result["steps"]:
        step["sov_owner"] = ""
    mock_route_response(page, result=result)
    plan_origin_to_dest(page, base_url)
    # The System cell's bold name div should have NO sibling muted div.
    sub = route_data_rows(page).nth(0).locator("td").nth(1).locator(".text-\\[11px\\]")
    expect(sub).to_have_count(0)
