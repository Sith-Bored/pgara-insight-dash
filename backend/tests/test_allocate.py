"""Greedy allocation validity, spills, and profile-sensitive choices."""

from fractions import Fraction

import pytest

from pgara.allocate import assert_allocation_valid, physical_registers
from pgara.cfg import build_cfg
from pgara.engine import analyze
from pgara.errors import InputError
from pgara.interference import build_interference
from pgara.liveness import analyze_liveness
from pgara.parser import parse
from pgara.samples import (
    BENCHMARK_CASES,
    CLIQUE_SOURCE,
    PROFILE_VS_STATIC_COUNTS,
    PROFILE_VS_STATIC_FLAT_COUNTS,
    PROFILE_VS_STATIC_SOURCE,
    SEQUENTIAL_SOURCE,
)


def _run(source, num_registers, profiles, algorithms, tradeoff=Fraction(0), budget=20):
    program = parse(source)
    return analyze(
        program,
        num_registers=num_registers,
        profiles=profiles,
        algorithms=algorithms,
        tradeoff=tradeoff,
        iteration_budget=budget,
        load_cost=1,
        store_cost=1,
        game_initial="all_spilled",
        allow_skip=False,
    )


def _ok(result, name):
    matches = [item for item in result.results if item.algorithm == name]
    assert len(matches) == 1
    return matches[0]


def test_non_interfering_ranges_share_one_register():
    result = _run(SEQUENTIAL_SOURCE, 1, [("once", {"entry": 1})], ["static_greedy"])
    allocation = _ok(result, "static_greedy")
    assert allocation.assignments == {"a": "p0", "b": "p0", "c": "p0"}
    assert allocation.spills == []
    assert allocation.stopping_reason == "single_pass"


def test_interfering_pair_spills_under_one_register():
    source = "block entry:\n  a = 1\n  b = 2\n  c = a + b\n  return c\n"
    result = _run(source, 1, [("once", {"entry": 1})], ["static_greedy"])
    allocation = _ok(result, "static_greedy")
    assert allocation.assignments["a"] != allocation.assignments["b"] or (
        allocation.assignments["a"] is None or allocation.assignments["b"] is None
    )
    # a and b interfere and have equal static cost, so id order gives a the register.
    assert allocation.assignments["a"] == "p0"
    assert allocation.assignments["b"] is None
    assert allocation.assignments["c"] == "p0"


def test_static_ignores_counts_and_profile_greedy_uses_them():
    hot = [("hot_b", dict(PROFILE_VS_STATIC_COUNTS))]
    flat = [("flat", dict(PROFILE_VS_STATIC_FLAT_COUNTS))]
    hot_result = _run(
        PROFILE_VS_STATIC_SOURCE,
        1,
        hot,
        ["static_greedy", "profile_greedy"],
    )
    flat_result = _run(
        PROFILE_VS_STATIC_SOURCE,
        1,
        flat,
        ["static_greedy", "profile_greedy"],
    )
    assert _ok(hot_result, "static_greedy").assignments["a"] == "p0"
    assert _ok(hot_result, "static_greedy").assignments["b"] is None
    assert _ok(flat_result, "static_greedy").assignments == _ok(hot_result, "static_greedy").assignments
    assert _ok(flat_result, "profile_greedy").assignments["a"] == "p0"
    assert _ok(flat_result, "profile_greedy").assignments["b"] is None
    assert _ok(hot_result, "profile_greedy").assignments["b"] == "p0"
    assert _ok(hot_result, "profile_greedy").assignments["a"] is None
    hot_costs = dict(_ok(hot_result, "profile_greedy").per_profile_costs)
    # Spilling a under the hot profile costs 8 estimated operations, not a runtime.
    assert hot_costs["hot_b"] == 8


def test_zero_registers_spill_every_live_range():
    result = _run(SEQUENTIAL_SOURCE, 0, [("once", {"entry": 1})], ["static_greedy", "profile_greedy"])
    for name in ("static_greedy", "profile_greedy"):
        allocation = _ok(result, name)
        assert allocation.physical_registers == []
        assert allocation.assignments == {"a": None, "b": None, "c": None}
        assert allocation.spills == ["a", "b", "c"]
        assert "num_registers is 0" in allocation.trace[0].reason


def test_insufficient_registers_remain_valid():
    program = parse(CLIQUE_SOURCE)
    result = _run(CLIQUE_SOURCE, 1, [("once", {"entry": 1, "use": 1})], ["static_greedy"])
    allocation = _ok(result, "static_greedy")
    graph = build_interference(program, analyze_liveness(program, build_cfg(program)))
    clique = ["a", "b", "c", "d"]
    spilled = [name for name in clique if allocation.assignments[name] is None]
    assert len(spilled) >= 3
    assert_allocation_valid(
        allocation.assignments,
        graph.edges,
        1,
        set(graph.ranges),
    )


def test_negative_register_count_is_rejected():
    program = parse(SEQUENTIAL_SOURCE)
    with pytest.raises(InputError, match="0 through"):
        analyze(
            program,
            num_registers=-1,
            profiles=[],
            algorithms=["static_greedy"],
            tradeoff=Fraction(0),
            iteration_budget=1,
            load_cost=1,
            store_cost=1,
            game_initial="all_spilled",
            allow_skip=False,
        )


def test_profile_allocator_refuses_missing_profiles():
    program = parse(SEQUENTIAL_SOURCE)
    with pytest.raises(InputError, match="does not invent"):
        analyze(
            program,
            num_registers=1,
            profiles=[],
            algorithms=["profile_greedy"],
            tradeoff=Fraction(0),
            iteration_budget=1,
            load_cost=1,
            store_cost=1,
            game_initial="all_spilled",
            allow_skip=False,
        )


def test_every_benchmark_case_is_a_valid_allocation():
    for case in BENCHMARK_CASES:
        result = _run(
            case.source,
            case.num_registers,
            list(case.profiles),
            ["static_greedy", "profile_greedy", "potential_game"],
            tradeoff=case.tradeoff,
            budget=case.iteration_budget,
        )
        edges = result.interference.edges
        ids = set(result.interference.ranges)
        for allocation in result.results:
            assert_allocation_valid(
                allocation.assignments, edges, case.num_registers, ids
            )
            for left, right in edges:
                left_reg = allocation.assignments[left]
                right_reg = allocation.assignments[right]
                assert left_reg is None or left_reg != right_reg


def test_physical_register_names():
    assert physical_registers(0) == []
    assert physical_registers(3) == ["p0", "p1", "p2"]
