"""Parsing and malformed-input tests."""

import pytest

from pgara.errors import IRError
from pgara.ir import format_program
from pgara.parser import parse
from pgara.samples import DIAMOND_SOURCE, LOOP_SOURCE, TRADEOFF_SOURCE


def test_parses_loop_and_round_trips_structure():
    program = parse(LOOP_SOURCE)
    assert [block.label for block in program.blocks] == ["entry", "header", "exit", "body"]
    again = parse(format_program(program))
    assert format_program(again) == format_program(program)
    assert program.blocks[1].instructions[0].op == "br"
    assert program.blocks[1].instructions[0].target == "body"


def test_parses_comments_blank_lines_and_negative_immediate():
    source = """
    # header comment
    block entry:  # trailing
      a = -3
      b = a + 4
      return b
    """
    program = parse(source)
    text = format_program(program)
    assert "a = -3" in text
    assert "b = a + 4" in text
    assert program.blocks[0].instructions[0].operands[0].value == -3


def test_unique_use_per_instruction():
    program = parse("block entry:\n  a = 1\n  b = a + a\n  return b\n")
    assert program.blocks[0].instructions[1].uses() == ["a"]


@pytest.mark.parametrize(
    "source, fragment",
    [
        ("", "no basic blocks"),
        ("# only a comment\n", "no basic blocks"),
        ("a = 1\n", "before the first block"),
        ("block entry:\n  goto\n", "goto needs one target"),
        ("block entry:\n  if goto later\n", "conditional branch"),
        ("block entry:\n  a = b +\n", "assignment must be"),
        ("block entry:\n  a = b % c\n", "unknown operator"),
        ("block :\n  return\n", "block header"),
        ("block entry\n  return\n", "block header"),
        ("block entry:\n  return 1\n  a = 2\n", "after terminator"),
        ("block entry:\n  return\nblock entry:\n  return\n", "duplicate block"),
        ("block entry:\n  a = if\n", "invalid virtual register"),
        ("block goto:\n  return\n", "invalid block label"),
        ("block entry:\n  a = b + c + d\n", "assignment must be"),
    ],
)
def test_malformed_programs_report_errors(source, fragment):
    with pytest.raises(IRError) as caught:
        parse(source)
    assert fragment in str(caught.value)


def test_error_includes_line_number():
    source = "block entry:\n  a = 1\n  goto\n"
    with pytest.raises(IRError) as caught:
        parse(source)
    assert caught.value.line == 3


def test_crlf_source_parses():
    source = "block entry:\r\n  a = 1\r\n  return a\r\n"
    program = parse(source)
    assert program.blocks[0].instructions[1].uses() == ["a"]


def test_sample_sources_parse():
    parse(DIAMOND_SOURCE)
    parse(LOOP_SOURCE)
    parse(TRADEOFF_SOURCE)
