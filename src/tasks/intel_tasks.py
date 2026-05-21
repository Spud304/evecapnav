"""Celery background tasks for ESI intel polling."""

import logging
import os

from celery import shared_task

from src.clients.esi_client import (
    fetch_fuel_prices,
    fetch_system_jumps,
    fetch_system_jumps_from_api,
    fetch_system_kills,
    fetch_weekly_hourly_jumps,
)
from src.stores.intel_cache_store import (
    load_danger_data,
    mark_esi_updated,
    save_esi_activity,
    save_esi_jumps,
    save_esi_kills,
    save_fuel_prices,
)

logger = logging.getLogger(__name__)


def _instance_path() -> str:
    override = os.environ.get("EVECAPNAV_INSTANCE_PATH")
    if override:
        return override
    # We're under src/tasks/intel_tasks.py — go up two dirs to reach src/.
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "instance"
    )


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

    if source == "fastapi":
        api_url = os.environ.get("JUMP_API_URL", "http://localhost:8001")
        activity = fetch_weekly_hourly_jumps(api_url)
        if activity:
            save_esi_activity(instance, activity)

    # Fuel-cost-in-ISK pricing — hourly is plenty fresh for an isk/fuel cell
    # that pilots only glance at when planning a route.
    prices = fetch_fuel_prices()
    if prices:
        save_fuel_prices(instance, prices)

    if kills or jumps:
        mark_esi_updated(instance)
