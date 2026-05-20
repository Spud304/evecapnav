"""Star map endpoint (`/api/map/data`)."""

from flask import Blueprint, current_app, jsonify

map_bp = Blueprint("map", __name__)


@map_bp.route("/api/map/data", methods=["GET"])
def get_map_data():
    map_service = current_app.extensions["evecapnav"]["map_service"]
    return jsonify(map_service.get_map_data())
