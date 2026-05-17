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

    def test_route_records_edge_type(self):
        """All hops in a pure-jump route are labeled edge_type='jump'."""
        steps = find_route(
            origin_id=1,
            dest_id=3,
            systems=self._make_systems(),
            graph=self._make_graph(),
            base_range_ly=5.0,
            jdc_level=5,
            fatigue_multiplier=1.0,
            fuel_per_ly=1000,
        )
        assert steps[0].edge_type == ""  # origin
        for s in steps[1:]:
            assert s.edge_type == "jump"

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


class TestRegionalGates:
    """Tests for the optional stargate-hop routing."""

    def _make_systems(self):
        ly = 9.461e15
        return {
            1: SystemInfo(
                1, "A", -0.5, 0.0, 0.0, 0.0, region_id=10, constellation_id=100
            ),
            2: SystemInfo(
                2, "B", -0.5, 5 * ly, 0.0, 0.0, region_id=10, constellation_id=100
            ),
            3: SystemInfo(
                3, "C", -0.5, 5 * ly, 5 * ly, 0.0, region_id=20, constellation_id=200
            ),
            4: SystemInfo(
                4, "D", -0.5, 10 * ly, 5 * ly, 0.0, region_id=20, constellation_id=200
            ),
        }

    def _make_graph(self):
        # Pure jump-only path A->B->D (each 5 LY), and B->C, C->D for the
        # alternative gate-assisted route. A cannot reach C/D directly by jump.
        return {
            1: [(2, 5.0)],
            2: [(1, 5.0), (3, 5.0)],
            3: [(2, 5.0), (4, 5.0)],
            4: [(3, 5.0)],
        }

    def _make_gate_graph(self):
        # Single cross-region stargate connection between A (region 10) and C (region 20).
        return {
            1: [(3, True, True)],
            2: [],
            3: [(1, True, True)],
            4: [],
        }

    def test_gate_mode_off_excludes_gates(self):
        """gate_mode='off' must reproduce legacy jump-only behavior."""
        steps = find_route(
            origin_id=1,
            dest_id=4,
            systems=self._make_systems(),
            graph=self._make_graph(),
            base_range_ly=5.0,
            jdc_level=0,
            fatigue_multiplier=1.0,
            fuel_per_ly=1000,
            gate_graph=self._make_gate_graph(),
            gate_mode="off",
        )
        ids = [s.system_id for s in steps]
        # Only the jump-graph path is reachable
        assert ids == [1, 2, 3, 4]
        for s in steps[1:]:
            assert s.edge_type == "jump"

    def test_interregional_takes_gate(self):
        """With a cheap inter-regional gate, the router prefers the gate hop."""
        steps = find_route(
            origin_id=1,
            dest_id=4,
            systems=self._make_systems(),
            graph=self._make_graph(),
            base_range_ly=5.0,
            jdc_level=0,
            fatigue_multiplier=1.0,
            fuel_per_ly=1000,
            mode="direct",
            gate_graph=self._make_gate_graph(),
            gate_mode="interregional",
            gate_equivalent_jumps=0.1,
        )
        ids = [s.system_id for s in steps]
        # Should hop A --gate--> C --jump--> D, skipping B
        assert ids == [1, 3, 4]
        assert steps[1].edge_type == "gate"
        assert steps[2].edge_type == "jump"

    def test_equivalent_jumps_threshold_falls_back(self):
        """A high gate cost (in jump-equivalents) forces the all-jump path."""
        steps = find_route(
            origin_id=1,
            dest_id=4,
            systems=self._make_systems(),
            graph=self._make_graph(),
            base_range_ly=5.0,
            jdc_level=0,
            fatigue_multiplier=1.0,
            fuel_per_ly=1000,
            mode="direct",
            gate_graph=self._make_gate_graph(),
            gate_mode="interregional",
            gate_equivalent_jumps=100.0,
        )
        ids = [s.system_id for s in steps]
        assert ids == [1, 2, 3, 4]
        for s in steps[1:]:
            assert s.edge_type == "jump"

    def test_gate_hop_metadata_no_fatigue_or_fuel(self):
        """Gate hops have zero fuel cost and do not change fatigue."""
        steps = find_route(
            origin_id=1,
            dest_id=4,
            systems=self._make_systems(),
            graph=self._make_graph(),
            base_range_ly=5.0,
            jdc_level=0,
            fatigue_multiplier=1.0,
            fuel_per_ly=1000,
            initial_fatigue_min=30.0,
            mode="direct",
            gate_graph=self._make_gate_graph(),
            gate_mode="interregional",
            gate_equivalent_jumps=0.1,
        )
        gate_step = next(s for s in steps if s.edge_type == "gate")
        assert gate_step.fuel_cost == 0
        # Fatigue is unchanged across the gate hop (no jump-drive activity)
        prev = steps[steps.index(gate_step) - 1]
        assert gate_step.fatigue_after_minutes == prev.fatigue_after_minutes

    def test_interregional_intra_region_gate_treated_as_one_jump(self):
        """In 'interregional' mode, intra-region gates are still available as
        regular edges (priced like one jump) so connectivity is preserved for
        short-range ships, but they don't get the user's shortcut discount."""
        # Mark the only gate as intra-region (cross_region=False)
        gate_graph = {
            1: [(3, False, True)],
            2: [],
            3: [(1, False, True)],
            4: [],
        }
        # Use a high gate_equivalent_jumps — irrelevant since intra-region gates
        # are priced at gate_unit_cost. With gate_unit_cost ~= one 5LY jump (11.2)
        # and the jump-only path costing 3 * 5^1.5 ~= 33.5, the gate shortcut
        # (one gate hop priced as 1 jump + one 5LY jump = ~22.4) wins.
        steps = find_route(
            origin_id=1,
            dest_id=4,
            systems=self._make_systems(),
            graph=self._make_graph(),
            base_range_ly=5.0,
            jdc_level=0,
            fatigue_multiplier=1.0,
            fuel_per_ly=1000,
            mode="direct",
            gate_graph=gate_graph,
            gate_mode="interregional",
            gate_equivalent_jumps=100.0,
        )
        ids = [s.system_id for s in steps]
        # Intra-region gate priced as 1 jump → still cheaper than 3 jumps
        assert ids == [1, 3, 4]
        assert steps[1].edge_type == "gate"

    def test_all_mode_uses_intra_region_gate(self):
        """gate_mode='all' uses gates regardless of region/constellation."""
        gate_graph = {
            1: [(3, False, False)],
            2: [],
            3: [(1, False, False)],
            4: [],
        }
        steps = find_route(
            origin_id=1,
            dest_id=4,
            systems=self._make_systems(),
            graph=self._make_graph(),
            base_range_ly=5.0,
            jdc_level=0,
            fatigue_multiplier=1.0,
            fuel_per_ly=1000,
            mode="direct",
            gate_graph=gate_graph,
            gate_mode="all",
            gate_equivalent_jumps=0.1,
        )
        ids = [s.system_id for s in steps]
        assert ids == [1, 3, 4]
        assert steps[1].edge_type == "gate"

    def test_route_through_gate_chain_with_jumps_out_of_range(self):
        """A 6-system chain reachable ONLY via stargates (no jump within range)
        must still be traversed end-to-end. Reproduces the 1DH-SX → AXDX-F bug
        where a low-range ship needs many sequential gate hops."""
        ly = 9.461e15
        # Six systems in a line, each 50 LY apart — far beyond jump range.
        systems = {
            i: SystemInfo(
                i, f"S{i}", -0.5, (i - 1) * 50 * ly, 0.0, 0.0, region_id=10 + i
            )
            for i in range(1, 7)
        }
        # No jump edges within 5 LY base range. All connectivity via stargates.
        jump_graph: dict[int, list[tuple[int, float]]] = {i: [] for i in range(1, 7)}
        # Linear gate chain 1-2-3-4-5-6, each edge inter-regional.
        gate_graph = {
            i: [(j, True, True) for j in (i - 1, i + 1) if 1 <= j <= 6]
            for i in range(1, 7)
        }

        steps = find_route(
            origin_id=1,
            dest_id=6,
            systems=systems,
            graph=jump_graph,
            base_range_ly=5.0,
            jdc_level=0,
            fatigue_multiplier=1.0,
            fuel_per_ly=1000,
            mode="direct",
            gate_graph=gate_graph,
            gate_mode="all",
            gate_equivalent_jumps=1.0,
        )
        ids = [s.system_id for s in steps]
        assert ids == [1, 2, 3, 4, 5, 6], (
            f"Expected the full 6-system gate chain, got {ids}"
        )
        for s in steps[1:]:
            assert s.edge_type == "gate"

    def test_route_finds_indirect_gate_path(self):
        """When a direct LY-distance heuristic would mislead A*, the BFS
        heuristic over the gate graph guides it through a long detour.

        Topology: origin and dest are physically close (5 LY) but the only
        connectivity goes through 4 distant systems via stargates. A planner
        biased by physical distance would never expand the detour; a BFS
        heuristic correctly costs the detour at 5 hops to dest."""
        ly = 9.461e15
        systems = {
            1: SystemInfo(1, "A", -0.5, 0.0, 0.0, 0.0, region_id=10),
            2: SystemInfo(2, "B", -0.5, 100 * ly, 0.0, 0.0, region_id=20),
            3: SystemInfo(3, "C", -0.5, 100 * ly, 100 * ly, 0.0, region_id=30),
            4: SystemInfo(4, "D", -0.5, 0.0, 100 * ly, 0.0, region_id=40),
            5: SystemInfo(5, "E", -0.5, 5 * ly, 5 * ly, 0.0, region_id=10),  # near A
        }
        # No jump edges in range (5 LY base, 0 JDC).
        jump_graph: dict[int, list[tuple[int, float]]] = {i: [] for i in range(1, 6)}
        # Gate chain A -> B -> C -> D -> E only (no direct A-E even though close).
        gate_graph = {
            1: [(2, True, True)],
            2: [(1, True, True), (3, True, True)],
            3: [(2, True, True), (4, True, True)],
            4: [(3, True, True), (5, True, True)],
            5: [(4, True, True)],
        }
        steps = find_route(
            origin_id=1,
            dest_id=5,
            systems=systems,
            graph=jump_graph,
            base_range_ly=5.0,
            jdc_level=0,
            fatigue_multiplier=1.0,
            fuel_per_ly=1000,
            mode="direct",
            gate_graph=gate_graph,
            gate_mode="all",
            gate_equivalent_jumps=1.0,
        )
        assert [s.system_id for s in steps] == [1, 2, 3, 4, 5]

    def test_disconnected_gate_dest_returns_empty(self):
        """When the destination is in a different gate-graph component from
        the origin and no jumps bridge them, find_route returns [] cleanly."""
        ly = 9.461e15
        systems = {
            1: SystemInfo(1, "A", -0.5, 0.0, 0.0, 0.0, region_id=10),
            2: SystemInfo(2, "B", -0.5, 1 * ly, 0.0, 0.0, region_id=10),
            3: SystemInfo(3, "C", -0.5, 1000 * ly, 0.0, 0.0, region_id=20),
            4: SystemInfo(4, "D", -0.5, 1001 * ly, 0.0, 0.0, region_id=20),
        }
        jump_graph: dict[int, list[tuple[int, float]]] = {i: [] for i in range(1, 5)}
        gate_graph = {
            1: [(2, False, False)],
            2: [(1, False, False)],
            3: [(4, False, False)],
            4: [(3, False, False)],
        }
        steps = find_route(
            origin_id=1,
            dest_id=4,
            systems=systems,
            graph=jump_graph,
            base_range_ly=5.0,
            jdc_level=0,
            fatigue_multiplier=1.0,
            fuel_per_ly=1000,
            mode="direct",
            gate_graph=gate_graph,
            gate_mode="all",
            gate_equivalent_jumps=1.0,
        )
        assert steps == []

    def test_safe_mode_avoids_hot_gate_endpoint(self):
        """High kills at a gate's destination push the router to the safer jump path.

        Topology: A can either:
          - gate directly to C (one hop), then jump to D.
          - jump through B, then to C, then to D.
        If C is extremely hot, 'safe' mode prefers visiting C only once via the
        jump chain (which still touches it), but the gate hop's edge weight
        plus C's danger should be high enough that the all-jump path wins
        when the gate cost is itself non-trivial.
        """
        danger = {3: {"ship_kills": 500, "ship_jumps": 1000, "pilot_activity": 500}}
        steps = find_route(
            origin_id=1,
            dest_id=4,
            systems=self._make_systems(),
            graph=self._make_graph(),
            base_range_ly=5.0,
            jdc_level=0,
            fatigue_multiplier=1.0,
            fuel_per_ly=1000,
            danger_data=danger,
            mode="safe",
            gate_graph=self._make_gate_graph(),
            gate_mode="interregional",
            gate_equivalent_jumps=10.0,
        )
        # The router still finds a route to D regardless of which option won
        assert steps[0].system_id == 1
        assert steps[-1].system_id == 4
