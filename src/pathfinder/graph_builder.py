"""Build the JD adjacency list from system 3D coordinates.

Pure computation — no DB access. Lives in the pathfinder package because
it's an algorithm input, not a data-access concern.
"""

import logging

import numpy as np

from src.constants import METERS_PER_LY
from src.schemas.system import SystemInfo

logger = logging.getLogger(__name__)


def build_jump_graph(
    systems: dict[int, SystemInfo],
    max_range_ly: float,
) -> dict[int, list[tuple[int, float]]]:
    """Precompute JD adjacency list for all systems within max_range_ly.

    Uses numpy vectorized distance for performance over ~7k systems.
    """
    sids = list(systems.keys())
    n = len(sids)
    if n == 0:
        return {}

    coords = np.array(
        [(systems[sid].x, systems[sid].y, systems[sid].z) for sid in sids]
    )

    max_range_m = max_range_ly * METERS_PER_LY
    graph: dict[int, list[tuple[int, float]]] = {sid: [] for sid in sids}

    # Process in chunks to avoid memory issues with large distance matrices
    chunk_size = 500
    for i_start in range(0, n, chunk_size):
        i_end = min(i_start + chunk_size, n)
        chunk = coords[i_start:i_end]  # (chunk_size, 3)

        diff = chunk[:, np.newaxis, :] - coords[np.newaxis, :, :]
        dists = np.sqrt(np.sum(diff**2, axis=2))

        for ci, i in enumerate(range(i_start, i_end)):
            for j in range(i + 1, n):
                d = dists[ci, j]
                if d <= max_range_m:
                    d_ly = d / METERS_PER_LY
                    graph[sids[i]].append((sids[j], d_ly))
                    graph[sids[j]].append((sids[i], d_ly))

    logger.info(
        "Jump graph built: %d systems, %d edges, max range %.1f LY",
        n,
        sum(len(v) for v in graph.values()) // 2,
        max_range_ly,
    )
    return graph
