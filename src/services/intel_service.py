"""Threat-intel service — wraps zKill + ESI threat aggregation.

Owns the per-system zkill fetch+cache and the quiet-hours computation.
"""

import logging

from src.clients.zkill_client import (
    extract_activity,
    extract_threat_summary,
    fetch_system_stats,
    find_quiet_hours,
)
from src.stores.intel_cache_store import (
    load_danger_data,
    load_zkill_stats,
    save_zkill_stats,
)

logger = logging.getLogger(__name__)


class IntelService:
    def __init__(self, instance_path: str) -> None:
        self.instance_path = instance_path

    def fetch_route_zkill(
        self, system_ids: list[int]
    ) -> tuple[dict[int, dict], list[int]]:
        """For each system on a route, load cached zkill stats or fetch
        fresh from zKill. Returns (per-system stats dict, aggregated
        24-hour activity histogram across the whole route).
        """
        zkill_data: dict[int, dict] = {}
        aggregate_hourly = [0] * 24
        for sid in system_ids:
            cached = load_zkill_stats(self.instance_path, sid)
            if cached:
                zkill_data[sid] = cached
            else:
                stats = fetch_system_stats(sid)
                if stats:
                    hourly = extract_activity(stats)
                    threat = extract_threat_summary(stats)
                    zkill_data[sid] = {
                        "hourly_activity": hourly,
                        **threat,
                    }
                    save_zkill_stats(self.instance_path, sid, hourly, threat)

            if sid in zkill_data:
                hourly_act = zkill_data[sid].get("hourly_activity", [0] * 24)
                for h in range(24):
                    aggregate_hourly[h] += hourly_act[h]
        return zkill_data, aggregate_hourly

    @staticmethod
    def compute_quiet_hours(aggregate_hourly: list[int]) -> tuple[int, int]:
        return find_quiet_hours(aggregate_hourly)

    def get_danger_data(self) -> dict[int, dict]:
        """Cached ESI kills/jumps/activity per system."""
        return load_danger_data(self.instance_path)
