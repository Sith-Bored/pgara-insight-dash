"""Three-address intermediate representation.

Milestone 1 uses one live range per virtual register. Live-range splitting
can be added later by introducing several ``LiveRange`` values that share a
``vreg`` and differ in ``id``. Allocators already key decisions by ``id``.
"""

from __future__ import annotations

from dataclasses import dataclass

from pgara.errors import IRError
from pgara.policy import MAX_BLOCKS, MAX_INSTRUCTIONS

KEYWORDS = frozenset({"block", "if", "goto", "return"})
BINOPS = {
    "add": "+",
    "sub": "-",
    "mul": "*",
    "div": "/",
}
IDENT = r"[A-Za-z_][A-Za-z0-9_]*"


@dataclass(frozen=True)
class Imm:
    value: int


@dataclass(frozen=True)
class Reg:
    name: str


Operand = Imm | Reg


@dataclass(frozen=True)
class Instruction:
    op: str
    dest: str | None
    operands: tuple[Operand, ...]
    target: str | None
    line: int | None

    def uses(self) -> list[str]:
        """Virtual registers read by this instruction, once each, in order."""
        seen: list[str] = []
        for operand in self.operands:
            if isinstance(operand, Reg) and operand.name not in seen:
                seen.append(operand.name)
        return seen


@dataclass
class Block:
    label: str
    instructions: list[Instruction]


@dataclass
class Program:
    blocks: list[Block]

    def labels(self) -> list[str]:
        return [block.label for block in self.blocks]


@dataclass(frozen=True)
class Site:
    block: str
    index: int
    kind: str  # "load" or "store"


@dataclass
class LiveRange:
    """A register-allocation player.

    ``id`` is the allocation key. In milestone 1 it equals ``vreg`` because
    ranges are not split. A later splitting pass can emit ids such as
    ``a#0`` and ``a#1`` without changing the allocators.
    """

    id: str
    vreg: str
    defs: list[Site]
    uses: list[Site]


def is_ident(text: str) -> bool:
    if not text or text[0].isdigit():
        return False
    return all(ch.isalnum() or ch == "_" for ch in text) and (
        text[0].isalpha() or text[0] == "_"
    )


def check_label(label: str, line: int | None = None) -> None:
    if not is_ident(label) or label in KEYWORDS:
        raise IRError(
            f"invalid block label {label!r}; labels must be identifiers and "
            "cannot be keywords (block, if, goto, return)",
            line,
        )


def check_reg_name(name: str, line: int | None = None) -> None:
    if not is_ident(name) or name in KEYWORDS:
        raise IRError(
            f"invalid virtual register {name!r}; registers must be identifiers "
            "and cannot be keywords (block, if, goto, return)",
            line,
        )


def check_instruction_shape(inst: Instruction) -> None:
    """Reject structurally impossible instructions from either input path."""
    line = inst.line
    if inst.dest is not None:
        check_reg_name(inst.dest, line)
    for operand in inst.operands:
        if isinstance(operand, Reg):
            check_reg_name(operand.name, line)
    if inst.target is not None:
        check_label(inst.target, line)

    if inst.op == "const":
        _expect(inst.dest is not None, "const needs a destination", line)
        _expect(len(inst.operands) == 1 and isinstance(inst.operands[0], Imm),
                "const needs one integer operand", line)
        _expect(inst.target is None, "const cannot have a target", line)
    elif inst.op == "mov":
        _expect(inst.dest is not None, "move needs a destination", line)
        _expect(len(inst.operands) == 1 and isinstance(inst.operands[0], Reg),
                "move needs one virtual-register operand", line)
        _expect(inst.target is None, "move cannot have a target", line)
    elif inst.op in BINOPS:
        _expect(inst.dest is not None, f"{inst.op} needs a destination", line)
        _expect(len(inst.operands) == 2, f"{inst.op} needs two operands", line)
        _expect(inst.target is None, f"{inst.op} cannot have a target", line)
    elif inst.op == "br":
        _expect(inst.dest is None, "conditional branch cannot have a destination", line)
        _expect(len(inst.operands) == 1, "conditional branch needs one condition", line)
        _expect(inst.target is not None, "conditional branch needs a target", line)
    elif inst.op == "jmp":
        _expect(inst.dest is None, "jump cannot have a destination", line)
        _expect(len(inst.operands) == 0, "jump cannot have operands", line)
        _expect(inst.target is not None, "jump needs a target", line)
    elif inst.op == "ret":
        _expect(inst.dest is None, "return cannot have a destination", line)
        _expect(len(inst.operands) <= 1, "return takes at most one operand", line)
        _expect(inst.target is None, "return cannot have a target", line)
    else:
        raise IRError(f"unknown opcode {inst.op!r}", line)


def is_terminator(inst: Instruction) -> bool:
    return inst.op in {"br", "jmp", "ret"}


def validate_program(program: Program) -> None:
    """Structural checks that do not need the control-flow graph.

    Branch targets and fall-through successors are checked when the CFG is built.
    """
    if not program.blocks:
        raise IRError("program has no basic blocks")
    if len(program.blocks) > MAX_BLOCKS:
        raise IRError(
            f"program has {len(program.blocks)} blocks; the limit is {MAX_BLOCKS}"
        )
    seen: set[str] = set()
    instruction_count = 0
    for block in program.blocks:
        check_label(block.label)
        if block.label in seen:
            raise IRError(f"duplicate block label {block.label!r}")
        seen.add(block.label)
        instruction_count += len(block.instructions)
        for index, inst in enumerate(block.instructions):
            check_instruction_shape(inst)
            if index > 0 and is_terminator(block.instructions[index - 1]):
                raise IRError(
                    f"instruction after terminator in block {block.label}",
                    inst.line,
                )
    if instruction_count > MAX_INSTRUCTIONS:
        raise IRError(
            f"program has {instruction_count} instructions; the limit is "
            f"{MAX_INSTRUCTIONS}"
        )


def undefined_uses(program: Program) -> list[str]:
    """Virtual registers that are read and never defined anywhere.

    This is not a path-sensitive initialization check. A register defined on
    only one branch is not listed here.
    """
    defined: set[str] = set()
    used: set[str] = set()
    for block in program.blocks:
        for inst in block.instructions:
            if inst.dest is not None:
                defined.add(inst.dest)
            used.update(inst.uses())
    return sorted(used - defined)


def mentioned_vregs(program: Program) -> set[str]:
    names: set[str] = set()
    for block in program.blocks:
        for inst in block.instructions:
            if inst.dest is not None:
                names.add(inst.dest)
            names.update(inst.uses())
    return names


def format_operand(operand: Operand) -> str:
    if isinstance(operand, Imm):
        return str(operand.value)
    return operand.name


def format_instruction(inst: Instruction) -> str:
    if inst.op == "ret":
        if inst.operands:
            return f"return {format_operand(inst.operands[0])}"
        return "return"
    if inst.op == "jmp":
        return f"goto {inst.target}"
    if inst.op == "br":
        return f"if {format_operand(inst.operands[0])} goto {inst.target}"
    if inst.op == "const":
        return f"{inst.dest} = {format_operand(inst.operands[0])}"
    if inst.op == "mov":
        return f"{inst.dest} = {format_operand(inst.operands[0])}"
    symbol = BINOPS[inst.op]
    return (
        f"{inst.dest} = {format_operand(inst.operands[0])} "
        f"{symbol} {format_operand(inst.operands[1])}"
    )


def format_program(program: Program) -> str:
    parts: list[str] = []
    for block in program.blocks:
        parts.append(f"block {block.label}:")
        for inst in block.instructions:
            parts.append(f"  {format_instruction(inst)}")
    return "\n".join(parts) + ("\n" if parts else "")


def _expect(condition: bool, message: str, line: int | None) -> None:
    if not condition:
        raise IRError(message, line)
