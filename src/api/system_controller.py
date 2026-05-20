"""System autocomplete endpoint (`/api/systems/search`)."""

from flask import Blueprint, current_app, jsonify, request

system_bp = Blueprint("system", __name__)


@system_bp.route("/api/systems/search", methods=["GET"])
def search_systems():
    q = request.args.get("q", "")
    system_service = current_app.extensions["evecapnav"]["system_service"]
    return jsonify(system_service.search(q))
