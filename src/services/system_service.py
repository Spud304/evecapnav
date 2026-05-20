"""System search + safe-spot scoring.

The autocomplete `/api/systems/search` endpoint hits MapSolarSystem
directly; the safe-spot scoring runs at startup as part of
`RouteService.initialize()`.
"""

import logging
import math

from src.constants import METERS_PER_AU
from src.schemas.system import Celestial, SafeSpotResult
from src.models.models import MapSolarSystem, SolarSystemName, db

logger = logging.getLogger(__name__)


class SystemService:
    """Holds no in-memory state; takes the Flask app via constructor only
    so signatures stay consistent with the other services."""

    def search(self, q: str, limit: int = 10) -> list[dict]:
        """Autocomplete system name prefix search."""
        q = q.strip()
        if len(q) < 2:
            return []

        results = (
            db.session.query(
                SolarSystemName.parentTypeId,
                SolarSystemName.en,
                MapSolarSystem.security,
            )
            .join(
                MapSolarSystem,
                SolarSystemName.parentTypeId == MapSolarSystem.solarSystemID,
            )
            .filter(SolarSystemName.parentTypeCategory == "")
            .filter(SolarSystemName.en.ilike(f"{q}%"))
            .limit(limit)
            .all()
        )

        return [
            {
                "id": r[0],
                "name": r[1],
                "security": round(r[2], 2) if r[2] else 0.0,
            }
            for r in results
        ]


def compute_best_safe_spot(celestials: list[Celestial]) -> SafeSpotResult:
    """Find the best safe spot by evaluating midpoints of all celestial pairs.

    For each pair, compute the midpoint (where you'd bookmark mid-warp).
    The quality = distance from that midpoint to the nearest OTHER celestial.
    The best safe spot = the pair whose midpoint is farthest from everything.

    Uses numpy for vectorized distance computation. For systems with many
    celestials (100+), processes pairs in chunks to avoid memory issues.
    """
    import numpy as np

    n = len(celestials)
    if n < 3:
        if n == 2:
            a, b = celestials[0], celestials[1]
            gap = math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2) / (
                2 * METERS_PER_AU
            )
            return SafeSpotResult(gap, f"{a.label} ↔ {b.label}", "")
        return SafeSpotResult(0.0, "", "")

    coords = np.array([(c.x, c.y, c.z) for c in celestials])
    ii, jj = np.triu_indices(n, k=1)
    n_pairs = len(ii)

    best_nearest_dist_sq = 0.0
    best_pair_idx = 0
    best_nearest_k = 0

    chunk_size = 2000
    for start in range(0, n_pairs, chunk_size):
        end = min(start + chunk_size, n_pairs)
        ci = ii[start:end]
        cj = jj[start:end]

        midpoints = (coords[ci] + coords[cj]) / 2.0
        diffs = midpoints[:, np.newaxis, :] - coords[np.newaxis, :, :]
        dists_sq = np.sum(diffs**2, axis=2)

        chunk_indices = np.arange(len(ci))
        dists_sq[chunk_indices, ci] = np.inf
        dists_sq[chunk_indices, cj] = np.inf

        min_dists = np.min(dists_sq, axis=1)
        min_indices = np.argmin(dists_sq, axis=1)

        chunk_best = np.argmax(min_dists)
        if min_dists[chunk_best] > best_nearest_dist_sq:
            best_nearest_dist_sq = float(min_dists[chunk_best])
            best_pair_idx = start + int(chunk_best)
            best_nearest_k = int(min_indices[chunk_best])

    best_i = int(ii[best_pair_idx])
    best_j = int(jj[best_pair_idx])

    nearest_au = math.sqrt(best_nearest_dist_sq) / METERS_PER_AU
    warp = f"{celestials[best_i].label} ↔ {celestials[best_j].label}"
    nearest = celestials[best_nearest_k].label
    return SafeSpotResult(nearest_au, warp, nearest)


def precompute_safety_scores(
    system_ids: set[int],
    all_celestials: dict[int, list[Celestial]],
) -> dict[int, SafeSpotResult]:
    """Compute best safe spot for each system."""
    scores = {}
    for sid in system_ids:
        cels = all_celestials.get(sid, [])
        scores[sid] = compute_best_safe_spot(cels)
    return scores
