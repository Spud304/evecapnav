"""Named threat-data scenarios for integration tests.

Each scenario is a dict of source-table inputs that `build_cache.build_seed_cache`
writes into a fresh `cache.sqlite`. Keep these tied to system IDs from
`tests.seeds.topology` so tests can reason about which path the pathfinder will
pick.
"""

from tests.seeds.topology import DANGER_ID, SAFE_A_ID, SAFE_B_ID, DEST_ID, ORIGIN_ID

# No threat data at all — pathfinder picks the geometrically shorter branch
# (via DANGER_ID).
EMPTY: dict = {
    "kills": {},
    "jumps": {},
    "activity": {},
    "zkill": {},
}

# Heavy kills on DANGER. With default danger_weight the pathfinder should reroute
# through SAFE_ID. The numbers are deliberately large so the test is robust to
# distance_exponent tuning.
KILLS_ON_DANGER: dict = {
    "kills": {DANGER_ID: {"ship_kills": 50, "npc_kills": 0, "pod_kills": 0}},
    "jumps": {},
    "activity": {},
    "zkill": {},
}

# Heavy jumps (traffic) on DANGER. Used to test the jumps_weight knob.
JUMPS_ON_DANGER: dict = {
    "kills": {},
    "jumps": {DANGER_ID: 500},
    "activity": {},
    "zkill": {},
}

# Heavy historical activity on DANGER. Tests the activity_weight knob.
ACTIVITY_ON_DANGER: dict = {
    "kills": {},
    "jumps": {},
    "activity": {DANGER_ID: 1000},
    "zkill": {},
}

# Zkill intel for the threat modal test. Hourly distribution has one hot hour at
# 13:00 UTC; we assert the modal renders these numbers.
ZKILL_INTEL: dict = {
    "kills": {},
    "jumps": {},
    "activity": {},
    "zkill": {
        DANGER_ID: {
            "hourly": [0] * 13 + [42] + [0] * 10,
            "active_characters": 17,
            "active_corps": 4,
            "gang_ratio": "63%",
            "ships_destroyed": 88,
        },
    },
}


SCENARIOS = {
    "empty": EMPTY,
    "kills_on_danger": KILLS_ON_DANGER,
    "jumps_on_danger": JUMPS_ON_DANGER,
    "activity_on_danger": ACTIVITY_ON_DANGER,
    "zkill_intel": ZKILL_INTEL,
}

# Exported so tests don't have to import topology too when they just want IDs.
__all__ = [
    "SCENARIOS",
    "EMPTY",
    "KILLS_ON_DANGER",
    "JUMPS_ON_DANGER",
    "ACTIVITY_ON_DANGER",
    "ZKILL_INTEL",
    "ORIGIN_ID",
    "DANGER_ID",
    "SAFE_A_ID",
    "SAFE_B_ID",
    "DEST_ID",
]
