"""Pathfinder package — multi-label Dijkstra + legacy single-criterion A*.

Public surface (re-exported here so callers can use the flat import path):

    from src.pathfinder import find_route, RouteStep

The names beginning with `_` are exposed only because existing tests and
the `swap_hop` controller reach for them directly. They aren't intended
as a public API.
"""

from src.pathfinder.cost import compute_distance_ly, compute_fatigue, compute_fuel_cost
from src.pathfinder.dispatcher import find_route
from src.pathfinder.single_criterion import (
    _find_route_single_criterion,
    _simulate_route,
    find_optimal_wait,
)
from src.pathfinder.types import RouteStep

__all__ = [
    "RouteStep",
    "find_route",
    "find_optimal_wait",
    "compute_distance_ly",
    "compute_fatigue",
    "compute_fuel_cost",
    "_find_route_single_criterion",
    "_simulate_route",
]
