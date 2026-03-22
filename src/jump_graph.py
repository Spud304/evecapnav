import logging
from dataclasses import dataclass

import numpy as np

from src.constants import (
    METERS_PER_LY,
    ATTR_JUMP_DRIVE_RANGE,
    ATTR_JUMP_FUEL_CONSUMPTION,
    ATTR_JUMP_FATIGUE_MULTIPLIER,
    GROUP_CARRIER,
    GROUP_DREADNOUGHT,
    GROUP_FAX,
    GROUP_CAPITAL_INDUSTRIAL,
    GROUP_SUPERCARRIER,
    GROUP_TITAN,
    GROUP_BLACK_OPS,
    GROUP_JUMP_FREIGHTER,
    CAPITAL_GROUP_IDS,
)
from src.models.models import db

logger = logging.getLogger(__name__)

GROUP_LABELS = {
    GROUP_CARRIER: "Carrier",
    GROUP_DREADNOUGHT: "Dreadnought",
    GROUP_FAX: "FAX",
    GROUP_CAPITAL_INDUSTRIAL: "Rorqual",
    GROUP_SUPERCARRIER: "Supercarrier",
    GROUP_TITAN: "Titan",
    GROUP_BLACK_OPS: "Black Ops",
    GROUP_JUMP_FREIGHTER: "Jump Freighter",
}


@dataclass
class ShipClass:
    label: str
    group_ids: list[int]
    base_range_ly: float
    fuel_per_ly: float
    fatigue_multiplier: float  # 1.0 = no bonus, 0.1 = JF, 0.25 = blops


def load_ship_classes() -> dict[str, ShipClass]:
    """Load ship classes from SDE dogma attributes, grouped by shared parameters."""
    from sqlalchemy import text

    group_ids = sorted(CAPITAL_GROUP_IDS)
    group_placeholders = ", ".join(f":g{i}" for i in range(len(group_ids)))
    params = {f"g{i}": gid for i, gid in enumerate(group_ids)}
    params["a1"] = ATTR_JUMP_DRIVE_RANGE
    params["a2"] = ATTR_JUMP_FUEL_CONSUMPTION
    params["a3"] = ATTR_JUMP_FATIGUE_MULTIPLIER

    engine = db.engine
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                f"""
                SELECT t.groupID, da.attributeID, da.value
                FROM EveType t
                JOIN EveGroup g ON t.groupID = g.groupID
                JOIN TypeDogmaAttribute da ON t.typeID = da.typeID
                WHERE t.groupID IN ({group_placeholders})
                  AND da.attributeID IN (:a1, :a2, :a3)
                  AND t.published = 1
                """
            ),
            params,
        ).fetchall()

    # Aggregate by group: take the first value seen per attribute
    group_attrs: dict[int, dict[int, float]] = {}
    for group_id, attr_id, value in rows:
        if group_id not in group_attrs:
            group_attrs[group_id] = {}
        if attr_id not in group_attrs[group_id]:
            group_attrs[group_id][attr_id] = float(value)

    # Build ship classes, merging groups with identical parameters
    param_to_groups: dict[tuple, list[int]] = {}
    for gid, attrs in group_attrs.items():
        key = (
            attrs.get(ATTR_JUMP_DRIVE_RANGE, 3.5),
            attrs.get(ATTR_JUMP_FUEL_CONSUMPTION, 1000),
            attrs.get(ATTR_JUMP_FATIGUE_MULTIPLIER, 1.0),
        )
        param_to_groups.setdefault(key, []).append(gid)

    ship_classes = {}
    for (base_range, fuel, fatigue_mult), gids in param_to_groups.items():
        label = "/".join(GROUP_LABELS.get(g, str(g)) for g in sorted(gids))
        sc = ShipClass(
            label=label,
            group_ids=sorted(gids),
            base_range_ly=base_range,
            fuel_per_ly=fuel,
            fatigue_multiplier=fatigue_mult,
        )
        ship_classes[label] = sc

    if not ship_classes:
        logger.warning("No ship classes loaded from SDE, using fallback defaults")
        ship_classes = _fallback_ship_classes()

    return ship_classes


def _fallback_ship_classes() -> dict[str, ShipClass]:
    """Hardcoded fallback if SDE query fails."""
    classes = [
        ShipClass(
            "Carrier/Dreadnought/FAX",
            [GROUP_CARRIER, GROUP_DREADNOUGHT, GROUP_FAX],
            3.5,
            1000,
            1.0,
        ),
        ShipClass("Rorqual", [GROUP_CAPITAL_INDUSTRIAL], 5.0, 1000, 1.0),
        ShipClass(
            "Supercarrier/Titan", [GROUP_SUPERCARRIER, GROUP_TITAN], 3.0, 1000, 1.0
        ),
        ShipClass("Black Ops", [GROUP_BLACK_OPS], 4.0, 500, 0.25),
        ShipClass("Jump Freighter", [GROUP_JUMP_FREIGHTER], 5.0, 1000, 0.1),
    ]
    return {c.label: c for c in classes}


def get_effective_range(base_range: float, jdc_level: int) -> float:
    """Compute effective jump range with Jump Drive Calibration skill."""
    return base_range * (1 + 0.20 * jdc_level)


def build_jump_graph(
    systems: dict,  # dict[int, SystemInfo]
    max_range_ly: float,
) -> dict[int, list[tuple[int, float]]]:
    """Precompute adjacency list for all systems within max_range_ly.

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

        # Compute distances from chunk to all systems
        diff = chunk[:, np.newaxis, :] - coords[np.newaxis, :, :]  # (chunk, n, 3)
        dists = np.sqrt(np.sum(diff**2, axis=2))  # (chunk, n)

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
