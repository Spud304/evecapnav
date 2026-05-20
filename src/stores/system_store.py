"""System repository — reads `MapSolarSystem` + moon/gate counts.

Returns domain dataclasses (`SystemInfo`), not ORM rows.
"""

from sqlalchemy import func

from src.schemas.system import SystemInfo
from src.models.models import MapMoon, MapSolarSystem, MapStargate, db


def load_systems() -> dict[int, SystemInfo]:
    """Load all low/null k-space systems from SDE.

    Filters:
      - security < 0.5: canonical lowsec/hisec line. Caps can jump into
        lowsec but not hisec.
      - regionID < 11000000: excludes J-space (Anoikis), Pochven, Abyssal,
        Jove. K-space is 10000001-10000069.
    """
    rows = (
        db.session.query(MapSolarSystem)
        .filter(MapSolarSystem.security < 0.5)
        .filter(MapSolarSystem.regionID < 11000000)
        .all()
    )

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

    systems: dict[int, SystemInfo] = {}
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
