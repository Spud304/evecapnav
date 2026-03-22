import responses

from src.constants import ESI_BASE_URL
from src.esi import fetch_system_kills, fetch_system_jumps
from src.tasks import poll_system_stats, get_danger_data


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
        with app.app_context():
            poll_system_stats()

        danger = get_danger_data()
        assert 30000142 in danger
        assert danger[30000142]["ship_kills"] == 10
        assert danger[30000142]["ship_jumps"] == 200
