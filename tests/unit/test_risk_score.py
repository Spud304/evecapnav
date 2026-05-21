"""Unit tests for RouteService.compute_risk_score — pure-function math."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class _Step:
    """Minimal step-shape stand-in. compute_risk_score uses getattr so we
    don't need to import the real RouteStep dataclass."""
    kills_per_hour: int = 0
    hourly_jumps: list = None
    gate_count: int = 5
    sov_owner: str = ""


def _compute(steps, avoid_alliances=""):
    from src.services.route_service import RouteService

    return RouteService.compute_risk_score(steps, avoid_alliances)


class TestRiskScore:
    def test_zero_input_yields_zero_risk(self):
        score, breakdown = _compute([_Step(), _Step()])
        assert score == 0
        assert breakdown == {
            "kills": 0,
            "peak_jumps": 0,
            "dead_ends": 0,
            "hostile_systems": 0,
        }

    def test_empty_steps_does_not_divide_by_zero(self):
        score, _ = _compute([])
        assert score == 0

    def test_kills_dominate_score(self):
        """20 kills per hop × 2.0 weight / 2 hops = 20 risk."""
        steps = [_Step(kills_per_hour=20), _Step(kills_per_hour=20)]
        score, breakdown = _compute(steps)
        # raw = 2.0 * 40 = 80. /2 hops = 40.
        assert score == 40
        assert breakdown["kills"] == 40

    def test_peak_jumps_contribute(self):
        """Two hops, each with peak hourly_jumps = 200 → 400 peak. 400*0.05/2 = 10."""
        steps = [
            _Step(hourly_jumps=[50] * 23 + [200]),
            _Step(hourly_jumps=[50] * 23 + [200]),
        ]
        score, breakdown = _compute(steps)
        assert score == 10
        assert breakdown["peak_jumps"] == 400

    def test_dead_ends_penalize(self):
        """gate_count == 1 → dead-end → +10 per hop / 2 hops = 5."""
        steps = [_Step(gate_count=1), _Step(gate_count=5)]
        score, breakdown = _compute(steps)
        # raw = 10 * 1 = 10. /2 = 5.
        assert score == 5
        assert breakdown["dead_ends"] == 1

    def test_hostile_sov_matches_avoid_list_case_insensitively(self):
        steps = [_Step(sov_owner="Goonswarm Federation"), _Step(sov_owner="Pandemic Horde")]
        score, breakdown = _compute(steps, avoid_alliances="goonswarm federation, brave")
        # 1 hostile system * 15 / 2 hops = 7 (rounded).
        assert breakdown["hostile_systems"] == 1
        assert score == 8 or score == 7  # round-half tolerance

    def test_score_caps_at_100(self):
        """A pathological route with massive kills should max out at 100."""
        steps = [_Step(kills_per_hour=10_000) for _ in range(3)]
        score, _ = _compute(steps)
        assert score == 100

    def test_per_hop_normalization_keeps_long_routes_from_inflating(self):
        """Same risk per hop should yield the same score regardless of route length."""
        short = [_Step(kills_per_hour=20)] * 2
        long_ = [_Step(kills_per_hour=20)] * 20
        score_short, _ = _compute(short)
        score_long, _ = _compute(long_)
        assert score_short == score_long
