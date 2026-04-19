ESI_BASE_URL = "https://esi.evetech.net/latest"

METERS_PER_LY = 9_460_730_472_580_800
METERS_PER_AU = 149_597_870_700
SAFE_SPOT_THRESHOLD_AU = 14.3
MAX_FATIGUE_MINUTES = 43200  # 30 days

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

# POS hopping: bonus per moon (reduces cost for moon-rich systems)
POS_MOON_BONUS = 5  # cost reduction per moon in system

# Dead-end system bonus (safe mode): systems with only 1 gate are quieter
DEAD_END_BONUS = 100  # cost reduction for single-gate systems
