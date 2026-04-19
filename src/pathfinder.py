import heapq
import logging
import math
from dataclasses import dataclass, asdict
from typing import Callable

from src.constants import (
    MAX_FATIGUE_MINUTES,
    BASE_SYSTEM_COST,
    DISTANCE_EXPONENT,
    DANGER_WEIGHT,
    JUMPS_WEIGHT,
    POS_MOON_BONUS,
    DEAD_END_BONUS,
)
from src.systems import SystemInfo, compute_distance_ly

logger = logging.getLogger(__name__)


@dataclass
class RouteStep:
    system_id: int
    system_name: str
    security: float
    distance_ly: float
    wait_minutes: float
    fatigue_after_minutes: float
    fuel_cost: int
    kills_per_hour: int
    jumps_per_hour: int
    safe_spot_au: float
    safe_spot_warp: str
    safe_spot_nearest: str
    moon_count: int
    gate_count: int
    sov_owner: str

    def to_dict(self) -> dict:
        return asdict(self)


def compute_fatigue(
    current_fatigue_min: float,
    distance_ly: float,
    fatigue_multiplier: float,
    extra_wait_min: float = 0.0,
) -> tuple[float, float]:
    """Compute new fatigue and total wait after a jump.

    All values in minutes.
    Returns (fatigue_after_waiting, total_wait_minutes).

    EVE formulas:
      cooldown = max(fatigue/10, 1 + ly * fatigue_multiplier)
      new_fatigue = min(43200, max(fatigue, 10) * (1 + ly * fatigue_multiplier))
      fatigue decays 1:1 with real time during the wait period
    """
    factor = distance_ly * fatigue_multiplier
    cooldown = max(current_fatigue_min / 10.0, 1.0 + factor)
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


def find_route(
    origin_id: int,
    dest_id: int,
    systems: dict[int, SystemInfo],
    graph: dict[int, list[tuple[int, float]]],
    base_range_ly: float,
    jdc_level: int,
    fatigue_multiplier: float,
    fuel_per_ly: float,
    initial_fatigue_min: float = 0.0,
    jfc_level: int = 0,
    danger_data: dict[int, dict] | None = None,
    on_progress: Callable[[str], None] | None = None,
    mode: str = "safe",
    avoid_alliances: set[str] | None = None,
    exclude_systems: set[int] | None = None,
    base_system_cost: int = BASE_SYSTEM_COST,
    distance_exponent: float = DISTANCE_EXPONENT,
    danger_weight: int = DANGER_WEIGHT,
    jumps_weight: int = JUMPS_WEIGHT,
    dead_end_bonus: int = DEAD_END_BONUS,
    pos_moon_bonus: int = POS_MOON_BONUS,
) -> list[RouteStep]:
    """A* search to find optimal jump route, then simulate fatigue.

    State is system_id only (no fatigue tracking in search).
    Distance is raised to distance_exponent (default 1.5) so the algorithm
    penalizes long jumps proportionally to their fatigue impact.
    Modes:
      - "safe": cost = dist^exp + danger penalty (avoids kills/traffic)
      - "direct": cost = dist^exp only (shortest path with fatigue awareness)
      - "pos": cost = dist^exp + danger - moon bonus (prefers moon-rich systems)
    Fatigue is simulated on the found path afterward.
    """
    if origin_id not in systems or dest_id not in systems:
        return []

    effective_range = base_range_ly * (1 + 0.20 * jdc_level)
    danger = danger_data or {}
    avoid = avoid_alliances or set()
    excluded = exclude_systems or set()
    dest = systems[dest_id]

    def _progress(msg: str) -> None:
        if on_progress:
            on_progress(msg)

    _progress(f"Computing route ({effective_range:.1f} LY range)...")

    # Heuristic: straight-line distance in LY
    def heuristic(sys_id: int) -> float:
        s = systems[sys_id]
        return compute_distance_ly(s.x, s.y, s.z, dest.x, dest.y, dest.z)

    # A* with state = system_id only
    # (est_total, cost_so_far, system_id)
    open_set: list[tuple[float, float, int]] = []
    heapq.heappush(open_set, (heuristic(origin_id), 0.0, origin_id))

    best_cost: dict[int, float] = {origin_id: 0.0}
    came_from: dict[int, int | None] = {origin_id: None}

    explored = 0
    while open_set:
        est_total, cost_so_far, sys_id = heapq.heappop(open_set)

        if sys_id == dest_id:
            _progress(f"Path found! Explored {explored} systems.")
            path = _reconstruct_path(sys_id, came_from)
            _progress("Simulating fatigue and fuel costs...")
            return _simulate_route(
                path,
                systems,
                fatigue_multiplier,
                fuel_per_ly,
                initial_fatigue_min,
                danger,
                jfc_level=jfc_level,
            )

        if cost_so_far > best_cost.get(sys_id, float("inf")):
            continue

        explored += 1
        if explored % 1000 == 0:
            _progress(f"Exploring systems... ({explored} searched)")

        for neighbor_id, dist_ly in graph.get(sys_id, []):
            if dist_ly > effective_range:
                continue
            if neighbor_id in excluded:
                continue

            # Cost depends on routing mode
            neighbor = systems[neighbor_id]
            if mode == "direct":
                extra_cost = 0
            else:
                sys_danger = danger.get(neighbor_id, {})
                danger_cost = (
                    base_system_cost
                    + sys_danger.get("ship_kills", 0) * danger_weight
                    + sys_danger.get("ship_jumps", 0) * jumps_weight
                )
                if mode == "pos":
                    danger_cost -= neighbor.moon_count * pos_moon_bonus
                if mode == "safe" and neighbor.gate_count == 1:
                    danger_cost -= dead_end_bonus
                # Clamp to zero — negative costs break A* admissibility
                extra_cost = max(0, danger_cost)

            # Heavily penalize avoided alliance space
            if avoid and neighbor.sov_alliance_name in avoid:
                extra_cost += 100000

            new_cost = cost_so_far + dist_ly**distance_exponent + extra_cost

            if new_cost < best_cost.get(neighbor_id, float("inf")):
                best_cost[neighbor_id] = new_cost
                came_from[neighbor_id] = sys_id
                est = new_cost + heuristic(neighbor_id)
                heapq.heappush(open_set, (est, new_cost, neighbor_id))

    _progress("No route found.")
    return []


def _reconstruct_path(goal_id: int, came_from: dict[int, int | None]) -> list[int]:
    """Reconstruct system ID path from came_from chain."""
    path = []
    current: int | None = goal_id
    while current is not None:
        path.append(current)
        current = came_from.get(current)
    path.reverse()
    return path


def _simulate_route(
    path: list[int],
    systems: dict[int, SystemInfo],
    fatigue_multiplier: float,
    fuel_per_ly: float,
    initial_fatigue_min: float,
    danger: dict[int, dict],
    extra_wait_min: float = 0.0,
    jfc_level: int = 0,
) -> list[RouteStep]:
    """Simulate fatigue/fuel on a path with optional extra wait per hop.

    extra_wait_min: additional minutes to wait at each stop beyond the
    minimum cooldown, allowing fatigue to decay further.
    """
    steps = []
    fatigue = initial_fatigue_min

    for i, sys_id in enumerate(path):
        s = systems[sys_id]
        sys_danger = danger.get(sys_id, {})
        kills = sys_danger.get("ship_kills", 0)
        jumps = sys_danger.get("ship_jumps", 0)

        if i == 0:
            steps.append(
                RouteStep(
                    system_id=sys_id,
                    system_name=s.name,
                    security=s.security,
                    distance_ly=0.0,
                    wait_minutes=0.0,
                    fatigue_after_minutes=fatigue,
                    fuel_cost=0,
                    kills_per_hour=kills,
                    jumps_per_hour=jumps,
                    safe_spot_au=s.safe_spot_au,
                    safe_spot_warp=s.safe_spot_warp,
                    safe_spot_nearest=s.safe_spot_nearest,
                    moon_count=s.moon_count,
                    gate_count=s.gate_count,
                    sov_owner=s.sov_alliance_name or s.sov_faction_name,
                )
            )
            continue

        prev = systems[path[i - 1]]
        dist_ly = compute_distance_ly(prev.x, prev.y, prev.z, s.x, s.y, s.z)
        fatigue_after, total_wait = compute_fatigue(
            fatigue, dist_ly, fatigue_multiplier, extra_wait_min
        )
        fuel = compute_fuel_cost(dist_ly, fuel_per_ly, jfc_level)

        steps.append(
            RouteStep(
                system_id=sys_id,
                system_name=s.name,
                security=s.security,
                distance_ly=round(dist_ly, 2),
                wait_minutes=round(total_wait, 1),
                fatigue_after_minutes=round(fatigue_after, 1),
                fuel_cost=fuel,
                kills_per_hour=kills,
                jumps_per_hour=jumps,
                safe_spot_au=s.safe_spot_au,
                safe_spot_warp=s.safe_spot_warp,
                safe_spot_nearest=s.safe_spot_nearest,
                moon_count=s.moon_count,
                gate_count=s.gate_count,
                sov_owner=s.sov_alliance_name or s.sov_faction_name,
            )
        )
        fatigue = fatigue_after

    return steps


def find_optimal_wait(
    path: list[int],
    systems: dict[int, SystemInfo],
    fatigue_multiplier: float,
    fuel_per_ly: float,
    initial_fatigue_min: float,
    danger: dict[int, dict],
    jfc_level: int = 0,
) -> tuple[list[RouteStep], float]:
    """Find the extra wait per hop that minimizes total trip time.

    Tests wait times from 0 to 120 minutes in 5-minute increments.
    Keeps the best result to avoid recomputing.
    """
    best_wait = 0.0
    best_total = float("inf")
    best_steps: list[RouteStep] = []

    for extra_wait in range(0, 125, 5):
        steps = _simulate_route(
            path,
            systems,
            fatigue_multiplier,
            fuel_per_ly,
            initial_fatigue_min,
            danger,
            extra_wait_min=float(extra_wait),
            jfc_level=jfc_level,
        )
        total_time = sum(s.wait_minutes for s in steps)
        if total_time < best_total:
            best_total = total_time
            best_wait = float(extra_wait)
            best_steps = steps

    return best_steps, best_wait
