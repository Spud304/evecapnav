"""File-based cache for computed data (SDE-derived and ESI-derived)."""

import logging
import os
import sqlite3
import time
from datetime import datetime, timezone

from src.systems import SafeSpotResult

logger = logging.getLogger(__name__)

_initialized_paths: set[str] = set()

# In-memory danger data cache (refreshed hourly, no need to hit SQLite per request)
_danger_cache: dict[int, dict] = {}
_danger_cache_time: float = 0.0
_DANGER_CACHE_TTL = 300  # 5 minutes


def _cache_path(instance_path: str) -> str:
    return os.path.join(instance_path, "cache.sqlite")


def _init_cache_db(path: str) -> None:
    if path in _initialized_paths:
        return
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS safe_spots (
            system_id INTEGER PRIMARY KEY,
            nearest_au REAL,
            warp_between TEXT,
            nearest_label TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS esi_kills (
            system_id INTEGER PRIMARY KEY,
            ship_kills INTEGER DEFAULT 0,
            npc_kills INTEGER DEFAULT 0,
            pod_kills INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS esi_jumps (
            system_id INTEGER PRIMARY KEY,
            ship_jumps INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS esi_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS esi_sovereignty (
            system_id INTEGER PRIMARY KEY,
            alliance_id INTEGER DEFAULT 0,
            alliance_name TEXT DEFAULT '',
            faction_id INTEGER DEFAULT 0,
            faction_name TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS esi_activity (
            system_id INTEGER PRIMARY KEY,
            pilot_activity INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS zkill_stats (
            system_id INTEGER PRIMARY KEY,
            hourly_activity TEXT DEFAULT '[]',
            active_characters INTEGER DEFAULT 0,
            active_corps INTEGER DEFAULT 0,
            gang_ratio TEXT DEFAULT '0%',
            ships_destroyed INTEGER DEFAULT 0,
            cached_at TEXT
        )
    """)
    conn.commit()
    conn.close()
    _initialized_paths.add(path)


def load_cached_safe_spots(instance_path: str) -> dict[int, SafeSpotResult] | None:
    """Load safe spots from cache. Returns None if cache is empty."""
    path = _cache_path(instance_path)
    if not os.path.exists(path):
        return None

    _init_cache_db(path)
    conn = sqlite3.connect(path)
    rows = conn.execute(
        "SELECT system_id, nearest_au, warp_between, nearest_label FROM safe_spots"
    ).fetchall()
    conn.close()

    if not rows:
        return None

    logger.info("Loaded %d safe spots from cache", len(rows))
    return {
        row[0]: SafeSpotResult(
            nearest_au=row[1],
            warp_between=row[2],
            nearest_label=row[3],
        )
        for row in rows
    }


def save_cached_safe_spots(
    instance_path: str, scores: dict[int, SafeSpotResult]
) -> None:
    """Save safe spots to cache."""
    path = _cache_path(instance_path)
    _init_cache_db(path)

    conn = sqlite3.connect(path)
    conn.executemany(
        "INSERT OR REPLACE INTO safe_spots (system_id, nearest_au, warp_between, nearest_label) VALUES (?, ?, ?, ?)",
        [
            (sid, r.nearest_au, r.warp_between, r.nearest_label)
            for sid, r in scores.items()
        ],
    )
    conn.commit()
    conn.close()
    logger.info("Saved %d safe spots to cache", len(scores))


def _set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO esi_meta (key, value) VALUES (?, ?)",
        (key, value),
    )


def _get_meta(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM esi_meta WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def _save_esi_table(
    instance_path: str,
    table: str,
    columns: str,
    placeholders: str,
    rows: list[tuple],
) -> None:
    """Generic save for ESI tables with exclusive transaction."""
    if not rows:
        return

    path = _cache_path(instance_path)
    _init_cache_db(path)
    conn = sqlite3.connect(path)
    conn.execute("BEGIN EXCLUSIVE")
    try:
        conn.execute(f"DELETE FROM {table}")  # noqa: S608
        conn.executemany(
            f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", rows
        )  # noqa: S608
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    logger.info("Saved %d rows to %s", len(rows), table)


def mark_esi_updated(instance_path: str) -> None:
    """Mark the ESI cache as freshly updated. Call after all saves succeed."""
    path = _cache_path(instance_path)
    _init_cache_db(path)
    conn = sqlite3.connect(path)
    _set_meta(conn, "esi_updated_at", datetime.now(timezone.utc).isoformat())
    conn.commit()
    conn.close()


def save_esi_kills(instance_path: str, kills: dict[int, dict]) -> None:
    _save_esi_table(
        instance_path,
        "esi_kills",
        "system_id, ship_kills, npc_kills, pod_kills",
        "?, ?, ?, ?",
        [
            (sid, d.get("ship_kills", 0), d.get("npc_kills", 0), d.get("pod_kills", 0))
            for sid, d in kills.items()
        ],
    )
    _invalidate_danger_cache()


def save_esi_jumps(instance_path: str, jumps: dict[int, int]) -> None:
    _save_esi_table(
        instance_path,
        "esi_jumps",
        "system_id, ship_jumps",
        "?, ?",
        list(jumps.items()),
    )
    _invalidate_danger_cache()


def save_esi_activity(instance_path: str, activity: dict[int, int]) -> None:
    """Save recent pilot activity data."""
    _save_esi_table(
        instance_path,
        "esi_activity",
        "system_id, pilot_activity",
        "?, ?",
        list(activity.items()),
    )
    _invalidate_danger_cache()


def save_sovereignty(
    instance_path: str, sov_data: list[tuple[int, int, str, int, str]]
) -> None:
    """Save sovereignty data: [(system_id, alliance_id, alliance_name, faction_id, faction_name)]."""
    _save_esi_table(
        instance_path,
        "esi_sovereignty",
        "system_id, alliance_id, alliance_name, faction_id, faction_name",
        "?, ?, ?, ?, ?",
        sov_data,
    )


def load_sovereignty(instance_path: str) -> dict[int, dict]:
    """Load sovereignty data. Returns {system_id: {alliance_id, alliance_name, faction_id, faction_name}}."""
    path = _cache_path(instance_path)
    if not os.path.exists(path):
        return {}
    _init_cache_db(path)
    conn = sqlite3.connect(path)
    rows = conn.execute(
        "SELECT system_id, alliance_id, alliance_name, faction_id, faction_name FROM esi_sovereignty"
    ).fetchall()
    conn.close()
    return {
        row[0]: {
            "alliance_id": row[1],
            "alliance_name": row[2],
            "faction_id": row[3],
            "faction_name": row[4],
        }
        for row in rows
    }


def save_zkill_stats(
    instance_path: str, system_id: int, hourly: list[int], threat: dict
) -> None:
    """Save zkill stats for a single system."""
    import json as json_mod

    path = _cache_path(instance_path)
    _init_cache_db(path)
    conn = sqlite3.connect(path)
    conn.execute(
        "INSERT OR REPLACE INTO zkill_stats "
        "(system_id, hourly_activity, active_characters, active_corps, gang_ratio, ships_destroyed, cached_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            system_id,
            json_mod.dumps(hourly),
            threat.get("active_characters", 0),
            threat.get("active_corps", 0),
            threat.get("gang_ratio", "0%"),
            threat.get("ships_destroyed", 0),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def load_zkill_stats(
    instance_path: str, system_id: int, max_age_hours: int = 24
) -> dict | None:
    """Load cached zkill stats for a system. Returns None if stale or missing."""
    import json as json_mod

    path = _cache_path(instance_path)
    if not os.path.exists(path):
        return None
    _init_cache_db(path)
    conn = sqlite3.connect(path)
    row = conn.execute(
        "SELECT hourly_activity, active_characters, active_corps, gang_ratio, ships_destroyed, cached_at "
        "FROM zkill_stats WHERE system_id = ?",
        (system_id,),
    ).fetchone()
    conn.close()

    if not row:
        return None

    cached_at = datetime.fromisoformat(row[5])
    age_hours = (datetime.now(timezone.utc) - cached_at).total_seconds() / 3600
    if age_hours > max_age_hours:
        return None

    return {
        "hourly_activity": json_mod.loads(row[0]),
        "active_characters": row[1],
        "active_corps": row[2],
        "gang_ratio": row[3],
        "ships_destroyed": row[4],
    }


def is_esi_cache_stale(instance_path: str, max_age_seconds: int = 3600) -> bool:
    """Check if ESI cache is older than max_age_seconds (default 1 hour)."""
    path = _cache_path(instance_path)
    if not os.path.exists(path):
        return True
    _init_cache_db(path)
    conn = sqlite3.connect(path)
    ts = _get_meta(conn, "esi_updated_at")
    conn.close()

    if not ts:
        return True

    updated = datetime.fromisoformat(ts)
    age = (datetime.now(timezone.utc) - updated).total_seconds()
    logger.info("ESI cache age: %.0f seconds", age)
    return age > max_age_seconds


def _invalidate_danger_cache() -> None:
    global _danger_cache_time
    _danger_cache_time = 0.0


def load_danger_data(instance_path: str) -> dict[int, dict]:
    """Load combined kills + jumps. Cached in-memory for 5 minutes."""
    global _danger_cache, _danger_cache_time

    now = time.monotonic()
    if _danger_cache and (now - _danger_cache_time) < _DANGER_CACHE_TTL:
        return _danger_cache

    path = _cache_path(instance_path)
    if not os.path.exists(path):
        return {}
    _init_cache_db(path)
    conn = sqlite3.connect(path)

    result: dict[int, dict] = {}
    for row in conn.execute(
        "SELECT system_id, ship_kills, npc_kills, pod_kills FROM esi_kills"
    ):
        result[row[0]] = {
            "ship_kills": row[1],
            "npc_kills": row[2],
            "pod_kills": row[3],
            "ship_jumps": 0,
            "pilot_activity": 0,
        }
    for row in conn.execute("SELECT system_id, ship_jumps FROM esi_jumps"):
        if row[0] in result:
            result[row[0]]["ship_jumps"] = row[1]
        else:
            result[row[0]] = {
                "ship_kills": 0,
                "npc_kills": 0,
                "pod_kills": 0,
                "ship_jumps": row[1],
                "pilot_activity": 0,
            }
    # Load historical pilot activity if available
    try:
        for row in conn.execute("SELECT system_id, pilot_activity FROM esi_activity"):
            if row[0] in result:
                result[row[0]]["pilot_activity"] = row[1]
            else:
                result[row[0]] = {
                    "ship_kills": 0,
                    "npc_kills": 0,
                    "pod_kills": 0,
                    "ship_jumps": 0,
                    "pilot_activity": row[1],
                }
    except sqlite3.OperationalError:
        pass  # Table may not exist yet on first run
    conn.close()

    _danger_cache = result
    _danger_cache_time = now
    return result
