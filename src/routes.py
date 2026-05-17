import json
import logging
import os

from flask import Blueprint, request, jsonify, Response

from src.models.models import db, SolarSystemName, MapSolarSystem
from src.constants import (
    BASE_SYSTEM_COST,
    DISTANCE_EXPONENT,
    DANGER_WEIGHT,
    JUMPS_WEIGHT,
    ACTIVITY_WEIGHT,
    DEAD_END_BONUS,
    POS_MOON_BONUS,
    GATE_EQUIVALENT_JUMPS,
)
from src.pathfinder import find_route, find_optimal_wait
from src.tasks import get_danger_data

_instance_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instance")

logger = logging.getLogger(__name__)

# These get populated at startup by init_route_data()
_systems = {}
_graph = {}
_gate_graph: dict = {}
_ship_classes = {}


def init_route_data(app):
    """Precompute systems, jump graph, and safety scores at startup."""
    global _systems, _graph, _ship_classes

    from src.systems import (
        load_systems,
        load_celestials,
        precompute_safety_scores,
    )
    from src.jump_graph import (
        load_ship_classes,
        build_jump_graph,
        build_gate_graph,
        get_effective_range,
    )

    with app.app_context():
        logger.info("Loading systems from SDE...")
        _systems.update(load_systems())
        logger.info("Loaded %d low/null-sec systems", len(_systems))

        logger.info("Loading ship classes from SDE...")
        _ship_classes.update(load_ship_classes())
        logger.info("Loaded %d ship classes", len(_ship_classes))

        # Max possible range: JF @ JDC V = 5 * (1 + 0.20*5) = 10 LY
        max_range = max(
            get_effective_range(sc.base_range_ly, 5) for sc in _ship_classes.values()
        )

        logger.info("Building jump graph (max range %.1f LY)...", max_range)
        _graph.update(build_jump_graph(_systems, max_range))

        logger.info("Building stargate graph...")
        _gate_graph.update(build_gate_graph(_systems))
        total_gate_edges = sum(len(v) for v in _gate_graph.values())
        systems_with_gates = sum(1 for v in _gate_graph.values() if v)
        # Use print() in addition to logger so this is visible even with
        # default Flask logging config.
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
        from src.cache import load_cached_safe_spots, save_cached_safe_spots

        scores = load_cached_safe_spots(app.instance_path)
        if scores is None:
            logger.info(
                "No cache found, computing safety scores (this may take a minute)..."
            )
            celestials = load_celestials()
            scores = precompute_safety_scores(set(_systems.keys()), celestials)
            save_cached_safe_spots(app.instance_path, scores)

        for sid, result in scores.items():
            if sid in _systems:
                _systems[sid].safe_spot_au = round(result.nearest_au, 1)
                _systems[sid].safe_spot_warp = result.warp_between
                _systems[sid].safe_spot_nearest = result.nearest_label

        # Fetch ESI data on startup if cache is missing or stale (>1 hour)
        # Uses a file lock to prevent concurrent writes from multiple processes
        import fcntl

        from src.cache import (
            is_esi_cache_stale,
            save_esi_kills,
            save_esi_jumps,
            save_esi_activity,
            save_sovereignty,
            load_sovereignty,
            mark_esi_updated,
        )
        from src.esi import (
            fetch_system_kills,
            fetch_system_jumps,
            fetch_system_jumps_from_api,
            fetch_recent_activity,
            fetch_sovereignty,
            fetch_names_batch,
        )

        lock_path = os.path.join(app.instance_path, ".esi_fetch.lock")
        try:
            lock_fd = open(lock_path, "w")
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

            if is_esi_cache_stale(app.instance_path):
                logger.info("ESI cache is stale or missing, fetching from ESI...")
                try:
                    kills = fetch_system_kills()
                    if kills:
                        save_esi_kills(app.instance_path, kills)
                    source = os.environ.get("JUMP_DATA_SOURCE", "esi")
                    if source == "fastapi":
                        api_url = os.environ.get(
                            "JUMP_API_URL", "http://localhost:8001"
                        )
                        jumps = fetch_system_jumps_from_api(api_url)
                    else:
                        jumps = fetch_system_jumps()
                    if jumps:
                        save_esi_jumps(app.instance_path, jumps)
                    # Fetch recent pilot activity from historical data API
                    if source == "fastapi":
                        api_url = os.environ.get(
                            "JUMP_API_URL", "http://localhost:8001"
                        )
                        activity = fetch_recent_activity(api_url)
                        if activity:
                            save_esi_activity(app.instance_path, activity)
                    # Fetch sovereignty
                    sov = fetch_sovereignty()
                    if sov:
                        # Resolve alliance names in one batch call
                        alliance_ids = [
                            v["alliance_id"] for v in sov.values() if v["alliance_id"]
                        ]
                        alliance_names = fetch_names_batch(list(set(alliance_ids)))
                        # Get NPC faction names from SDE
                        from sqlalchemy import text

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
                        save_sovereignty(app.instance_path, sov_rows)
                    mark_esi_updated(app.instance_path)
                except Exception as e:
                    logger.warning("Failed to fetch ESI data on startup: %s", e)
            else:
                logger.info("ESI cache is fresh, skipping fetch")

            # Load sovereignty into systems
            sov_data = load_sovereignty(app.instance_path)
            for sid, sov_info in sov_data.items():
                if sid in _systems:
                    _systems[sid].sov_alliance_name = sov_info["alliance_name"]
                    _systems[sid].sov_faction_name = sov_info["faction_name"]

            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()
        except OSError:
            logger.info("Another process is fetching ESI data, skipping")

        logger.info("Route data initialization complete")


class RouteBlueprint(Blueprint):
    def __init__(self, name, import_name):
        super().__init__(name, import_name)
        self._add_routes()

    def _add_routes(self):
        self.add_url_rule(
            "/api/systems/search",
            "search_systems",
            self.search_systems,
            methods=["GET"],
        )
        self.add_url_rule(
            "/api/ship-classes",
            "ship_classes",
            self.get_ship_classes,
            methods=["GET"],
        )
        self.add_url_rule("/api/route", "plan_route", self.plan_route, methods=["GET"])
        self.add_url_rule(
            "/api/route/swap",
            "swap_hop",
            self.swap_hop,
            methods=["GET"],
        )
        self.add_url_rule(
            "/api/danger-data",
            "danger_data",
            self.get_danger_data,
            methods=["GET"],
        )

    def search_systems(self):
        q = request.args.get("q", "").strip()
        if len(q) < 2:
            return jsonify([])

        results = (
            db.session.query(
                SolarSystemName.parentTypeId,
                SolarSystemName.en,
                MapSolarSystem.security,
            )
            .join(
                MapSolarSystem,
                SolarSystemName.parentTypeId == MapSolarSystem.solarSystemID,
            )
            .filter(SolarSystemName.parentTypeCategory == "")
            .filter(SolarSystemName.en.ilike(f"{q}%"))
            .limit(10)
            .all()
        )

        return jsonify(
            [
                {
                    "id": r[0],
                    "name": r[1],
                    "security": round(r[2], 2) if r[2] else 0.0,
                }
                for r in results
            ]
        )

    def get_ship_classes(self):
        from src.jump_graph import get_effective_range

        classes = []
        for label, sc in _ship_classes.items():
            classes.append(
                {
                    "label": label,
                    "base_range_ly": sc.base_range_ly,
                    "fatigue_multiplier": sc.fatigue_multiplier,
                    "max_range_ly": round(get_effective_range(sc.base_range_ly, 5), 1),
                }
            )
        return jsonify(classes)

    def plan_route(self):
        """SSE endpoint that streams progress updates, then the final route result."""
        origin_id = request.args.get("origin_id", type=int)
        dest_id = request.args.get("destination_id", type=int)
        ship_class_label = request.args.get("ship_class", "")
        jdc_level = request.args.get("jdc_level", 5, type=int)
        initial_fatigue = request.args.get("initial_fatigue", 0.0, type=float)
        jfc_level = request.args.get("jfc_level", 0, type=int)
        mode = request.args.get("mode", "safe")
        avoid_alliances_str = request.args.get("avoid_alliances", "")
        avoid_alliances = (
            {name.strip() for name in avoid_alliances_str.split(",") if name.strip()}
            if avoid_alliances_str
            else set()
        )
        base_system_cost = request.args.get(
            "base_system_cost", BASE_SYSTEM_COST, type=int
        )
        distance_exponent = request.args.get(
            "distance_exponent", DISTANCE_EXPONENT, type=float
        )
        danger_weight = request.args.get("danger_weight", DANGER_WEIGHT, type=int)
        jumps_weight = request.args.get("jumps_weight", JUMPS_WEIGHT, type=int)
        activity_weight = request.args.get("activity_weight", ACTIVITY_WEIGHT, type=int)
        dead_end_bonus = request.args.get("dead_end_bonus", DEAD_END_BONUS, type=int)
        pos_moon_bonus = request.args.get("pos_moon_bonus", POS_MOON_BONUS, type=int)
        gate_mode = request.args.get("gate_mode", "off")
        if gate_mode not in ("off", "interregional", "all"):
            gate_mode = "off"
        gate_equivalent_jumps = request.args.get(
            "gate_equivalent_jumps", GATE_EQUIVALENT_JUMPS, type=float
        )

        def generate():
            def send_event(event: str, data: dict | str) -> str:
                payload = json.dumps(data) if isinstance(data, dict) else data
                return f"event: {event}\ndata: {payload}\n\n"

            if not origin_id or not dest_id or not ship_class_label:
                yield send_event(
                    "error",
                    {"error": "origin_id, destination_id, and ship_class are required"},
                )
                return

            if ship_class_label not in _ship_classes:
                yield send_event(
                    "error", {"error": f"Unknown ship class: {ship_class_label}"}
                )
                return

            jdc = max(0, min(5, jdc_level))
            sc = _ship_classes[ship_class_label]
            danger = get_danger_data()

            # Echo the gate config to stdout so we can confirm requests are
            # reaching the latest code at runtime.
            if gate_mode != "off":
                print(
                    f"[evecapnav] /api/route gate_mode={gate_mode} "
                    f"gate_equiv_jumps={gate_equivalent_jumps} "
                    f"gate_graph_edges={sum(len(v) for v in _gate_graph.values())}",
                    flush=True,
                )

            progress_messages: list[str] = []

            def on_progress_collect(msg: str):
                progress_messages.append(msg)

            yield send_event("progress", "Searching for route...")

            steps = find_route(
                origin_id=origin_id,
                dest_id=dest_id,
                systems=_systems,
                graph=_graph,
                base_range_ly=sc.base_range_ly,
                jdc_level=jdc,
                fatigue_multiplier=sc.fatigue_multiplier,
                fuel_per_ly=sc.fuel_per_ly,
                initial_fatigue_min=initial_fatigue,
                jfc_level=jfc_level,
                danger_data=danger,
                on_progress=on_progress_collect,
                mode=mode,
                avoid_alliances=avoid_alliances if avoid_alliances else None,
                base_system_cost=base_system_cost,
                distance_exponent=distance_exponent,
                danger_weight=danger_weight,
                jumps_weight=jumps_weight,
                activity_weight=activity_weight,
                dead_end_bonus=dead_end_bonus,
                pos_moon_bonus=pos_moon_bonus,
                gate_graph=_gate_graph if _gate_graph else None,
                gate_mode=gate_mode,
                gate_equivalent_jumps=gate_equivalent_jumps,
            )

            for msg in progress_messages:
                yield send_event("progress", msg)

            if not steps:
                yield send_event("result", {"error": "No route found", "steps": []})
                return

            total_fuel = sum(s.fuel_cost for s in steps)
            total_wait = sum(s.wait_minutes for s in steps)

            # Compute optimized wait strategy (skip in direct mode)
            optimized_steps = None
            optimal_extra_wait = 0.0
            optimized_fuel = 0
            optimized_wait = 0.0
            if mode != "direct":
                yield send_event("progress", "Optimizing wait times...")
                path = [
                    (s.system_id, s.edge_type if s.edge_type else "jump") for s in steps
                ]
                optimized_steps, optimal_extra_wait = find_optimal_wait(
                    path,
                    _systems,
                    sc.fatigue_multiplier,
                    sc.fuel_per_ly,
                    initial_fatigue,
                    danger,
                    jfc_level=jfc_level,
                )
                optimized_fuel = sum(s.fuel_cost for s in optimized_steps)
                optimized_wait = sum(s.wait_minutes for s in optimized_steps)

            # Fetch zkill intel for route systems
            from src.zkill import (
                fetch_system_stats,
                extract_activity,
                extract_threat_summary,
                find_quiet_hours,
            )
            from src.cache import save_zkill_stats, load_zkill_stats

            yield send_event("progress", "Fetching threat intel...")
            zkill_data: dict[int, dict] = {}
            aggregate_hourly = [0] * 24
            for step in steps:
                sid = step.system_id
                cached = load_zkill_stats(_instance_path, sid)
                if cached:
                    zkill_data[sid] = cached
                else:
                    stats = fetch_system_stats(sid)
                    if stats:
                        hourly = extract_activity(stats)
                        threat = extract_threat_summary(stats)
                        zkill_data[sid] = {
                            "hourly_activity": hourly,
                            **threat,
                        }
                        save_zkill_stats(_instance_path, sid, hourly, threat)

                if sid in zkill_data:
                    for h in range(24):
                        aggregate_hourly[h] += zkill_data[sid].get(
                            "hourly_activity", [0] * 24
                        )[h]

            quiet_start, quiet_end = find_quiet_hours(aggregate_hourly)

            # Compute alternative systems for each hop
            from src.jump_graph import get_effective_range as _get_eff_range

            eff_range = _get_eff_range(sc.base_range_ly, jdc)
            route_ids = {s.system_id for s in steps}
            alternatives: dict[str, list[dict]] = {}
            for idx in range(1, len(steps)):
                prev_id = steps[idx - 1].system_id
                alts = []
                for neighbor_id, dist_ly in _graph.get(prev_id, []):
                    if dist_ly > eff_range or neighbor_id in route_ids:
                        continue
                    ns = _systems.get(neighbor_id)
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
                alternatives[str(steps[idx].system_id)] = alts[:10]

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
            yield send_event("result", result_data)

        return Response(
            generate(),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    def get_danger_data(self):
        return jsonify(get_danger_data())

    def swap_hop(self):
        """Swap a system at a given hop with an alternative, re-route the rest."""
        # Current path as comma-separated system IDs
        path_str = request.args.get("path", "")
        hop_index = request.args.get("hop", type=int)
        alt_system_id = request.args.get("alt_id", type=int)
        ship_class_label = request.args.get("ship_class", "")
        jdc_level = request.args.get("jdc_level", 5, type=int)
        jfc_level = request.args.get("jfc_level", 0, type=int)
        initial_fatigue = request.args.get("initial_fatigue", 0.0, type=float)
        mode = request.args.get("mode", "safe")
        base_system_cost = request.args.get(
            "base_system_cost", BASE_SYSTEM_COST, type=int
        )
        distance_exponent = request.args.get(
            "distance_exponent", DISTANCE_EXPONENT, type=float
        )
        danger_weight = request.args.get("danger_weight", DANGER_WEIGHT, type=int)
        jumps_weight = request.args.get("jumps_weight", JUMPS_WEIGHT, type=int)
        activity_weight = request.args.get("activity_weight", ACTIVITY_WEIGHT, type=int)
        dead_end_bonus = request.args.get("dead_end_bonus", DEAD_END_BONUS, type=int)
        pos_moon_bonus = request.args.get("pos_moon_bonus", POS_MOON_BONUS, type=int)

        if (
            not path_str
            or hop_index is None
            or not alt_system_id
            or not ship_class_label
        ):
            return jsonify({"error": "path, hop, alt_id, and ship_class required"}), 400

        if ship_class_label not in _ship_classes:
            return jsonify({"error": f"Unknown ship class: {ship_class_label}"}), 400

        current_path = [int(x) for x in path_str.split(",") if x.strip()]
        if hop_index < 1 or hop_index >= len(current_path):
            return jsonify({"error": "Invalid hop index"}), 400

        sc = _ship_classes[ship_class_label]
        jdc = max(0, min(5, jdc_level))
        danger = get_danger_data()

        # Keep prefix (hops before the swap), insert alt, re-route from alt to dest
        prefix = current_path[:hop_index]
        replaced_id = current_path[hop_index]
        dest_id = current_path[-1]

        from src.pathfinder import _simulate_route

        # Route from alt to dest, excluding the replaced system so A* doesn't loop back
        suffix_steps = find_route(
            origin_id=alt_system_id,
            dest_id=dest_id,
            systems=_systems,
            graph=_graph,
            base_range_ly=sc.base_range_ly,
            jdc_level=jdc,
            fatigue_multiplier=sc.fatigue_multiplier,
            fuel_per_ly=sc.fuel_per_ly,
            danger_data=danger,
            mode=mode,
            exclude_systems={replaced_id},
            base_system_cost=base_system_cost,
            distance_exponent=distance_exponent,
            danger_weight=danger_weight,
            jumps_weight=jumps_weight,
            activity_weight=activity_weight,
            dead_end_bonus=dead_end_bonus,
            pos_moon_bonus=pos_moon_bonus,
        )

        if not suffix_steps:
            return jsonify({"error": "No route from alternative to destination"}), 200

        # Build full path: prefix + alt route
        suffix_ids = [s.system_id for s in suffix_steps]
        full_path = prefix + suffix_ids

        # Simulate fatigue on the full stitched path
        steps = _simulate_route(
            full_path,
            _systems,
            sc.fatigue_multiplier,
            sc.fuel_per_ly,
            initial_fatigue,
            danger,
            jfc_level=jfc_level,
        )

        total_fuel = sum(s.fuel_cost for s in steps)
        total_wait = sum(s.wait_minutes for s in steps)

        # Compute alternatives for the new path
        from src.jump_graph import get_effective_range as _get_eff_range

        eff_range = _get_eff_range(sc.base_range_ly, jdc)
        route_ids = {s.system_id for s in steps}
        alternatives: dict[str, list[dict]] = {}
        for idx in range(1, len(steps)):
            prev_id = steps[idx - 1].system_id
            alts = []
            for neighbor_id, dist_ly in _graph.get(prev_id, []):
                if dist_ly > eff_range or neighbor_id in route_ids:
                    continue
                ns = _systems.get(neighbor_id)
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
            alternatives[str(steps[idx].system_id)] = alts[:10]

        return jsonify(
            {
                "steps": [s.to_dict() for s in steps],
                "total_jumps": len(steps) - 1,
                "total_fuel": total_fuel,
                "total_wait_minutes": round(total_wait, 1),
                "alternatives": alternatives,
            }
        )
