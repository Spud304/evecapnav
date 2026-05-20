"""Route domain dataclass.

`RouteStep` is the wire-level shape returned to the API — one row per
hop in a planned route. Lives in `domain/` because it's a domain entity,
not an algorithm internal. The pathfinder *produces* a list of these
but doesn't use them in its search state (that's `Vertex`).
"""

from dataclasses import asdict, dataclass


@dataclass
class RouteStep:
    system_id: int
    system_name: str
    security: float
    distance_ly: float
    wait_minutes: float
    fatigue_after_minutes: float
    fuel_cost: int
    kills_per_hour: int
    jumps_per_hour: int
    safe_spot_au: float
    safe_spot_warp: str
    safe_spot_nearest: str
    moon_count: int
    gate_count: int
    sov_owner: str
    edge_type: str = "jump"  # "jump" for jump-drive hops, "gate" for stargate hops

    def to_dict(self) -> dict:
        return asdict(self)


__all__ = ["RouteStep"]
