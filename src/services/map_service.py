"""Map data service — orchestrates the star-map data payload.

Reads systems, regions, and gates directly from the SDE (not from the
routing graph) so the map shows hi-sec systems too even though they're
un-routable for caps.
"""

import logging

from sqlalchemy import text

from src.constants import METERS_PER_LY
from src.models.models import db
from src.stores.intel_cache_store import load_sovereignty

logger = logging.getLogger(__name__)


class MapService:
    """Builds the `/api/map/data` response: every K-space system + region
    centroids + undirected gate edges, projected to the classic top-down
    Dotlan-style `(x, -z)` layout in light-years.
    """

    def __init__(self, instance_path: str) -> None:
        self.instance_path = instance_path

    def get_map_data(self) -> dict:
        region_names: dict[int, str] = {}
        with db.engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT parentTypeId, en FROM RegionName "
                    "WHERE parentTypeCategory = ''"
                )
            ).fetchall()
            for rid, name in rows:
                region_names[rid] = name

            # All K-space systems (hi/low/null). Pochven (10000070) and
            # J-space (11000001+) excluded via the region-ID range.
            sys_rows = conn.execute(
                text(
                    """
                    SELECT ms.solarSystemID, ms.regionID, ms.securityStatus,
                           ms.x, ms.y, ms.z, sn.en
                    FROM mapSolarSystem ms
                    LEFT JOIN SolarSystemName sn
                      ON sn.parentTypeId = ms.solarSystemID
                      AND sn.parentTypeCategory = ''
                    WHERE ms.regionID < 11000000
                      AND ms.x IS NOT NULL
                    """
                )
            ).fetchall()

            gate_rows = conn.execute(
                text(
                    """
                    SELECT s.solarSystemID AS src, d.solarSystemID AS dst
                    FROM mapStargate s
                    JOIN StargateDestination d
                      ON d.stargateID = s.stargateID
                    """
                )
            ).fetchall()

        # Sov info from the local cache — covers cap-routable systems.
        # Hi-sec systems just get an empty string in the response.
        sov_map = load_sovereignty(self.instance_path)
        sov_by_id: dict[int, str] = {
            sid: (info.get("alliance_name") or info.get("faction_name") or "")
            for sid, info in sov_map.items()
        }

        systems_json: list[dict] = []
        region_centroids: dict[int, list[float]] = {}
        region_counts: dict[int, int] = {}
        system_region: dict[int, int] = {}
        for sid, rid, sec, x, y, z, name in sys_rows:
            if x is None or y is None or z is None:
                continue
            try:
                fx = float(x)
                fz = float(z)
            except (TypeError, ValueError):
                continue
            px = fx / METERS_PER_LY
            py = -fz / METERS_PER_LY
            systems_json.append(
                {
                    "id": sid,
                    "name": name or str(sid),
                    "x": px,
                    "y": py,
                    "sec": round(float(sec), 2) if sec is not None else 0.0,
                    "region_id": rid or 0,
                    "sov": sov_by_id.get(sid, ""),
                }
            )
            if rid:
                acc = region_centroids.setdefault(rid, [0.0, 0.0])
                acc[0] += px
                acc[1] += py
                region_counts[rid] = region_counts.get(rid, 0) + 1
                system_region[sid] = rid

        regions_json = [
            {
                "id": rid,
                "name": region_names.get(rid, str(rid)),
                "x": acc[0] / region_counts[rid],
                "y": acc[1] / region_counts[rid],
                "system_count": region_counts[rid],
            }
            for rid, acc in region_centroids.items()
        ]

        # Undirected gate edges. Each stargate has two rows in the SDE
        # (one per side); dedupe by always storing (min, max).
        edges_json: list[list] = []
        seen: set[tuple[int, int]] = set()
        for src, dst in gate_rows:
            if src is None or dst is None:
                continue
            if src not in system_region or dst not in system_region:
                continue
            a, b = (src, dst) if src < dst else (dst, src)
            if (a, b) in seen:
                continue
            seen.add((a, b))
            cross_region = 1 if system_region[a] != system_region[b] else 0
            edges_json.append([a, b, cross_region])

        return {
            "systems": systems_json,
            "regions": regions_json,
            "gate_edges": edges_json,
        }
