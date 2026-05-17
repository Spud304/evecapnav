"""Integration-test SDE topology.

Four-system fork the A* must choose between when threat data is seeded:

    ItgOrigin (90000001) ──5 LY── ItgDanger (90000002) ──5 LY── ItgDest (90000004)
            └─5.83 LY── ItgSafe (90000003) ──5.83 LY──┘

Origin→Dest direct is 10 LY (out of range for Archon @ JDC 5 = 7 LY), so the
pathfinder MUST pick one of the two two-hop branches. The danger branch is
slightly shorter, so without any kills seeded it is chosen; once we seed kills
on ItgDanger the safe branch must win.

This module only defines the topology data — the actual DB insert is done by
build_app.create_integration_app() so the test fixture controls lifecycle.
"""

LY_METERS = 9.461e15
AU_METERS = 149_597_870_700

ORIGIN_ID = 90000001
DANGER_ID = 90000002
SAFE_ID = 90000003
DEST_ID = 90000004

SYSTEM_NAMES = {
    ORIGIN_ID: "ItgOrigin",
    DANGER_ID: "ItgDanger",
    SAFE_ID: "ItgSafe",
    DEST_ID: "ItgDest",
}

# (system_id, security, x_ly, y_ly, z_ly)
SYSTEM_COORDS = [
    (ORIGIN_ID, -0.5, 0.0, 0.0, 0.0),
    (DANGER_ID, -0.3, 5.0, 0.0, 0.0),
    (SAFE_ID, -0.4, 5.0, 3.0, 0.0),
    (DEST_ID, -0.6, 10.0, 0.0, 0.0),
]

# Ship class label used in tests; matches the Archon group label produced by
# load_ship_classes() given the dogma rows seeded below (range 3.5, mult 1.0).
SHIP_CLASS_LABEL = "Carrier"

# Capital ship dogma rows (typeID, attributeID, value). attributeIDs:
#   867 = jumpDriveRange (LY)
#   868 = jumpDriveConsumptionAmount (fuel per LY)
#   1971 = jumpFatigueMultiplier
SHIP_DOGMA = [
    # Archon (Carrier, group 547) — 3.5 LY base, mult 1.0
    (23757, 867, 3.5),
    (23757, 868, 1000.0),
    # Rhea (JF, group 902) — 5 LY, mult 0.1
    (28848, 867, 5.0),
    (28848, 868, 1000.0),
    (28848, 1971, 0.1),
]

SHIP_TYPES = [
    # (typeID, groupID, name)
    (23757, 547, "Archon"),
    (28848, 902, "Rhea"),
]

SHIP_GROUPS = [
    # (groupID, categoryID)
    (547, 6),  # Carrier
    (902, 6),  # Jump Freighter
]
