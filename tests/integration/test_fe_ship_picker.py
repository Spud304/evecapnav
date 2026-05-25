"""ShipPicker typeahead — replaces the previous Ship-class <select> dropdown.

Backed by /api/cap-ships which returns individual cap ship type names mapped
to their merged class label. The picker writes the type_name into a visible
input and the class_label into RouteControls' internal state.
"""

from __future__ import annotations

from playwright.sync_api import Page, expect


def test_picker_auto_selects_first_ship_on_load(page: Page, base_url: str) -> None:
    """When the cap-ships fetch resolves, the picker should auto-select the
    alphabetically-first ship so Plan Route works without user interaction
    (mirrors the old dropdown's default-to-first behavior)."""
    page.goto(base_url)
    inp = page.get_by_test_id("ship-picker-input")
    # /api/cap-ships returns Archon before Rhea (alphabetical).
    expect(inp).to_have_value("Archon", timeout=5_000)


def test_picker_filters_by_ship_name(page: Page, base_url: str) -> None:
    page.goto(base_url)
    inp = page.get_by_test_id("ship-picker-input")
    inp.click()
    inp.fill("")
    inp.type("Rhe", delay=20)
    expect(
        page.locator('[data-testid="ship-picker-option"][data-ship-name="Rhea"]')
    ).to_be_visible()
    expect(
        page.locator('[data-testid="ship-picker-option"][data-ship-name="Archon"]')
    ).to_have_count(0)


def test_picker_filters_by_class_label(page: Page, base_url: str) -> None:
    """Typing a class label (e.g. 'Carrier') should still surface ships of
    that class — the matcher checks both type_name and class_label."""
    page.goto(base_url)
    inp = page.get_by_test_id("ship-picker-input")
    inp.click()
    inp.fill("")
    inp.type("Carrier", delay=20)
    expect(
        page.locator('[data-testid="ship-picker-option"][data-ship-name="Archon"]')
    ).to_be_visible()


def test_picker_click_commits_selection(page: Page, base_url: str) -> None:
    """Clicking an option fills the input with the type name and closes the menu."""
    page.goto(base_url)
    inp = page.get_by_test_id("ship-picker-input")
    inp.click()
    inp.fill("")
    inp.type("Rhe", delay=20)
    page.locator('[data-testid="ship-picker-option"][data-ship-name="Rhea"]').click()
    expect(inp).to_have_value("Rhea")
    # Picking a JF reveals the JF skill field.
    expect(page.get_by_text("JF skill", exact=True)).to_be_visible()


def test_picker_keyboard_arrow_and_enter(page: Page, base_url: str) -> None:
    """Arrow-down + Enter should commit the highlighted option."""
    page.goto(base_url)
    inp = page.get_by_test_id("ship-picker-input")
    inp.click()
    inp.fill("")
    inp.type("Rhe", delay=20)
    # Already on first option (Rhea); press Enter to commit.
    inp.press("Enter")
    expect(inp).to_have_value("Rhea")


def test_range_badge_renders_with_default_jdc(page: Page, base_url: str) -> None:
    """Range badge shows `Range X LY · Fuel Y/LY · Fatigue ×Z` once a ship
    is selected. Default JDC=5 + Archon (base 3.5 LY) → 3.5 × 2.0 = 7.0 LY."""
    page.goto(base_url)
    badge = page.get_by_test_id("ship-range-badge")
    expect(badge).to_be_visible(timeout=5_000)
    text = badge.inner_text()
    assert "7.0 LY" in text, text
    assert "Fuel" in text
    assert "Fatigue" in text


def test_range_badge_updates_when_jdc_changes(page: Page, base_url: str) -> None:
    """Lowering JDC to 0 collapses Archon's range from 7.0 LY to 3.5 LY.
    Verifies the badge formula reactively re-renders without an API call."""
    from tests.integration.helpers import set_jdc

    page.goto(base_url)
    badge = page.get_by_test_id("ship-range-badge")
    expect(badge).to_be_visible(timeout=5_000)
    set_jdc(page, 0)
    expect(badge).to_contain_text("3.5 LY")


def test_range_badge_updates_when_ship_changes(page: Page, base_url: str) -> None:
    """Selecting Rhea (JF, base 5.0 LY) at default JDC=5 yields 10.0 LY range."""
    from tests.integration.helpers import set_ship

    page.goto(base_url)
    badge = page.get_by_test_id("ship-range-badge")
    expect(badge).to_be_visible(timeout=5_000)
    set_ship(page, "Rhea")
    expect(badge).to_contain_text("10.0 LY")
    # JF has fatigue multiplier 0.1.
    expect(badge).to_contain_text("×0.1")


def test_picker_sends_class_label_in_plan_request(
    page: Page, base_url: str, reseed
) -> None:
    """Selecting Rhea (Jump Freighter class) should send
    ship_class=Jump+Freighter in the /api/route URL."""
    from tests.integration.helpers import select_system, plan_route, set_ship

    reseed("empty")
    page.goto(base_url)
    select_system(page, "Origin", "ItgOrigin")
    select_system(page, "Destination", "ItgDest")
    set_ship(page, "Rhea")
    with page.expect_request("**/api/route?**") as info:
        plan_route(page)
    assert "ship_class=Jump+Freighter" in info.value.url, info.value.url
