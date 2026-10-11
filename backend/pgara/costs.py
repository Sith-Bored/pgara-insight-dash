"""Spill-cost estimates.

Profile costs use only execution counts the caller supplied. Static costs
count IR occurrences. Neither quantity is measured runtime.
"""

from __future__ import annotations

from fractions import Fraction

from pgara.errors import InputError
from pgara.ir import LiveRange, Program


def validate_profiles(
    program: Program,
    profiles: list[tuple[str, dict[str, int]]],
) -> None:
    labels = set(program.labels())
    seen: set[str] = set()
    for name, counts in profiles:
        if not name or name != name.strip():
            raise InputError("profile name must be a non-empty string without surrounding whitespace")
        if name in seen:
            raise InputError(f"duplicate profile name {name!r}")
        seen.add(name)
        missing = sorted(labels - set(counts))
        unknown = sorted(set(counts) - labels)
        if missing:
            raise InputError(
                f"profile {name!r} is missing execution counts for blocks: "
                + ", ".join(missing)
            )
        if unknown:
            raise InputError(
                f"profile {name!r} has execution counts for unknown blocks: "
                + ", ".join(unknown)
            )
        for label, count in counts.items():
            if isinstance(count, bool) or not isinstance(count, int):
                raise InputError(
                    f"profile {name!r} execution count for block {label!r} must be an integer"
                )
            if count < 0:
                raise InputError(
                    f"profile {name!r} has a negative execution count for block {label!r}"
                )


def static_spill_operations(live_range: LiveRange, load_cost: int, store_cost: int) -> int:
    """Spill operations counted once per IR site, ignoring execution counts."""
    return load_cost * len(live_range.uses) + store_cost * len(live_range.defs)


def profile_spill_operations(
    live_range: LiveRange,
    block_counts: dict[str, int],
    load_cost: int,
    store_cost: int,
) -> int:
    """Estimated dynamic spill operations for one spilled range under one profile."""
    total = 0
    for site in live_range.uses:
        total += load_cost * block_counts[site.block]
    for site in live_range.defs:
        total += store_cost * block_counts[site.block]
    return total


def allocation_profile_costs(
    assignments: dict[str, str | None],
    ranges: dict[str, LiveRange],
    profiles: list[tuple[str, dict[str, int]]],
    load_cost: int,
    store_cost: int,
) -> list[tuple[str, int]]:
    """Estimated dynamic spill operations of an allocation, per supplied profile."""
    totals: list[tuple[str, int]] = []
    for name, counts in profiles:
        total = 0
        for live_id, register in assignments.items():
            if register is None:
                total += profile_spill_operations(ranges[live_id], counts, load_cost, store_cost)
        totals.append((name, total))
    return totals


def allocation_static_cost(
    assignments: dict[str, str | None],
    ranges: dict[str, LiveRange],
    load_cost: int,
    store_cost: int,
) -> int:
    total = 0
    for live_id, register in assignments.items():
        if register is None:
            total += static_spill_operations(ranges[live_id], load_cost, store_cost)
    return total


def potential(costs: list[int], tradeoff: Fraction) -> Fraction:
    """``(1 - tradeoff) * average + tradeoff * worst``.

    ``tradeoff`` is the weight on the worst supplied profile. ``0`` uses only
    the average estimated spill cost. ``1`` uses only the worst profile.
    """
    if not costs:
        raise InputError("potential is undefined without at least one profile")
    if tradeoff < 0 or tradeoff > 1:
        raise InputError("tradeoff must be between 0 and 1 inclusive")
    average = Fraction(sum(costs), len(costs))
    worst = Fraction(max(costs))
    return (1 - tradeoff) * average + tradeoff * worst
