"""Backwards-compat shim.

Functions moved to:
  - `src.domain.ship` — ShipClass, GROUP_LABELS
  - `src.repositories.ship_repository` — load_ship_classes,
    _fallback_ship_classes, get_effective_range
  - `src.repositories.gate_repository` — build_gate_graph
  - `src.pathfinder.graph_builder` — build_jump_graph (pure computation,
    moved to live next to the algorithm)

Keeping the legacy import path here so callers and tests don't break
through Phase G of the layered restructure.
"""

from src.schemas.ship import GROUP_LABELS, ShipClass  # noqa: F401
from src.pathfinder.graph_builder import build_jump_graph  # noqa: F401
from src.stores.gate_store import build_gate_graph  # noqa: F401
from src.stores.ship_store import (  # noqa: F401
    _fallback_ship_classes,
    get_effective_range,
    load_ship_classes,
)

__all__ = [
    "ShipClass",
    "GROUP_LABELS",
    "load_ship_classes",
    "_fallback_ship_classes",
    "get_effective_range",
    "build_jump_graph",
    "build_gate_graph",
]
