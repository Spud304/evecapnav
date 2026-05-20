"""Edge cost helpers shared by the multi-label and single-criterion searches.

Pure functions — no logging, no I/O.
"""

import math

from src.constants import MAX_COOLDOWN_MINUTES, MAX_FATIGUE_MINUTES, METERS_PER_LY
from src.schemas.system import SystemInfo
from src.pathfinder.types import Vertex


def compute_distance_ly(
    x1: float, y1: float, z1: float, x2: float, y2: float, z2: float
) -> float:
    """Euclidean distance between two points in meters, converted to LY."""
    dx = x2 - x1
    dy = y2 - y1
    dz = z2 - z1
    return math.sqrt(dx * dx + dy * dy + dz * dz) / METERS_PER_LY


def compute_fatigue(
    current_fatigue_min: float,
    distance_ly: float,
    fatigue_multiplier: float,
    extra_wait_min: float = 0.0,
) -> tuple[float, float]:
    """Compute new fatigue and total wait after a jump.

    All values in minutes.
    Returns (fatigue_after_waiting, total_wait_minutes).

    EVE formulas (post-March-2018):
      cooldown = min(30, max(fatigue/10, 1 + ly * fatigue_multiplier))   # red timer caps at 30 min
      new_fatigue = min(300, max(fatigue, 10) * (1 + ly * fatigue_multiplier))  # blue timer caps at 5 h
      fatigue decays 1:1 with real time during the wait period
    """
    factor = distance_ly * fatigue_multiplier
    cooldown = min(MAX_COOLDOWN_MINUTES, max(current_fatigue_min / 10.0, 1.0 + factor))
    raw_fatigue = min(
        MAX_FATIGUE_MINUTES, max(current_fatigue_min, 10.0) * (1.0 + factor)
    )
    total_wait = cooldown + extra_wait_min
    fatigue_after = max(0.0, raw_fatigue - total_wait)
    return fatigue_after, total_wait


def compute_fuel_cost(
    distance_ly: float, fuel_per_ly: float, jfc_level: int = 0
) -> int:
    """Compute isotope fuel cost for a jump."""
    return math.ceil(distance_ly * fuel_per_ly * (1.0 - 0.10 * jfc_level))


def _danger_cost(
    neighbor: SystemInfo,
    sys_danger: dict,
    mode: str,
    base_system_cost: int,
    danger_weight: int,
    jumps_weight: int,
    activity_weight: int,
    dead_end_penalty: int,
    pos_moon_bonus: int,
) -> float:
    """Per-system safety/danger cost. Matches the formula used by
    `_find_route_single_criterion` so multi-label and single-criterion
    stay comparable.
    """
    if mode == "direct":
        return 0.0
    cost = (
        base_system_cost
        + sys_danger.get("ship_kills", 0) * danger_weight
        + sys_danger.get("ship_jumps", 0) * jumps_weight
        + sys_danger.get("pilot_activity", 0) * activity_weight
    )
    if mode == "pos":
        cost -= neighbor.moon_count * pos_moon_bonus
    if mode == "safe" and neighbor.gate_count == 1:
        # Dead-end systems are camp-prone (one entry/exit means hostiles
        # only need to watch one gate). Penalize them in safe mode.
        cost += dead_end_penalty
    return max(0.0, cost)


def _path_contains(v: Vertex | None, sys_id: int) -> bool:
    """Walk the parent chain to check whether sys_id is on the path so far.
    Cap routes are ~5-30 hops, so this stays cheap.
    """
    while v is not None:
        if v.sys_id == sys_id:
            return True
        v = v.parent
    return False
