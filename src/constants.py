ESI_BASE_URL = "https://esi.evetech.net/latest"

METERS_PER_LY = 9_460_730_472_580_800
METERS_PER_AU = 149_597_870_700
SAFE_SPOT_THRESHOLD_AU = 14.3
MAX_FATIGUE_MINUTES = 300  # blue timer caps at 5 hours (March 2018 changes)
MAX_COOLDOWN_MINUTES = 30  # red timer (jump activation cooldown) caps at 30 minutes

# Dogma attribute IDs
ATTR_JUMP_DRIVE_RANGE = 867
ATTR_JUMP_FUEL_CONSUMPTION = 868
ATTR_JUMP_FATIGUE_MULTIPLIER = 1971

# Ship group IDs
GROUP_TITAN = 30
GROUP_DREADNOUGHT = 485
GROUP_CARRIER = 547
GROUP_SUPERCARRIER = 659
GROUP_CAPITAL_INDUSTRIAL = 883
GROUP_BLACK_OPS = 898
GROUP_JUMP_FREIGHTER = 902
GROUP_FAX = 1538

CAPITAL_GROUP_IDS = {
    GROUP_CARRIER,
    GROUP_DREADNOUGHT,
    GROUP_FAX,
    GROUP_CAPITAL_INDUSTRIAL,
    GROUP_SUPERCARRIER,
    GROUP_TITAN,
    GROUP_BLACK_OPS,
    GROUP_JUMP_FREIGHTER,
}

# Danger penalties added to A* cost per system
BASE_SYSTEM_COST = 200  # baseline cost for every system (bonuses subtract from this)
DISTANCE_EXPONENT = 1.5  # dist^exp in cost — 1.0=linear, 2.0=heavy fatigue penalty
DANGER_WEIGHT = 600  # per kill/hr
JUMPS_WEIGHT = 60  # per jump/hr (traffic = eyes on you)
ACTIVITY_WEIGHT = 30  # per recent pilot activity count (historical data)

# POS hopping: bonus per moon (reduces cost for moon-rich systems)
POS_MOON_BONUS = 5  # cost reduction per moon in system

# Dead-end system bonus (safe mode): systems with only 1 gate are quieter
DEAD_END_BONUS = 100  # cost reduction for single-gate systems

# Stargate hop cost in jump-equivalents (GARPA-style: gate ~= N jumps)
GATE_EQUIVALENT_JUMPS = 5.0
# Per-LY reference distance used to convert "gate equivalent jumps" into an
# A* cost comparable to dist^exp jump costs. 5 LY is the rough middle of cap
# jump ranges.
GATE_JUMP_REFERENCE_LY = 5.0
# Wall-clock seconds added for a stargate hop (align, decloak, jump cycle).
GATE_TRAVEL_SECONDS = 45.0
