"""Ship-class listing endpoint (`/api/ship-classes`)."""

from flask import Blueprint, current_app, jsonify

ship_bp = Blueprint("ship", __name__)


@ship_bp.route("/api/ship-classes", methods=["GET"])
def get_ship_classes():
    route_service = current_app.extensions["evecapnav"]["route_service"]
    return jsonify(route_service.list_ship_classes_serialized())


@ship_bp.route("/api/cap-ships", methods=["GET"])
def get_cap_ships():
    """All jump-capable cap ship types, for the typeahead picker."""
    route_service = current_app.extensions["evecapnav"]["route_service"]
    return jsonify(route_service.list_cap_ships_serialized())
