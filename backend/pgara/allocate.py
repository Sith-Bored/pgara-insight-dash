"""Register allocators.

Static greedy and profile-weighted greedy pack live ranges in a single pass.
The potential-game allocator starts from a valid assignment and accepts a
unilateral strategy change only when the documented potential strictly falls.

None of these procedures claims a globally optimal coloring.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from pgara.costs import (
    allocation_profile_costs,
    allocation_static_cost,
    potential,
    profile_spill_operations,
    static_spill_operations,
)
from pgara.errors import AllocationError, InputError
from pgara.ir import LiveRange
from pgara.policy import (
    GAME_LOCAL_NOTE,
    MAX_REGISTERS,
    PHYSICAL_REGISTER_PREFIX,
)


@dataclass(frozen=True)
class Decision:
    step: int
    live_range: str
    action: str
    previous_strategy: str | None
    strategy: str
    previous_potential: Fraction | None
    new_potential: Fraction | None
    previous_profile_costs: tuple[tuple[str, int], ...] | None
    new_profile_costs: tuple[tuple[str, int], ...] | None
    reason: str


@dataclass
class Allocation:
    algorithm: str
    assignments: dict[str, str | None]
    spills: list[str]
    physical_registers: list[str]
    static_spill_operations: int
    per_profile_costs: list[tuple[str, int]]
    potential_value: Fraction | None
    iterations: int
    stopping_reason: str
    initial_allocation: dict[str, str | None] | None
    trace: list[Decision]
    notes: list[str]


def physical_registers(num_registers: int) -> list[str]:
    check_num_registers(num_registers)
    return [f"{PHYSICAL_REGISTER_PREFIX}{index}" for index in range(num_registers)]


def check_num_registers(num_registers: int) -> None:
    if isinstance(num_registers, bool) or not isinstance(num_registers, int):
        raise InputError(
            "num_registers must be an integer from 0 through "
            f"{MAX_REGISTERS} inclusive"
        )
    if num_registers < 0 or num_registers > MAX_REGISTERS:
        raise InputError(
            "num_registers must be an integer from 0 through "
            f"{MAX_REGISTERS} inclusive. Zero is valid and spills every live range."
        )


def assert_allocation_valid(
    assignments: dict[str, str | None],
    edges: list[tuple[str, str]],
    num_registers: int,
    range_ids: set[str],
) -> None:
    """Reject two non-spilled interfering ranges that share a register."""
    allowed = set(physical_registers(num_registers))
    if set(assignments) != range_ids:
        missing = sorted(range_ids - set(assignments))
        extra = sorted(set(assignments) - range_ids)
        raise AllocationError(
            "assignment does not cover exactly the live ranges "
            f"(missing {missing}, extra {extra})"
        )
    for live_id, register in assignments.items():
        if register is not None and register not in allowed:
            raise AllocationError(
                f"live range {live_id} was assigned {register!r}, which is not "
                "one of the configured physical registers"
            )
    lookup = assignments
    for left, right in edges:
        left_reg = lookup[left]
        right_reg = lookup[right]
        if left_reg is not None and left_reg == right_reg:
            raise AllocationError(
                f"interfering live ranges {left} and {right} both received {left_reg}"
            )


def allocate_greedy(
    *,
    algorithm: str,
    ranges: dict[str, LiveRange],
    edges: list[tuple[str, str]],
    num_registers: int,
    profiles: list[tuple[str, dict[str, int]]],
    load_cost: int,
    store_cost: int,
    tradeoff: Fraction,
    weight_of,
    notes: list[str],
) -> Allocation:
    registers = physical_registers(num_registers)
    neighbors = _neighbors(ranges, edges)
    weights = {live_id: weight_of(live_range) for live_id, live_range in ranges.items()}
    order = sorted(ranges, key=lambda live_id: (-weights[live_id], live_id))
    assignments: dict[str, str | None] = {}
    trace: list[Decision] = []
    for step, live_id in enumerate(order):
        occupied: dict[str, list[str]] = {}
        for neighbor in sorted(neighbors[live_id]):
            held = assignments.get(neighbor)
            if held is not None:
                occupied.setdefault(held, []).append(neighbor)
        chosen: str | None = None
        for register in registers:
            if register not in occupied:
                chosen = register
                break
        assignments[live_id] = chosen
        if chosen is None:
            if num_registers == 0:
                reason = (
                    f"spilled {live_id}; num_registers is 0, so every live range spills"
                )
            else:
                held_text = ", ".join(
                    f"{register} held by {'/'.join(occupied[register])}"
                    for register in registers
                )
                reason = (
                    f"spilled {live_id}; every physical register is held by an "
                    f"interfering neighbor ({held_text}); heuristic weight {weights[live_id]}"
                )
            action = "spill"
            strategy = "spill"
        else:
            action = "assign"
            strategy = chosen
            reason = (
                f"assigned {chosen} to {live_id}; heuristic weight {weights[live_id]}"
            )
        trace.append(
            Decision(
                step=step,
                live_range=live_id,
                action=action,
                previous_strategy=None,
                strategy=strategy,
                previous_potential=None,
                new_potential=None,
                previous_profile_costs=None,
                new_profile_costs=None,
                reason=reason,
            )
        )
    return _finish(
        algorithm=algorithm,
        assignments=assignments,
        ranges=ranges,
        edges=edges,
        num_registers=num_registers,
        profiles=profiles,
        load_cost=load_cost,
        store_cost=store_cost,
        tradeoff=tradeoff,
        iterations=len(order),
        stopping_reason="single_pass",
        initial_allocation=None,
        trace=trace,
        notes=notes,
    )


def allocate_static_greedy(
    ranges: dict[str, LiveRange],
    edges: list[tuple[str, str]],
    num_registers: int,
    profiles: list[tuple[str, dict[str, int]]],
    load_cost: int,
    store_cost: int,
    tradeoff: Fraction,
) -> Allocation:
    notes = [
        "Static greedy orders live ranges by descending static spill-operation "
        "count and breaks ties by live-range id. Static counts are IR "
        "occurrences multiplied by load_cost and store_cost. They are not "
        "execution counts, and this allocator does not read profiles.",
        "Each range receives the lowest-numbered physical register that is not "
        "already held by an interfering neighbor assigned earlier. If none is "
        "free, the range spills.",
        "When profiles are present, per_profile_costs evaluate this static "
        "assignment under those supplied counts. They did not affect the "
        "decisions, and they are not measured runtime.",
        "The reported potential, when profiles are present, uses the request "
        "tradeoff so assignments can be compared. Static greedy does not "
        "optimize that potential.",
    ]

    def weight_of(live_range: LiveRange) -> int:
        return static_spill_operations(live_range, load_cost, store_cost)

    return allocate_greedy(
        algorithm="static_greedy",
        ranges=ranges,
        edges=edges,
        num_registers=num_registers,
        profiles=profiles,
        load_cost=load_cost,
        store_cost=store_cost,
        tradeoff=tradeoff,
        weight_of=weight_of,
        notes=notes,
    )


def allocate_profile_greedy(
    ranges: dict[str, LiveRange],
    edges: list[tuple[str, str]],
    num_registers: int,
    profiles: list[tuple[str, dict[str, int]]],
    load_cost: int,
    store_cost: int,
    tradeoff: Fraction,
) -> Allocation:
    if not profiles:
        raise InputError(
            "profile_greedy needs at least one execution profile. "
            "The analyzer does not invent execution counts."
        )
    notes = [
        "Profile-weighted greedy orders live ranges by the sum, across the "
        "supplied profiles, of estimated dynamic spill operations. Ties break "
        "by live-range id. Execution counts come only from the request.",
        "Register choice and spilling use the same one-pass packing rule as "
        "static greedy.",
        "per_profile_costs are estimated dynamic spill operations, not measured "
        "runtime. This heuristic does not claim to minimize the potential.",
    ]

    def weight_of(live_range: LiveRange) -> int:
        return sum(
            profile_spill_operations(live_range, counts, load_cost, store_cost)
            for _, counts in profiles
        )

    return allocate_greedy(
        algorithm="profile_greedy",
        ranges=ranges,
        edges=edges,
        num_registers=num_registers,
        profiles=profiles,
        load_cost=load_cost,
        store_cost=store_cost,
        tradeoff=tradeoff,
        weight_of=weight_of,
        notes=notes,
    )


def allocate_potential_game(
    ranges: dict[str, LiveRange],
    edges: list[tuple[str, str]],
    num_registers: int,
    profiles: list[tuple[str, dict[str, int]]],
    load_cost: int,
    store_cost: int,
    tradeoff: Fraction,
    iteration_budget: int,
    initial: str,
) -> Allocation:
    """Best-improvement dynamics on one live range at a time.

    Strategies are the physical registers and spilling. A move is feasible
    when the chosen register is not held by an interfering neighbor that is
    currently in a register. Spilling is always feasible. The move is accepted
    only when the potential strictly decreases. Among improving moves, the
    search keeps the lowest potential, scanning live ranges in id order and
    strategies in the order p0, p1, ..., spill.
    """
    if not profiles:
        raise InputError(
            "potential_game needs at least one execution profile. "
            "The analyzer does not invent execution counts."
        )
    if isinstance(iteration_budget, bool) or not isinstance(iteration_budget, int):
        raise InputError("iteration_budget must be an integer")
    if iteration_budget < 0:
        raise InputError("iteration_budget must be >= 0")
    if initial not in {"all_spilled", "static_greedy", "profile_greedy"}:
        raise InputError(
            "game_initial must be all_spilled, static_greedy, or profile_greedy"
        )

    registers = physical_registers(num_registers)
    neighbors = _neighbors(ranges, edges)
    if initial == "all_spilled":
        current = {live_id: None for live_id in ranges}
        initial_note = "Search started from the valid all-spilled allocation."
    elif initial == "static_greedy":
        seeded = allocate_static_greedy(
            ranges, edges, num_registers, profiles, load_cost, store_cost, tradeoff
        )
        current = dict(seeded.assignments)
        initial_note = "Search started from the static greedy allocation."
    else:
        seeded = allocate_profile_greedy(
            ranges, edges, num_registers, profiles, load_cost, store_cost, tradeoff
        )
        current = dict(seeded.assignments)
        initial_note = "Search started from the profile-weighted greedy allocation."

    initial_allocation = _ordered(current)
    strategies: list[tuple[str | None, str]] = [(name, name) for name in registers]
    strategies.append((None, "spill"))
    trace: list[Decision] = []
    stopping = "iteration_budget"
    if iteration_budget == 0:
        stopping = "iteration_budget"
    else:
        for _ in range(iteration_budget):
            current_costs = allocation_profile_costs(
                current, ranges, profiles, load_cost, store_cost
            )
            current_potential = potential([cost for _, cost in current_costs], tradeoff)
            best: tuple[Fraction, str, str | None, str, dict[str, str | None], list[tuple[str, int]]] | None = None
            for live_id in sorted(current):
                for strategy, strategy_name in strategies:
                    if current[live_id] == strategy:
                        continue
                    if not _feasible(live_id, strategy, current, neighbors):
                        continue
                    candidate = dict(current)
                    candidate[live_id] = strategy
                    candidate_costs = allocation_profile_costs(
                        candidate, ranges, profiles, load_cost, store_cost
                    )
                    candidate_potential = potential(
                        [cost for _, cost in candidate_costs], tradeoff
                    )
                    if candidate_potential < current_potential and (
                        best is None or candidate_potential < best[0]
                    ):
                        best = (
                            candidate_potential,
                            live_id,
                            strategy,
                            strategy_name,
                            candidate,
                            candidate_costs,
                        )
            if best is None:
                stopping = "no_improving_move"
                break
            new_potential, live_id, _strategy, strategy_name, candidate, candidate_costs = best
            previous_name = "spill" if current[live_id] is None else current[live_id]
            trace.append(
                Decision(
                    step=len(trace),
                    live_range=live_id,
                    action="move",
                    previous_strategy=previous_name,
                    strategy=strategy_name,
                    previous_potential=current_potential,
                    new_potential=new_potential,
                    previous_profile_costs=tuple(current_costs),
                    new_profile_costs=tuple(candidate_costs),
                    reason=(
                        f"moved {live_id} from {previous_name} to {strategy_name}; "
                        f"potential {current_potential} -> {new_potential}"
                    ),
                )
            )
            current = candidate
        else:
            stopping = "iteration_budget"

    notes = [
        initial_note,
        GAME_LOCAL_NOTE,
        "The potential is (1 - tradeoff) * (average estimated spill cost across "
        "profiles) + tradeoff * (worst-profile estimated spill cost). "
        "Costs are estimated spill operations, not measured runtime.",
        "A move between two physical registers does not change this cost model. "
        "Only a spill change that strictly lowers the potential is accepted. "
        "Because only one live range moves at a time, a better assignment that "
        "requires two ranges to change together may be unreachable from the start.",
    ]
    return _finish(
        algorithm="potential_game",
        assignments=current,
        ranges=ranges,
        edges=edges,
        num_registers=num_registers,
        profiles=profiles,
        load_cost=load_cost,
        store_cost=store_cost,
        tradeoff=tradeoff,
        iterations=len(trace),
        stopping_reason=stopping,
        initial_allocation=initial_allocation,
        trace=trace,
        notes=notes,
    )


def _feasible(
    live_id: str,
    strategy: str | None,
    assignments: dict[str, str | None],
    neighbors: dict[str, set[str]],
) -> bool:
    if strategy is None:
        return True
    for neighbor in neighbors[live_id]:
        if assignments[neighbor] == strategy:
            return False
    return True


def _neighbors(
    ranges: dict[str, LiveRange], edges: list[tuple[str, str]]
) -> dict[str, set[str]]:
    adj = {live_id: set() for live_id in ranges}
    for left, right in edges:
        adj[left].add(right)
        adj[right].add(left)
    return adj


def _ordered(assignments: dict[str, str | None]) -> dict[str, str | None]:
    return {live_id: assignments[live_id] for live_id in sorted(assignments)}


def _finish(
    *,
    algorithm: str,
    assignments: dict[str, str | None],
    ranges: dict[str, LiveRange],
    edges: list[tuple[str, str]],
    num_registers: int,
    profiles: list[tuple[str, dict[str, int]]],
    load_cost: int,
    store_cost: int,
    tradeoff: Fraction,
    iterations: int,
    stopping_reason: str,
    initial_allocation: dict[str, str | None] | None,
    trace: list[Decision],
    notes: list[str],
) -> Allocation:
    ordered = _ordered(assignments)
    assert_allocation_valid(ordered, edges, num_registers, set(ranges))
    profile_costs = allocation_profile_costs(
        ordered, ranges, profiles, load_cost, store_cost
    )
    potential_value = (
        potential([cost for _, cost in profile_costs], tradeoff) if profiles else None
    )
    spills = [live_id for live_id, register in ordered.items() if register is None]
    return Allocation(
        algorithm=algorithm,
        assignments=ordered,
        spills=spills,
        physical_registers=physical_registers(num_registers),
        static_spill_operations=allocation_static_cost(
            ordered, ranges, load_cost, store_cost
        ),
        per_profile_costs=profile_costs,
        potential_value=potential_value,
        iterations=iterations,
        stopping_reason=stopping_reason,
        initial_allocation=initial_allocation,
        trace=trace,
        notes=notes,
    )
