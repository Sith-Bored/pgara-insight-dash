"""End-to-end analysis used by the library, tests, and HTTP API."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from fractions import Fraction

from pgara.allocate import (
    Allocation,
    allocate_potential_game,
    allocate_profile_greedy,
    allocate_static_greedy,
    physical_registers,
)
from pgara.cfg import CFG, build_cfg
from pgara.costs import (
    profile_spill_operations,
    static_spill_operations,
    validate_profiles,
)
from pgara.errors import InputError
from pgara.interference import Interference, build_interference
from pgara.ir import Program, undefined_uses
from pgara.liveness import Liveness, analyze_liveness
from pgara.policy import PROFILES_REQUIRED


@dataclass
class SkippedAllocation:
    algorithm: str
    skip_reason: str
    notes: list[str]
    physical_registers: list[str] = field(default_factory=list)


@dataclass
class EngineResult:
    program: Program
    cfg: CFG
    liveness: Liveness
    interference: Interference
    undefined_uses: list[str]
    live_range_static_costs: dict[str, int]
    live_range_profile_costs: dict[str, list[tuple[str, int]]]
    results: list[Allocation | SkippedAllocation] = field(default_factory=list)
    timings_ms: dict[str, float] = field(default_factory=dict)


def analyze(
    program: Program,
    *,
    num_registers: int,
    profiles: list[tuple[str, dict[str, int]]],
    algorithms: list[str],
    tradeoff: Fraction,
    iteration_budget: int,
    load_cost: int,
    store_cost: int,
    game_initial: str,
    allow_skip: bool,
) -> EngineResult:
    if tradeoff < 0 or tradeoff > 1:
        raise InputError("tradeoff must be between 0 and 1 inclusive")
    if load_cost < 0 or store_cost < 0:
        raise InputError("load_cost and store_cost must be >= 0")
    validate_profiles(program, profiles)
    cfg = build_cfg(program)
    liveness = analyze_liveness(program, cfg)
    interference = build_interference(program, liveness)
    ranges = interference.ranges
    static_costs = {
        live_id: static_spill_operations(live_range, load_cost, store_cost)
        for live_id, live_range in ranges.items()
    }
    profile_costs = {
        live_id: [
            (
                name,
                profile_spill_operations(live_range, counts, load_cost, store_cost),
            )
            for name, counts in profiles
        ]
        for live_id, live_range in ranges.items()
    }
    result = EngineResult(
        program=program,
        cfg=cfg,
        liveness=liveness,
        interference=interference,
        undefined_uses=undefined_uses(program),
        live_range_static_costs=static_costs,
        live_range_profile_costs=profile_costs,
    )
    for algorithm in algorithms:
        if algorithm in {"profile_greedy", "potential_game"} and not profiles:
            if not allow_skip:
                raise InputError(PROFILES_REQUIRED)
            result.results.append(
                SkippedAllocation(
                    algorithm,
                    PROFILES_REQUIRED,
                    [PROFILES_REQUIRED],
                    physical_registers(num_registers),
                )
            )
            result.timings_ms[algorithm] = 0.0
            continue
        started = time.perf_counter()
        if algorithm == "static_greedy":
            allocation = allocate_static_greedy(
                ranges,
                interference.edges,
                num_registers,
                profiles,
                load_cost,
                store_cost,
                tradeoff,
            )
        elif algorithm == "profile_greedy":
            allocation = allocate_profile_greedy(
                ranges,
                interference.edges,
                num_registers,
                profiles,
                load_cost,
                store_cost,
                tradeoff,
            )
        elif algorithm == "potential_game":
            allocation = allocate_potential_game(
                ranges,
                interference.edges,
                num_registers,
                profiles,
                load_cost,
                store_cost,
                tradeoff,
                iteration_budget,
                game_initial,
            )
        else:
            raise InputError(f"unknown algorithm {algorithm!r}")
        result.timings_ms[algorithm] = (time.perf_counter() - started) * 1000.0
        result.results.append(allocation)
    return result
