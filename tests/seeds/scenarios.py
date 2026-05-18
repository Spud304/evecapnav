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

# Mid-band kills on DANGER. kills_per_hour is passed straight through from
# ship_kills (see src/pathfinder.py::_simulate_route), so 5 lands in the
# (3, 10] amber band — used to exercise the amber row + amber kills-cell
# color in test_fe_route_table.py. We use this with danger_weight=0 so the
# planner still routes through Danger and the FE has a row to color.
KILLS_AMBER_ON_DANGER: dict = {
    "kills": {DANGER_ID: {"ship_kills": 5, "npc_kills": 0, "pod_kills": 0}},
    "jumps": {},
    "activity": {},
    "zkill": {},
}

# 20 kills on DANGER → kills_per_hour=20 lands in the >10 red band, used to
# verify the red row + bad-color cell.
KILLS_RED_ON_DANGER: dict = {
    "kills": {DANGER_ID: {"ship_kills": 20, "npc_kills": 0, "pod_kills": 0}},
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

# Hourly activity spanning every color band the modal renders. The bar
# colorings in ThreatModal.tsx are: > 70% of max → red, > 30% → amber,
# else green. With max = 100, we want:
#   - At least one hour at 100   (>70%, red)
#   - At least one hour at 50    (>30%, ≤70%, amber)
#   - At least one hour at 10    (≤30%, green)
# Cell extraction in tests indexes by hour; values are picked so the FE
# rendering is unambiguous if any of the threshold constants change.
VARIED_HOURLY_ZKILL: dict = {
    "kills": {},
    "jumps": {},
    "activity": {},
    "zkill": {
        DANGER_ID: {
            "hourly": (
                [10] * 8  # 0-7:  green
                + [50] * 8  # 8-15: amber
                + [100] * 7  # 16-22: red
                + [100]  # 23:   red (anchors max)
            ),
            "active_characters": 25,
            "active_corps": 7,
            "gang_ratio": "55%",
            "ships_destroyed": 312,
        },
    },
}


SCENARIOS = {
    "empty": EMPTY,
    "kills_on_danger": KILLS_ON_DANGER,
    "kills_amber_on_danger": KILLS_AMBER_ON_DANGER,
    "kills_red_on_danger": KILLS_RED_ON_DANGER,
    "jumps_on_danger": JUMPS_ON_DANGER,
    "activity_on_danger": ACTIVITY_ON_DANGER,
    "zkill_intel": ZKILL_INTEL,
    "varied_hourly_zkill": VARIED_HOURLY_ZKILL,
}

# Exported so tests don't have to import topology too when they just want IDs.
__all__ = [
    "SCENARIOS",
    "EMPTY",
    "KILLS_ON_DANGER",
    "KILLS_AMBER_ON_DANGER",
    "KILLS_RED_ON_DANGER",
    "JUMPS_ON_DANGER",
    "ACTIVITY_ON_DANGER",
    "ZKILL_INTEL",
    "VARIED_HOURLY_ZKILL",
    "ORIGIN_ID",
    "DANGER_ID",
    "SAFE_A_ID",
    "SAFE_B_ID",
    "DEST_ID",
]
