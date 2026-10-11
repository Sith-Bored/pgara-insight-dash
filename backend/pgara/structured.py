"""Build a Program from the structured JSON IR."""

from __future__ import annotations

from pgara.errors import IRError
from pgara.ir import Block, Imm, Instruction, Program, Reg, validate_program
from pgara.schemas import OperandIn, ProgramIn


def program_from_structured(model: ProgramIn) -> Program:
    blocks = [
        Block(block.label, [_instruction(inst) for inst in block.instructions])
        for block in model.blocks
    ]
    program = Program(blocks)
    validate_program(program)
    return program


def _instruction(model) -> Instruction:
    return Instruction(
        op=model.op,
        dest=model.dest,
        operands=tuple(_operand(operand) for operand in model.operands),
        target=model.target,
        line=None,
    )


def _operand(operand: OperandIn) -> Imm | Reg:
    if operand.kind == "imm":
        if operand.name is not None:
            raise IRError("immediate operand cannot include a register name")
        if operand.value is None or isinstance(operand.value, bool):
            raise IRError("immediate operand needs an integer value")
        return Imm(operand.value)
    if operand.name is None:
        raise IRError("register operand needs a name")
    if operand.value is not None:
        raise IRError("register operand cannot include an integer value")
    return Reg(operand.name)
