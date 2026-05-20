"""Diagnostic / observability helpers for the pathfinder.

`_bfs_reachability` is the only function consumed by the dispatcher beyond
the algorithm itself. The `_log_*` helpers are invoked from the dispatcher
when BFS reveals an unreachable route, to help triage whether the failure
is a graph-data issue or an algorithm issue.

numpy is imported at module level (was a late import in the pre-refactor
monolith); numpy is already required by the rest of the project.
"""

import logging
import math
from collections import deque

import numpy as np

from src.constants import METERS_PER_LY
from src.schemas.system import SystemInfo

logger = logging.getLogger(__name__)


def _bfs_reachability(
    origin_id: int,
    dest_id: int,
    graph: dict[int, list[tuple[int, float]]],
    effective_range: float,
) -> tuple[bool, int, set[int]]:
    """Plain BFS over the JD graph at the given effective range. Returns
    (reachable, min_hops, visited_set). Diagnostic only — independent
    of cost/fatigue heuristics, so it tells us whether a route is *possible*
    in the graph regardless of any algorithm's cost model.
    """
    if origin_id == dest_id:
        return True, 0, {origin_id}
    visited = {origin_id}
    queue: deque[tuple[int, int]] = deque([(origin_id, 0)])
    while queue:
        sys_id, hops = queue.popleft()
        for nb, d in graph.get(sys_id, []):
            if d > effective_range or nb in visited:
                continue
            if nb == dest_id:
                visited.add(nb)
                return True, hops + 1, visited
            visited.add(nb)
            queue.append((nb, hops + 1))
    return False, -1, visited


def _log_dotlan_chain_membership(
    systems: dict[int, SystemInfo],
    graph: dict[int, list[tuple[int, float]]],
    bfs_origin_set: set[int],
    effective_range: float,
    dest_id: int,
) -> None:
    """Log per-system membership + per-edge presence for a known-good
    Dotlan 1DH-SX → AXDX-F lowsec-bridging route. Used to verify whether
    capnav's load_systems filter is excluding lowsec bridge systems.
    """
    chain_names = [
        "1DH-SX",
        "SKR-SP",
        "Schmaeel",
        "Perbhe",
        "Marmeha",
        "Lela",
        "Menai",
        "Gademam",
        "Nomash",
        "Ziriert",
        "TU-RI6",
        "INQ-WR",
        "A-803L",
        "3L3N-X",
        "YF-P4X",
        "R-XDKM",
        "73-JQO",
        "AXDX-F",
    ]
    name_to_sys = {s.name: s for s in systems.values()}
    _, _, dest_bfs_set = _bfs_reachability(dest_id, -1, graph, effective_range)
    logger.warning("[dotlan-chain] Membership check:")
    for name in chain_names:
        s = name_to_sys.get(name)
        if s is None:
            logger.warning(
                "  %-9s: NOT IN SYSTEMS DICT (filtered out by load_systems)", name
            )
            continue
        in_origin = s.system_id in bfs_origin_set
        in_dest = s.system_id in dest_bfs_set
        neighbors = graph.get(s.system_id, [])
        in_range = sum(1 for _, d in neighbors if d <= effective_range)
        cluster = "ORIGIN" if in_origin else ("DEST" if in_dest else "ORPHANED")
        logger.warning(
            "  %-9s id=%d region=%d sec=%.3f cluster=%-8s in_range=%d",
            name,
            s.system_id,
            s.region_id,
            s.security,
            cluster,
            in_range,
        )
    logger.warning("[dotlan-chain] Edge presence check:")
    for i in range(len(chain_names) - 1):
        a_name, b_name = chain_names[i], chain_names[i + 1]
        a = name_to_sys.get(a_name)
        b = name_to_sys.get(b_name)
        if a is None or b is None:
            logger.warning(
                "  %s -> %s: SKIP (missing: %s)",
                a_name,
                b_name,
                ",".join(n for n, x in [(a_name, a), (b_name, b)] if x is None),
            )
            continue
        edge = next(
            ((d) for nb_id, d in graph.get(a.system_id, []) if nb_id == b.system_id),
            None,
        )
        raw_ly = (
            math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2)
            / METERS_PER_LY
        )
        if edge is None:
            logger.warning(
                "  %s -> %s: MISSING from graph (raw=%.3f LY)",
                a_name,
                b_name,
                raw_ly,
            )
        else:
            note = (
                ""
                if edge <= effective_range
                else f" EXCEEDS eff_range {effective_range}"
            )
            logger.warning(
                "  %s -> %s: graph_d=%.3f LY%s",
                a_name,
                b_name,
                edge,
                note,
            )


def _log_cross_cluster_gap(
    bfs_set: set[int],
    systems: dict[int, SystemInfo],
    effective_range: float,
    dest_id: int,
) -> None:
    """Compute the smallest raw-coord distance between any system in
    bfs_set and any system NOT in bfs_set. If that distance is less than
    `effective_range`, the JD graph build is missing edges (real bug).
    If it's greater, the cluster is genuinely isolated in the loaded
    coordinate data.
    """
    in_items = [(sid, systems[sid]) for sid in bfs_set if sid in systems]
    out_items = [(sid, s) for sid, s in systems.items() if sid not in bfs_set]
    if not in_items or not out_items:
        logger.warning("[find_route] gap diagnostic: empty cluster, skipping")
        return

    in_coords = np.array([(s.x, s.y, s.z) for _, s in in_items], dtype=np.float64)
    out_coords = np.array([(s.x, s.y, s.z) for _, s in out_items], dtype=np.float64)

    # All-pairs squared distance (n_in × n_out). At ~232 × ~3800 = ~900k
    # pairs this is well under memory budget; avoids double-loop in Python.
    diff = in_coords[:, np.newaxis, :] - out_coords[np.newaxis, :, :]
    dists_sq = np.sum(diff**2, axis=2)
    min_idx_flat = int(np.argmin(dists_sq))
    n_out = len(out_items)
    in_idx = min_idx_flat // n_out
    out_idx = min_idx_flat % n_out
    min_d_ly = float(np.sqrt(dists_sq[in_idx, out_idx])) / METERS_PER_LY

    a_sid, a = in_items[in_idx]
    b_sid, b = out_items[out_idx]
    logger.warning(
        "[find_route] MIN cross-cluster gap = %.3f LY "
        "(in=%s/%d region=%d ↔ out=%s/%d region=%d). "
        "%s",
        min_d_ly,
        a.name,
        a_sid,
        a.region_id,
        b.name,
        b_sid,
        b.region_id,
        (
            f"GAP <= range ({effective_range:.2f}LY) — graph BUILD is missing this edge."
            if min_d_ly <= effective_range
            else f"GAP > range ({effective_range:.2f}LY) — capnav's coords genuinely separate these clusters at this range."
        ),
    )

    # Also show the closest 5 cross-cluster pairs to see if there's a
    # cluster of just-too-far edges (precision issue) or a single odd one.
    flat_dists = dists_sq.ravel()
    closest_n = min(5, len(flat_dists))
    top_idx = np.argpartition(flat_dists, closest_n - 1)[:closest_n]
    top_idx = top_idx[np.argsort(flat_dists[top_idx])]
    logger.warning("[find_route] Top %d closest cross-cluster pairs:", closest_n)
    for k, flat_i in enumerate(top_idx):
        ii = int(flat_i) // n_out
        jj = int(flat_i) % n_out
        d_ly = float(np.sqrt(flat_dists[flat_i])) / METERS_PER_LY
        ain_sid, ain = in_items[ii]
        aout_sid, aout = out_items[jj]
        logger.warning(
            "  [%d] %.3f LY: %s (%d, r=%d) -> %s (%d, r=%d)%s",
            k + 1,
            d_ly,
            ain.name,
            ain_sid,
            ain.region_id,
            aout.name,
            aout_sid,
            aout.region_id,
            "  <-- DESTINATION" if aout_sid == dest_id else "",
        )
