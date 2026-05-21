"""Unit tests for src.stores.ship_store — ShipClass merging + cap ship type list."""

from __future__ import annotations


class TestLoadShipClasses:
    def test_merges_groups_with_identical_params(self, app):
        """Archon (Carrier, group 547) and Revelation (Dread, group 485) both
        have base range 3.5 and fuel 1000, so load_ship_classes() should merge
        them under a single label."""
        from src.stores.ship_store import load_ship_classes

        with app.app_context():
            classes = load_ship_classes()

        merged = [label for label in classes if "Carrier" in label and "Dreadnought" in label]
        assert merged, f"expected a merged Carrier/Dreadnought label, got: {list(classes)}"

    def test_jump_freighter_is_separate_class(self, app):
        from src.stores.ship_store import load_ship_classes

        with app.app_context():
            classes = load_ship_classes()
        assert "Jump Freighter" in classes
        assert classes["Jump Freighter"].fatigue_multiplier == 0.1


class TestLoadCapShipTypes:
    def test_returns_seeded_cap_ships(self, app):
        """Unit-test SDE has 4 seeded cap ships — all 4 should come back with
        their class_label resolved from the merged ShipClass map."""
        from src.stores.ship_store import load_ship_classes, load_cap_ship_types

        with app.app_context():
            classes = load_ship_classes()
            ships = load_cap_ship_types(classes)

        names = {s["type_name"] for s in ships}
        # All four seeded cap ships should be present.
        assert {"Archon", "Revelation", "Sin", "Rhea"} <= names, names

    def test_each_entry_has_required_fields(self, app):
        from src.stores.ship_store import load_ship_classes, load_cap_ship_types

        with app.app_context():
            classes = load_ship_classes()
            ships = load_cap_ship_types(classes)
        assert ships
        sample = ships[0]
        for key in (
            "type_id",
            "type_name",
            "group_id",
            "class_label",
            "base_range_ly",
            "fuel_per_ly",
            "fatigue_multiplier",
        ):
            assert key in sample, f"missing key {key!r} in {sample}"
        assert isinstance(sample["type_id"], int)
        assert isinstance(sample["type_name"], str)
        assert isinstance(sample["class_label"], str)
        assert isinstance(sample["base_range_ly"], (int, float))
        assert isinstance(sample["fuel_per_ly"], (int, float))
        assert isinstance(sample["fatigue_multiplier"], (int, float))

    def test_rhea_carries_jf_fatigue_multiplier(self, app):
        """Rhea is a JF — fatigue_multiplier should be 0.1, matching the
        SDE dogma seed at tests/conftest.py:117."""
        from src.stores.ship_store import load_ship_classes, load_cap_ship_types

        with app.app_context():
            classes = load_ship_classes()
            ships = load_cap_ship_types(classes)
        rhea = next(s for s in ships if s["type_name"] == "Rhea")
        assert rhea["fatigue_multiplier"] == 0.1

    def test_carrier_and_dreadnought_share_class_label(self, app):
        """Archon (Carrier) and Revelation (Dread) are merged into one
        ShipClass — both ships should report the SAME class_label, so the
        typeahead can show 'Carrier/Dreadnought/FAX' (or whatever the merge
        order produces) for both."""
        from src.stores.ship_store import load_ship_classes, load_cap_ship_types

        with app.app_context():
            classes = load_ship_classes()
            ships = load_cap_ship_types(classes)

        archon = next(s for s in ships if s["type_name"] == "Archon")
        revelation = next(s for s in ships if s["type_name"] == "Revelation")
        assert archon["class_label"] == revelation["class_label"]

    def test_jf_class_label_matches_ship_class(self, app):
        """Rhea (JF) should resolve to the 'Jump Freighter' class label so the
        FE's isJf check (shipClass === 'Jump Freighter') still fires."""
        from src.stores.ship_store import load_ship_classes, load_cap_ship_types

        with app.app_context():
            classes = load_ship_classes()
            ships = load_cap_ship_types(classes)
        rhea = next(s for s in ships if s["type_name"] == "Rhea")
        assert rhea["class_label"] == "Jump Freighter"
        assert rhea["base_range_ly"] == 5.0
