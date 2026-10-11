"""Interference edges come from simultaneously live ranges."""

from pgara.cfg import build_cfg
from pgara.interference import build_interference
from pgara.liveness import analyze_liveness
from pgara.parser import parse
from pgara.samples import DIAMOND_SOURCE, LOOP_SOURCE, PARAMETERS_SOURCE, SEQUENTIAL_SOURCE


def _graph(source: str):
    program = parse(source)
    liveness = analyze_liveness(program, build_cfg(program))
    return program, liveness, build_interference(program, liveness)


def test_parameters_that_are_live_together_interfere():
    _program, _liveness, graph = _graph(PARAMETERS_SOURCE)
    assert ("a", "b") in graph.edges
    assert "a" in graph.ranges and "b" in graph.ranges
    assert all(left != "c" and right != "c" for left, right in graph.edges) or (
        "c" not in {name for edge in graph.edges for name in edge}
    )


def test_sequential_copies_do_not_interfere():
    _program, _liveness, graph = _graph(SEQUENTIAL_SOURCE)
    assert graph.edges == []
    assert set(graph.ranges) == {"a", "b", "c"}


def test_loop_ranges_interfere_and_record_sites():
    _program, _liveness, graph = _graph(LOOP_SOURCE)
    assert graph.edges == [("i", "s")]
    assert {site.kind for site in graph.ranges["i"].defs} == {"store"}
    assert graph.ranges["i"].uses
    assert graph.ranges["s"].uses


def test_diamond_interference_matches_every_co_live_pair():
    program, liveness, graph = _graph(DIAMOND_SOURCE)
    co_live: set[tuple[str, str]] = set()
    for block in program.blocks:
        boundaries = [liveness.live_in[block.label], liveness.live_out[block.label]]
        boundaries.extend(liveness.inst_live_in[block.label])
        boundaries.extend(liveness.inst_live_out[block.label])
        for live in boundaries:
            ordered = sorted(live)
            for index, left in enumerate(ordered):
                for right in ordered[index + 1 :]:
                    co_live.add((left, right))
    assert set(graph.edges) == co_live
    assert ("a", "b") in graph.edges
    assert "c" in graph.ranges


def test_dead_definition_is_not_a_live_range():
    _program, _liveness, graph = _graph("block entry:\n  a = 1\n  return 0\n")
    assert graph.ranges == {}
    assert len(graph.dead_defs) == 1
    assert graph.dead_defs[0].dest == "a"
