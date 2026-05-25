"""Backwards-compat shim. The ESI gateway moved to
`src.gateways.esi_gateway`; tests and `src.tasks` still import from here
through Phase G of the layered restructure.
"""

from src.constants import ESI_BASE_URL  # noqa: F401
from src.clients.esi_client import (  # noqa: F401
    esi_get,
    fetch_alliance_name,
    fetch_names_batch,
    fetch_sovereignty,
    fetch_system_jumps,
    fetch_system_jumps_from_api,
    fetch_system_kills,
    fetch_weekly_hourly_jumps,
)
