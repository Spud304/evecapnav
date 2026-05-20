"""Route planning service.

Owns the loaded in-memory state (systems, JD graph, gate graph, ship
classes) and exposes the high-level operations the controllers need:
plan a route, swap a hop on an existing route, find alternative systems
to swap *to*.
"""

import logging
import os
from typing import Iterator

from src.schemas.ship import ShipClass
from src.schemas.system import SystemInfo
from src.pathfinder import find_route
from src.pathfinder.graph_builder import build_jump_graph
from src.pathfinder.single_criterion import _simulate_route
from src.stores.celestial_store import load_celestials
from src.stores.gate_store import build_gate_graph
from src.stores.intel_cache_store import (
    is_esi_cache_stale,
    load_cached_safe_spots,
    load_sovereignty,
    mark_esi_updated,
    save_cached_safe_spots,
    save_esi_activity,
    save_esi_jumps,
    save_esi_kills,
    save_sovereignty,
)
from src.stores.ship_store import get_effective_range, load_ship_classes
from src.stores.system_store import load_systems
from src.services.system_service import precompute_safety_scores

logger = logging.getLogger(__name__)


class RouteService:
    """Owns the loaded routing state and orchestrates the pathfinder.

    Construct once at startup, then call `initialize(app)` to populate.
    Handlers read it via `current_app.extensions["evecapnav"]["route_service"]`.
    """

    def __init__(self) -> None:
        self.systems: dict[int, SystemInfo] = {}
        self.graph: dict[int, list[tuple[int, float]]] = {}
        self.gate_graph: dict[int, list[tuple[int, bool, bool]]] = {}
        self.ship_classes: dict[str, ShipClass] = {}

    def initialize(self, app) -> None:
        """Load SDE data, build graphs, fetch ESI on startup if stale, load sov."""
        with app.app_context():
            logger.info("Loading systems from SDE...")
            self.systems.update(load_systems())
            logger.info("Loaded %d low/null-sec systems", len(self.systems))

            logger.info("Loading ship classes from SDE...")
            self.ship_classes.update(load_ship_classes())
            logger.info("Loaded %d ship classes", len(self.ship_classes))

            # Max possible range: JF @ JDC V = 5 * (1 + 0.20*5) = 10 LY
            max_range = max(
                get_effective_range(sc.base_range_ly, 5)
                for sc in self.ship_classes.values()
            )

            logger.info("Building jump graph (max range %.1f LY)...", max_range)
            self.graph.update(build_jump_graph(self.systems, max_range))

            logger.info("Building stargate graph...")
            self.gate_graph.update(build_gate_graph(self.systems))
            total_gate_edges = sum(len(v) for v in self.gate_graph.values())
            systems_with_gates = sum(1 for v in self.gate_graph.values() if v)
            print(
                f"[evecapnav] Gate graph ready: {systems_with_gates} systems with edges, "
                f"{total_gate_edges} directed edges",
                flush=True,
            )
            logger.info(
                "Gate graph: %d systems with edges, %d total directed edges",
                systems_with_gates,
                total_gate_edges,
            )
            if total_gate_edges == 0:
                print(
                    "[evecapnav] WARNING: Gate graph is EMPTY — gate routing will not work.",
                    flush=True,
                )
                logger.error(
                    "Gate graph is EMPTY — gate routing will not work. "
                    "Check that the SDE has 'mapStargate' and 'StargateDestination' tables."
                )

            logger.info("Loading safety scores...")
            scores = load_cached_safe_spots(app.instance_path)
            if scores is None:
                logger.info(
                    "No cache found, computing safety scores (this may take a minute)..."
                )
                celestials = load_celestials()
                scores = precompute_safety_scores(set(self.systems.keys()), celestials)
                save_cached_safe_spots(app.instance_path, scores)

            for sid, result in scores.items():
                if sid in self.systems:
                    self.systems[sid].safe_spot_au = round(result.nearest_au, 1)
                    self.systems[sid].safe_spot_warp = result.warp_between
                    self.systems[sid].safe_spot_nearest = result.nearest_label

            self._startup_esi_fetch(app.instance_path)
            logger.info("Route data initialization complete")

    def _startup_esi_fetch(self, instance_path: str) -> None:
        """ESI fetch on startup if cache is missing or stale (>1 hour).
        Uses a file lock to prevent concurrent writes from multiple processes.
        `fcntl` is Unix-only; on Windows we skip the lock (tests + dev only).
        """
        from typing import Any
        try:
            import fcntl as _fcntl_mod  # type: ignore[import-not-found]
            fcntl: Any = _fcntl_mod
        except ImportError:
            fcntl = None

        from src.clients.esi_client import (
            fetch_names_batch,
            fetch_recent_activity,
            fetch_sovereignty,
            fetch_system_jumps,
            fetch_system_jumps_from_api,
            fetch_system_kills,
        )
        from src.models.models import db
        from sqlalchemy import text

        lock_path = os.path.join(instance_path, ".esi_fetch.lock")
        try:
            lock_fd = open(lock_path, "w")
            if fcntl is not None:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

            if is_esi_cache_stale(instance_path):
                logger.info("ESI cache is stale or missing, fetching from ESI...")
                try:
                    kills = fetch_system_kills()
                    if kills:
                        save_esi_kills(instance_path, kills)
                    source = os.environ.get("JUMP_DATA_SOURCE", "esi")
                    if source == "fastapi":
                        api_url = os.environ.get(
                            "JUMP_API_URL", "http://localhost:8001"
                        )
                        jumps = fetch_system_jumps_from_api(api_url)
                    else:
                        jumps = fetch_system_jumps()
                    if jumps:
                        save_esi_jumps(instance_path, jumps)
                    if source == "fastapi":
                        api_url = os.environ.get(
                            "JUMP_API_URL", "http://localhost:8001"
                        )
                        activity = fetch_recent_activity(api_url)
                        if activity:
                            save_esi_activity(instance_path, activity)
                    sov = fetch_sovereignty()
                    if sov:
                        alliance_ids = [
                            v["alliance_id"] for v in sov.values() if v["alliance_id"]
                        ]
                        alliance_names = fetch_names_batch(list(set(alliance_ids)))
                        faction_names = {}
                        with db.engine.connect() as conn:
                            for row in conn.execute(
                                text(
                                    "SELECT parentTypeId, en FROM FactionName WHERE parentTypeCategory = ''"
                                )
                            ):
                                faction_names[row[0]] = row[1]
                        sov_rows = [
                            (
                                sid,
                                v["alliance_id"],
                                alliance_names.get(v["alliance_id"], ""),
                                v["faction_id"],
                                faction_names.get(v["faction_id"], ""),
                            )
                            for sid, v in sov.items()
                        ]
                        save_sovereignty(instance_path, sov_rows)
                    mark_esi_updated(instance_path)
                except Exception as e:
                    logger.warning("Failed to fetch ESI data on startup: %s", e)
            else:
                logger.info("ESI cache is fresh, skipping fetch")

            sov_data = load_sovereignty(instance_path)
            for sid, sov_info in sov_data.items():
                if sid in self.systems:
                    self.systems[sid].sov_alliance_name = sov_info["alliance_name"]
                    self.systems[sid].sov_faction_name = sov_info["faction_name"]

            if fcntl is not None:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()
        except OSError:
            logger.info("Another process is fetching ESI data, skipping")

    def find_alternatives(
        self,
        prev_id: int,
        route_ids: set[int],
        eff_range: float,
        limit: int = 10,
    ) -> list[dict]:
        """Find candidate systems reachable from prev_id by JD at the
        given effective range, excluding any system already on the route.
        Returned sorted by ascending distance, capped at `limit`.
        Consolidates logic that was duplicated across plan_route and
        swap_hop in the legacy controller.
        """
        alts: list[dict] = []
        for neighbor_id, dist_ly in self.graph.get(prev_id, []):
            if dist_ly > eff_range or neighbor_id in route_ids:
                continue
            ns = self.systems.get(neighbor_id)
            if not ns:
                continue
            alts.append(
                {
                    "id": neighbor_id,
                    "name": ns.name,
                    "distance_ly": round(dist_ly, 2),
                    "security": round(ns.security, 1),
                    "sov_owner": ns.sov_alliance_name or ns.sov_faction_name,
                    "moon_count": ns.moon_count,
                    "safe_spot_au": ns.safe_spot_au,
                }
            )
        alts.sort(key=lambda a: a["distance_ly"])
        return alts[:limit]

    def list_ship_classes_serialized(self) -> list[dict]:
        """Serialize ship classes for /api/ship-classes."""
        return [
            {
                "label": label,
                "base_range_ly": sc.base_range_ly,
                "fatigue_multiplier": sc.fatigue_multiplier,
                "max_range_ly": round(get_effective_range(sc.base_range_ly, 5), 1),
            }
            for label, sc in self.ship_classes.items()
        ]

    def plan_route(
        self, params: dict, intel_service, danger_data: dict
    ) -> Iterator[tuple[str, dict | str]]:
        """Generator yielding (event_name, payload) tuples for SSE.

        Validates the request, runs the pathfinder, fetches threat intel
        via `intel_service`, computes alternatives, and assembles the
        final result payload. Controllers wrap each tuple in SSE format.
        """
        origin_id = params["origin_id"]
        dest_id = params["dest_id"]
        ship_class_label = params["ship_class"]
        jdc_level = params["jdc_level"]
        initial_fatigue = params["initial_fatigue"]
        jfc_level = params["jfc_level"]
        mode = params["mode"]
        avoid_alliances = params["avoid_alliances"]
        base_system_cost = params["base_system_cost"]
        distance_exponent = params["distance_exponent"]
        danger_weight = params["danger_weight"]
        jumps_weight = params["jumps_weight"]
        activity_weight = params["activity_weight"]
        dead_end_penalty = params["dead_end_penalty"]
        pos_moon_bonus = params["pos_moon_bonus"]
        gate_mode = params["gate_mode"]
        gate_equivalent_jumps = params["gate_equivalent_jumps"]
        wait_weight = params["wait_weight"]

        if not origin_id or not dest_id or not ship_class_label:
            yield (
                "error",
                {"error": "origin_id, destination_id, and ship_class are required"},
            )
            return

        if ship_class_label not in self.ship_classes:
            yield ("error", {"error": f"Unknown ship class: {ship_class_label}"})
            return

        jdc = max(0, min(5, jdc_level))
        sc = self.ship_classes[ship_class_label]

        # Echo the gate config to stdout so we can confirm requests are
        # reaching the latest code at runtime.
        if gate_mode != "off":
            print(
                f"[evecapnav] /api/route gate_mode={gate_mode} "
                f"gate_equiv_jumps={gate_equivalent_jumps} "
                f"gate_graph_edges={sum(len(v) for v in self.gate_graph.values())}",
                flush=True,
            )

        progress_messages: list[str] = []

        def on_progress_collect(msg: str) -> None:
            progress_messages.append(msg)

        yield ("progress", "Searching for route...")

        steps = find_route(
            origin_id=origin_id,
            dest_id=dest_id,
            systems=self.systems,
            graph=self.graph,
            base_range_ly=sc.base_range_ly,
            jdc_level=jdc,
            fatigue_multiplier=sc.fatigue_multiplier,
            fuel_per_ly=sc.fuel_per_ly,
            initial_fatigue_min=initial_fatigue,
            jfc_level=jfc_level,
            danger_data=danger_data,
            on_progress=on_progress_collect,
            mode=mode,
            avoid_alliances=avoid_alliances if avoid_alliances else None,
            base_system_cost=base_system_cost,
            distance_exponent=distance_exponent,
            danger_weight=danger_weight,
            jumps_weight=jumps_weight,
            activity_weight=activity_weight,
            dead_end_penalty=dead_end_penalty,
            pos_moon_bonus=pos_moon_bonus,
            gate_graph=self.gate_graph if self.gate_graph else None,
            gate_mode=gate_mode,
            gate_equivalent_jumps=gate_equivalent_jumps,
            wait_weight=wait_weight,
        )

        for msg in progress_messages:
            yield ("progress", msg)

        if not steps:
            yield ("result", {"error": "No route found", "steps": []})
            return

        total_fuel = sum(s.fuel_cost for s in steps)
        total_wait = sum(s.wait_minutes for s in steps)

        # `find_optimal_wait` is now a no-op shim (the multi-label search
        # picks waits implicitly), so just return zero-extra-wait results
        # to keep the wire shape compatible with the existing FE.
        optimized_steps = None
        optimal_extra_wait = 0.0
        optimized_fuel = 0
        optimized_wait = 0.0

        yield ("progress", "Fetching threat intel...")
        zkill_data, aggregate_hourly = intel_service.fetch_route_zkill(
            [s.system_id for s in steps]
        )
        quiet_start, quiet_end = intel_service.compute_quiet_hours(aggregate_hourly)

        eff_range = get_effective_range(sc.base_range_ly, jdc)
        route_ids = {s.system_id for s in steps}
        alternatives: dict[str, list[dict]] = {}
        for idx in range(1, len(steps)):
            prev_id = steps[idx - 1].system_id
            alternatives[str(steps[idx].system_id)] = self.find_alternatives(
                prev_id, route_ids, eff_range
            )

        jump_data_source = os.environ.get("JUMP_DATA_SOURCE", "esi")
        jump_hops = sum(1 for s in steps if s.edge_type == "jump")
        gate_hops = sum(1 for s in steps if s.edge_type == "gate")
        result_data: dict = {
            "steps": [s.to_dict() for s in steps],
            "total_jumps": jump_hops,
            "total_gate_hops": gate_hops,
            "total_fuel": total_fuel,
            "total_wait_minutes": round(total_wait, 1),
            "alternatives": alternatives,
            "zkill": {
                sid: zkill_data.get(sid, {}) for sid in [s.system_id for s in steps]
            },
            "quiet_hours": {
                "start": quiet_start,
                "end": quiet_end,
            },
            "jump_data_window": "24h" if jump_data_source == "fastapi" else "1h",
        }
        if optimized_steps:
            result_data["optimized"] = {
                "steps": [s.to_dict() for s in optimized_steps],
                "extra_wait_minutes": optimal_extra_wait,
                "total_fuel": optimized_fuel,
                "total_wait_minutes": round(optimized_wait, 1),
            }
        yield ("result", result_data)

    def swap_hop(self, params: dict, danger_data: dict) -> dict | tuple[dict, int]:
        """Swap a system at a given hop with an alternative, re-route the rest.

        Returns either a JSON-ready dict, or `(dict, http_status)` for
        error responses.
        """
        path_str = params["path"]
        hop_index = params["hop"]
        alt_system_id = params["alt_id"]
        ship_class_label = params["ship_class"]
        jdc_level = params["jdc_level"]
        jfc_level = params["jfc_level"]
        initial_fatigue = params["initial_fatigue"]
        mode = params["mode"]
        base_system_cost = params["base_system_cost"]
        distance_exponent = params["distance_exponent"]
        danger_weight = params["danger_weight"]
        jumps_weight = params["jumps_weight"]
        activity_weight = params["activity_weight"]
        dead_end_penalty = params["dead_end_penalty"]
        pos_moon_bonus = params["pos_moon_bonus"]
        wait_weight = params["wait_weight"]

        if (
            not path_str
            or hop_index is None
            or not alt_system_id
            or not ship_class_label
        ):
            return ({"error": "path, hop, alt_id, and ship_class required"}, 400)

        if ship_class_label not in self.ship_classes:
            return ({"error": f"Unknown ship class: {ship_class_label}"}, 400)

        current_path = [int(x) for x in path_str.split(",") if x.strip()]
        if hop_index < 1 or hop_index >= len(current_path):
            return ({"error": "Invalid hop index"}, 400)

        sc = self.ship_classes[ship_class_label]
        jdc = max(0, min(5, jdc_level))

        prefix = current_path[:hop_index]
        replaced_id = current_path[hop_index]
        dest_id = current_path[-1]

        suffix_steps = find_route(
            origin_id=alt_system_id,
            dest_id=dest_id,
            systems=self.systems,
            graph=self.graph,
            base_range_ly=sc.base_range_ly,
            jdc_level=jdc,
            fatigue_multiplier=sc.fatigue_multiplier,
            fuel_per_ly=sc.fuel_per_ly,
            danger_data=danger_data,
            mode=mode,
            exclude_systems={replaced_id},
            base_system_cost=base_system_cost,
            distance_exponent=distance_exponent,
            danger_weight=danger_weight,
            jumps_weight=jumps_weight,
            activity_weight=activity_weight,
            dead_end_penalty=dead_end_penalty,
            pos_moon_bonus=pos_moon_bonus,
            wait_weight=wait_weight,
        )

        if not suffix_steps:
            return ({"error": "No route from alternative to destination"}, 200)

        suffix_ids = [s.system_id for s in suffix_steps]
        full_path = prefix + suffix_ids

        steps = _simulate_route(
            full_path,
            self.systems,
            sc.fatigue_multiplier,
            sc.fuel_per_ly,
            initial_fatigue,
            danger_data,
            jfc_level=jfc_level,
        )

        total_fuel = sum(s.fuel_cost for s in steps)
        total_wait = sum(s.wait_minutes for s in steps)

        eff_range = get_effective_range(sc.base_range_ly, jdc)
        route_ids = {s.system_id for s in steps}
        alternatives: dict[str, list[dict]] = {}
        for idx in range(1, len(steps)):
            prev_id = steps[idx - 1].system_id
            alternatives[str(steps[idx].system_id)] = self.find_alternatives(
                prev_id, route_ids, eff_range
            )

        return {
            "steps": [s.to_dict() for s in steps],
            "total_jumps": len(steps) - 1,
            "total_fuel": total_fuel,
            "total_wait_minutes": round(total_wait, 1),
            "alternatives": alternatives,
        }
