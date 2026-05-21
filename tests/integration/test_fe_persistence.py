"""localStorage round-trip — origin / dest / ship / skills must survive a reload."""

from __future__ import annotations

from playwright.sync_api import Page, expect

from tests.integration.helpers import (
    select_system,
    set_ship,
    set_jdc,
)


def test_form_state_persists_across_reload(page: Page, base_url: str) -> None:
    """After picking origin, dest, ship, and JDC, reloading the page should
    re-hydrate the form with the same values."""
    page.goto(base_url)
    select_system(page, "Origin", "ItgOrigin")
    select_system(page, "Destination", "ItgDest")
    set_ship(page, "Rhea")
    set_jdc(page, 4)

    # The save is debounced 500ms — wait it out before reloading.
    page.wait_for_timeout(700)
    page.reload()

    # SystemSearch defaultValue mirrors what was persisted.
    origin = page.get_by_text("Origin", exact=True).locator("..").locator("input")
    dest = page.get_by_text("Destination", exact=True).locator("..").locator("input")
    expect(origin).to_have_value("ItgOrigin")
    expect(dest).to_have_value("ItgDest")

    # Ship + JDC.
    expect(page.get_by_test_id("ship-picker-input")).to_have_value("Rhea")
    jdc_sel = page.get_by_text("JDC level", exact=True).locator("..").locator("select")
    expect(jdc_sel).to_have_value("4")


def test_clear_saved_button_wipes_persistence(page: Page, base_url: str) -> None:
    """Clicking ↺ Clear saved should remove the localStorage entry; after
    reload the form goes back to defaults (no origin/dest, Archon, JDC 5)."""
    page.goto(base_url)
    select_system(page, "Origin", "ItgOrigin")
    select_system(page, "Destination", "ItgDest")
    set_ship(page, "Rhea")
    page.wait_for_timeout(700)

    # The reset button reloads the page; expect that to happen automatically.
    page.get_by_test_id("reset-all-button").click()
    page.wait_for_load_state("networkidle")

    # Origin/dest cleared.
    origin = page.get_by_text("Origin", exact=True).locator("..").locator("input")
    dest = page.get_by_text("Destination", exact=True).locator("..").locator("input")
    expect(origin).to_have_value("")
    expect(dest).to_have_value("")
    # Ship defaults back to Archon (auto-select first cap on load).
    expect(page.get_by_test_id("ship-picker-input")).to_have_value("Archon")


def test_localStorage_corruption_does_not_crash_form(
    page: Page, base_url: str
) -> None:
    """If a user manually wrote garbage into evecapnav.prefs, loadPrefs()
    should swallow the JSON.parse error and return an empty object so the
    form still renders."""
    # Pre-set bad data BEFORE first navigation so loadPrefs sees it on mount.
    page.add_init_script(
        "try { localStorage.setItem('evecapnav.prefs', '<<not-json>>'); } catch {}"
    )
    page.goto(base_url)
    # App should still render the route form.
    expect(page.get_by_role("button", name="Plan Route")).to_be_visible()
