"""Route planning + hop-swap endpoints (`/api/route`, `/api/route/swap`)."""

import json

from flask import Blueprint, Response, current_app, jsonify, request

from src.constants import (
    ACTIVITY_WEIGHT,
    BASE_SYSTEM_COST,
    DANGER_WEIGHT,
    DEAD_END_PENALTY,
    DISTANCE_EXPONENT,
    GATE_EQUIVALENT_JUMPS,
    JUMPS_WEIGHT,
    POS_MOON_BONUS,
    WAIT_WEIGHT,
)
from src.services.intel_service import IntelService
from src.services.route_service import RouteService

route_bp = Blueprint("route", __name__)


def _services() -> dict:
    return current_app.extensions["evecapnav"]


@route_bp.route("/api/route", methods=["GET"])
def plan_route():
    """SSE endpoint that streams progress + final route result."""
    avoid_alliances_str = request.args.get("avoid_alliances", "")
    avoid_alliances = (
        {name.strip() for name in avoid_alliances_str.split(",") if name.strip()}
        if avoid_alliances_str
        else set()
    )
    gate_mode = request.args.get("gate_mode", "off")
    if gate_mode not in ("off", "interregional", "all"):
        gate_mode = "off"

    params = {
        "origin_id": request.args.get("origin_id", type=int),
        "dest_id": request.args.get("destination_id", type=int),
        "ship_class": request.args.get("ship_class", ""),
        "jdc_level": request.args.get("jdc_level", 5, type=int),
        "initial_fatigue": request.args.get("initial_fatigue", 0.0, type=float),
        "jfc_level": request.args.get("jfc_level", 0, type=int),
        "mode": request.args.get("mode", "safe"),
        "avoid_alliances": avoid_alliances,
        "base_system_cost": request.args.get(
            "base_system_cost", BASE_SYSTEM_COST, type=int
        ),
        "distance_exponent": request.args.get(
            "distance_exponent", DISTANCE_EXPONENT, type=float
        ),
        "danger_weight": request.args.get("danger_weight", DANGER_WEIGHT, type=int),
        "jumps_weight": request.args.get("jumps_weight", JUMPS_WEIGHT, type=int),
        "activity_weight": request.args.get(
            "activity_weight", ACTIVITY_WEIGHT, type=int
        ),
        "dead_end_penalty": request.args.get(
            "dead_end_penalty", DEAD_END_PENALTY, type=int
        ),
        "pos_moon_bonus": request.args.get("pos_moon_bonus", POS_MOON_BONUS, type=int),
        "gate_mode": gate_mode,
        "gate_equivalent_jumps": request.args.get(
            "gate_equivalent_jumps", GATE_EQUIVALENT_JUMPS, type=float
        ),
        "wait_weight": request.args.get("wait_weight", WAIT_WEIGHT, type=float),
    }

    # Capture services + danger data inside the request context, then
    # pass them into the generator (which executes outside it).
    svcs = _services()
    route_service: RouteService = svcs["route_service"]
    intel_service: IntelService = svcs["intel_service"]
    danger_data = intel_service.get_danger_data()

    def generate():
        for event_name, payload in route_service.plan_route(
            params, intel_service, danger_data
        ):
            # Preserve the legacy `event: NAME\ndata: PAYLOAD\n\n` wire
            # format — the FE's EventSource parser depends on it.
            data = json.dumps(payload) if isinstance(payload, dict) else payload
            yield f"event: {event_name}\ndata: {data}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@route_bp.route("/api/route/swap", methods=["GET"])
def swap_hop():
    params = {
        "path": request.args.get("path", ""),
        "hop": request.args.get("hop", type=int),
        "alt_id": request.args.get("alt_id", type=int),
        "ship_class": request.args.get("ship_class", ""),
        "jdc_level": request.args.get("jdc_level", 5, type=int),
        "jfc_level": request.args.get("jfc_level", 0, type=int),
        "initial_fatigue": request.args.get("initial_fatigue", 0.0, type=float),
        "mode": request.args.get("mode", "safe"),
        "base_system_cost": request.args.get(
            "base_system_cost", BASE_SYSTEM_COST, type=int
        ),
        "distance_exponent": request.args.get(
            "distance_exponent", DISTANCE_EXPONENT, type=float
        ),
        "danger_weight": request.args.get("danger_weight", DANGER_WEIGHT, type=int),
        "jumps_weight": request.args.get("jumps_weight", JUMPS_WEIGHT, type=int),
        "activity_weight": request.args.get(
            "activity_weight", ACTIVITY_WEIGHT, type=int
        ),
        "dead_end_penalty": request.args.get(
            "dead_end_penalty", DEAD_END_PENALTY, type=int
        ),
        "pos_moon_bonus": request.args.get("pos_moon_bonus", POS_MOON_BONUS, type=int),
        "wait_weight": request.args.get("wait_weight", WAIT_WEIGHT, type=float),
    }
    svcs = _services()
    danger_data = svcs["intel_service"].get_danger_data()
    result = svcs["route_service"].swap_hop(params, danger_data)
    if isinstance(result, tuple):
        body, status = result
        return jsonify(body), status
    return jsonify(result)
