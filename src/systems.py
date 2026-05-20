"""Backwards-compat shim.

Functions moved during the layered restructure:
  - `src.domain.system` — SystemInfo, Celestial, SafeSpotResult (dataclasses)
  - `src.repositories.system_repository` — load_systems
  - `src.repositories.celestial_repository` — load_celestials
  - `src.services.system_service` — compute_best_safe_spot,
    precompute_safety_scores
  - `src.pathfinder.cost` — compute_distance_ly (used by the algorithm)

Keeping the legacy module path here so older callers and tests don't
break. New code should import from the canonical locations above.
"""

from src.constants import METERS_PER_AU, METERS_PER_LY  # noqa: F401
from src.schemas.system import (  # noqa: F401
    Celestial,
    SafeSpotResult,
    SystemInfo,
)
from src.pathfinder.cost import compute_distance_ly  # noqa: F401
from src.stores.celestial_store import load_celestials  # noqa: F401
from src.stores.system_store import load_systems  # noqa: F401
from src.services.system_service import (  # noqa: F401
    compute_best_safe_spot,
    precompute_safety_scores,
)

__all__ = [
    "SystemInfo",
    "Celestial",
    "SafeSpotResult",
    "load_systems",
    "load_celestials",
    "compute_distance_ly",
    "compute_best_safe_spot",
    "precompute_safety_scores",
    "METERS_PER_LY",
    "METERS_PER_AU",
]
