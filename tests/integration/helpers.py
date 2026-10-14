"""Reusable Playwright interaction helpers for the route-planner FE."""

from __future__ import annotations

import json

from playwright.sync_api import Page, expect, Route


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
    # Result is rendered once the summary card with "Total Hops" shows up.
    page.get_by_text("Total Hops", exact=True).wait_for(state="visible", timeout=10_000)


def route_system_names(page: Page) -> list[str]:
    """Return the system names in the rendered route table, in order.

    Reads the leading TEXT NODE of the bold inner div in the System column.
    Avoids `.font-semibold .inner_text()` because Gate / Dead End pills live
    as `<span>` children of the same div and get concatenated (e.g.
    "ItgSafeADead End"). Pulling node 0 specifically gives the system name
    in isolation and is robust to any pill the FE renders alongside it.
    """
    rows = page.locator("table tbody tr").filter(has=page.locator("td"))
    names: list[str] = []
    for i in range(rows.count()):
        row = rows.nth(i)
        # Skip the alternatives expansion row (colSpan=11, no per-cell content).
        if row.locator("td").count() < 5:
            continue
        cell = row.locator("td").nth(1)
        text = cell.locator(".font-semibold").first.evaluate(
            "el => el.childNodes[0]?.textContent ?? ''"
        )
        names.append(text.strip())
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
) -> None:
    """Open advanced weights, set the given knobs, replan, wait for table.

    The FE doesn't expose activity_weight in the form, so tests that need to
    flip that knob navigate directly with a query-string param via page.goto
    instead.
    """
    open_advanced_weights(page)
    if danger_weight is not None:
        set_weight(page, "Danger weight", danger_weight)
    if jumps_weight is not None:
        set_weight(page, "Jumps weight", jumps_weight)
    plan_route(page)


def plan_origin_to_dest(page: Page, base_url: str) -> None:
    """Navigate, select the canonical ItgOrigin/ItgDest pair, plan, wait."""
    page.goto(base_url)
    select_system(page, "Origin", "ItgOrigin")
    select_system(page, "Destination", "ItgDest")
    plan_route(page)


def plan_through_danger(
    page: Page, base_url: str, *, zero_jumps_weight: bool = False
) -> None:
    """Plan the canonical route via ItgDanger by zeroing danger_weight so the
    planner picks the geometrically shortest branch. Some tests also need
    `jumps_weight=0` (e.g. row-coloring on the `jumps_on_danger` scenario)."""
    page.goto(base_url)
    select_system(page, "Origin", "ItgOrigin")
    select_system(page, "Destination", "ItgDest")
    plan_with_weights(
        page,
        danger_weight=0,
        jumps_weight=0 if zero_jumps_weight else None,
    )


# ---------------------------------------------------------------------------
# Form helpers
# ---------------------------------------------------------------------------


def select_routing_mode(page: Page, mode: str) -> None:
    """Switch the routing-mode dropdown (`safe` / `direct` / `pos`)."""
    sel = page.get_by_text("Routing mode", exact=True).locator("..").locator("select")
    sel.select_option(value=mode)


def set_ship(page: Page, ship_name: str) -> None:
    """Pick a ship by its type name via the typeahead (e.g. 'Archon', 'Rhea').

    Clears the input, types the name, waits for the option to appear, clicks it.
    The picker sets shipClass internally based on the chosen ship's class label.
    """
    inp = page.get_by_test_id("ship-picker-input")
    inp.fill("")
    inp.type(ship_name, delay=20)
    option = page.locator(
        f'[data-testid="ship-picker-option"][data-ship-name="{ship_name}"]'
    ).first
    option.wait_for(state="visible")
    option.click()
    expect(inp).to_have_value(ship_name)


def set_jdc(page: Page, level: int) -> None:
    sel = page.get_by_text("JDC level", exact=True).locator("..").locator("select")
    sel.select_option(value=str(level))


def set_jfc(page: Page, level: int) -> None:
    sel = page.get_by_text("JFC level", exact=True).locator("..").locator("select")
    sel.select_option(value=str(level))


def set_initial_fatigue(page: Page, value: int | str) -> None:
    """Set the Initial Fatigue field via the new text input.

    Accepts either an integer (treated as raw minutes — `60` → "60") or a
    string in any format parseFatigueInput() understands (`"1h 30m"`,
    `"1:30"`, `"90m"`, etc.).
    """
    inp = page.get_by_test_id("initial-fatigue-input")
    inp.fill(str(value))


def set_avoid_alliances(page: Page, value: str) -> None:
    inp = page.get_by_text("Avoid alliances", exact=True).locator("..").locator("input")
    inp.fill(value)


def set_gate_mode(page: Page, mode: str) -> None:
    """Pick a gate-mode dropdown value (`off` / `interregional` / `all`)."""
    sel = page.get_by_text("Stargate hops", exact=True).locator("..").locator("select")
    sel.select_option(value=mode)


def click_reset_weights(page: Page) -> None:
    page.get_by_role("button", name="Reset defaults").click()


# ---------------------------------------------------------------------------
# Route table helpers
# ---------------------------------------------------------------------------


def route_data_rows(page: Page):
    """Return the locator for the data rows of the route table.

    Excludes the alternatives-expansion row (which renders a single colSpan
    cell) by requiring that the row contain at least a 5th `<td>` — the
    Wait column. Using `.nth(4)` matches Playwright's 0-indexed cell access
    elsewhere in this file.
    """
    return page.locator("table tbody tr").filter(has=page.locator("td").nth(4))


def expand_alternatives(page: Page, hop_index: int) -> None:
    """Click the ▸ toggle on a hop's index cell to expand the alternatives panel."""
    row = route_data_rows(page).nth(hop_index)
    row.get_by_title("Show alternative systems").click()
    page.get_by_text("Alternatives reachable from").wait_for(state="visible")


def collapse_alternatives(page: Page, hop_index: int) -> None:
    """Click the toggle a second time to collapse."""
    row = route_data_rows(page).nth(hop_index)
    row.get_by_title("Show alternative systems").click()


# ---------------------------------------------------------------------------
# Summary card
# ---------------------------------------------------------------------------


def read_summary_card(page: Page) -> dict[str, str]:
    """Return the summary cells as `{label: primary_value}`.

    The layout has five labelled cells: Total Hops, Total LY, Fuel,
    Total Wait, and a merged Quietest cell (two lines — jumps and kills).
    The merged cell's two lines are exposed as keys
    ``Quietest · Jumps`` / ``Quietest · Kills`` to keep test assertions
    stable across the merge.
    """
    out: dict[str, str] = {}
    for label in ("Total Hops", "Total LY", "Fuel", "Total Wait", "Risk"):
        cell = page.get_by_text(label, exact=True).locator("..")
        out[label] = cell.locator(".text-\\[18px\\]").first.inner_text().strip()
    # Merged Quietest cell: each line is identified by a data-testid. The
    # cell has two children — a leading text node (the HH–HH window or "—")
    # and a <span> with the "jumps"/"kills" caption. Read just the text node
    # so callers see only the window value.
    for key, testid in (
        ("Quietest · Jumps", "quiet-jumps-line"),
        ("Quietest · Kills", "quiet-kills-line"),
    ):
        text = page.get_by_test_id(testid).evaluate(
            "el => el.childNodes[0]?.textContent?.trim() ?? ''"
        )
        out[key] = text
    return out


# ---------------------------------------------------------------------------
# Threat modal
# ---------------------------------------------------------------------------


def open_threat_modal_for(page: Page, system_name: str) -> None:
    """Click the row's Threat cell to open the modal for a given system.

    Uses the `data-testid="threat-cell"` attribute so the test isn't
    sensitive to the column shifting when the Moons column hides itself in
    non-POS routing modes.
    """
    row = route_data_rows(page).filter(has_text=system_name).first
    row.locator('[data-testid="threat-cell"]').click()
    page.get_by_text("Active PVPers", exact=True).wait_for(state="visible")


def close_threat_modal(page: Page, *, method: str = "button") -> None:
    if method == "button":
        page.get_by_role("button", name="Close").click()
    elif method == "backdrop":
        # The fixed inset-0 div is the backdrop. Click its top-left where the
        # card doesn't sit (1px,1px).
        page.locator("div.fixed.inset-0.z-50").first.click(position={"x": 1, "y": 1})
    else:
        raise ValueError(f"Unknown close method {method!r}")
    page.get_by_text("Active PVPers", exact=True).wait_for(state="hidden")


# ---------------------------------------------------------------------------
# Network-level mocking — used ONLY for response-shape edge cases the real
# backend can't ergonomically produce (missing keys, malformed SSE, etc.).
# ---------------------------------------------------------------------------


def mock_route_response(
    page: Page, *, result: dict, progress: list[str] | None = None
) -> None:
    """Intercept the NEXT /api/route call and return a hand-crafted SSE stream.

    `result` is dumped as the final `event: result` payload. Optional
    `progress` strings are emitted first as `event: progress` events.
    Cleared after one use so a single test can plan multiple times without
    every plan being intercepted.
    """
    state = {"used": False}

    def handler(route: Route) -> None:
        if state["used"]:
            route.continue_()
            return
        state["used"] = True
        chunks: list[str] = []
        for msg in progress or []:
            chunks.append(f"event: progress\ndata: {json.dumps(msg)}\n\n")
        chunks.append(f"event: result\ndata: {json.dumps(result)}\n\n")
        route.fulfill(
            status=200,
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
            },
            body="".join(chunks),
        )

    page.route("**/api/route?**", handler)


def mock_no_route_result(page: Page, *, error_message: str = "No route found") -> None:
    """Emit a result event whose payload is `{error, steps: []}` — the format
    the backend produces when A* finds nothing. This drives App.tsx's
    no-route message branches (gate_mode dependent)."""

    def handler(route: Route) -> None:
        body = (
            f"event: result\ndata: "
            f"{json.dumps({'error': error_message, 'steps': []})}\n\n"
        )
        route.fulfill(
            status=200,
            headers={"Content-Type": "text/event-stream"},
            body=body,
        )

    page.route("**/api/route?**", handler)


def mock_route_error(
    page: Page, *, error_message: str | None, malformed_json: bool = False
) -> None:
    """Intercept /api/route and return an `event: error` SSE payload.

    Set `malformed_json=True` to emit invalid JSON in the data field; the FE
    should fall back to the generic "Unknown error" message
    (frontend/src/api.ts onError handler).
    """

    def handler(route: Route) -> None:
        if malformed_json:
            body = "event: error\ndata: not-json-payload\n\n"
        else:
            body = f"event: error\ndata: {json.dumps({'error': error_message})}\n\n"
        route.fulfill(
            status=200,
            headers={"Content-Type": "text/event-stream"},
            body=body,
        )

    page.route("**/api/route?**", handler)


def mock_route_abort(page: Page) -> None:
    """Abort the next /api/route request — used to drive the 'Connection lost'
    error branch in api.ts when EventSource itself errors out."""

    def handler(route: Route) -> None:
        route.abort("failed")

    page.route("**/api/route?**", handler)


def mock_swap_response(page: Page, *, payload: dict) -> None:
    """Intercept the next /api/route/swap call and return a JSON body."""
    state = {"used": False}

    def handler(route: Route) -> None:
        if state["used"]:
            route.continue_()
            return
        state["used"] = True
        route.fulfill(
            status=200,
            headers={"Content-Type": "application/json"},
            body=json.dumps(payload),
        )

    page.route("**/api/route/swap?**", handler)


def mock_swap_abort(page: Page) -> None:
    def handler(route: Route) -> None:
        route.abort("failed")

    page.route("**/api/route/swap?**", handler)


# ---------------------------------------------------------------------------
# Clipboard / window helpers
# ---------------------------------------------------------------------------


def read_clipboard(page: Page) -> str:
    return page.evaluate("navigator.clipboard.readText()")


# ---------------------------------------------------------------------------
# Mock-payload builders. Shared by tests that drive /api/route via page.route
# so they don't each duplicate the 17-field step dict.
# ---------------------------------------------------------------------------


def step_dict(**overrides) -> dict:
    """Default RouteStep payload; overrides win.

    Every field the FE reads is included so a test can mutate exactly one
    without crashing the table on a missing key.
    """
    return {
        "system_id": 0,
        "system_name": "",
        "security": 0.0,
        "distance_ly": 0,
        "wait_minutes": 0,
        "fatigue_after_minutes": 0,
        "fuel_cost": 0,
        "kills_per_hour": 0,
        "jumps_per_hour": 0,
        "hourly_jumps": [],
        "wait_cooldown_minutes": 0,
        "wait_decay_minutes": 0,
        "safe_spot_au": 10,
        "safe_spot_warp": "",
        "safe_spot_nearest": "",
        "moon_count": 0,
        "gate_count": 1,
        "sov_owner": "",
        "edge_type": "",
        **overrides,
    }


def two_hop_result(**top_overrides) -> dict:
    """Canonical ItgOrigin → ItgDest result payload used by response-shape and
    progress/loading tests. Top-level overrides win."""
    base: dict = {
        "steps": [
            step_dict(system_id=90000001, system_name="ItgOrigin", security=-0.5),
            step_dict(
                system_id=90000004,
                system_name="ItgDest",
                security=-0.6,
                distance_ly=5,
                wait_minutes=6,
                fatigue_after_minutes=294,
                fuel_cost=5000,
                edge_type="jump",
            ),
        ],
        "total_jumps": 1,
        "total_fuel": 5000,
        "total_wait_minutes": 6.0,
        "alternatives": {},
        "zkill": {},
        "quiet_hours": {"start": 4, "end": 8},
        "quiet_jumps": {"start": 23, "end": 3, "hourly": [0.0] * 24},
    }
    base.update(top_overrides)
    return base


def install_window_open_recorder(page: Page) -> None:
    """Patch window.open so we can read what URL the FE tried to open without
    actually spawning a new tab. Records the most recent URL on
    `window.__lastOpenUrl`."""
    page.add_init_script(
        "window.__lastOpenUrl = null; "
        "window.open = (url, target) => { window.__lastOpenUrl = url; return null; };"
    )


def last_opened_url(page: Page) -> str | None:
    return page.evaluate("window.__lastOpenUrl")
