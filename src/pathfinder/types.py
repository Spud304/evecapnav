"""Algorithm-internal types for the pathfinder package.

`Vertex` and the `JT_*` bitfield are pure search state — they never
leave the package. `RouteStep` (the wire-level output shape) lives in
`src.schemas.route`; we re-export it here for convenience so callers
can `from src.pathfinder.types import RouteStep, Vertex` if needed,
but the canonical definition is in schemas.
"""

from dataclasses import dataclass

from src.schemas.route import RouteStep  # re-exported for convenience

# Jump-type bitfield for Vertex.jump_type. Trimmed to the four edge
# classes evecapnav models: real JD edges, real gate edges, and two
# kinds of synthetic wait edges that advance time without moving.
JT_NONE = 0
JT_JUMP = 1  # Jump-drive (cyno) hop
JT_GATE = 2  # Stargate hop
JT_FATIGUE_WAIT = 4  # Pseudo-edge: waited for blue timer to decay
JT_COOLDOWN_WAIT = 8  # Pseudo-edge: waited for red timer to expire

# Hard cap on label expansions before we bail out and return the seed route.
# Prevents pathological label-table explosion on degenerate topologies.
_MAX_LABEL_POPS = 200_000


@dataclass(slots=True)
class Vertex:
    """One label in the multi-label Dijkstra search.

    Two labels at the same system are both retained iff neither dominates the
    other on (cost, est_fatigue_min) — see `_dominates`. This is what lets the
    search trade "wait longer here" against "different topology there."
    """

    sys_id: int
    cost: float
    time_seconds: float
    est_fatigue_min: float
    est_cooldown_min: float
    jump_type: int
    edge_type_str: str  # "jump" | "gate" | ""  (matches RouteStep.edge_type)
    distance_ly: float
    fuel_cost: int
    parent: "Vertex | None"
    segment_root: "Vertex | None" = None
    dominated: bool = False


__all__ = [
    "RouteStep",
    "Vertex",
    "JT_NONE",
    "JT_JUMP",
    "JT_GATE",
    "JT_FATIGUE_WAIT",
    "JT_COOLDOWN_WAIT",
    "_MAX_LABEL_POPS",
]
