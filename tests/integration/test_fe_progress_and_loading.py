"""Loading spinner, Plan button disabled state, banner clear-on-replan."""

from __future__ import annotations

import json

from playwright.sync_api import Page, Route, expect

from tests.integration.helpers import (
    select_system,
    plan_route,
    set_jdc,
    two_hop_result,
)


def _slow_route_mock(page: Page, delay_ms: int = 800) -> None:
    """Hold the /api/route response open for `delay_ms` then emit a happy-path
    result. Lets us assert the progress banner / disabled button while the
    request is in flight."""
    result = two_hop_result()

    def handler(route: Route) -> None:
        page.wait_for_timeout(delay_ms)
        body = (
            'event: progress\ndata: "Searching for route..."\n\n'
            f"event: result\ndata: {json.dumps(result)}\n\n"
        )
        route.fulfill(
            status=200,
            headers={"Content-Type": "text/event-stream"},
            body=body,
        )

    page.route("**/api/route?**", handler)


def test_progress_banner_visible_during_plan(page: Page, base_url: str) -> None:
    _slow_route_mock(page, delay_ms=600)
    page.goto(base_url)
    select_system(page, "Origin", "ItgOrigin")
    select_system(page, "Destination", "ItgDest")
    page.get_by_role("button", name="Plan Route").click()
    # The "Connecting..." progress string appears immediately on click.
    expect(
        page.get_by_text("Connecting...", exact=False).or_(
            page.get_by_text("Searching", exact=False)
        )
    ).to_be_visible(timeout=2000)


def test_plan_button_disabled_during_plan(page: Page, base_url: str) -> None:
    _slow_route_mock(page, delay_ms=800)
    page.goto(base_url)
    select_system(page, "Origin", "ItgOrigin")
    select_system(page, "Destination", "ItgDest")
    btn = page.get_by_role("button", name="Plan Route").or_(
        page.get_by_role("button", name="Planning…")
    )
    page.get_by_role("button", name="Plan Route").click()
    expect(btn).to_be_disabled(timeout=2000)
    # And re-enables once the response resolves.
    expect(page.get_by_role("button", name="Plan Route")).to_be_enabled(timeout=5000)


def test_result_clears_on_subsequent_no_route(
    page: Page, base_url: str, reseed
) -> None:
    """Planning a route then planning again with no-route inputs should
    clear the rendered route table (handleError sets result back to null)."""
    reseed("empty")
    page.goto(base_url)
    select_system(page, "Origin", "ItgOrigin")
    select_system(page, "Destination", "ItgDest")
    plan_route(page)
    # Table is rendered now. Drop JDC → no-route → planTable goes away.
    set_jdc(page, 0)
    page.get_by_role("button", name="Plan Route").click()
    expect(page.get_by_text("No route found at this ship", exact=False)).to_be_visible(
        timeout=15_000
    )
    # The summary card ("Total Hops") should no longer be on the page.
    expect(page.get_by_text("Total Hops", exact=True)).to_have_count(0)


def test_progress_banner_clears_after_completion(
    page: Page, base_url: str, reseed
) -> None:
    reseed("empty")
    page.goto(base_url)
    select_system(page, "Origin", "ItgOrigin")
    select_system(page, "Destination", "ItgDest")
    plan_route(page)
    # After result arrives the progress card with the spinner is removed.
    expect(page.locator("span.animate-spin")).to_have_count(0)
