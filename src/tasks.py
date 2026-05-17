import logging
import os

from celery import shared_task

from src.esi import (
    fetch_system_kills,
    fetch_system_jumps,
    fetch_system_jumps_from_api,
    fetch_recent_activity,
)
from src.cache import (
    save_esi_kills,
    save_esi_jumps,
    save_esi_activity,
    load_danger_data,
    mark_esi_updated,
)

logger = logging.getLogger(__name__)


def _instance_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "instance")


def get_danger_data() -> dict[int, dict]:
    """Get the current danger data from the cache DB."""
    return load_danger_data(_instance_path())


@shared_task
def poll_system_stats():
    """Fetch kills and jumps from ESI and save to cache DB."""
    instance = _instance_path()

    kills = fetch_system_kills()
    if kills:
        save_esi_kills(instance, kills)

    source = os.environ.get("JUMP_DATA_SOURCE", "esi")
    if source == "fastapi":
        api_url = os.environ.get("JUMP_API_URL", "http://localhost:8001")
        jumps = fetch_system_jumps_from_api(api_url)
    else:
        jumps = fetch_system_jumps()
    if jumps:
        save_esi_jumps(instance, jumps)

    # Fetch recent pilot activity from historical data if available
    if source == "fastapi":
        api_url = os.environ.get("JUMP_API_URL", "http://localhost:8001")
        activity = fetch_recent_activity(api_url)
        if activity:
            save_esi_activity(instance, activity)

    if kills or jumps:
        mark_esi_updated(instance)
