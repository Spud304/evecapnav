import json


class TestSearchSystems:
    def test_typeahead_returns_results(self, client, app):
        resp = client.get("/api/systems/search?q=Test")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) > 0
        assert any(s["name"].startswith("Test") for s in data)

    def test_typeahead_short_query(self, client, app):
        resp = client.get("/api/systems/search?q=T")
        assert resp.status_code == 200
        assert resp.get_json() == []


class TestShipClasses:
    def test_returns_classes(self, client, app):
        resp = client.get("/api/ship-classes")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) > 0
        for c in data:
            assert "label" in c
            assert "base_range_ly" in c


def _parse_sse_events(data: bytes) -> list[tuple[str, str]]:
    """Parse SSE stream into list of (event_type, data) tuples."""
    events = []
    current_event = ""
    current_data = ""
    for line in data.decode().split("\n"):
        if line.startswith("event: "):
            current_event = line[7:]
        elif line.startswith("data: "):
            current_data = line[6:]
        elif line == "":
            if current_event:
                events.append((current_event, current_data))
                current_event = ""
                current_data = ""
    return events


class TestPlanRoute:
    def test_missing_fields(self, client, app):
        resp = client.get("/api/route")
        events = _parse_sse_events(resp.data)
        assert any(e[0] == "error" for e in events)

    def test_unknown_ship_class(self, client, app):
        resp = client.get(
            "/api/route?origin_id=90000001&destination_id=90000003"
            "&ship_class=Nonexistent&jdc_level=5"
        )
        events = _parse_sse_events(resp.data)
        assert any(e[0] == "error" for e in events)

    def test_valid_route_returns_result(self, client, app):
        # Get a valid ship class label first
        classes_resp = client.get("/api/ship-classes")
        classes = classes_resp.get_json()
        ship_class = classes[0]["label"]

        resp = client.get(
            f"/api/route?origin_id=90000001&destination_id=90000003"
            f"&ship_class={ship_class}&jdc_level=5"
        )
        events = _parse_sse_events(resp.data)
        result_events = [e for e in events if e[0] == "result"]
        assert len(result_events) == 1
        result = json.loads(result_events[0][1])
        assert "steps" in result
