import os

import responses

from src.constants import ESI_BASE_URL
from src.clients.esi_client import fetch_fuel_prices
from src.esi import fetch_system_kills, fetch_system_jumps
from src.stores.intel_cache_store import load_fuel_prices, save_fuel_prices
from src.tasks import poll_system_stats, get_danger_data
from src.tasks.intel_tasks import _instance_path


class TestInstancePathIsolation:
    def test_env_var_redirects_cache_away_from_prod(self):
        override = os.environ.get("EVECAPNAV_INSTANCE_PATH")
        assert override, "EVECAPNAV_INSTANCE_PATH must be set during tests"
        resolved = os.path.abspath(_instance_path())
        prod = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "src", "instance")
        )
        assert resolved != prod, (
            f"Tests are resolving to the production instance path {prod!r}; "
            "the autouse fixture in tests/conftest.py is not firing."
        )


class TestESIFetch:
    @responses.activate
    def test_fetch_system_kills(self):
        responses.add(
            responses.GET,
            f"{ESI_BASE_URL}/universe/system_kills/",
            json=[
                {
                    "system_id": 30000142,
                    "ship_kills": 5,
                    "npc_kills": 100,
                    "pod_kills": 2,
                },
            ],
            status=200,
        )
        kills = fetch_system_kills()
        assert 30000142 in kills
        assert kills[30000142]["ship_kills"] == 5

    @responses.activate
    def test_fetch_system_jumps(self):
        responses.add(
            responses.GET,
            f"{ESI_BASE_URL}/universe/system_jumps/",
            json=[{"system_id": 30000142, "ship_jumps": 500}],
            status=200,
        )
        jumps = fetch_system_jumps()
        assert jumps[30000142] == 500

    @responses.activate
    def test_fetch_handles_failure(self):
        responses.add(
            responses.GET,
            f"{ESI_BASE_URL}/universe/system_kills/",
            status=500,
        )
        kills = fetch_system_kills()
        assert kills == {}


class TestPollTask:
    @responses.activate
    def test_poll_updates_cache(self, app):
        responses.add(
            responses.GET,
            f"{ESI_BASE_URL}/universe/system_kills/",
            json=[
                {
                    "system_id": 30000142,
                    "ship_kills": 10,
                    "npc_kills": 50,
                    "pod_kills": 3,
                },
            ],
            status=200,
        )
        responses.add(
            responses.GET,
            f"{ESI_BASE_URL}/universe/system_jumps/",
            json=[{"system_id": 30000142, "ship_jumps": 200}],
            status=200,
        )
        # poll_system_stats now also fetches /markets/prices/ every tick to
        # power the fuel-cost-in-ISK summary cell.
        responses.add(
            responses.GET,
            f"{ESI_BASE_URL}/markets/prices/",
            json=[
                {"type_id": 16274, "average_price": 1500.0},
                {"type_id": 17887, "average_price": 1400.0},
            ],
            status=200,
        )
        with app.app_context():
            poll_system_stats()

        danger = get_danger_data()
        assert 30000142 in danger
        assert danger[30000142]["ship_kills"] == 10
        assert danger[30000142]["ship_jumps"] == 200


class TestFuelPrices:
    @responses.activate
    def test_fetch_filters_to_known_isotope_types(self):
        """fetch_fuel_prices() returns only the four capital-ship isotope
        type_ids — pricing for unrelated market items is dropped."""
        responses.add(
            responses.GET,
            f"{ESI_BASE_URL}/markets/prices/",
            json=[
                {"type_id": 16274, "average_price": 1500.0},  # Helium — kept
                {"type_id": 17889, "average_price": 1300.0},  # Hydrogen — kept
                {"type_id": 34, "average_price": 5.0},  # Tritanium — dropped
            ],
            status=200,
        )
        prices = fetch_fuel_prices()
        assert set(prices.keys()) == {16274, 17889}
        assert prices[16274] == 1500.0

    @responses.activate
    def test_fetch_returns_empty_on_failure(self):
        responses.add(
            responses.GET,
            f"{ESI_BASE_URL}/markets/prices/",
            status=500,
        )
        assert fetch_fuel_prices() == {}

    def test_save_and_load_round_trip(self, tmp_path):
        save_fuel_prices(str(tmp_path), {16274: 1500.0, 17889: 1300.0})
        loaded = load_fuel_prices(str(tmp_path))
        assert loaded == {16274: 1500.0, 17889: 1300.0}
