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

# Dead-end system penalty (safe mode): systems with only 1 gate are
# camp-prone (only one entry/exit means hostile pilots only need to watch
# one gate). Earlier versions treated dead-ends as a bonus on the
# assumption they were quieter — that was wrong; they're actively
# avoided by experienced cap pilots. Cost addition for single-gate systems.
DEAD_END_PENALTY = 100

# Multi-label search: cost added per minute of wait at a system (fatigue/cooldown
# decay). Tuned so 60 min of waiting costs roughly the same as one 5LY jump
# (≈ 5^1.5 ≈ 11.2), letting the search trade waits against extra jumps.
# Higher = "quickest"  (waits expensive, search avoids JD, prefers gates).
# Lower  = "least jumps" (waits cheap, search uses long JD with fatigue OK).
WAIT_WEIGHT = 0.2

# Per-hop overhead cost = wait_weight * HOP_OVERHEAD_FACTOR. Applied uniformly
# to gate AND JD edges so at high wait_weight the search penalizes total hop
# count regardless of edge type. Without this, gates always dominate at high
# wait_weight because gate cost is fixed (~56) while JD's fatigue-time cost
# scales with wait_weight (~1000 at wait_weight=20), and the search ends up
# picking 35 short gates over 17 long JDs. With this overhead set at 100,
# 1×wait_weight=20 hop ≈ 2000 cost, which dominates and pushes the search
# toward mixed routes (long JD where possible, gates only as real shortcuts
# that save many hops).
HOP_OVERHEAD_FACTOR = 100

# Stargate hop cost expressed in jump-equivalents (a gate hop is treated
# as ~N JD jumps for cost-comparison purposes).
GATE_EQUIVALENT_JUMPS = 5.0
# Per-LY reference distance used to convert "gate equivalent jumps" into an
# A* cost comparable to dist^exp jump costs. 5 LY is the rough middle of cap
# jump ranges.
GATE_JUMP_REFERENCE_LY = 5.0
# Wall-clock seconds added for a stargate hop (align, decloak, jump cycle).
GATE_TRAVEL_SECONDS = 45.0
