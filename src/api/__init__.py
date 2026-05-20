"""API controllers — thin Flask blueprints that parse requests and
delegate to services on `app.extensions["evecapnav"]`.

Use `register_blueprints(app)` to register all five resource blueprints.
"""

from flask import Flask

from src.api.intel_controller import intel_bp
from src.api.map_controller import map_bp
from src.api.route_controller import route_bp
from src.api.ship_controller import ship_bp
from src.api.system_controller import system_bp


def register_blueprints(app: Flask) -> None:
    """Register all five resource blueprints on `app`."""
    app.register_blueprint(route_bp)
    app.register_blueprint(map_bp)
    app.register_blueprint(system_bp)
    app.register_blueprint(ship_bp)
    app.register_blueprint(intel_bp)
