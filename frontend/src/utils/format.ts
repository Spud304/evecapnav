export function formatTime(minutes: number): string {
  if (minutes < 1) return `${Math.round(minutes * 60)}s`;
  if (minutes < 60) return `${Math.round(minutes)}m`;
  const h = Math.floor(minutes / 60);
  const m = Math.round(minutes % 60);
  return `${h}h ${m}m`;
}

/** Parse a human fatigue input into minutes.
 *
 * Accepts (case-insensitive, whitespace-flexible):
 *   - bare number      → minutes  (e.g. "90"     → 90)
 *   - Nm / Nmin        → minutes  ("90m"        → 90)
 *   - Nh               → hours    ("2h"         → 120)
 *   - Nh Mm            → mixed    ("1h 30m"    → 90)
 *   - H:MM             → mixed    ("1:30"      → 90)
 *   - decimal hours    → hours    ("1.5h"      → 90, "1.5" rejected as ambiguous)
 *
 * Returns NaN when the input cannot be parsed unambiguously, so callers
 * can render a validation hint. Always clamps to >= 0.
 */
export function parseFatigueInput(raw: string): number {
  const s = raw.trim().toLowerCase();
  if (!s) return 0;

  // H:MM format.
  const colon = s.match(/^(\d+):(\d{1,2})$/);
  if (colon) {
    const h = parseInt(colon[1], 10);
    const m = parseInt(colon[2], 10);
    if (m >= 60) return NaN;
    return Math.max(0, h * 60 + m);
  }

  // "Nh Mm" / "Nh" / "Nm" / decimal hours.
  const re = /^(?:(\d+(?:\.\d+)?)\s*h)?\s*(?:(\d+)\s*m(?:in)?)?$/;
  if (re.test(s) && s !== '') {
    const m = s.match(re)!;
    const hStr = m[1];
    const mStr = m[2];
    if (!hStr && !mStr) {
      // Falls through to bare-number branch below.
    } else {
      const hours = hStr ? parseFloat(hStr) : 0;
      const mins = mStr ? parseInt(mStr, 10) : 0;
      return Math.max(0, Math.round(hours * 60 + mins));
    }
  }

  // Bare integer → minutes.
  if (/^\d+$/.test(s)) {
    return Math.max(0, parseInt(s, 10));
  }

  return NaN;
}

export function secColor(sec: number): string {
  if (sec >= 0.45) return '#2d7a4a';
  if (sec > 0) return '#b07a14';
  return '#b1382f';
}

/** Map true sec value to its space class.
 *
 * The rules come from CLAUDE.md (verified): hi-sec = stored sec ≥ 0.5;
 * low-sec = 0.0 ≤ sec < 0.5; null-sec = sec < 0. The boundary checks use
 * the raw float; the displayed `(0.0)` / `(-0.0)` UI value rounds, which
 * is why filtering on the rounded value silently drops systems.
 *
 * Wormhole / Pochven aren't distinguishable from a sec number alone;
 * once RouteStep carries `region_id` we can extend this with a `regionId`
 * argument to surface WH and POCH bands.
 */
export function secBand(sec: number): 'HS' | 'LS' | 'NS' {
  if (sec >= 0.5) return 'HS';
  if (sec >= 0) return 'LS';
  return 'NS';
}
