import os
import tempfile

os.environ.setdefault("STATIC_DB", "test_static")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

import pytest
from sqlalchemy import text


@pytest.fixture(autouse=True, scope="session")
def _isolate_instance_path(tmp_path_factory):
    """Redirect cache.sqlite writes to a tempdir so tests never touch src/instance/."""
    tmp = str(tmp_path_factory.mktemp("evecapnav_test_instance"))
    previous = os.environ.get("EVECAPNAV_INSTANCE_PATH")
    os.environ["EVECAPNAV_INSTANCE_PATH"] = tmp
    try:
        yield tmp
    finally:
        if previous is None:
            os.environ.pop("EVECAPNAV_INSTANCE_PATH", None)
        else:
            os.environ["EVECAPNAV_INSTANCE_PATH"] = previous


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


def _seed_static_data():
    """Insert minimal SDE fixture data for jump route planner tests."""
    engine = db.engine
    with engine.connect() as conn:
        conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS TypeDogmaAttribute (
                typeID INTEGER,
                attributeID INTEGER,
                value REAL,
                PRIMARY KEY (typeID, attributeID)
            )
        """)
        )
        conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS StargateDestination (
                stargateID INTEGER PRIMARY KEY,
                solarSystemID INTEGER,
                destinationStargateID INTEGER
            )
        """)
        )
        conn.commit()

    # Ship groups (capital ships)
    groups = [
        EveGroup(groupID=547, categoryID=6),  # Carrier
        EveGroup(groupID=485, categoryID=6),  # Dreadnought
        EveGroup(groupID=1538, categoryID=6),  # FAX
        EveGroup(groupID=898, categoryID=6),  # Black Ops
        EveGroup(groupID=902, categoryID=6),  # Jump Freighter
    ]
    for g in groups:
        db.session.merge(g)

    # Ship types
    ship_types = [
        EveType(typeID=23757, groupID=547, published=1),  # Archon (Carrier)
        EveType(typeID=19720, groupID=485, published=1),  # Revelation (Dread)
        EveType(typeID=22428, groupID=898, published=1),  # Sin (Black Ops)
        EveType(typeID=28848, groupID=902, published=1),  # Rhea (JF)
    ]
    for t in ship_types:
        db.session.merge(t)

    type_names = [
        EveTypeName(
            parentTypeId=23757, parentTypeId2=0, parentTypeCategory="", en="Archon"
        ),
        EveTypeName(
            parentTypeId=19720, parentTypeId2=0, parentTypeCategory="", en="Revelation"
        ),
        EveTypeName(
            parentTypeId=22428, parentTypeId2=0, parentTypeCategory="", en="Sin"
        ),
        EveTypeName(
            parentTypeId=28848, parentTypeId2=0, parentTypeCategory="", en="Rhea"
        ),
    ]
    for tn in type_names:
        db.session.merge(tn)

    # Dogma attributes for ships
    with engine.connect() as conn:
        conn.execute(
            text("""
            INSERT OR REPLACE INTO TypeDogmaAttribute (typeID, attributeID, value)
            VALUES
                (23757, 867, 3.5),  -- Archon jump range
                (23757, 868, 1000), -- Archon fuel/LY
                (19720, 867, 3.5),  -- Revelation jump range
                (19720, 868, 1000),
                (22428, 867, 4.0),  -- Sin jump range
                (22428, 868, 500),
                (22428, 1971, 0.25), -- Sin fatigue multiplier
                (28848, 867, 5.0),  -- Rhea jump range
                (28848, 868, 1000),
                (28848, 1971, 0.1)  -- Rhea fatigue multiplier
        """)
        )
        conn.commit()

    # Low/null-sec solar systems with known coordinates
    # System A: origin (null-sec)
    # System B: ~5 LY from A (null-sec)
    # System C: ~8 LY from A, ~4 LY from B (null-sec)
    # System D: ~15 LY from A (unreachable for most ships)
    # 1 LY = 9.461e15 meters
    ly = 9.461e15
    systems = [
        MapSolarSystem(
            solarSystemID=90000001,
            security=-0.5,
            regionID=1,
            wormholeClassID=0,
            x=str(0),
            y=str(0),
            z=str(0),
        ),
        MapSolarSystem(
            solarSystemID=90000002,
            security=-0.3,
            regionID=1,
            wormholeClassID=0,
            x=str(5 * ly),
            y=str(0),
            z=str(0),
        ),
        MapSolarSystem(
            solarSystemID=90000003,
            security=-0.1,
            regionID=1,
            wormholeClassID=0,
            x=str(8 * ly),
            y=str(0),
            z=str(0),
        ),
        MapSolarSystem(
            solarSystemID=90000004,
            security=-0.8,
            regionID=1,
            wormholeClassID=0,
            x=str(20 * ly),
            y=str(0),
            z=str(0),
        ),
        # High-sec system (should be excluded from jump graph)
        MapSolarSystem(
            solarSystemID=90000005,
            security=0.9,
            regionID=2,
            wormholeClassID=0,
            x=str(2 * ly),
            y=str(0),
            z=str(0),
        ),
    ]
    for s in systems:
        db.session.merge(s)

    system_names = [
        SolarSystemName(
            parentTypeId=90000001,
            parentTypeId2=0,
            parentTypeCategory="",
            en="TestOrigin",
        ),
        SolarSystemName(
            parentTypeId=90000002, parentTypeId2=0, parentTypeCategory="", en="TestMid"
        ),
        SolarSystemName(
            parentTypeId=90000003, parentTypeId2=0, parentTypeCategory="", en="TestDest"
        ),
        SolarSystemName(
            parentTypeId=90000004, parentTypeId2=0, parentTypeCategory="", en="TestFar"
        ),
        SolarSystemName(
            parentTypeId=90000005,
            parentTypeId2=0,
            parentTypeCategory="",
            en="TestHighSec",
        ),
    ]
    for sn in system_names:
        db.session.merge(sn)

    # Celestial positions for safe spot testing
    # System A: planets spread out > 14.3 AU apart
    au = 149_597_870_700
    planets_a = [
        MapPlanet(planetID=100001, solarSystemID=90000001, x=0, y=0, z=0),
        MapPlanet(planetID=100002, solarSystemID=90000001, x=int(20 * au), y=0, z=0),
    ]
    for p in planets_a:
        db.session.merge(p)

    # System B: planets close together (< 14.3 AU)
    planets_b = [
        MapPlanet(planetID=100003, solarSystemID=90000002, x=0, y=0, z=0),
        MapPlanet(planetID=100004, solarSystemID=90000002, x=int(5 * au), y=0, z=0),
    ]
    for p in planets_b:
        db.session.merge(p)

    db.session.commit()


def create_test_app():
    """Build a Flask app configured for testing with in-memory SQLite."""
    tmp = tempfile.mkdtemp()
    src_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"
    )
    app = Application("src.main", instance_path=tmp, root_path=src_dir)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret-key"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"

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
        _seed_static_data()

    init_route_data(app)

    return app


@pytest.fixture(scope="session")
def app():
    """Session-scoped test app."""
    return create_test_app()


@pytest.fixture(autouse=True)
def _cleanup(app):
    """Reset DB session after each test."""
    yield
    with app.app_context():
        db.session.remove()


@pytest.fixture()
def client(app):
    """Per-test Flask test client."""
    return app.test_client()
