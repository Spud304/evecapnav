"""Threat-intel endpoint (`/api/danger-data`)."""

from flask import Blueprint, current_app, jsonify

intel_bp = Blueprint("intel", __name__)


@intel_bp.route("/api/danger-data", methods=["GET"])
def get_danger_data():
    intel_service = current_app.extensions["evecapnav"]["intel_service"]
    return jsonify(intel_service.get_danger_data())
