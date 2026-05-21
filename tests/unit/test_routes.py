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


class TestCapShips:
    def test_endpoint_returns_typed_ships(self, client, app):
        """/api/cap-ships powers the ShipPicker typeahead; each entry is a
        single cap ship type with the merged ShipClass label attached."""
        resp = client.get("/api/cap-ships")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        assert len(data) > 0
        names = {s["type_name"] for s in data}
        # Unit-test SDE seeds these four.
        assert {"Archon", "Revelation", "Sin", "Rhea"} <= names

    def test_each_entry_has_all_fields(self, client, app):
        resp = client.get("/api/cap-ships")
        data = resp.get_json()
        for entry in data:
            for key in ("type_id", "type_name", "group_id", "class_label", "base_range_ly"):
                assert key in entry, f"missing {key!r} in {entry}"


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

    def test_result_includes_risk_score_and_breakdown(self, client, app):
        """The /api/route result should include a 0–100 risk_score plus a
        breakdown dict (kills / peak_jumps / dead_ends / hostile_systems)."""
        classes_resp = client.get("/api/ship-classes")
        ship_class = classes_resp.get_json()[0]["label"]
        resp = client.get(
            f"/api/route?origin_id=90000001&destination_id=90000003"
            f"&ship_class={ship_class}&jdc_level=5"
        )
        events = _parse_sse_events(resp.data)
        result = json.loads(next(e for e in events if e[0] == "result")[1])
        assert "risk_score" in result
        assert isinstance(result["risk_score"], int)
        assert 0 <= result["risk_score"] <= 100
        breakdown = result.get("risk_breakdown")
        assert breakdown is not None
        for key in ("kills", "peak_jumps", "dead_ends", "hostile_systems"):
            assert key in breakdown


    def test_result_includes_quiet_jumps_and_hourly_per_step(self, client, app):
        """Wire-shape regression: /api/route must include the new quiet_jumps
        field (route-aggregated weekly quietest window) and every RouteStep
        must carry hourly_jumps so the FE Sparkline column has data to bind to."""
        classes_resp = client.get("/api/ship-classes")
        ship_class = classes_resp.get_json()[0]["label"]
        resp = client.get(
            f"/api/route?origin_id=90000001&destination_id=90000003"
            f"&ship_class={ship_class}&jdc_level=5"
        )
        events = _parse_sse_events(resp.data)
        result = json.loads(
            next(e for e in events if e[0] == "result")[1]
        )
        # Route-level summary
        assert "quiet_jumps" in result
        qj = result["quiet_jumps"]
        for key in ("start", "end", "hourly"):
            assert key in qj
        assert isinstance(qj["hourly"], list)
        assert len(qj["hourly"]) == 24
        # Per-step
        for step in result["steps"]:
            assert "hourly_jumps" in step
            assert isinstance(step["hourly_jumps"], list)
