/**
 * Lightweight localStorage wrapper for the route-form preferences.
 *
 * Single key `evecapnav.prefs` holds a JSON-encoded {@link RoutePrefs}.
 * All operations are wrapped in try/catch — a thrown SecurityError (private
 * browsing) or QuotaExceededError must NOT break the form.
 */

const KEY = 'evecapnav.prefs';

export interface RoutePrefs {
  originId?: number;
  originName?: string;
  destId?: number;
  destName?: string;
  shipName?: string;
  shipClass?: string;
  jdc?: number;
  jfc?: number;
  jfSkill?: number;
  initialFatigue?: number;
  mode?: 'safe' | 'direct' | 'pos';
  gateMode?: 'off' | 'interregional' | 'all';
  waitWeight?: number;
}

export function loadPrefs(): RoutePrefs {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return typeof parsed === 'object' && parsed !== null ? parsed : {};
  } catch {
    return {};
  }
}

export function savePrefs(prefs: RoutePrefs): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(prefs));
  } catch {
    /* private browsing / quota — drop silently */
  }
}

export function clearPrefs(): void {
  try {
    localStorage.removeItem(KEY);
  } catch {
    /* same */
  }
}
