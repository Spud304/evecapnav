"""Backwards-compat shim. The zKill gateway moved to
`src.gateways.zkill_gateway` in Phase C of the layered restructure.
"""

from src.clients.zkill_client import (  # noqa: F401
    extract_activity,
    extract_threat_summary,
    fetch_system_stats,
    find_quiet_hours,
    zkill_get,
)
