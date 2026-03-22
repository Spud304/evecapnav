"""zKillboard API client with rate limiting and caching."""

import logging
import time

import requests

logger = logging.getLogger(__name__)

ZKILL_BASE = "https://zkillboard.com/api"
ZKILL_USER_AGENT = "evecapnav https://github.com/evecapnav maintainer@evecapnav.dev"
_last_request_time = 0.0
_MIN_INTERVAL = 1.0  # seconds between requests


def _rate_limit() -> None:
    """Ensure at least _MIN_INTERVAL seconds between zkill requests."""
    global _last_request_time
    now = time.monotonic()
    elapsed = now - _last_request_time
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    _last_request_time = time.monotonic()


def zkill_get(url: str) -> dict | list | None:
    """GET from zKillboard with rate limiting and User-Agent."""
    _rate_limit()
    try:
        resp = requests.get(
            url,
            headers={
                "User-Agent": ZKILL_USER_AGENT,
                "Accept-Encoding": "gzip",
            },
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json()
        logger.warning("zKill request failed: %s — status %s", url, resp.status_code)
        return None
    except requests.RequestException as e:
        logger.warning("zKill request error: %s — %s", url, e)
        return None


def fetch_system_stats(system_id: int) -> dict | None:
    """Fetch zKillboard stats for a system.

    Returns the full stats dict including 'activity', 'activepvp',
    'gangRatio', etc. Returns None on failure.
    """
    return zkill_get(f"{ZKILL_BASE}/stats/solarSystemID/{system_id}/")


def extract_activity(stats: dict) -> list[int]:
    """Extract aggregated hourly activity (24 values) from zkill stats.

    Sums across all days of the week to get total kills per hour-of-day.
    """
    activity = stats.get("activity", {})
    hourly = [0] * 24
    for day_key in range(7):
        day_data = activity.get(str(day_key), {})
        if isinstance(day_data, dict):
            for hour_str, count in day_data.items():
                hour = int(hour_str)
                if 0 <= hour < 24:
                    hourly[hour] += count
        elif isinstance(day_data, list):
            for hour in range(min(24, len(day_data))):
                hourly[hour] += day_data[hour]
    return hourly


def extract_threat_summary(stats: dict) -> dict:
    """Extract threat summary from zkill stats."""
    active_pvp = stats.get("activepvp", {})
    return {
        "active_characters": active_pvp.get("characters", {}).get("count", 0),
        "active_corps": active_pvp.get("corporations", {}).get("count", 0),
        "gang_ratio": stats.get("gangRatio", "0%"),
        "ships_destroyed": stats.get("shipsDestroyed", 0),
    }


def find_quiet_hours(hourly_totals: list[int], window_size: int = 4) -> tuple[int, int]:
    """Find the quietest N-hour window in a 24-hour cycle.

    Returns (start_hour, end_hour) UTC.
    """
    if not hourly_totals or len(hourly_totals) < 24:
        return 0, window_size

    best_start = 0
    best_sum = float("inf")
    for start in range(24):
        total = sum(hourly_totals[(start + h) % 24] for h in range(window_size))
        if total < best_sum:
            best_sum = total
            best_start = start

    return best_start, (best_start + window_size) % 24
