"""Solar-system domain dataclasses. Pure data — no I/O, no DB, no behavior
beyond storage. Constructed by repositories and consumed by services.
"""

from dataclasses import dataclass


@dataclass
class SystemInfo:
    system_id: int
    name: str
    security: float
    x: float
    y: float
    z: float
    region_id: int
    constellation_id: int = 0
    x2d: float = 0.0
    y2d: float = 0.0
    safe_spot_au: float = 0.0
    safe_spot_warp: str = ""
    safe_spot_nearest: str = ""
    moon_count: int = 0
    gate_count: int = 0
    sov_alliance_name: str = ""
    sov_faction_name: str = ""


@dataclass
class Celestial:
    label: str
    x: float
    y: float
    z: float


@dataclass
class SafeSpotResult:
    """Best safe spot for a system."""

    nearest_au: float  # distance from midpoint to nearest other celestial
    warp_between: str  # "Planet IV ↔ Moon VIII-3"
    nearest_label: str  # label of nearest celestial to midpoint
