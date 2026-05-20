"""Public `find_route` dispatcher.

Runs the BFS reachability probe (and verbose chain diagnostics on
failure), then the multi-label search, with the legacy single-criterion
A* as a no-route fallback.
"""

import logging
from typing import Callable

from src.constants import (
    ACTIVITY_WEIGHT,
    BASE_SYSTEM_COST,
    DANGER_WEIGHT,
    DEAD_END_PENALTY,
    DISTANCE_EXPONENT,
    GATE_EQUIVALENT_JUMPS,
    JUMPS_WEIGHT,
    POS_MOON_BONUS,
    WAIT_WEIGHT,
)
from src.pathfinder.diagnostics import (
    _bfs_reachability,
    _log_cross_cluster_gap,
    _log_dotlan_chain_membership,
)
from src.schemas.system import SystemInfo
from src.pathfinder.multi_label import _find_route_multi_label
from src.pathfinder.single_criterion import _find_route_single_criterion
from src.pathfinder.types import RouteStep

logger = logging.getLogger(__name__)


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
    dead_end_penalty: int = DEAD_END_PENALTY,
    pos_moon_bonus: int = POS_MOON_BONUS,
    gate_graph: dict[int, list[tuple[int, bool, bool]]] | None = None,
    gate_mode: str = "off",
    gate_equivalent_jumps: float = GATE_EQUIVALENT_JUMPS,
    wait_weight: float = WAIT_WEIGHT,
) -> list[RouteStep]:
    """Optimal multi-label route finder (cost + fatigue).

    The search itself picks per-hop waits via fatigue-decay pseudo-edges,
    so the returned RouteSteps' `wait_minutes` already reflects an optimal
    wait strategy. `wait_weight` controls the tradeoff: high values bias
    the search toward fewer jumps (waits are expensive), low values toward
    longer-LY jumps with more waiting (waits are cheap).

    If multi-label search fails (hit pop cap or truly unreachable), falls
    back to the legacy single-criterion A* so callers always get a sensible
    answer when one exists.
    """
    effective_range = base_range_ly * (1 + 0.20 * jdc_level)
    logger.info(
        "="
        * 70
        + "\n[find_route] origin=%d dest=%d ship_range=%.2fLY jdc=%d eff=%.2fLY "
        "ff_mult=%.2f mode=%s wait_weight=%.3f gates=%s",
        origin_id,
        dest_id,
        base_range_ly,
        jdc_level,
        effective_range,
        fatigue_multiplier,
        mode,
        wait_weight,
        gate_mode,
    )
    if origin_id not in systems:
        logger.warning("[find_route] origin %d NOT in systems dict", origin_id)
    if dest_id not in systems:
        logger.warning("[find_route] dest %d NOT in systems dict", dest_id)

    # Diagnostic: does a route even exist at this effective range, ignoring
    # all cost/fatigue heuristics? BFS gives a definitive answer cheaply.
    reachable, min_hops, bfs_visited_set = _bfs_reachability(
        origin_id, dest_id, graph, effective_range
    )
    if reachable:
        logger.info(
            "[find_route] BFS: REACHABLE in min %d hops (visited %d systems "
            "at %.2fLY range)",
            min_hops,
            len(bfs_visited_set),
            effective_range,
        )
    else:
        logger.warning(
            "[find_route] BFS: UNREACHABLE via pure JD at %.2fLY range "
            "(BFS visited %d systems from origin without finding dest). "
            "No algorithm can find a JD-only route here.",
            effective_range,
            len(bfs_visited_set),
        )
        # Region breakdown of the connected component the origin is in.
        # If this shows e.g. "only Delve+Querious", we know which region(s)
        # the graph fails to connect to.
        region_counts: dict[int, int] = {}
        for sid in bfs_visited_set:
            sinfo = systems.get(sid)
            if sinfo:
                region_counts[sinfo.region_id] = (
                    region_counts.get(sinfo.region_id, 0) + 1
                )
        logger.warning(
            "[find_route] BFS reachable cluster by region: %s",
            sorted(region_counts.items(), key=lambda kv: -kv[1]),
        )
        # Sanity check: is dest_id even in the systems dict?
        if dest_id in systems:
            dest_sys = systems[dest_id]
            logger.warning(
                "[find_route] dest %d (region=%d) IS in systems dict — graph "
                "edges to it must be missing or filtered out.",
                dest_id,
                dest_sys.region_id,
            )
            # How many JD neighbors does dest have at this range?
            dest_neighbors = graph.get(dest_id, [])
            dest_in_range = sum(1 for _, d in dest_neighbors if d <= effective_range)
            logger.warning(
                "[find_route] dest has %d total JD neighbors, %d within range. "
                "If 0 in-range, dest is isolated in the graph.",
                len(dest_neighbors),
                dest_in_range,
            )
            # Cross-cluster gap analysis: find smallest raw-coord distance
            # between any BFS-reached system and any non-reached system.
            # If this is <= effective_range, the graph build is missing
            # edges that should exist (real bug). If it's > effective_range,
            # the BFS cluster is genuinely walled off in capnav's coords.
            _log_cross_cluster_gap(bfs_visited_set, systems, effective_range, dest_id)
            # Membership + edge-presence check against a known-good Dotlan
            # lowsec-bridging route, to spot if load_systems filtered out
            # any of those bridge systems.
            _log_dotlan_chain_membership(
                systems, graph, bfs_visited_set, effective_range, dest_id
            )
        else:
            logger.warning(
                "[find_route] dest %d is NOT in the systems dict — "
                "load_systems() filtered it out.",
                dest_id,
            )

    ml_steps = _find_route_multi_label(
        origin_id=origin_id,
        dest_id=dest_id,
        systems=systems,
        graph=graph,
        base_range_ly=base_range_ly,
        jdc_level=jdc_level,
        fatigue_multiplier=fatigue_multiplier,
        fuel_per_ly=fuel_per_ly,
        initial_fatigue_min=initial_fatigue_min,
        jfc_level=jfc_level,
        danger_data=danger_data,
        on_progress=on_progress,
        mode=mode,
        avoid_alliances=avoid_alliances,
        exclude_systems=exclude_systems,
        base_system_cost=base_system_cost,
        distance_exponent=distance_exponent,
        danger_weight=danger_weight,
        jumps_weight=jumps_weight,
        activity_weight=activity_weight,
        dead_end_penalty=dead_end_penalty,
        pos_moon_bonus=pos_moon_bonus,
        gate_graph=gate_graph,
        gate_mode=gate_mode,
        gate_equivalent_jumps=gate_equivalent_jumps,
        wait_weight=wait_weight,
    )
    if ml_steps:
        logger.info(
            "[find_route] multi-label SUCCESS: returning %d-step route",
            len(ml_steps),
        )
        return ml_steps
    logger.warning(
        "[find_route] multi-label returned %s, falling back to single-criterion",
        "empty list" if ml_steps == [] else "None",
    )
    # Multi-label found nothing (truly unreachable or hit pop cap). Fall
    # back to the always-reliable single-criterion A*.
    sc_steps = _find_route_single_criterion(
        origin_id=origin_id,
        dest_id=dest_id,
        systems=systems,
        graph=graph,
        base_range_ly=base_range_ly,
        jdc_level=jdc_level,
        fatigue_multiplier=fatigue_multiplier,
        fuel_per_ly=fuel_per_ly,
        initial_fatigue_min=initial_fatigue_min,
        jfc_level=jfc_level,
        danger_data=danger_data,
        on_progress=on_progress,
        mode=mode,
        avoid_alliances=avoid_alliances,
        exclude_systems=exclude_systems,
        base_system_cost=base_system_cost,
        distance_exponent=distance_exponent,
        danger_weight=danger_weight,
        jumps_weight=jumps_weight,
        activity_weight=activity_weight,
        dead_end_penalty=dead_end_penalty,
        pos_moon_bonus=pos_moon_bonus,
        gate_graph=gate_graph,
        gate_mode=gate_mode,
        gate_equivalent_jumps=gate_equivalent_jumps,
    )
    if sc_steps:
        logger.info(
            "[find_route] single-criterion SUCCESS: returning %d-step route",
            len(sc_steps),
        )
    else:
        logger.warning(
            "[find_route] single-criterion ALSO failed — returning empty. "
            "BFS reachability was %s.",
            "REACHABLE (algo bug somewhere)" if reachable else "UNREACHABLE",
        )
    return sc_steps
