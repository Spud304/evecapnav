"""Backwards-compat shim.

The HTTP API has moved to `src.api` (per-resource controllers under
`src/api/*.py`). This module keeps the legacy `RouteBlueprint` class and
`init_route_data(app)` function so test fixtures (conftest.py +
tests/seeds/app_factory.py) continue to work without edits through
Phase G of the layered restructure.

When `app.register_blueprint(RouteBlueprint(...))` is called, this shim
intercepts registration to install all five per-resource blueprints
from `src.api` instead.
"""

from flask import Blueprint

from src.api import register_blueprints
from src.schemas.system import SystemInfo
from src.services.intel_service import IntelService
from src.services.map_service import MapService
from src.services.route_service import RouteService
from src.services.system_service import SystemService

# Legacy module-level alias for the systems dict. Populated by
# `init_route_data` so older integration tests that mutate
# `src.routes._systems[sid].sov_alliance_name` keep working — they're
# editing the same SystemInfo objects the running RouteService holds.
_systems: dict[int, SystemInfo] = {}


def init_route_data(app) -> None:
    """Build services at startup, store them on `app.extensions["evecapnav"]`.

    Same name + signature as the legacy function so test fixtures don't
    need to change.
    """
    route_service = RouteService()
    route_service.initialize(app)
    intel_service = IntelService(app.instance_path)
    map_service = MapService(app.instance_path)
    system_service = SystemService()
    app.extensions["evecapnav"] = {
        "route_service": route_service,
        "intel_service": intel_service,
        "map_service": map_service,
        "system_service": system_service,
    }
    # Re-bind the legacy alias to the freshly-loaded systems dict.
    global _systems
    _systems = route_service.systems


class RouteBlueprint(Blueprint):
    """Legacy umbrella blueprint. Registering it now installs the five
    per-resource blueprints from `src/api/` onto the app instead of
    binding URL rules to itself.
    """

    def __init__(self, name: str, import_name: str) -> None:
        super().__init__(name, import_name)

    def register(self, app, options) -> None:  # type: ignore[override]
        register_blueprints(app)
        # Still call super so this (empty) blueprint is recorded against
        # the app; otherwise some Flask internals (and tests that introspect
        # `app.blueprints`) would behave inconsistently.
        super().register(app, options)
