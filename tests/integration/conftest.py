"""Integration test harness: real Flask server + seedable threat cache + Playwright.

Avoids depending on `tests/conftest.py` so the unit-test fixtures and the
integration-test fixtures can evolve independently. The unit suite uses
in-memory SQLite + a 5-system layout intended for fast pathfinder cases;
this suite needs a fork topology, a real HTTP port, and a writable cache
directory shared with `src.tasks._instance_path`.
"""

from __future__ import annotations

import os
import socket
import threading
from dataclasses import dataclass
from typing import Callable

import pytest

# Env vars must be set BEFORE importing src.*
os.environ.setdefault("STATIC_DB", "integration_sde")
os.environ.setdefault("SECRET_KEY", "integration-test-secret")
os.environ.setdefault("JUMP_DATA_SOURCE", "esi")


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@dataclass
class LiveServer:
    base_url: str
    instance_path: str
    reseed: Callable[[str], None]


@pytest.fixture(scope="session")
def live_server(tmp_path_factory) -> LiveServer:
    """Start a real Flask server on a free port with a seeded fork topology.

    Sets EVECAPNAV_INSTANCE_PATH so `src.tasks.get_danger_data()` and the zkill
    loader in `src.routes` both read from the temp cache directory we control.
    """
    instance_path = str(tmp_path_factory.mktemp("evecapnav_itg"))
    os.environ["EVECAPNAV_INSTANCE_PATH"] = instance_path

    # Imports deferred until env vars are in place.
    from werkzeug.serving import make_server

    from tests.seeds.app_factory import create_integration_app
    from tests.seeds.build_cache import build_seed_cache

    # Default scenario: empty threat cache. Individual tests reseed.
    build_seed_cache(instance_path, "empty")

    app = create_integration_app(instance_path)
    port = _find_free_port()
    server = make_server("127.0.0.1", port, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"

    def reseed(scenario: str) -> None:
        build_seed_cache(instance_path, scenario)

    try:
        yield LiveServer(base_url=base_url, instance_path=instance_path, reseed=reseed)
    finally:
        server.shutdown()
        thread.join(timeout=2)


# Override the autouse `_cleanup` from tests/conftest.py — that fixture wants
# the unit-test in-memory app, which load_ship_classes() then reads, leaking
# Dreadnought/etc. ship groups into our integration assertions.
@pytest.fixture(autouse=True)
def _cleanup() -> None:  # noqa: PT004
    yield


@pytest.fixture(scope="session")
def base_url(live_server: LiveServer) -> str:
    return live_server.base_url


@pytest.fixture
def reseed(live_server: LiveServer) -> Callable[[str], None]:
    return live_server.reseed


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Default pytest-playwright context args + a viewport.

    Tests can override per-test; this just keeps screenshots/videos sane.
    """
    return {
        **browser_context_args,
        "viewport": {"width": 1400, "height": 900},
    }
