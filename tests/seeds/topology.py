"""Integration-test SDE topology.

Five-system fork the A* must choose between when threat data is seeded:

    ItgOrigin ─5─ ItgDanger ─5─ ItgDest                    ← danger path (2 hops)
            └─5─ ItgSafeA ─4─ ItgSafeB ─5─ ItgDest         ← safe path  (3 hops)

Origin→Dest direct is 10 LY (out of range for Archon @ JDC 5 = 7 LY), and
Origin→ItgSafeB is 8.06 LY (also out of range), so the only safe option is the
3-hop detour. That extra hop pays one more `base_system_cost`, giving the safe
branch a ~208-cost penalty over the 2-hop danger branch — large enough that
the test isn't sensitive to small float / heap-ordering differences between
local macOS and Linux CI. Threat data on ItgDanger easily clears that
threshold (50 kills × 600 = 30,000), so the route still flips when weights
are non-zero.

This module only defines the topology data — the actual DB insert is done by
build_app.create_integration_app() so the test fixture controls lifecycle.
"""

LY_METERS = 9.461e15
AU_METERS = 149_597_870_700

ORIGIN_ID = 90000001
DANGER_ID = 90000002
SAFE_A_ID = 90000003
DEST_ID = 90000004
SAFE_B_ID = 90000005

SYSTEM_NAMES = {
    ORIGIN_ID: "ItgOrigin",
    DANGER_ID: "ItgDanger",
    SAFE_A_ID: "ItgSafeA",
    SAFE_B_ID: "ItgSafeB",
    DEST_ID: "ItgDest",
}

# (system_id, security, x_ly, y_ly, z_ly).
# Geometry chosen so Carrier @ JDC 5 (range 7 LY) can take any 5-LY edge but
# CANNOT shortcut Origin→Dest (10 LY), Origin→ItgSafeB (8.06 LY), or
# ItgSafeA→Dest (8.06 LY) — that forces the 3-hop safe branch.
SYSTEM_COORDS = [
    (ORIGIN_ID, -0.5, 0.0, 0.0, 0.0),
    (DANGER_ID, -0.3, 5.0, 0.0, 0.0),
    (SAFE_A_ID, -0.4, 3.0, 4.0, 0.0),
    (SAFE_B_ID, -0.4, 7.0, 4.0, 0.0),
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
