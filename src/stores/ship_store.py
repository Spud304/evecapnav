"""Ship repository — reads `EveType` + `TypeDogmaAttribute` and constructs
`ShipClass` domain objects.
"""

import logging

from sqlalchemy import text

from src.constants import (
    ATTR_JUMP_DRIVE_RANGE,
    ATTR_JUMP_FATIGUE_MULTIPLIER,
    ATTR_JUMP_FUEL_CONSUMPTION,
    CAPITAL_GROUP_IDS,
    GROUP_BLACK_OPS,
    GROUP_CAPITAL_INDUSTRIAL,
    GROUP_CARRIER,
    GROUP_DREADNOUGHT,
    GROUP_FAX,
    GROUP_JUMP_FREIGHTER,
    GROUP_SUPERCARRIER,
    GROUP_TITAN,
)
from src.schemas.ship import GROUP_LABELS, ShipClass
from src.models.models import db

logger = logging.getLogger(__name__)


def load_ship_classes() -> dict[str, ShipClass]:
    """Load ship classes from SDE dogma attributes, grouped by shared parameters."""
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

    ship_classes: dict[str, ShipClass] = {}
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
    """Hardcoded fallback if SDE query fails. Values mirror current SDE dogma attrs."""
    classes = [
        ShipClass(
            "Carrier/Dreadnought/FAX",
            [GROUP_CARRIER, GROUP_DREADNOUGHT, GROUP_FAX],
            3.5,
            3000,
            1.0,
        ),
        ShipClass("Rorqual", [GROUP_CAPITAL_INDUSTRIAL], 5.0, 4000, 0.1),
        ShipClass(
            "Supercarrier/Titan", [GROUP_SUPERCARRIER, GROUP_TITAN], 3.0, 3000, 1.0
        ),
        ShipClass("Black Ops", [GROUP_BLACK_OPS], 4.0, 700, 0.25),
        ShipClass("Jump Freighter", [GROUP_JUMP_FREIGHTER], 5.0, 9000, 0.1),
    ]
    return {c.label: c for c in classes}


def load_cap_ship_types(
    ship_classes: dict[str, "ShipClass"],
) -> list[dict]:
    """Return all published, jump-capable cap ship types with their parent class label.

    [{type_id, type_name, group_id, class_label, base_range_ly}, ...]
    Group → class_label is derived by scanning ship_classes (a group can belong
    to exactly one merged class). Ships whose group isn't in any class are dropped.
    """
    group_to_label: dict[int, str] = {}
    group_to_range: dict[int, float] = {}
    group_to_fuel: dict[int, float] = {}
    group_to_fatigue: dict[int, float] = {}
    for label, sc in ship_classes.items():
        for gid in sc.group_ids:
            group_to_label[gid] = label
            group_to_range[gid] = sc.base_range_ly
            group_to_fuel[gid] = sc.fuel_per_ly
            group_to_fatigue[gid] = sc.fatigue_multiplier

    group_ids = sorted(group_to_label.keys())
    if not group_ids:
        return []
    placeholders = ", ".join(f":g{i}" for i in range(len(group_ids)))
    params = {f"g{i}": gid for i, gid in enumerate(group_ids)}

    with db.engine.connect() as conn:
        rows = conn.execute(
            text(
                f"""
                SELECT t.typeID, n.en, t.groupID
                FROM EveType t
                JOIN EveTypeName n ON n.parentTypeId = t.typeID
                WHERE t.groupID IN ({placeholders})
                  AND t.published = 1
                ORDER BY n.en
                """
            ),
            params,
        ).fetchall()

    return [
        {
            "type_id": int(type_id),
            "type_name": type_name,
            "group_id": int(group_id),
            "class_label": group_to_label[int(group_id)],
            "base_range_ly": group_to_range[int(group_id)],
            "fuel_per_ly": group_to_fuel[int(group_id)],
            "fatigue_multiplier": group_to_fatigue[int(group_id)],
        }
        for type_id, type_name, group_id in rows
        if int(group_id) in group_to_label
    ]


def get_effective_range(base_range: float, jdc_level: int) -> float:
    """Compute effective jump range with Jump Drive Calibration skill."""
    return base_range * (1 + 0.20 * jdc_level)
