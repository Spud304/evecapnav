"""Build a Flask app for the Playwright integration suite.

This factory deliberately avoids `tests/conftest.py::create_test_app` because
the unit-test seed has only 5 systems wired for unit-level pathfinder cases,
and we need a fork topology (origin -> {danger, safe} -> dest) plus dogma rows
for the ship classes we exercise in the FE.
"""

import os

from sqlalchemy import text

from src.application import Application
from src.celery_app import celery_init_app
from src.models.models import (
    db,
    MapSolarSystem,
    MapPlanet,
    SolarSystemName,
    EveType,
    EveTypeName,
    EveGroup,
)
from src.routes import RouteBlueprint, init_route_data

from tests.seeds.topology import (
    LY_METERS,
    AU_METERS,
    SYSTEM_COORDS,
    SYSTEM_NAMES,
    SHIP_TYPES,
    SHIP_GROUPS,
    SHIP_DOGMA,
    STARGATE_PAIRS,
)


def _create_static_tables() -> None:
    """Create SDE auxiliary tables that aren't ORM-mapped."""
    with db.engine.connect() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS TypeDogmaAttribute (
                    typeID INTEGER,
                    attributeID INTEGER,
                    value REAL,
                    PRIMARY KEY (typeID, attributeID)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS StargateDestination (
                    stargateID INTEGER PRIMARY KEY,
                    solarSystemID INTEGER,
                    destinationStargateID INTEGER
                )
                """
            )
        )
        conn.commit()


def _seed_topology() -> None:
    # Ship groups and types (so load_ship_classes finds at least one capital).
    for gid, cat in SHIP_GROUPS:
        db.session.merge(EveGroup(groupID=gid, categoryID=cat))
    for type_id, group_id, name in SHIP_TYPES:
        db.session.merge(EveType(typeID=type_id, groupID=group_id, published=1))
        db.session.merge(
            EveTypeName(
                parentTypeId=type_id, parentTypeId2=0, parentTypeCategory="", en=name
            )
        )
    # Flush ORM inserts before opening a raw engine connection — on SQLite the
    # ORM transaction otherwise blocks the raw write with "database is locked".
    db.session.commit()

    with db.engine.connect() as conn:
        for type_id, attr_id, value in SHIP_DOGMA:
            conn.execute(
                text(
                    "INSERT OR REPLACE INTO TypeDogmaAttribute (typeID, attributeID, value) "
                    "VALUES (:t, :a, :v)"
                ),
                {"t": type_id, "a": attr_id, "v": value},
            )
        conn.commit()

    # Solar systems
    for sid, sec, x_ly, y_ly, z_ly in SYSTEM_COORDS:
        db.session.merge(
            MapSolarSystem(
                solarSystemID=sid,
                security=sec,
                regionID=1,
                wormholeClassID=0,
                x=str(x_ly * LY_METERS),
                y=str(y_ly * LY_METERS),
                z=str(z_ly * LY_METERS),
            )
        )
        db.session.merge(
            SolarSystemName(
                parentTypeId=sid,
                parentTypeId2=0,
                parentTypeCategory="",
                en=SYSTEM_NAMES[sid],
            )
        )

    # Two planets per system spaced 10 AU apart so the safe-spot precompute
    # has something to work with (avoids NaNs in the FE).
    planet_id = 100_000
    for sid, _sec, _x, _y, _z in SYSTEM_COORDS:
        for offset_au in (0, 10):
            db.session.merge(
                MapPlanet(
                    planetID=planet_id,
                    solarSystemID=sid,
                    x=int(offset_au * AU_METERS),
                    y=0,
                    z=0,
                )
            )
            planet_id += 1

    db.session.commit()

    # Stargates — both mapStargate and StargateDestination are ORM tables
    # provisioned by db.create_all() from src/models/models.py. Use raw SQL
    # so we don't have to import the ORM class for a one-shot insert. Mirror
    # each pair so each gate is directional A→B + B→A; the planner reads it
    # as undirected via the SELF-JOIN in build_gate_graph.
    with db.engine.connect() as conn:
        for sg_a, sys_a, sg_b, sys_b in STARGATE_PAIRS:
            # Gate sg_a is physically located in sys_a and warps you to sys_b.
            conn.execute(
                text(
                    "INSERT OR REPLACE INTO mapStargate "
                    "(stargateID, solarSystemID, x, y, z) "
                    "VALUES (:gid, :sys, '0', '0', '0')"
                ),
                {"gid": sg_a, "sys": sys_a},
            )
            conn.execute(
                text(
                    "INSERT OR REPLACE INTO StargateDestination "
                    "(stargateID, solarSystemID) VALUES (:gid, :sys)"
                ),
                {"gid": sg_a, "sys": sys_b},
            )
            # Paired return gate sg_b in sys_b → sys_a.
            conn.execute(
                text(
                    "INSERT OR REPLACE INTO mapStargate "
                    "(stargateID, solarSystemID, x, y, z) "
                    "VALUES (:gid, :sys, '0', '0', '0')"
                ),
                {"gid": sg_b, "sys": sys_b},
            )
            conn.execute(
                text(
                    "INSERT OR REPLACE INTO StargateDestination "
                    "(stargateID, solarSystemID) VALUES (:gid, :sys)"
                ),
                {"gid": sg_b, "sys": sys_a},
            )
        conn.commit()


def create_integration_app(instance_path: str) -> Application:
    """Build a Flask app backed by in-memory SQLite + seeded fork topology.

    Caller is expected to have set EVECAPNAV_INSTANCE_PATH so the danger /
    zkill lookups in routes.py and tasks.py find the same `cache.sqlite` the
    test fixture writes to.
    """
    os.makedirs(instance_path, exist_ok=True)

    src_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "src",
    )
    app = Application("src.main", instance_path=instance_path, root_path=src_dir)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "integration-test-secret"
    # File-backed SQLite so the werkzeug serving thread (separate connection)
    # can read the same DB the seed step wrote to.
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        f"sqlite:///{os.path.join(instance_path, 'integration_sde.sqlite')}"
    )
    app.config["CELERY"] = {
        "broker_url": "memory://",
        "result_backend": "cache+memory://",
        "task_always_eager": True,
        "task_eager_propagates": True,
    }

    db.init_app(app)
    celery_init_app(app)

    app.register_blueprint(RouteBlueprint("routes", __name__))

    with app.app_context():
        db.create_all()
        _create_static_tables()
        _seed_topology()

    # init_route_data fetches systems, builds jump graph + gate graph (empty),
    # computes safe spots, and would try to hit ESI — we suppress that by
    # marking the cache as fresh first.
    from src.cache import mark_esi_updated

    mark_esi_updated(instance_path)

    init_route_data(app)
    return app
