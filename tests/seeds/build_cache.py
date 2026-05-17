"""Write a fresh `cache.sqlite` for a named scenario from `scenarios.py`.

The build path is always equal to `<instance_path>/cache.sqlite`. We use
`src.cache` helpers directly so any future schema change in cache.py
automatically applies here too.
"""

import os
import sqlite3

from src.cache import (
    _init_cache_db,
    _cache_path,
    save_esi_kills,
    save_esi_jumps,
    save_esi_activity,
    save_zkill_stats,
    mark_esi_updated,
    _invalidate_danger_cache,
)

from tests.seeds.scenarios import SCENARIOS


def build_seed_cache(instance_path: str, scenario_name: str) -> None:
    """Truncate any existing cache.sqlite tables and write a fresh scenario.

    Always invalidates the in-process danger cache so the next
    `load_danger_data()` call re-reads from disk.
    """
    if scenario_name not in SCENARIOS:
        raise ValueError(
            f"Unknown scenario {scenario_name!r}. Known: {sorted(SCENARIOS)}"
        )

    os.makedirs(instance_path, exist_ok=True)
    path = _cache_path(instance_path)
    _init_cache_db(path)

    # Clear ESI / zkill rows from any previous scenario before writing the new one.
    # safe_spots is intentionally preserved — it is precomputed at app init and
    # threat scenarios don't touch celestial geometry.
    conn = sqlite3.connect(path)
    for table in ("esi_kills", "esi_jumps", "esi_activity", "zkill_stats"):
        conn.execute(f"DELETE FROM {table}")  # noqa: S608 — table names are fixed literals
    conn.commit()
    conn.close()

    scenario = SCENARIOS[scenario_name]

    if scenario["kills"]:
        save_esi_kills(instance_path, scenario["kills"])
    if scenario["jumps"]:
        save_esi_jumps(instance_path, scenario["jumps"])
    if scenario["activity"]:
        save_esi_activity(instance_path, scenario["activity"])
    for sid, z in scenario["zkill"].items():
        save_zkill_stats(
            instance_path,
            sid,
            z["hourly"],
            {
                "active_characters": z["active_characters"],
                "active_corps": z["active_corps"],
                "gang_ratio": z["gang_ratio"],
                "ships_destroyed": z["ships_destroyed"],
            },
        )

    mark_esi_updated(instance_path)
    _invalidate_danger_cache()
