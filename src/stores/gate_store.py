"""Stargate repository — reads `mapStargate` + `StargateDestination`."""

import logging

from sqlalchemy import text

from src.schemas.system import SystemInfo
from src.models.models import db

logger = logging.getLogger(__name__)


def build_gate_graph(
    systems: dict[int, SystemInfo],
) -> dict[int, list[tuple[int, bool, bool]]]:
    """Build stargate adjacency: src_sys -> [(dest_sys, cross_region, cross_constellation), ...].

    Reads MapStargate + StargateDestination from the SDE. Only includes edges
    where both endpoints are in the loaded `systems` dict (i.e. null/low k-space).
    """
    with db.engine.connect() as conn:
        # Verify required SDE tables exist before attempting the join — without
        # this, a missing table just produces a confusing OperationalError.
        existing = {
            row[0]
            for row in conn.execute(
                text(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name IN ('mapStargate', 'StargateDestination')"
                )
            ).fetchall()
        }
        missing = {"mapStargate", "StargateDestination"} - existing
        if missing:
            raise RuntimeError(
                f"SDE is missing required tables for gate routing: {sorted(missing)}. "
                "Re-download a recent SDE dump."
            )

        rows = conn.execute(
            text(
                """
                SELECT s.solarSystemID AS src_sys, d.solarSystemID AS dst_sys
                FROM mapStargate s
                JOIN StargateDestination d ON d.stargateID = s.stargateID
                """
            )
        ).fetchall()

    logger.info("Gate graph: read %d raw stargate rows from SDE", len(rows))

    graph: dict[int, list[tuple[int, bool, bool]]] = {sid: [] for sid in systems}
    edge_count = 0
    dropped_src = 0
    dropped_dst = 0
    for src, dst in rows:
        if src not in systems:
            dropped_src += 1
            continue
        if dst not in systems:
            dropped_dst += 1
            continue
        s_src = systems[src]
        s_dst = systems[dst]
        cross_region = s_src.region_id != s_dst.region_id
        cross_constellation = s_src.constellation_id != s_dst.constellation_id
        graph[src].append((dst, cross_region, cross_constellation))
        edge_count += 1

    # Sample 3 edges for sanity (helps confirm src/dst aren't swapped).
    sample = []
    for sid, edges in graph.items():
        if not edges:
            continue
        for dst, cross_r, _ in edges[:1]:
            sample.append(
                f"{systems[sid].name} -> {systems[dst].name}"
                + (" [cross-region]" if cross_r else "")
            )
        if len(sample) >= 3:
            break
    logger.info(
        "Gate graph built: %d systems, %d directed edges "
        "(dropped %d edges with src not loaded, %d with dst not loaded). Sample: %s",
        len(systems),
        edge_count,
        dropped_src,
        dropped_dst,
        ", ".join(sample) if sample else "<none>",
    )
    return graph
