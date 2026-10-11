"""Spill-cost calculations stay tied to supplied counts."""

import pytest

from pgara.cfg import build_cfg
from pgara.costs import (
    allocation_profile_costs,
    profile_spill_operations,
    static_spill_operations,
    validate_profiles,
)
from pgara.errors import InputError
from pgara.interference import build_interference
from pgara.liveness import analyze_liveness
from pgara.parser import parse
from pgara.samples import (
    PROFILE_VS_STATIC_COUNTS,
    PROFILE_VS_STATIC_SOURCE,
    TRADEOFF_PROFILES,
    TRADEOFF_SOURCE,
)


def _ranges(source: str):
    program = parse(source)
    graph = build_interference(program, analyze_liveness(program, build_cfg(program)))
    return program, graph.ranges


def test_tradeoff_program_costs_match_the_documented_counts():
    program, ranges = _ranges(TRADEOFF_SOURCE)
    validate_profiles(program, list(TRADEOFF_PROFILES))
    skew = dict(TRADEOFF_PROFILES[0][1])
    quiet = dict(TRADEOFF_PROFILES[1][1])
    assert static_spill_operations(ranges["a"], 1, 1) == 4
    assert profile_spill_operations(ranges["a"], skew, 1, 1) == 10
    assert profile_spill_operations(ranges["a"], quiet, 1, 1) == 10
    assert profile_spill_operations(ranges["b"], skew, 1, 1) == 19
    assert profile_spill_operations(ranges["b"], quiet, 1, 1) == 0
    # The dead update of b is a load, not a store.
    assert len(ranges["b"].defs) == 1
    assert len(ranges["b"].uses) == 1


def test_profile_versus_static_costs():
    _program, ranges = _ranges(PROFILE_VS_STATIC_SOURCE)
    counts = PROFILE_VS_STATIC_COUNTS
    assert static_spill_operations(ranges["a"], 1, 1) == 8
    assert static_spill_operations(ranges["b"], 1, 1) == 2
    assert profile_spill_operations(ranges["a"], counts, 1, 1) == 8
    assert profile_spill_operations(ranges["b"], counts, 1, 1) == 101


def test_allocation_cost_sums_only_spilled_ranges():
    program, ranges = _ranges(TRADEOFF_SOURCE)
    assignments = {"a": "p0", "b": None}
    costs = allocation_profile_costs(assignments, ranges, list(TRADEOFF_PROFILES), 1, 1)
    assert costs == [("skew", 19), ("quiet_b", 0)]
    kept_none = {"a": None, "b": None}
    both = allocation_profile_costs(kept_none, ranges, list(TRADEOFF_PROFILES), 1, 1)
    assert both == [("skew", 29), ("quiet_b", 10)]


def test_zero_block_count_is_explicit_and_adds_nothing():
    _program, ranges = _ranges(TRADEOFF_SOURCE)
    zeros = {label: 0 for label in ("def_a", "def_b", "use_a", "use_b", "exit")}
    assert profile_spill_operations(ranges["a"], zeros, 1, 1) == 0


def test_load_and_store_weights_scale_sites():
    _program, ranges = _ranges("block entry:\n  a = 1\n  return a\n")
    counts = {"entry": 3}
    assert profile_spill_operations(ranges["a"], counts, load_cost=2, store_cost=5) == 2 * 3 + 5 * 3


@pytest.mark.parametrize(
    "profiles, fragment",
    [
        ([("p", {"entry": 1})], "missing execution counts"),
        ([("p", {"entry": 1, "next": 1, "nope": 1})], "unknown blocks"),
        ([("p", {"entry": -1, "next": 0})], "negative"),
        (
            [("p", {"entry": 1, "next": 1}), ("p", {"entry": 0, "next": 0})],
            "duplicate",
        ),
    ],
)
def test_profile_validation(profiles, fragment):
    program = parse("block entry:\n  goto next\nblock next:\n  return 0\n")
    with pytest.raises(InputError, match=fragment):
        validate_profiles(program, profiles)
