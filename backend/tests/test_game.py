"""Potential-game moves, monotonicity, and tradeoff-sensitive choices."""

from fractions import Fraction

from pgara.costs import potential
from pgara.engine import analyze
from pgara.parser import parse
from pgara.samples import SEQUENTIAL_SOURCE, TRADEOFF_PROFILES, TRADEOFF_SOURCE


def _game(source, profiles, num_registers, tradeoff, budget, initial="all_spilled"):
    result = analyze(
        parse(source),
        num_registers=num_registers,
        profiles=profiles,
        algorithms=["potential_game"],
        tradeoff=tradeoff,
        iteration_budget=budget,
        load_cost=1,
        store_cost=1,
        game_initial=initial,
        allow_skip=False,
    )
    return result.results[0]


def test_tradeoff_changes_the_kept_range():
    profiles = list(TRADEOFF_PROFILES)
    average = _game(TRADEOFF_SOURCE, profiles, 1, Fraction(0), 10)
    worst = _game(TRADEOFF_SOURCE, profiles, 1, Fraction(1), 10)
    assert average.assignments == {"a": "p0", "b": None}
    assert worst.assignments == {"a": None, "b": "p0"}
    assert average.stopping_reason == "no_improving_move"
    assert worst.stopping_reason == "no_improving_move"
    assert [step.live_range for step in average.trace] == ["a"]
    assert [step.live_range for step in worst.trace] == ["b"]
    assert "not a proof of global optimality" in " ".join(average.notes)


def test_every_accepted_move_strictly_decreases_potential():
    allocation = _game(TRADEOFF_SOURCE, list(TRADEOFF_PROFILES), 1, Fraction(1, 2), 10)
    assert allocation.trace
    for step in allocation.trace:
        assert step.previous_potential is not None
        assert step.new_potential is not None
        assert step.new_potential < step.previous_potential
        recomputed_before = potential(
            [cost for _, cost in step.previous_profile_costs], Fraction(1, 2)
        )
        recomputed_after = potential(
            [cost for _, cost in step.new_profile_costs], Fraction(1, 2)
        )
        assert recomputed_before == step.previous_potential
        assert recomputed_after == step.new_potential
    # tradeoff 1/2 prefers keeping b: potentials 14.25 then 10.
    assert allocation.assignments["b"] == "p0"
    assert allocation.potential_value == Fraction(10)


def test_iteration_budget_stops_before_equilibrium():
    profiles = [("once", {"entry": 1})]
    stopped = _game(SEQUENTIAL_SOURCE, profiles, 1, Fraction(0), 1)
    finished = _game(SEQUENTIAL_SOURCE, profiles, 1, Fraction(0), 10)
    assert stopped.stopping_reason == "iteration_budget"
    assert stopped.iterations == 1
    assert stopped.assignments["a"] == "p0"
    assert stopped.assignments["b"] is None
    assert finished.stopping_reason == "no_improving_move"
    assert finished.assignments == {"a": "p0", "b": "p0", "c": "p0"}
    for step in finished.trace:
        assert step.new_potential < step.previous_potential


def test_zero_budget_does_not_move():
    allocation = _game(SEQUENTIAL_SOURCE, [("once", {"entry": 1})], 1, Fraction(0), 0)
    assert allocation.iterations == 0
    assert allocation.stopping_reason == "iteration_budget"
    assert allocation.assignments == {"a": None, "b": None, "c": None}


def test_zero_spill_weights_do_not_invent_an_improving_move():
    result = analyze(
        parse(SEQUENTIAL_SOURCE),
        num_registers=2,
        profiles=[("once", {"entry": 1})],
        algorithms=["potential_game", "static_greedy"],
        tradeoff=Fraction(0),
        iteration_budget=10,
        load_cost=0,
        store_cost=0,
        game_initial="all_spilled",
        allow_skip=False,
    )
    game = next(item for item in result.results if item.algorithm == "potential_game")
    static = next(item for item in result.results if item.algorithm == "static_greedy")
    assert game.trace == []
    assert game.stopping_reason == "no_improving_move"
    assert all(register is None for register in game.assignments.values())
    # Greedy still packs registers; it is not searching the potential.
    assert all(register is not None for register in static.assignments.values())


def test_starting_from_profile_greedy_can_miss_the_worst_case_choice():
    """A unilateral search cannot swap two ranges in one move.

    Profile-weighted greedy keeps a. Tradeoff 1 would prefer b, but b cannot
    take p0 while a still holds it, and spilling a alone raises the potential.
    The search correctly stops. This is not a global optimum.
    """
    allocation = _game(
        TRADEOFF_SOURCE,
        list(TRADEOFF_PROFILES),
        1,
        Fraction(1),
        10,
        initial="profile_greedy",
    )
    assert allocation.initial_allocation == {"a": "p0", "b": None}
    assert allocation.assignments == {"a": "p0", "b": None}
    assert allocation.iterations == 0
    assert allocation.stopping_reason == "no_improving_move"


def test_zero_registers_game_has_no_register_strategy():
    allocation = _game(SEQUENTIAL_SOURCE, [("once", {"entry": 1})], 0, Fraction(0), 5)
    assert allocation.assignments == {"a": None, "b": None, "c": None}
    assert allocation.stopping_reason == "no_improving_move"
    assert allocation.iterations == 0
