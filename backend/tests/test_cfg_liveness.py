"""Control-flow graph and iterative liveness tests."""

import pytest

from pgara.cfg import build_cfg
from pgara.errors import IRError
from pgara.liveness import analyze_liveness
from pgara.parser import parse
from pgara.samples import DIAMOND_SOURCE, LOOP_SOURCE


def _analyze(source: str):
    program = parse(source)
    cfg = build_cfg(program)
    return program, cfg, analyze_liveness(program, cfg)


def test_diamond_edges_use_next_block_as_false_successor():
    _program, cfg, _liveness = _analyze(DIAMOND_SOURCE)
    kinds = {(edge.source, edge.target, edge.kind) for edge in cfg.edges}
    assert ("entry", "left", "branch_true") in kinds
    assert ("entry", "right", "branch_false") in kinds
    assert ("right", "join", "jump") in kinds
    assert ("left", "join", "jump") in kinds
    assert cfg.edges_from("join") == []


def test_fallthrough_when_block_has_no_terminator():
    _program, cfg, liveness = _analyze("block entry:\n  a = 1\nblock next:\n  return a\n")
    assert [(edge.target, edge.kind) for edge in cfg.edges] == [("next", "fallthrough")]
    assert liveness.live_in["entry"] == set()
    assert liveness.live_out["entry"] == {"a"}
    assert liveness.live_in["next"] == {"a"}
    assert liveness.live_out["next"] == set()


def test_loop_liveness_reaches_fixpoint():
    _program, cfg, liveness = _analyze(LOOP_SOURCE)
    assert liveness.iterations >= 2
    assert liveness.live_in["entry"] == set()
    assert liveness.live_in["header"] == {"i", "s"}
    assert liveness.live_in["body"] == {"i", "s"}
    assert liveness.live_in["exit"] == {"s"}
    assert liveness.live_out["exit"] == set()
    header_edges = {(edge.target, edge.kind) for edge in cfg.edges_from("header")}
    assert header_edges == {("body", "branch_true"), ("exit", "branch_false")}


def test_instruction_liveness_is_adjacent():
    program, _cfg, liveness = _analyze(LOOP_SOURCE)
    for block in program.blocks:
        inst_in = liveness.inst_live_in[block.label]
        inst_out = liveness.inst_live_out[block.label]
        if not block.instructions:
            continue
        assert inst_in[0] == liveness.live_in[block.label]
        assert inst_out[-1] == liveness.live_out[block.label]
        for index in range(len(block.instructions) - 1):
            assert inst_out[index] == inst_in[index + 1]


def test_self_loop_with_a_use_converges():
    _program, _cfg, liveness = _analyze("block entry:\n  a = a + 1\n  goto entry\n")
    assert liveness.live_in["entry"] == {"a"}
    assert liveness.live_out["entry"] == {"a"}


def test_dead_self_loop_has_empty_liveness():
    _program, _cfg, liveness = _analyze("block entry:\n  a = 1\n  goto entry\n")
    assert liveness.live_in["entry"] == set()
    assert liveness.live_out["entry"] == set()


def test_missing_target_is_rejected():
    program = parse("block entry:\n  goto missing\n")
    with pytest.raises(IRError, match="unknown block"):
        build_cfg(program)


def test_final_block_without_terminator_is_rejected():
    program = parse("block entry:\n  a = 1\n")
    with pytest.raises(IRError, match="does not end with"):
        build_cfg(program)


def test_conditional_in_final_block_is_rejected():
    program = parse("block entry:\n  a = 1\n  if a goto entry\n")
    with pytest.raises(IRError, match="no false successor"):
        build_cfg(program)
