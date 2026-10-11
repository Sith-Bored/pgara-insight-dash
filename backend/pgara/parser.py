"""Line-oriented parser for the milestone-1 three-address IR.

One instruction per line. ``#`` starts a comment. Binary operators must be
separated from their operands by whitespace, so ``a = b - 1`` is subtraction
and ``a = -1`` is a constant.
"""

from __future__ import annotations

import re

from pgara.errors import IRError
from pgara.ir import (
    BINOPS,
    Block,
    Imm,
    Instruction,
    Program,
    Reg,
    check_label,
    check_reg_name,
    validate_program,
)

_IMM = re.compile(r"[-+]?\d+\Z")
_SYMBOL_TO_OP = {symbol: op for op, symbol in BINOPS.items()}


def parse(source: str) -> Program:
    """Parse ``source`` and return a structurally validated program.

    Control-flow targets are checked later by CFG construction.
    """
    if source is None:
        raise IRError("source is missing")
    if source.startswith("\ufeff"):
        source = source[1:]
    blocks: list[Block] = []
    current: Block | None = None
    for line_number, raw in enumerate(source.splitlines(), start=1):
        text = _strip_comment(raw).strip()
        if not text:
            continue
        if text.startswith("block ") or text == "block":
            label = _parse_block_header(text, line_number)
            current = Block(label, [])
            blocks.append(current)
            continue
        if current is None:
            raise IRError("instruction appears before the first block", line_number)
        current.instructions.append(_parse_instruction(text, line_number))
    program = Program(blocks)
    validate_program(program)
    return program


def _strip_comment(raw: str) -> str:
    hash_at = raw.find("#")
    if hash_at >= 0:
        return raw[:hash_at]
    return raw


def _parse_block_header(text: str, line: int) -> str:
    tokens = text.split()
    if not tokens or tokens[0] != "block":
        raise IRError("expected a block header", line)
    if len(tokens) == 2 and tokens[1].endswith(":") and tokens[1] != ":":
        label = tokens[1][:-1]
    elif len(tokens) == 3 and tokens[2] == ":":
        label = tokens[1]
    else:
        raise IRError(
            "block header must look like 'block name:'",
            line,
        )
    check_label(label, line)
    return label


def _parse_instruction(text: str, line: int) -> Instruction:
    tokens = text.split()
    head = tokens[0]
    if head == "return":
        if len(tokens) == 1:
            return Instruction("ret", None, (), None, line)
        if len(tokens) == 2:
            return Instruction("ret", None, (_parse_operand(tokens[1], line),), None, line)
        raise IRError("return takes at most one operand", line)
    if head == "goto":
        if len(tokens) != 2:
            raise IRError("goto needs one target label", line)
        check_label(tokens[1], line)
        return Instruction("jmp", None, (), tokens[1], line)
    if head == "if":
        if len(tokens) != 4 or tokens[2] != "goto":
            raise IRError("conditional branch must look like 'if <operand> goto <label>'", line)
        check_label(tokens[3], line)
        return Instruction("br", None, (_parse_operand(tokens[1], line),), tokens[3], line)
    if len(tokens) < 3 or tokens[1] != "=":
        raise IRError(
            "expected an assignment, 'if', 'goto', or 'return'",
            line,
        )
    dest = tokens[0]
    check_reg_name(dest, line)
    rhs = tokens[2:]
    if len(rhs) == 1:
        operand = _parse_operand(rhs[0], line)
        if isinstance(operand, Imm):
            return Instruction("const", dest, (operand,), None, line)
        return Instruction("mov", dest, (operand,), None, line)
    if len(rhs) == 3:
        symbol = rhs[1]
        if symbol not in _SYMBOL_TO_OP:
            raise IRError(
                f"unknown operator {symbol!r}; use +, -, *, or / with spaces around it",
                line,
            )
        left = _parse_operand(rhs[0], line)
        right = _parse_operand(rhs[2], line)
        return Instruction(_SYMBOL_TO_OP[symbol], dest, (left, right), None, line)
    raise IRError(
        "assignment must be 'reg = operand' or 'reg = operand <op> operand'",
        line,
    )


def _parse_operand(token: str, line: int) -> Imm | Reg:
    if _IMM.fullmatch(token):
        return Imm(int(token))
    check_reg_name(token, line)
    return Reg(token)
