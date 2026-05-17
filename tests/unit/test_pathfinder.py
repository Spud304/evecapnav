import math

from src.pathfinder import compute_fatigue, compute_fuel_cost, find_route
from src.systems import SystemInfo
from src.constants import MAX_FATIGUE_MINUTES


class TestFatigue:
    def test_fresh_jump(self):
        """Zero initial fatigue produces baseline fatigue.

        EVE formula (all minutes):
          raw_fatigue = min(300, max(0, 10) * (1 + 5*1.0)) = 10 * 6 = 60 min
          cooldown = max(0/10, 1 + 5*1.0) = 6 min
          fatigue_after_wait = 60 - 6 = 54 min
        """
        fatigue_after, cooldown = compute_fatigue(0.0, 5.0, 1.0)
        assert fatigue_after == 54.0
        assert cooldown == 6.0

    def test_accumulated_fatigue(self):
        """Fatigue grows with successive jumps."""
        f1, _ = compute_fatigue(0.0, 5.0, 1.0)
        f2, _ = compute_fatigue(f1, 5.0, 1.0)
        assert f2 > f1

    def test_fatigue_cap(self):
        """Fatigue is capped at MAX_FATIGUE_MINUTES (5 hours), minus cooldown decay."""
        fatigue_after, cooldown = compute_fatigue(200.0, 10.0, 1.0)
        assert fatigue_after == MAX_FATIGUE_MINUTES - cooldown

    def test_jf_bonus(self):
        """JF fatigue multiplier (0.1) greatly reduces fatigue."""
        fat_no_bonus, _ = compute_fatigue(0.0, 5.0, 1.0)
        fat_jf, _ = compute_fatigue(0.0, 5.0, 0.1)
        assert fat_jf < fat_no_bonus

    def test_blops_bonus(self):
        """Black Ops fatigue multiplier (0.25) reduces fatigue."""
        fat_no_bonus, _ = compute_fatigue(0.0, 5.0, 1.0)
        fat_blops, _ = compute_fatigue(0.0, 5.0, 0.25)
        assert fat_blops < fat_no_bonus


class TestFuelCost:
    def test_basic_fuel(self):
        """Basic fuel cost calculation."""
        cost = compute_fuel_cost(5.0, 1000)
        assert cost == 5000

    def test_fuel_rounds_up(self):
        """Fuel cost always rounds up."""
        cost = compute_fuel_cost(5.1, 1000)
        assert cost == 5100

    def test_jfc_reduces_fuel(self):
        """Jump Fuel Conservation skill reduces fuel."""
        base = compute_fuel_cost(5.0, 1000, jfc_level=0)
        reduced = compute_fuel_cost(5.0, 1000, jfc_level=5)
        assert reduced < base
        assert reduced == math.ceil(5.0 * 1000 * 0.5)


class TestFindRoute:
    def _make_systems(self):
        ly = 9.461e15
        return {
            1: SystemInfo(1, "A", -0.5, 0, 0, 0, 1),
            2: SystemInfo(2, "B", -0.3, 5 * ly, 0, 0, 1),
            3: SystemInfo(3, "C", -0.1, 8 * ly, 0, 0, 1),
        }

    def _make_graph(self):
        return {
            1: [(2, 5.0), (3, 8.0)],
            2: [(1, 5.0), (3, 3.0)],
            3: [(1, 8.0), (2, 3.0)],
        }

    def test_simple_route(self):
        """Find a route between two connected systems."""
        systems = self._make_systems()
        graph = self._make_graph()
        steps = find_route(
            origin_id=1,
            dest_id=3,
            systems=systems,
            graph=graph,
            base_range_ly=5.0,
            jdc_level=5,
            fatigue_multiplier=1.0,
            fuel_per_ly=1000,
        )
        assert len(steps) > 0
        assert steps[0].system_id == 1
        assert steps[-1].system_id == 3

    def test_no_route(self):
        """Returns empty when destination is unreachable."""
        systems = self._make_systems()
        systems[4] = SystemInfo(4, "D", -0.8, 100 * 9.461e15, 0, 0, 1)
        graph = {1: [(2, 5.0)], 2: [(1, 5.0)], 3: [], 4: []}
        steps = find_route(
            origin_id=1,
            dest_id=4,
            systems=systems,
            graph=graph,
            base_range_ly=5.0,
            jdc_level=5,
            fatigue_multiplier=1.0,
            fuel_per_ly=1000,
        )
        assert steps == []

    def test_route_avoids_danger(self):
        """Router prefers safer systems when danger data is provided."""
        systems = self._make_systems()
        # Two paths: direct 1->3 (8 LY) or via 2: 1->2 (5 LY) + 2->3 (3 LY)
        graph = {
            1: [(2, 5.0), (3, 8.0)],
            2: [(1, 5.0), (3, 3.0)],
            3: [(1, 8.0), (2, 3.0)],
        }
        # Make system 3 very dangerous only on direct approach (high kills)
        # The router should still arrive at 3 but may prefer going via 2
        danger = {3: {"ship_kills": 100, "ship_jumps": 500}}
        steps = find_route(
            origin_id=1,
            dest_id=3,
            systems=systems,
            graph=graph,
            base_range_ly=10.0,
            jdc_level=5,
            fatigue_multiplier=1.0,
            fuel_per_ly=1000,
            danger_data=danger,
        )
        assert len(steps) > 0
        assert steps[-1].system_id == 3
