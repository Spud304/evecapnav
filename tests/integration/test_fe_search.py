"""SystemSearch debounce, < 2-char short-circuit, click-outside close."""

from __future__ import annotations

from playwright.sync_api import Page, expect


def _origin_input(page: Page):
    return page.get_by_text("Origin", exact=True).locator("..").locator("input")


def test_search_does_not_fire_for_single_char(page: Page, base_url: str) -> None:
    """Typing one character must not trigger a /api/systems/search call.

    `requests_made` is tracked via page.on('request', ...) for the lifetime
    of the test; we wait past the 300 ms debounce window and assert no hit.
    """
    page.goto(base_url)
    requests: list[str] = []
    page.on(
        "request",
        lambda req: (
            requests.append(req.url) if "/api/systems/search" in req.url else None
        ),
    )
    inp = _origin_input(page)
    inp.fill("")
    inp.type("I", delay=10)
    page.wait_for_timeout(500)
    assert not requests, requests
    # Dropdown also stays closed.
    expect(page.get_by_text("ItgOrigin")).to_have_count(0)


def test_search_fires_after_debounce_with_two_chars(page: Page, base_url: str) -> None:
    page.goto(base_url)
    inp = _origin_input(page)
    inp.fill("")
    with page.expect_request("**/api/systems/search?q=It*") as info:
        inp.type("It", delay=10)
    assert "q=It" in info.value.url


def test_search_empty_results_keeps_dropdown_closed(page: Page, base_url: str) -> None:
    """A query with no matches in the seed (`ZZZZ`) returns []; the
    SystemSearch component only opens the dropdown when data.length > 0."""
    page.goto(base_url)
    inp = _origin_input(page)
    inp.fill("")
    inp.type("ZZZZ", delay=10)
    page.wait_for_timeout(500)
    # No system named ZZZZ — dropdown items shouldn't render.
    expect(page.locator("div.cursor-pointer", has_text="ZZZZ")).to_have_count(0)


def test_click_outside_closes_dropdown(page: Page, base_url: str) -> None:
    page.goto(base_url)
    inp = _origin_input(page)
    inp.fill("")
    inp.type("Itg", delay=10)
    page.get_by_text("ItgOrigin").first.wait_for(state="visible")
    # Click the page header (well outside any SystemSearch wrap).
    page.get_by_role("heading", name="EVE CapNav").click()
    expect(page.get_by_text("ItgOrigin")).to_have_count(0)


def test_selecting_result_fills_input(page: Page, base_url: str) -> None:
    page.goto(base_url)
    inp = _origin_input(page)
    inp.fill("")
    inp.type("ItgOri", delay=10)
    page.locator("div.cursor-pointer", has_text="ItgOrigin").first.click()
    expect(inp).to_have_value("ItgOrigin")
