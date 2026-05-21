import logging
from datetime import datetime

import requests

from src.constants import ESI_BASE_URL

logger = logging.getLogger(__name__)


def esi_get(url: str) -> tuple[int, dict | list | None]:
    """GET from ESI with timeout. Returns (status_code, json_or_None)."""
    try:
        resp = requests.get(url, timeout=10)
        return resp.status_code, resp.json() if resp.text else None
    except requests.RequestException as e:
        logger.warning("ESI request failed: %s — %s", url, e)
        return 0, None


def fetch_system_kills() -> dict[int, dict]:
    """Fetch system kills from ESI. Returns {system_id: {ship_kills, npc_kills, pod_kills}}."""
    status, data = esi_get(f"{ESI_BASE_URL}/universe/system_kills/")
    if status != 200 or not data:
        logger.warning("Failed to fetch system kills: status=%s", status)
        return {}
    return {
        entry["system_id"]: {
            "ship_kills": entry.get("ship_kills", 0),
            "npc_kills": entry.get("npc_kills", 0),
            "pod_kills": entry.get("pod_kills", 0),
        }
        for entry in data
    }


def fetch_system_jumps() -> dict[int, int]:
    """Fetch system jumps from ESI. Returns {system_id: ship_jumps}."""
    status, data = esi_get(f"{ESI_BASE_URL}/universe/system_jumps/")
    if status != 200 or not data:
        logger.warning("Failed to fetch system jumps: status=%s", status)
        return {}
    return {entry["system_id"]: entry.get("ship_jumps", 0) for entry in data}


def fetch_system_jumps_from_api(api_url: str) -> dict[int, int]:
    """Fetch 24h aggregated system jumps from FastAPI jump history service.

    Calls /api/jumps/history?window=24h and sums all hourly snapshots per system.
    Returns {system_id: total_ship_jumps_over_24h}.
    """
    try:
        resp = requests.get(
            f"{api_url}/api/jumps/history", params={"window": "24h"}, timeout=30
        )
        if resp.status_code != 200:
            logger.warning(
                "Failed to fetch jump history from API: status=%s", resp.status_code
            )
            return {}
        data = resp.json()
        totals: dict[int, int] = {}
        for snapshot in data.get("snapshots", []):
            for sys_id_str, count in snapshot.get("systems", {}).items():
                sid = int(sys_id_str)
                totals[sid] = totals.get(sid, 0) + count
        logger.info(
            "Aggregated 24h jump data: %d systems from %d snapshots",
            len(totals),
            len(data.get("snapshots", [])),
        )
        return totals
    except requests.RequestException as e:
        logger.warning("Jump API history request failed: %s", e)
        return {}


def fetch_weekly_hourly_jumps(api_url: str) -> dict[int, dict]:
    """Fetch a per-system hour-of-day jump profile averaged over the past week.

    Calls /api/jumps/history?window=week (up to 168 hourly snapshots) and
    buckets each snapshot's systems by hour-of-day UTC. Returns:
        {system_id: {
            "pilot_activity": int,   # mean jumps/hour over the whole week
            "hourly_jumps":   [24],  # per-hour means, UTC, index 0=00:00
        }}
    """
    try:
        resp = requests.get(
            f"{api_url}/api/jumps/history", params={"window": "week"}, timeout=60
        )
        if resp.status_code != 200:
            logger.warning(
                "Failed to fetch weekly history from API: status=%s", resp.status_code
            )
            return {}
        snapshots = resp.json().get("snapshots", [])
        if not snapshots:
            return {}

        sums: dict[int, list[int]] = {}
        counts = [0] * 24
        for snap in snapshots:
            try:
                hour = datetime.fromisoformat(snap["timestamp"]).hour
            except (KeyError, ValueError):
                continue
            counts[hour] += 1
            for sid_str, jumps in snap.get("systems", {}).items():
                sid = int(sid_str)
                bucket = sums.setdefault(sid, [0] * 24)
                bucket[hour] += jumps

        result: dict[int, dict] = {}
        for sid, bucket in sums.items():
            hourly = [
                bucket[h] / counts[h] if counts[h] else 0.0 for h in range(24)
            ]
            mean = sum(hourly) / 24
            result[sid] = {
                "pilot_activity": int(round(mean)),
                "hourly_jumps": hourly,
            }
        logger.info(
            "Built weekly hourly profile: %d systems from %d snapshots",
            len(result),
            len(snapshots),
        )
        return result
    except requests.RequestException as e:
        logger.warning("Weekly history request failed: %s", e)
        return {}


# Cap-ship isotope type IDs (SDE marketGroup 1396). All four are returned —
# downstream code picks one (currently Helium) as a pricing proxy until per-
# race fuel-cost accounting is wired up.
FUEL_TYPE_IDS = {
    16274: "Helium Isotopes",
    17887: "Oxygen Isotopes",
    17888: "Nitrogen Isotopes",
    17889: "Hydrogen Isotopes",
}


def fetch_fuel_prices() -> dict[int, float]:
    """Fetch global average prices for cap-ship isotopes from ESI.

    Calls `GET /markets/prices/` (public, no auth). Filters to the four
    capital-ship isotope type_ids. Returns {type_id: average_price_isk}.
    Missing/unparseable types are skipped silently.
    """
    status, data = esi_get(f"{ESI_BASE_URL}/markets/prices/")
    if status != 200 or not isinstance(data, list):
        logger.warning("Failed to fetch fuel prices: status=%s", status)
        return {}
    out: dict[int, float] = {}
    for entry in data:
        tid = entry.get("type_id")
        if tid in FUEL_TYPE_IDS:
            try:
                out[int(tid)] = float(entry.get("average_price", 0))
            except (TypeError, ValueError):
                continue
    logger.info("Fetched fuel prices for %d isotope types", len(out))
    return out


def fetch_sovereignty() -> dict[int, dict]:
    """Fetch sovereignty map. Returns {system_id: {alliance_id, faction_id}}."""
    status, data = esi_get(f"{ESI_BASE_URL}/sovereignty/map/")
    if status != 200 or not data:
        logger.warning("Failed to fetch sovereignty: status=%s", status)
        return {}
    result = {}
    for entry in data:
        result[entry["system_id"]] = {
            "alliance_id": entry.get("alliance_id", 0),
            "faction_id": entry.get("faction_id", 0),
        }
    return result


def fetch_alliance_name(alliance_id: int) -> str:
    """Fetch alliance name by ID."""
    status, data = esi_get(f"{ESI_BASE_URL}/alliances/{alliance_id}/")
    if status != 200 or not isinstance(data, dict):
        return ""
    return data.get("name", "")


def fetch_names_batch(ids: list[int]) -> dict[int, str]:
    """Resolve IDs to names in a single ESI call (up to 1000)."""
    if not ids:
        return {}
    try:
        resp = requests.post(
            f"{ESI_BASE_URL}/universe/names/",
            json=ids[:1000],
            timeout=10,
        )
        if resp.status_code == 200:
            return {entry["id"]: entry["name"] for entry in resp.json()}
        logger.warning("Failed to batch resolve names: status=%s", resp.status_code)
    except requests.RequestException as e:
        logger.warning("Batch name resolve failed: %s", e)
    return {}
