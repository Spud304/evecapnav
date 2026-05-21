"""Dark theme — verify the palette flipped via index.css is actually applied.

We sample the computed background color of `<body>` and the page header.
Both should be dark (RGB sum well under 384, i.e. far from a white #fff
which sums to 765). Specific hex values aren't asserted because Tailwind's
@theme generator may emit slightly different RGB strings; the threshold-
based check still catches a regression to a light palette.
"""

from __future__ import annotations

from playwright.sync_api import Page


def _rgb_sum(rgb: str) -> int:
    """Parse 'rgb(R, G, B)' → R+G+B. Returns 999 on parse failure so a buggy
    test surfaces as a failure rather than passing silently."""
    inside = rgb[rgb.find("(") + 1 : rgb.rfind(")")]
    parts = [p.strip() for p in inside.split(",")[:3]]
    try:
        return sum(int(p) for p in parts)
    except (ValueError, TypeError):
        return 999


def test_body_background_is_dark(page: Page, base_url: str) -> None:
    page.goto(base_url)
    bg = page.evaluate("getComputedStyle(document.body).backgroundColor")
    assert _rgb_sum(bg) < 80, f"body background not dark: {bg}"


def test_text_color_is_light(page: Page, base_url: str) -> None:
    """Body text must contrast against the dark canvas (RGB sum well above 384)."""
    page.goto(base_url)
    fg = page.evaluate("getComputedStyle(document.body).color")
    assert _rgb_sum(fg) > 384, f"body text color not light enough: {fg}"


def test_header_is_dark_paper(page: Page, base_url: str) -> None:
    """The header uses --color-paper (#161b22) which is a few notches lighter
    than the canvas but still dark."""
    page.goto(base_url)
    header_bg = page.evaluate(
        "getComputedStyle(document.querySelector('header')).backgroundColor"
    )
    assert _rgb_sum(header_bg) < 120, f"header bg not dark: {header_bg}"


def test_no_legacy_light_classes_in_dom(page: Page, base_url: str) -> None:
    """Lock in the migration: no stray light-mode Tailwind classes appear on
    rendered elements after planning a route. Regression guard against a
    future edit that accidentally reintroduces them.

    Tailwind arbitrary values (e.g. `bg-[#fafbfc]`) embed `[` `#` `]` in the
    class string, which aren't valid in a CSS class-selector. We scan via a
    JS evaluate that walks className strings as plain text instead.
    """
    from tests.integration.helpers import plan_origin_to_dest

    plan_origin_to_dest(page, base_url)
    found = page.evaluate(
        """
        () => {
          const banned = ['bg-white', 'bg-red-50', 'bg-amber-50',
                          'bg-[#fafbfc]', 'bg-[#f9fafc]', 'bg-[#f6f7f9]'];
          const hits = {};
          for (const el of document.querySelectorAll('*')) {
            const cls = el.getAttribute('class') || '';
            for (const b of banned) {
              if (cls.split(/\\s+/).includes(b)) {
                hits[b] = (hits[b] || 0) + 1;
              }
            }
          }
          return hits;
        }
        """
    )
    assert found == {}, f"Light-mode classes still in DOM: {found}"
