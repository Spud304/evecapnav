"""Ship-class domain dataclass + the `groupID → label` mapping."""

from dataclasses import dataclass

from src.constants import (
    GROUP_BLACK_OPS,
    GROUP_CAPITAL_INDUSTRIAL,
    GROUP_CARRIER,
    GROUP_DREADNOUGHT,
    GROUP_FAX,
    GROUP_JUMP_FREIGHTER,
    GROUP_SUPERCARRIER,
    GROUP_TITAN,
)

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
