"""Celestial repository — reads `mapPlanet`, `mapMoon`, `mapAsteroidBelt`,
`mapStargate` and returns labeled `Celestial` lists per system.
"""

from sqlalchemy import text

from src.schemas.system import Celestial
from src.models.models import MapAsteroidBelt, MapMoon, MapPlanet, MapStargate, db

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


def load_celestials() -> dict[int, list[Celestial]]:
    """Load all celestial positions with labels, grouped by system."""
    celestials: dict[int, list[Celestial]] = {}

    def _ensure(sid: int) -> list[Celestial]:
        if sid not in celestials:
            celestials[sid] = [Celestial("Star", 0.0, 0.0, 0.0)]
        return celestials[sid]

    for p in db.session.query(MapPlanet).all():
        label = f"Planet {_roman(p.celestialIndex)}" if p.celestialIndex else "Planet"
        if p.solarSystemID is None or p.x is None or p.y is None or p.z is None:
            continue
        _ensure(p.solarSystemID).append(
            Celestial(label, float(p.x), float(p.y), float(p.z))
        )

    for m in db.session.query(MapMoon).all():
        planet = _roman(m.celestialIndex) if m.celestialIndex else "?"
        moon = str(m.orbitIndex) if m.orbitIndex else "?"
        if m.solarSystemID is None or m.x is None or m.y is None or m.z is None:
            continue
        _ensure(m.solarSystemID).append(
            Celestial(f"Moon {planet}-{moon}", float(m.x), float(m.y), float(m.z))
        )

    for b in db.session.query(MapAsteroidBelt).all():
        if b.solarSystemID is None or not b.positionX or not b.positionY or not b.positionZ:
            continue
        # mapAsteroidBelt mirrors mapMoon's structure: celestialIndex is the
        # parent planet (II, III, …) and orbitIndex is the belt number around
        # it. "Belt VII-1" reads the same as in-game and on dotlan, beats the
        # legacy "Belt" label which collapsed every rock anomaly to one name.
        if b.celestialIndex and b.orbitIndex:
            label = f"Belt {_roman(b.celestialIndex)}-{b.orbitIndex}"
        elif b.celestialIndex:
            label = f"Belt {_roman(b.celestialIndex)}"
        else:
            label = "Belt"
        _ensure(b.solarSystemID).append(
            Celestial(label, float(b.positionX), float(b.positionY), float(b.positionZ))
        )

    # Build stargate → destination system name lookup
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
        if g.solarSystemID is not None and g.x and g.y and g.z:
            dest_name = gate_dest_names.get(g.stargateID, "")
            label = f"Gate ({dest_name})" if dest_name else "Gate"
            _ensure(g.solarSystemID).append(
                Celestial(label, float(g.x), float(g.y), float(g.z))
            )

    return celestials
