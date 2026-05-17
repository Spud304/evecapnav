import heapq
import logging
import math
from collections import deque
from dataclasses import dataclass, asdict
from typing import Callable

from src.constants import (
    MAX_FATIGUE_MINUTES,
    MAX_COOLDOWN_MINUTES,
    BASE_SYSTEM_COST,
    DISTANCE_EXPONENT,
    DANGER_WEIGHT,
    JUMPS_WEIGHT,
    ACTIVITY_WEIGHT,
    POS_MOON_BONUS,
    DEAD_END_BONUS,
    GATE_EQUIVALENT_JUMPS,
    GATE_JUMP_REFERENCE_LY,
    GATE_TRAVEL_SECONDS,
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
    edge_type: str = "jump"  # "jump" for jump-drive hops, "gate" for stargate hops

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
    activity_weight: int = ACTIVITY_WEIGHT,
    dead_end_bonus: int = DEAD_END_BONUS,
    pos_moon_bonus: int = POS_MOON_BONUS,
    gate_graph: dict[int, list[tuple[int, bool, bool]]] | None = None,
    gate_mode: str = "off",
    gate_equivalent_jumps: float = GATE_EQUIVALENT_JUMPS,
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

    gates_enabled = gate_mode in ("interregional", "all") and gate_graph is not None
    gate_unit_cost = GATE_JUMP_REFERENCE_LY**distance_exponent
    gate_edge_cost = gate_equivalent_jumps * gate_unit_cost

    def _progress(msg: str) -> None:
        if on_progress:
            on_progress(msg)

    _progress(f"Computing route ({effective_range:.1f} LY range)...")

    # Heuristic:
    # - Without gates: straight-line LY distance (admissible since each jump
    #   costs dist^exp ≥ dist for dist ≥ 1).
    # - With gates enabled: BFS over the stargate graph backwards from dest_id
    #   gives the minimum number of gate hops needed; multiply by the cheapest
    #   single gate edge cost in the current mode for an admissible h. This
    #   mirrors dotlan's pure-stargate routing and gives strong directional
    #   bias along the actual gate network, so A* doesn't get stuck preferring
    #   physically-near-but-graph-far systems. Systems unreachable in the gate
    #   graph fall back to LY distance capped at the cheapest gate edge cost.
    if gates_enabled:
        # Cheapest possible single gate edge cost in the current mode.
        # - "all": every gate hop costs gate_edge_cost.
        # - "interregional": intra-region gates cost gate_unit_cost, inter-regional
        #   cost gate_edge_cost; the cheaper of the two is the floor.
        if gate_mode == "interregional":
            min_edge_cost = min(gate_unit_cost, gate_edge_cost)
        else:
            min_edge_cost = gate_edge_cost
        # BFS over reversed gate graph from dest to label every node with hop count.
        # The gate graph here is symmetric (each stargate has its paired entry),
        # so the forward graph works equivalently as a reverse adjacency.
        gate_hops_to_dest: dict[int, int] = {dest_id: 0}
        bfs_queue: deque[int] = deque([dest_id])
        while bfs_queue:
            cur = bfs_queue.popleft()
            cur_hops = gate_hops_to_dest[cur]
            for nb, _cross_r, _cross_c in gate_graph.get(cur, []):
                if nb not in gate_hops_to_dest:
                    gate_hops_to_dest[nb] = cur_hops + 1
                    bfs_queue.append(nb)

        _progress(
            f"Gate-graph BFS: {len(gate_hops_to_dest)} systems reachable from destination"
        )

        def heuristic(sys_id: int) -> float:
            hops = gate_hops_to_dest.get(sys_id)
            if hops is not None:
                # Admissible: any gate-using path from sys_id to dest needs
                # at least `hops` edges, each costing at least min_edge_cost.
                return hops * min_edge_cost
            s = systems[sys_id]
            ly = compute_distance_ly(s.x, s.y, s.z, dest.x, dest.y, dest.z)
            return min(ly, min_edge_cost)
    else:

        def heuristic(sys_id: int) -> float:
            s = systems[sys_id]
            return compute_distance_ly(s.x, s.y, s.z, dest.x, dest.y, dest.z)

    # A* with state = system_id only
    # (est_total, cost_so_far, system_id)
    open_set: list[tuple[float, float, int]] = []
    heapq.heappush(open_set, (heuristic(origin_id), 0.0, origin_id))

    best_cost: dict[int, float] = {origin_id: 0.0}
    came_from: dict[int, tuple[int | None, str]] = {origin_id: (None, "")}

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

        # Build candidate neighbor list: jumps (filtered by range) + optional gates.
        # Each candidate carries its own edge_cost so gate edges can be priced
        # differently (e.g. intra-region vs inter-regional shortcuts).
        candidates: list[tuple[int, float, float, str]] = []
        for neighbor_id, dist_ly in graph.get(sys_id, []):
            if dist_ly > effective_range:
                continue
            candidates.append(
                (neighbor_id, dist_ly, dist_ly**distance_exponent, "jump")
            )

        if gates_enabled:
            for neighbor_id, cross_region, cross_constellation in gate_graph.get(
                sys_id, []
            ):
                if gate_mode == "interregional":
                    # In this mode inter-regional gates are the user's "shortcut"
                    # (priced at gate_equivalent_jumps), while intra-region gates
                    # are still available but priced as one normal jump so they
                    # don't get spammed and don't break connectivity for
                    # short-range ships.
                    edge_cost = gate_edge_cost if cross_region else gate_unit_cost
                else:
                    # "all" mode: every gate uses the same shortcut cost.
                    edge_cost = gate_edge_cost
                candidates.append((neighbor_id, 0.0, edge_cost, "gate"))

        for neighbor_id, dist_ly, edge_cost, edge_type in candidates:
            if neighbor_id in excluded:
                continue
            if neighbor_id not in systems:
                continue

            neighbor = systems[neighbor_id]

            if mode == "direct":
                extra_cost = 0
            else:
                sys_danger = danger.get(neighbor_id, {})
                danger_cost = (
                    base_system_cost
                    + sys_danger.get("ship_kills", 0) * danger_weight
                    + sys_danger.get("ship_jumps", 0) * jumps_weight
                    + sys_danger.get("pilot_activity", 0) * activity_weight
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

            new_cost = cost_so_far + edge_cost + extra_cost

            if new_cost < best_cost.get(neighbor_id, float("inf")):
                best_cost[neighbor_id] = new_cost
                came_from[neighbor_id] = (sys_id, edge_type)
                est = new_cost + heuristic(neighbor_id)
                heapq.heappush(open_set, (est, new_cost, neighbor_id))

    _progress("No route found.")
    return []


def _reconstruct_path(
    goal_id: int, came_from: dict[int, tuple[int | None, str]]
) -> list[tuple[int, str]]:
    """Reconstruct (system_id, edge_type_used_to_reach) path from came_from chain.

    Edge type for the origin is "" (no inbound edge).
    """
    path: list[tuple[int, str]] = []
    current: int | None = goal_id
    while current is not None:
        parent, edge_type = came_from.get(current, (None, ""))
        path.append((current, edge_type))
        current = parent
    path.reverse()
    return path


def _simulate_route(
    path: list[int] | list[tuple[int, str]],
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
    # Normalize path to list[(sys_id, edge_type)] — accept plain id list too
    norm_path: list[tuple[int, str]] = []
    for item in path:
        if isinstance(item, tuple):
            norm_path.append(item)
        else:
            norm_path.append((item, "jump"))

    steps = []
    fatigue = initial_fatigue_min
    gate_wait_min = GATE_TRAVEL_SECONDS / 60.0

    for i, (sys_id, edge_type) in enumerate(norm_path):
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
                    edge_type="",
                )
            )
            continue

        prev = systems[norm_path[i - 1][0]]

        if edge_type == "gate":
            # No fatigue, no fuel on gate hops. Distance reported as actual
            # straight-line LY between systems (informational only).
            dist_ly = compute_distance_ly(prev.x, prev.y, prev.z, s.x, s.y, s.z)
            steps.append(
                RouteStep(
                    system_id=sys_id,
                    system_name=s.name,
                    security=s.security,
                    distance_ly=round(dist_ly, 2),
                    wait_minutes=round(gate_wait_min, 1),
                    fatigue_after_minutes=round(fatigue, 1),
                    fuel_cost=0,
                    kills_per_hour=kills,
                    jumps_per_hour=jumps,
                    safe_spot_au=s.safe_spot_au,
                    safe_spot_warp=s.safe_spot_warp,
                    safe_spot_nearest=s.safe_spot_nearest,
                    moon_count=s.moon_count,
                    gate_count=s.gate_count,
                    sov_owner=s.sov_alliance_name or s.sov_faction_name,
                    edge_type="gate",
                )
            )
            continue

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
                edge_type="jump",
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
