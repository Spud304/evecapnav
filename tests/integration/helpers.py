"""Reusable Playwright interaction helpers for the route-planner FE."""

from __future__ import annotations

from playwright.sync_api import Page, expect


def select_system(page: Page, label: str, system_name: str) -> None:
    """Type into the Origin / Destination search and click the matching result.

    SystemSearch debounces input by 300ms before firing the request, so we wait
    for the dropdown row to appear rather than racing the API call.
    """
    field = page.get_by_text(label, exact=True).locator("..").locator("input")
    field.fill("")
    field.type(system_name, delay=20)
    page.get_by_text(system_name, exact=False).first.wait_for(state="visible")
    # The dropdown row is the second occurrence (first is the label echo in the
    # input). Click any dropdown <div> that contains the full name.
    page.locator(f"div.cursor-pointer:has-text('{system_name}')").first.click()


def plan_route(page: Page) -> None:
    """Click the Plan Route button and wait for the result table to render."""
    page.get_by_role("button", name="Plan Route").click()
    # Result is rendered once the summary card with "Total Jumps" shows up.
    page.get_by_text("Total Jumps", exact=True).wait_for(
        state="visible", timeout=10_000
    )


def route_system_names(page: Page) -> list[str]:
    """Return the system names in the rendered route table, in order.

    Reads the first `<td>` of the System column (which contains the bold name)
    rather than relying on a data attribute on the row — keeps us decoupled
    from purely visual markup changes.
    """
    rows = page.locator("table tbody tr").filter(has=page.locator("td"))
    names: list[str] = []
    for i in range(rows.count()):
        row = rows.nth(i)
        # Skip the alternatives expansion row (colSpan=11, no per-cell content).
        if row.locator("td").count() < 5:
            continue
        # Column 2 is "System"; the bold inner div holds the name (and a possible
        # pill). The name is always the first text node — take it via inner_text
        # and strip pills.
        cell = row.locator("td").nth(1)
        text = cell.locator(".font-semibold").first.inner_text().strip()
        # Strip any trailing pill text like "Gate" / "Dead End"
        text = text.split("\n", 1)[0].strip()
        names.append(text)
    return names


def open_advanced_weights(page: Page) -> None:
    """Expand the 'Advanced cost weights' section if collapsed."""
    toggle = page.get_by_text("Advanced cost weights")
    if "▸" in toggle.inner_text():
        toggle.click()
        # The danger weight input is rendered once expanded; wait for it.
        page.get_by_text("Danger weight").wait_for(state="visible")


def set_weight(page: Page, label: str, value: int | float) -> None:
    """Set the value of an advanced-cost-weights numeric input by its label."""
    field = page.get_by_text(label, exact=True).locator("..").locator("input")
    field.fill(str(value))
    expect(field).to_have_value(str(value))


def plan_with_weights(
    page: Page,
    *,
    danger_weight: int | None = None,
    jumps_weight: int | None = None,
    activity_weight: int | None = None,
) -> None:
    """Open advanced weights, set the given knobs, replan, wait for table.

    `activity_weight` is included for symmetry — the FE does not currently
    expose an activity-weight input, so when callers pass it we set the
    danger/jumps inputs and rely on the URL fallback (see test_threat_weighting
    notes). Today this argument is unused; tests use `page.goto` with a query
    param for the activity case instead.
    """
    open_advanced_weights(page)
    if danger_weight is not None:
        set_weight(page, "Danger weight", danger_weight)
    if jumps_weight is not None:
        set_weight(page, "Jumps weight", jumps_weight)
    plan_route(page)
