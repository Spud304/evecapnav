import logging

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
    if status != 200 or not data:
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
