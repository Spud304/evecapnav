"""Multi-label (bicriterion: cost + fatigue) Dijkstra search.

State per node is `Vertex(cost, fatigue, cooldown, ...)`; multiple
non-dominated labels per system are retained so the search can trade
"wait longer at X" against "different topology via Y."
"""

import heapq
import itertools
import logging
from collections import defaultdict
from typing import Callable

from src.constants import (
    ACTIVITY_WEIGHT,
    BASE_SYSTEM_COST,
    DANGER_WEIGHT,
    DEAD_END_PENALTY,
    DISTANCE_EXPONENT,
    GATE_EQUIVALENT_JUMPS,
    GATE_JUMP_REFERENCE_LY,
    GATE_TRAVEL_SECONDS,
    HOP_OVERHEAD_FACTOR,
    JUMPS_WEIGHT,
    MAX_COOLDOWN_MINUTES,
    MAX_FATIGUE_MINUTES,
    POS_MOON_BONUS,
    WAIT_WEIGHT,
)
from src.schemas.system import SystemInfo
from src.pathfinder.cost import (
    _danger_cost,
    _path_contains,
    compute_distance_ly,
    compute_fuel_cost,
)
from src.pathfinder.types import (
    JT_COOLDOWN_WAIT,
    JT_FATIGUE_WAIT,
    JT_GATE,
    JT_JUMP,
    JT_NONE,
    RouteStep,
    Vertex,
    _MAX_LABEL_POPS,
)

logger = logging.getLogger(__name__)


def _dominates(a: Vertex, b: Vertex) -> bool:
    """True iff `a` is at least as good as `b` on every axis we care about.

    Special cases:
      - A wait-pseudo label never dominates a non-wait label at the same
        system — we want the search to retain the option to "act now"
        even if a "wait first" label looks cheaper on paper.
      - Two gate-only labels sharing a `segment_root` use *segment-local*
        cost (`cost - segment_root.cost`) for domination. This preserves
        alternate gate sub-walks that started from different JD entry
        points, so we don't kill the global optimum by over-pruning.
    """
    a_is_wait = (a.jump_type & (JT_FATIGUE_WAIT | JT_COOLDOWN_WAIT)) != 0
    b_is_wait = (b.jump_type & (JT_FATIGUE_WAIT | JT_COOLDOWN_WAIT)) != 0
    if a_is_wait and not b_is_wait:
        return False
    if (
        a.jump_type == JT_GATE
        and b.jump_type == JT_GATE
        and a.segment_root is b.segment_root
        and a.segment_root is not None
        and b.segment_root is not None
    ):
        a_local = a.cost - a.segment_root.cost
        b_local = b.cost - b.segment_root.cost
        return a_local <= b_local
    return a.est_fatigue_min <= b.est_fatigue_min and a.cost <= b.cost


def _check_domination(v: Vertex, label_table: dict[int, list[Vertex]]) -> bool:
    """Returns True iff `v` is dominated by an existing label.

    Side effects: removes any existing labels that `v` dominates; appends
    `v` to the bucket if it survived. Lazy-deletes by setting
    `Vertex.dominated = True` on losers so any pending heap entries for
    them get skipped at pop time.
    """
    bucket = label_table[v.sys_id]
    dominated = False
    survivors: list[Vertex] = []
    for other in bucket:
        if not dominated and _dominates(other, v):
            dominated = True
            v.dominated = True
            survivors.append(other)
        elif _dominates(v, other):
            other.dominated = True
        else:
            survivors.append(other)
    if not dominated:
        survivors.append(v)
    label_table[v.sys_id] = survivors
    return dominated


def _extend_labels(
    cur: Vertex,
    *,
    systems: dict[int, SystemInfo],
    graph: dict[int, list[tuple[int, float]]],
    gate_graph: dict[int, list[tuple[int, bool, bool]]],
    gates_enabled: bool,
    effective_range: float,
    fatigue_multiplier: float,
    fuel_per_ly: float,
    jfc_level: int,
    mode: str,
    danger: dict[int, dict],
    avoid: set[str],
    excluded: set[int],
    base_system_cost: int,
    distance_exponent: float,
    danger_weight: int,
    jumps_weight: int,
    activity_weight: int,
    dead_end_penalty: int,
    pos_moon_bonus: int,
    gate_unit_cost: float,
    gate_edge_cost: float,
    gate_mode: str,
    wait_weight: float,
):
    """Yield successor Vertex labels for `cur`. Four successor classes:
    gate hop, fatigue-wait pseudo-edge, cooldown-wait pseudo-edge, and
    jump-drive edge."""
    cur_sys = systems[cur.sys_id]

    # 1. Cooldown-wait pseudo-edge. Required between JD jumps — JD-edge
    #    expansion below is gated on `est_cooldown_min <= 0`. Cost is zero
    #    (it's mandatory, doesn't bias topology); it just advances time and
    #    decays both timers.
    if cur.est_cooldown_min > 0:
        cooldown = cur.est_cooldown_min
        yield Vertex(
            sys_id=cur.sys_id,
            cost=cur.cost,
            time_seconds=cur.time_seconds + cooldown * 60.0,
            est_fatigue_min=max(0.0, cur.est_fatigue_min - cooldown),
            est_cooldown_min=0.0,
            jump_type=JT_COOLDOWN_WAIT,
            edge_type_str="",
            distance_ly=0.0,
            fuel_cost=0,
            parent=cur,
            segment_root=cur.segment_root,
        )

    # 2. Fatigue-decay wait pseudo-edge. Optional — only emitted when
    #    fatigue is still high enough that the *next* JD jump would push it
    #    further (i.e. fatigue > 10 min, the floor in compute_fatigue).
    if cur.est_cooldown_min <= 0 and cur.est_fatigue_min > 10.0:
        wait_min = cur.est_fatigue_min - 10.0
        yield Vertex(
            sys_id=cur.sys_id,
            cost=cur.cost + wait_weight * wait_min,
            time_seconds=cur.time_seconds + wait_min * 60.0,
            est_fatigue_min=10.0,
            est_cooldown_min=0.0,
            jump_type=JT_FATIGUE_WAIT,
            edge_type_str="",
            distance_ly=0.0,
            fuel_cost=0,
            parent=cur,
            segment_root=cur.segment_root,
        )

    # 3. Gate edges. Pricing mirrors _find_route_single_criterion;
    #    intra-region gates are cheap, cross-region "shortcut" gates use
    #    the larger gate_edge_cost in interregional mode.
    if gates_enabled:
        for neighbor_id, cross_region, _cross_constellation in gate_graph.get(
            cur.sys_id, []
        ):
            if neighbor_id in excluded or neighbor_id not in systems:
                continue
            if _path_contains(cur, neighbor_id):
                continue
            neighbor = systems[neighbor_id]
            if gate_mode == "interregional":
                edge_cost = gate_edge_cost if cross_region else gate_unit_cost
            else:
                edge_cost = gate_edge_cost
            sys_danger = danger.get(neighbor_id, {})
            extra = _danger_cost(
                neighbor,
                sys_danger,
                mode,
                base_system_cost,
                danger_weight,
                jumps_weight,
                activity_weight,
                dead_end_penalty,
                pos_moon_bonus,
            )
            if avoid and neighbor.sov_alliance_name in avoid:
                extra += 100_000
            dist_ly = compute_distance_ly(
                cur_sys.x, cur_sys.y, cur_sys.z, neighbor.x, neighbor.y, neighbor.z
            )
            # Per-hop overhead so high wait_weight biases the search toward
            # fewer total hops (not just fewer JDs). Applied uniformly to
            # gate and JD edges so they compete on hop count.
            hop_overhead = wait_weight * HOP_OVERHEAD_FACTOR
            # Gate hops don't change fatigue/cooldown — matches the legacy
            # `_simulate_route` convention. (Strictly, EVE does decay fatigue
            # during the ~45s gate cycle, but the impact is tiny and the
            # legacy tests assert it stays constant.)
            yield Vertex(
                sys_id=neighbor_id,
                cost=cur.cost + edge_cost + extra + hop_overhead,
                time_seconds=cur.time_seconds + GATE_TRAVEL_SECONDS,
                est_fatigue_min=cur.est_fatigue_min,
                est_cooldown_min=cur.est_cooldown_min,
                jump_type=JT_GATE,
                edge_type_str="gate",
                distance_ly=dist_ly,
                fuel_cost=0,
                parent=cur,
                segment_root=cur.segment_root,  # gate stays in current segment
            )

    # 4. Jump-drive edges. Only when cooldown is clear (matches EVE: JD
    #    activation is blocked while the red timer is active).
    if cur.est_cooldown_min <= 0:
        for neighbor_id, dist_ly in graph.get(cur.sys_id, []):
            if dist_ly > effective_range:
                continue
            if neighbor_id in excluded or neighbor_id not in systems:
                continue
            if _path_contains(cur, neighbor_id):
                continue
            neighbor = systems[neighbor_id]
            sys_danger = danger.get(neighbor_id, {})
            extra = _danger_cost(
                neighbor,
                sys_danger,
                mode,
                base_system_cost,
                danger_weight,
                jumps_weight,
                activity_weight,
                dead_end_penalty,
                pos_moon_bonus,
            )
            if avoid and neighbor.sov_alliance_name in avoid:
                extra += 100_000
            # Post-jump fatigue/cooldown per the EVE formula (mirrors
            # compute_fatigue, but we need the *raw* post-jump values, before
            # any wait is applied — wait happens via pseudo-edge below).
            factor = dist_ly * fatigue_multiplier
            new_cooldown = min(
                MAX_COOLDOWN_MINUTES,
                max(cur.est_fatigue_min / 10.0, 1.0 + factor),
            )
            new_fatigue_raw = min(
                MAX_FATIGUE_MINUTES,
                max(cur.est_fatigue_min, 10.0) * (1.0 + factor),
            )
            fuel = compute_fuel_cost(dist_ly, fuel_per_ly, jfc_level)
            # Price the *fatigue* this jump leaves in its wake. Fatigue
            # above 10 min has to be either waited off (a fatigue-wait
            # pseudo-edge) or absorbed into a worse subsequent jump, so
            # the search needs to see it as a cost up front.
            fatigue_excess = max(0.0, new_fatigue_raw - 10.0)
            fatigue_cost = wait_weight * fatigue_excess
            # Per-hop overhead (see gate branch above). Same for JD and
            # gate so the search trades off purely on edge base cost +
            # fatigue, not on which type of edge has more inherent waits.
            hop_overhead = wait_weight * HOP_OVERHEAD_FACTOR
            new_vertex = Vertex(
                sys_id=neighbor_id,
                cost=cur.cost
                + dist_ly**distance_exponent
                + extra
                + fatigue_cost
                + hop_overhead,
                time_seconds=cur.time_seconds + 60.0,
                est_fatigue_min=new_fatigue_raw,
                est_cooldown_min=new_cooldown,
                jump_type=JT_JUMP,
                edge_type_str="jump",
                distance_ly=dist_ly,
                fuel_cost=fuel,
                parent=cur,
                segment_root=None,
            )
            new_vertex.segment_root = new_vertex  # JD starts a fresh segment
            yield new_vertex


def _reconstruct_route(
    end_vertex: Vertex,
    systems: dict[int, SystemInfo],
    danger: dict[int, dict],
) -> list[RouteStep]:
    """Walk parent chain and merge wait pseudo-edges into the next real
    hop's wait_minutes. The wait_minutes attribution matches the legacy
    `_simulate_route` convention: "the wait recorded at hop N is the time
    spent AT system N after arriving there, before doing the next thing."
    """
    chain: list[Vertex] = []
    v: Vertex | None = end_vertex
    while v is not None:
        chain.append(v)
        v = v.parent
    chain.reverse()

    gate_wait_min = GATE_TRAVEL_SECONDS / 60.0
    steps: list[RouteStep] = []
    i = 0
    while i < len(chain):
        vx = chain[i]
        if (vx.jump_type & (JT_FATIGUE_WAIT | JT_COOLDOWN_WAIT)) != 0:
            # Should already have been merged into a prior real hop's wait.
            # If it appears at position 0 it's a no-op (the start is never a wait).
            i += 1
            continue

        # Look ahead: accumulate consecutive wait pseudo-edges at the same system.
        # Track cooldown vs fatigue-decay waits separately for the two-tone
        # Wait cell in the frontend (red timer vs blue timer).
        j = i + 1
        wait_after = 0.0
        wait_cooldown = 0.0
        wait_decay = 0.0
        while (
            j < len(chain)
            and (chain[j].jump_type & (JT_FATIGUE_WAIT | JT_COOLDOWN_WAIT)) != 0
        ):
            delta_min = (chain[j].time_seconds - chain[j - 1].time_seconds) / 60.0
            wait_after += delta_min
            if (chain[j].jump_type & JT_COOLDOWN_WAIT) != 0:
                wait_cooldown += delta_min
            else:
                wait_decay += delta_min
            j += 1

        sys = systems[vx.sys_id]
        sys_danger = danger.get(vx.sys_id, {})

        if i == 0:
            # Start vertex: no inbound edge or fuel, but the search may
            # have inserted a fatigue/cooldown wait at the origin before
            # the first hop (e.g. with non-zero initial_fatigue). Surface
            # that wait + the post-wait fatigue so the row matches what
            # the user actually has to do.
            wait_min = wait_after
            distance_ly = 0.0
            edge_type_out = ""
            fuel = 0
            fatigue_after_min = (
                chain[j - 1].est_fatigue_min if j > i + 1 else vx.est_fatigue_min
            )
        elif vx.edge_type_str == "gate":
            # Gate hop: travel time + any (rare) trailing waits.
            wait_min = gate_wait_min + wait_after
            distance_ly = vx.distance_ly
            edge_type_out = "gate"
            fuel = 0
            fatigue_after_min = (
                chain[j - 1].est_fatigue_min if j > i + 1 else vx.est_fatigue_min
            )
        else:
            # JD jump. wait_minutes is the sum of all wait pseudo-edges that
            # followed this jump in the chain. If the search ended exactly on
            # a JD vertex (e.g. destination is reached with cooldown still
            # active), synthesize the mandatory cooldown so wait_minutes
            # matches what `_simulate_route` would report on the same path.
            inbound_cooldown = 0.0
            if j == i + 1 and vx.est_cooldown_min > 0:
                inbound_cooldown = vx.est_cooldown_min
            wait_min = wait_after + inbound_cooldown
            # The synthesized inbound cooldown counts as a red-timer wait.
            wait_cooldown += inbound_cooldown
            distance_ly = vx.distance_ly
            edge_type_out = "jump"
            fuel = vx.fuel_cost
            if j > i + 1:
                fatigue_after_min = chain[j - 1].est_fatigue_min
            elif inbound_cooldown > 0:
                fatigue_after_min = max(0.0, vx.est_fatigue_min - inbound_cooldown)
            else:
                fatigue_after_min = vx.est_fatigue_min

        steps.append(
            RouteStep(
                system_id=vx.sys_id,
                system_name=sys.name,
                security=sys.security,
                distance_ly=round(distance_ly, 2),
                wait_minutes=round(wait_min, 1),
                fatigue_after_minutes=round(fatigue_after_min, 1),
                fuel_cost=fuel,
                kills_per_hour=sys_danger.get("ship_kills", 0),
                jumps_per_hour=sys_danger.get("ship_jumps", 0),
                safe_spot_au=sys.safe_spot_au,
                safe_spot_warp=sys.safe_spot_warp,
                safe_spot_nearest=sys.safe_spot_nearest,
                moon_count=sys.moon_count,
                gate_count=sys.gate_count,
                sov_owner=sys.sov_alliance_name or sys.sov_faction_name,
                edge_type=edge_type_out,
                hourly_jumps=list(sys_danger.get("hourly_jumps", [])),
                wait_cooldown_minutes=round(wait_cooldown, 1),
                wait_decay_minutes=round(wait_decay, 1),
            )
        )
        i = j

    return steps


def _find_route_multi_label(
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
    horizon: float = float("inf"),
) -> list[RouteStep] | None:
    """Bicriterion (cost + fatigue) label-setting Dijkstra. Returns None if
    no route is found under `horizon` within the pop budget.
    """
    if origin_id not in systems:
        logger.warning("[ML] origin %d not in systems dict — aborting", origin_id)
        return None
    if dest_id not in systems:
        logger.warning("[ML] dest %d not in systems dict — aborting", dest_id)
        return None

    effective_range = base_range_ly * (1 + 0.20 * jdc_level)
    danger = danger_data or {}
    avoid = avoid_alliances or set()
    excluded = exclude_systems or set()
    gates_enabled = gate_mode in ("interregional", "all") and gate_graph is not None
    gate_unit_cost = GATE_JUMP_REFERENCE_LY**distance_exponent
    gate_edge_cost = gate_equivalent_jumps * gate_unit_cost

    def _progress(msg: str) -> None:
        if on_progress:
            on_progress(msg)

    n_jd_neighbors = len(graph.get(origin_id, []))
    n_in_range = sum(1 for _, d in graph.get(origin_id, []) if d <= effective_range)
    logger.info(
        "[ML] START origin=%d dest=%d eff_range=%.2fLY mode=%s wait_weight=%.3f "
        "gates=%s horizon=%.1f initial_fatigue=%.1f",
        origin_id,
        dest_id,
        effective_range,
        mode,
        wait_weight,
        gate_mode,
        horizon if horizon != float("inf") else -1.0,
        initial_fatigue_min,
    )
    logger.info(
        "[ML] graph: origin has %d total JD neighbors, %d within %.1f LY range",
        n_jd_neighbors,
        n_in_range,
        effective_range,
    )

    _progress(f"Multi-label search ({effective_range:.1f} LY range)...")

    label_table: dict[int, list[Vertex]] = defaultdict(list)
    seq = itertools.count()
    heap: list[tuple[float, int, Vertex]] = []

    start = Vertex(
        sys_id=origin_id,
        cost=0.0,
        time_seconds=0.0,
        est_fatigue_min=initial_fatigue_min,
        est_cooldown_min=0.0,
        jump_type=JT_NONE,
        edge_type_str="",
        distance_ly=0.0,
        fuel_cost=0,
        parent=None,
    )
    start.segment_root = start
    heapq.heappush(heap, (0.0, next(seq), start))

    _gate_graph = gate_graph or {}

    def _extend(cur: Vertex):
        return _extend_labels(
            cur,
            systems=systems,
            graph=graph,
            gate_graph=_gate_graph,
            gates_enabled=gates_enabled,
            effective_range=effective_range,
            fatigue_multiplier=fatigue_multiplier,
            fuel_per_ly=fuel_per_ly,
            jfc_level=jfc_level,
            mode=mode,
            danger=danger,
            avoid=avoid,
            excluded=excluded,
            base_system_cost=base_system_cost,
            distance_exponent=distance_exponent,
            danger_weight=danger_weight,
            jumps_weight=jumps_weight,
            activity_weight=activity_weight,
            dead_end_penalty=dead_end_penalty,
            pos_moon_bonus=pos_moon_bonus,
            gate_unit_cost=gate_unit_cost,
            gate_edge_cost=gate_edge_cost,
            gate_mode=gate_mode,
            wait_weight=wait_weight,
        )

    best: Vertex | None = None
    pops = 0
    pruned_dominated = 0
    pruned_horizon = 0
    pushed = 0
    max_heap_size = 0

    while heap:
        _, _, cur = heapq.heappop(heap)
        pops += 1
        if pops > _MAX_LABEL_POPS:
            logger.warning(
                "[ML] POP CAP HIT (%d) — heap_remaining=%d label_systems=%d "
                "best=%s pushed=%d pruned_dominated=%d pruned_horizon=%d",
                _MAX_LABEL_POPS,
                len(heap),
                len(label_table),
                f"cost={best.cost:.1f}" if best else "None",
                pushed,
                pruned_dominated,
                pruned_horizon,
            )
            break
        if cur.dominated:
            pruned_dominated += 1
            continue
        if cur.cost > horizon:
            pruned_horizon += 1
            continue
        if cur.sys_id == dest_id:
            if best is None:
                logger.info(
                    "[ML] FIRST DEST HIT at pop=%d cost=%.2f time=%.0fs fatigue=%.1f",
                    pops,
                    cur.cost,
                    cur.time_seconds,
                    cur.est_fatigue_min,
                )
            elif cur.cost < best.cost:
                logger.info(
                    "[ML] BETTER DEST HIT at pop=%d cost=%.2f (was %.2f)",
                    pops,
                    cur.cost,
                    best.cost,
                )
            if best is None or cur.cost < best.cost:
                best = cur
                horizon = cur.cost  # shrink the horizon to the new best cost
            continue  # don't expand the destination
        if pops % 5000 == 0:
            logger.info(
                "[ML] progress: pops=%d heap=%d label_systems=%d horizon=%.1f "
                "current_cost=%.2f current_sys=%d pushed=%d",
                pops,
                len(heap),
                len(label_table),
                horizon,
                cur.cost,
                cur.sys_id,
                pushed,
            )
            _progress(f"Multi-label: {pops} pops, horizon={horizon:.1f}")
        for nb in _extend(cur):
            if nb.cost > horizon:
                pruned_horizon += 1
                continue
            if not _check_domination(nb, label_table):
                heapq.heappush(heap, (nb.cost, next(seq), nb))
                pushed += 1
                if len(heap) > max_heap_size:
                    max_heap_size = len(heap)

    if best is None:
        logger.warning(
            "[ML] NO ROUTE FOUND. pops=%d pushed=%d max_heap=%d "
            "label_systems=%d pruned_dominated=%d pruned_horizon=%d horizon=%.1f",
            pops,
            pushed,
            max_heap_size,
            len(label_table),
            pruned_dominated,
            pruned_horizon,
            horizon,
        )
        # Did we even reach the destination's neighborhood? Log how close.
        dest_labels = label_table.get(dest_id, [])
        if dest_labels:
            logger.warning(
                "[ML] dest_id %d has %d labels in label_table (min cost %.2f)",
                dest_id,
                len(dest_labels),
                min(lbl.cost for lbl in dest_labels),
            )
        else:
            logger.warning("[ML] dest_id %d was NEVER reached by the search.", dest_id)
        return None
    logger.info(
        "[ML] FOUND route cost=%.2f pops=%d pushed=%d max_heap=%d "
        "label_systems=%d pruned_horizon=%d",
        best.cost,
        pops,
        pushed,
        max_heap_size,
        len(label_table),
        pruned_horizon,
    )
    _progress(f"Multi-label found route at cost {best.cost:.1f} after {pops} pops")
    return _reconstruct_route(best, systems, danger)
