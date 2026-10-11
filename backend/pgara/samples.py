"""Deterministic synthetic programs shared by tests and the benchmark endpoint.

Block counts in these profiles are written explicitly. They are not inferred.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class SampleCase:
    name: str
    description: str
    source: str
    num_registers: int
    profiles: tuple[tuple[str, dict[str, int]], ...]
    tradeoff: Fraction
    iteration_budget: int
    game_initial: str = "all_spilled"


LOOP_SOURCE = """\
block entry:
  i = 0
  s = 0
  goto header
block header:
  if i goto body
block exit:
  return s
block body:
  s = s + i
  i = i + 1
  goto header
"""

DIAMOND_SOURCE = """\
block entry:
  a = 1
  b = 2
  if a goto left
block right:
  c = b
  goto join
block left:
  c = a + b
  goto join
block join:
  return c
"""

SEQUENTIAL_SOURCE = """\
block entry:
  a = 1
  b = a
  c = b
  return c
"""

PARAMETERS_SOURCE = """\
block entry:
  c = a + b
  return c
"""

# a has more static sites in a cold block. b has one use in a hot block.
# With one physical register, static greedy keeps a and profile-weighted
# greedy keeps b when hot's execution count is large.
PROFILE_VS_STATIC_SOURCE = """\
block entry:
  a = 0
  b = 0
  goto cold
block cold:
  a = a + 1
  a = a + 1
  a = a + 1
  goto hot
block hot:
  b = b + 1
  goto exit
block exit:
  return a
"""

PROFILE_VS_STATIC_COUNTS = {
    "entry": 1,
    "cold": 1,
    "hot": 100,
    "exit": 1,
}

PROFILE_VS_STATIC_FLAT_COUNTS = {
    "entry": 1,
    "cold": 1,
    "hot": 1,
    "exit": 1,
}

# a and b interfere. Supplied counts make a's estimated spill cost 10 on both
# profiles and b's estimated spill cost 19 on skew and 0 on quiet_b.
# The new value of `b = b + 1` is unused, so that instruction contributes a
# load of b and not a store.
TRADEOFF_SOURCE = """\
block def_a:
  a = 1
  goto def_b
block def_b:
  b = 1
  goto use_a
block use_a:
  a = a + 1
  goto use_b
block use_b:
  b = b + 1
  goto exit
block exit:
  return a
"""

TRADEOFF_PROFILES = (
    (
        "skew",
        {"def_a": 2, "def_b": 9, "use_a": 3, "use_b": 10, "exit": 2},
    ),
    (
        "quiet_b",
        {"def_a": 2, "def_b": 0, "use_a": 3, "use_b": 0, "exit": 2},
    ),
)

CLIQUE_SOURCE = """\
block entry:
  a = 1
  b = 2
  c = 3
  d = 4
  goto use
block use:
  e = a + b
  f = c + d
  g = e + f
  return g
"""


def _uniform(source_labels: list[str], count: int = 1) -> dict[str, int]:
    return {label: count for label in source_labels}


LOOP_LABELS = ["entry", "header", "exit", "body"]
DIAMOND_LABELS = ["entry", "right", "left", "join"]
SEQUENTIAL_LABELS = ["entry"]
CLIQUE_LABELS = ["entry", "use"]

BENCHMARK_CASES: tuple[SampleCase, ...] = (
    SampleCase(
        name="sequential_reuse",
        description=(
            "Three non-interfering ranges in one block. One physical register "
            "can be reused by all of them."
        ),
        source=SEQUENTIAL_SOURCE,
        num_registers=1,
        profiles=(("once", _uniform(SEQUENTIAL_LABELS)),),
        tradeoff=Fraction(1, 2),
        iteration_budget=10,
    ),
    SampleCase(
        name="diamond",
        description="A conditional branch with two paths that join.",
        source=DIAMOND_SOURCE,
        num_registers=1,
        profiles=(("once", _uniform(DIAMOND_LABELS)),),
        tradeoff=Fraction(1, 2),
        iteration_budget=20,
    ),
    SampleCase(
        name="loop",
        description="A loop whose header and body need iterative liveness.",
        source=LOOP_SOURCE,
        num_registers=1,
        profiles=(("ten", {label: 10 for label in LOOP_LABELS}),),
        tradeoff=Fraction(1, 2),
        iteration_budget=20,
    ),
    SampleCase(
        name="profile_versus_static",
        description=(
            "One physical register. Static spill counts prefer a; the supplied "
            "hot-block counts prefer b."
        ),
        source=PROFILE_VS_STATIC_SOURCE,
        num_registers=1,
        profiles=(("hot_b", dict(PROFILE_VS_STATIC_COUNTS)),),
        tradeoff=Fraction(0),
        iteration_budget=10,
    ),
    SampleCase(
        name="game_average",
        description=(
            "Two profiles and tradeoff 0. From all-spilled, the game's first "
            "strict improvement keeps a, the higher average-cost range."
        ),
        source=TRADEOFF_SOURCE,
        num_registers=1,
        profiles=TRADEOFF_PROFILES,
        tradeoff=Fraction(0),
        iteration_budget=10,
    ),
    SampleCase(
        name="game_worst",
        description=(
            "Same program as game_average with tradeoff 1. The first strict "
            "improvement keeps b, which lowers the worse profile."
        ),
        source=TRADEOFF_SOURCE,
        num_registers=1,
        profiles=TRADEOFF_PROFILES,
        tradeoff=Fraction(1),
        iteration_budget=10,
    ),
    SampleCase(
        name="zero_registers",
        description=(
            "num_registers is 0. The input policy spills every live range."
        ),
        source=SEQUENTIAL_SOURCE,
        num_registers=0,
        profiles=(("once", _uniform(SEQUENTIAL_LABELS)),),
        tradeoff=Fraction(1, 2),
        iteration_budget=5,
    ),
    SampleCase(
        name="insufficient_registers",
        description=(
            "Four simultaneously live ranges and one physical register, so at "
            "least three of them spill."
        ),
        source=CLIQUE_SOURCE,
        num_registers=1,
        profiles=(("once", _uniform(CLIQUE_LABELS)),),
        tradeoff=Fraction(1, 2),
        iteration_budget=20,
    ),
)

SAMPLE_PROGRAM = SampleCase(
    name="tradeoff_pair",
    description=(
        "Two interfering live ranges, a and b, and two supplied profiles. "
        "With one physical register, tradeoff 0 and tradeoff 1 select "
        "different ranges when the game starts from all spilled."
    ),
    source=TRADEOFF_SOURCE,
    num_registers=1,
    profiles=TRADEOFF_PROFILES,
    tradeoff=Fraction(1, 2),
    iteration_budget=10,
)
