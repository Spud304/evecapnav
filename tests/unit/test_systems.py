from src.systems import (
    Celestial,
    compute_distance_ly,
    compute_best_safe_spot,
    load_systems,
    load_celestials,
    precompute_safety_scores,
)
from src.constants import METERS_PER_LY, METERS_PER_AU


class TestDistanceCalc:
    def test_same_point_is_zero(self):
        assert compute_distance_ly(0, 0, 0, 0, 0, 0) == 0.0

    def test_known_distance(self):
        x2 = 5 * METERS_PER_LY
        dist = compute_distance_ly(0, 0, 0, x2, 0, 0)
        assert abs(dist - 5.0) < 0.01

    def test_diagonal_distance(self):
        x2 = 3 * METERS_PER_LY
        y2 = 4 * METERS_PER_LY
        dist = compute_distance_ly(0, 0, 0, x2, y2, 0)
        assert abs(dist - 5.0) < 0.01


class TestSafeSpot:
    def test_single_celestial(self):
        result = compute_best_safe_spot([Celestial("Star", 0, 0, 0)])
        assert result.nearest_au == 0.0

    def test_two_celestials(self):
        result = compute_best_safe_spot(
            [
                Celestial("Star", 0, 0, 0),
                Celestial("Planet I", 20 * METERS_PER_AU, 0, 0),
            ]
        )
        # Midpoint is 10 AU from each
        assert abs(result.nearest_au - 10.0) < 0.1
        assert "Star" in result.warp_between
        assert "Planet I" in result.warp_between

    def test_midpoint_nearest_check(self):
        """Best safe = pair whose midpoint is farthest from nearest other celestial."""
        au = METERS_PER_AU
        cels = [
            Celestial("Star", 0, 0, 0),
            Celestial("Planet I", 40 * au, 0, 0),  # midpoint at 20 AU
            Celestial("Planet II", 22 * au, 0, 0),  # near the midpoint of Star-PI
        ]
        result = compute_best_safe_spot(cels)
        # Star ↔ Planet I midpoint is at 20 AU, but Planet II is only 2 AU away
        # Star ↔ Planet II midpoint is at 11 AU, Planet I is 29 AU away
        # Planet I ↔ Planet II midpoint is at 31 AU, Star is 31 AU away
        # Best should be Planet I ↔ Planet II (nearest is Star at ~31 AU)
        assert result.nearest_au > 20
        assert "Planet I" in result.warp_between
        assert "Planet II" in result.warp_between
        assert result.nearest_label == "Star"


class TestLoadSystems:
    def test_loads_lowsec_nullsec_only(self, app):
        with app.app_context():
            systems = load_systems()
            assert 90000001 in systems
            assert 90000002 in systems
            assert 90000005 not in systems

    def test_system_has_coordinates(self, app):
        with app.app_context():
            systems = load_systems()
            s = systems[90000001]
            assert s.x == 0.0
            assert s.name == "TestOrigin"


class TestSafetyScores:
    def test_safe_system(self, app):
        with app.app_context():
            celestials = load_celestials()
            scores = precompute_safety_scores({90000001}, celestials)
            result = scores[90000001]
            assert result.nearest_au > 0
            assert result.warp_between != ""

    def test_unsafe_system(self, app):
        with app.app_context():
            celestials = load_celestials()
            scores = precompute_safety_scores({90000002}, celestials)
            result = scores[90000002]
            # System B has planets only 5 AU apart, midpoint ~2.5 AU from star
            assert result.nearest_au < 14.3
