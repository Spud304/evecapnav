import math
from dataclasses import dataclass

from src.constants import METERS_PER_LY, METERS_PER_AU
from src.models.models import (
    db,
    MapSolarSystem,
    MapPlanet,
    MapMoon,
    MapAsteroidBelt,
    MapStargate,
)

_ROMAN = {
    1: "I",
    2: "II",
    3: "III",
    4: "IV",
    5: "V",
    6: "VI",
    7: "VII",
    8: "VIII",
    9: "IX",
    10: "X",
    11: "XI",
    12: "XII",
    13: "XIII",
    14: "XIV",
    15: "XV",
    16: "XVI",
    17: "XVII",
    18: "XVIII",
}


def _roman(n: int) -> str:
    return _ROMAN.get(n, str(n))


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


def load_systems() -> dict[int, SystemInfo]:
    """Load all low/null k-space systems from SDE."""
    rows = (
        db.session.query(MapSolarSystem)
        .filter(MapSolarSystem.security < 0.45)
        .filter(
            (MapSolarSystem.wormholeClassID == 0)
            | (MapSolarSystem.wormholeClassID.is_(None))
        )
        .filter(MapSolarSystem.regionID < 14000000)  # exclude Jove space
        .all()
    )
    # Count moons and gates per system
    from sqlalchemy import func

    moon_counts = dict(
        db.session.query(MapMoon.solarSystemID, func.count(MapMoon.moonID))
        .group_by(MapMoon.solarSystemID)
        .all()
    )
    gate_counts = dict(
        db.session.query(MapStargate.solarSystemID, func.count(MapStargate.stargateID))
        .group_by(MapStargate.solarSystemID)
        .all()
    )

    systems = {}
    for r in rows:
        if r.x is None or r.y is None or r.z is None:
            continue
        systems[r.solarSystemID] = SystemInfo(
            system_id=r.solarSystemID,
            name=r.solarSystemName or str(r.solarSystemID),
            security=r.security or 0.0,
            x=float(r.x),
            y=float(r.y),
            z=float(r.z),
            region_id=r.regionID or 0,
            constellation_id=r.constellationID or 0,
            x2d=float(r.x2D) if r.x2D else 0.0,
            y2d=float(r.y2D) if r.y2D else 0.0,
            moon_count=moon_counts.get(r.solarSystemID, 0),
            gate_count=gate_counts.get(r.solarSystemID, 0),
        )
    return systems


def compute_distance_ly(
    x1: float, y1: float, z1: float, x2: float, y2: float, z2: float
) -> float:
    """Euclidean distance between two points in meters, converted to LY."""
    dx = x2 - x1
    dy = y2 - y1
    dz = z2 - z1
    return math.sqrt(dx * dx + dy * dy + dz * dz) / METERS_PER_LY


def load_celestials() -> dict[int, list[Celestial]]:
    """Load all celestial positions with labels, grouped by system."""
    celestials: dict[int, list[Celestial]] = {}

    def _ensure(sid: int) -> list[Celestial]:
        if sid not in celestials:
            celestials[sid] = [Celestial("Star", 0.0, 0.0, 0.0)]
        return celestials[sid]

    for p in db.session.query(MapPlanet).all():
        label = f"Planet {_roman(p.celestialIndex)}" if p.celestialIndex else "Planet"
        _ensure(p.solarSystemID).append(
            Celestial(label, float(p.x), float(p.y), float(p.z))
        )

    for m in db.session.query(MapMoon).all():
        planet = _roman(m.celestialIndex) if m.celestialIndex else "?"
        moon = str(m.orbitIndex) if m.orbitIndex else "?"
        _ensure(m.solarSystemID).append(
            Celestial(f"Moon {planet}-{moon}", float(m.x), float(m.y), float(m.z))
        )

    for b in db.session.query(MapAsteroidBelt).all():
        if b.positionX and b.positionY and b.positionZ:
            _ensure(b.solarSystemID).append(
                Celestial(
                    "Belt", float(b.positionX), float(b.positionY), float(b.positionZ)
                )
            )

    # Build stargate → destination system name lookup
    from sqlalchemy import text

    gate_dest_names: dict[int, str] = {}
    with db.engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT d.stargateID, n.en
                FROM StargateDestination d
                JOIN SolarSystemName n
                  ON n.parentTypeId = d.solarSystemID
                  AND n.parentTypeCategory = ''
            """)
        ).fetchall()
        for gate_id, name in rows:
            gate_dest_names[gate_id] = name

    for g in db.session.query(MapStargate).all():
        if g.x and g.y and g.z:
            dest_name = gate_dest_names.get(g.stargateID, "")
            label = f"Gate ({dest_name})" if dest_name else "Gate"
            _ensure(g.solarSystemID).append(
                Celestial(label, float(g.x), float(g.y), float(g.z))
            )

    return celestials


@dataclass
class SafeSpotResult:
    """Best safe spot for a system."""

    nearest_au: float  # distance from midpoint to nearest other celestial
    warp_between: str  # "Planet IV ↔ Moon VIII-3"
    nearest_label: str  # label of nearest celestial to midpoint


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

    # Process in chunks to limit memory (each chunk needs n_chunk × n × 3 floats)
    chunk_size = 2000
    for start in range(0, n_pairs, chunk_size):
        end = min(start + chunk_size, n_pairs)
        ci = ii[start:end]
        cj = jj[start:end]

        midpoints = (coords[ci] + coords[cj]) / 2.0  # (chunk, 3)

        # Distance from each midpoint to all celestials: (chunk, n)
        diffs = midpoints[:, np.newaxis, :] - coords[np.newaxis, :, :]
        dists_sq = np.sum(diffs**2, axis=2)

        # Mask the pair celestials
        chunk_indices = np.arange(len(ci))
        dists_sq[chunk_indices, ci] = np.inf
        dists_sq[chunk_indices, cj] = np.inf

        # Nearest celestial per midpoint
        min_dists = np.min(dists_sq, axis=1)
        min_indices = np.argmin(dists_sq, axis=1)

        # Best in this chunk
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
