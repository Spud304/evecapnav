"""Avoid-low-sec routing: exclusion set, pathfinder behavior, alternatives."""

import math

from src.constants import METERS_PER_LY
from src.pathfinder import find_route
from src.schemas.system import SystemInfo
from src.services.route_service import RouteService

ORIGIN, LOW_MID, NULL_MID, DEST = 1, 2, 3, 4

# Origin→(5,3) diagonal hop length used by the null-sec detour.
DIAG_LY = math.sqrt(5.0**2 + 3.0**2)


def _sys(sid: int, name: str, sec: float, x_ly: float, y_ly: float = 0.0) -> SystemInfo:
    return SystemInfo(
        system_id=sid,
        name=name,
        security=sec,
        x=x_ly * METERS_PER_LY,
        y=y_ly * METERS_PER_LY,
        z=0.0,
        region_id=10000001,
    )


def _fixture() -> tuple[dict[int, SystemInfo], dict[int, list[tuple[int, float]]]]:
    """Diamond: origin→dest is 10 LY (out of range at 7 LY). The short
    midpoint (5 LY per hop) is low-sec; the detour midpoint (5.83 LY per
    hop) is null-sec, so the default route prefers the low-sec hop.
    """
    systems = {
        ORIGIN: _sys(ORIGIN, "Origin", -0.2, 0.0),
        LOW_MID: _sys(LOW_MID, "LowMid", 0.3, 5.0),
        NULL_MID: _sys(NULL_MID, "NullMid", -0.5, 5.0, 3.0),
        DEST: _sys(DEST, "Dest", -0.8, 10.0),
    }
    graph = {
        ORIGIN: [(LOW_MID, 5.0), (NULL_MID, DIAG_LY), (DEST, 10.0)],
        LOW_MID: [(ORIGIN, 5.0), (DEST, 5.0), (NULL_MID, 3.0)],
        NULL_MID: [(ORIGIN, DIAG_LY), (DEST, DIAG_LY), (LOW_MID, 3.0)],
        DEST: [(LOW_MID, 5.0), (NULL_MID, DIAG_LY), (ORIGIN, 10.0)],
    }
    return systems, graph


def _service(systems: dict[int, SystemInfo]) -> RouteService:
    svc = RouteService()
    svc.systems.update(systems)
    return svc


def _route_ids(systems, graph, exclude: set[int] | None = None) -> list[int]:
    steps = find_route(
        origin_id=ORIGIN,
        dest_id=DEST,
        systems=systems,
        graph=graph,
        base_range_ly=7.0,
        jdc_level=0,
        fatigue_multiplier=1.0,
        fuel_per_ly=1000,
        exclude_systems=exclude,
    )
    return [s.system_id for s in steps]


class TestLowsecExclusions:
    def test_excludes_lowsec_keeps_nullsec(self):
        svc = _service(_fixture()[0])
        excl = svc.lowsec_exclusions(set())
        assert LOW_MID in excl
        assert NULL_MID not in excl

    def test_allowed_ids_are_carved_out(self):
        systems = _fixture()[0]
        systems[ORIGIN].security = 0.4  # low-sec staging origin
        svc = _service(systems)
        excl = svc.lowsec_exclusions({ORIGIN, DEST})
        assert ORIGIN not in excl
        assert LOW_MID in excl

    def test_zero_stored_sec_counts_as_lowsec(self):
        # Low-sec band is 0.0 <= stored sec < 0.5 — exactly 0.0 is low-sec.
        svc = _service({5: _sys(5, "ZeroSec", 0.0, 0.0)})
        assert 5 in svc.lowsec_exclusions(set())


class TestAvoidLowsecRouting:
    def test_default_route_takes_lowsec_shortcut(self):
        systems, graph = _fixture()
        assert _route_ids(systems, graph) == [ORIGIN, LOW_MID, DEST]

    def test_excluded_route_detours_through_nullsec(self):
        systems, graph = _fixture()
        svc = _service(systems)
        excl = svc.lowsec_exclusions({ORIGIN, DEST})
        assert _route_ids(systems, graph, exclude=excl) == [ORIGIN, NULL_MID, DEST]


class TestFindAlternativesLowsec:
    def test_lowsec_alternatives_filtered(self):
        systems, graph = _fixture()
        svc = _service(systems)
        svc.graph.update(graph)
        default_alts = {a["id"] for a in svc.find_alternatives(ORIGIN, set(), 7.0)}
        assert LOW_MID in default_alts
        filtered_alts = {
            a["id"]
            for a in svc.find_alternatives(ORIGIN, set(), 7.0, avoid_lowsec=True)
        }
        assert LOW_MID not in filtered_alts
        assert NULL_MID in filtered_alts
