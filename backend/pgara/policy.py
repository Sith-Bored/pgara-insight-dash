"""Input limits and messages shared by the library and the HTTP API.

These bounds keep the prototype predictable. They are part of the input
policy, not estimates of program behavior.
"""

from fractions import Fraction

API_VERSION = "1.0"

MAX_REGISTERS = 256
MAX_SOURCE_CHARS = 100_000
MAX_BLOCKS = 500
MAX_INSTRUCTIONS = 5_000
MAX_PROFILES = 32
MAX_ITERATION_BUDGET = 10_000
MAX_SPILL_WEIGHT = 1_000
DEFAULT_ITERATION_BUDGET = 200
DEFAULT_LOAD_COST = 1
DEFAULT_STORE_COST = 1
DEFAULT_TRADEOFF = Fraction(1, 2)

# Physical registers are named p0, p1, ... so they are not confused with
# virtual register names the user wrote in the IR.
PHYSICAL_REGISTER_PREFIX = "p"

PROFILES_REQUIRED = (
    "This algorithm needs at least one execution profile. "
    "Each profile must give a non-negative integer execution count for every "
    "basic block. The analyzer does not invent execution counts."
)

COST_SUMMARY = (
    "If a live range is spilled, its estimated dynamic spill operations for a "
    "profile are load_cost times the sum of that profile's execution counts on "
    "blocks where the range is used, plus store_cost times the sum of execution "
    "counts on blocks where the range has a live definition. "
    "A definition whose new value is never live does not contribute a store. "
    "Each instruction contributes at most one load per live range, even if the "
    "same virtual register appears twice in that instruction. "
    "The allocation cost of a profile is the sum of those estimates over spilled "
    "live ranges. These figures are estimates derived from the execution counts "
    "you supplied. They are not measured runtime. "
    "Static spill cost is the same formula with one occurrence per instruction "
    "in the IR and does not use execution counts."
)

GAME_LOCAL_NOTE = (
    "The potential-game search starts from a valid allocation and accepts a "
    "change of one live range's strategy only when that change strictly "
    "decreases the global potential. A stop reason of no_improving_move is a "
    "local equilibrium of single-range moves. It is not a proof of global "
    "optimality. A stop reason of iteration_budget means the configured budget "
    "was exhausted first."
)
