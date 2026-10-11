"""Iterative backward liveness analysis.

The analysis is may-liveness over virtual registers. It repeats a monotone
transfer until the block live-in and live-out sets stop changing. It does not
prove that a register is initialized on every path.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pgara.cfg import CFG
from pgara.errors import IRError
from pgara.ir import Program, mentioned_vregs


@dataclass
class Liveness:
    live_in: dict[str, set[str]]
    live_out: dict[str, set[str]]
    inst_live_in: dict[str, list[set[str]]]
    inst_live_out: dict[str, list[set[str]]]
    iterations: int = field(default=0)


def analyze_liveness(program: Program, cfg: CFG) -> Liveness:
    successors = cfg.successors()
    for block in program.blocks:
        successors.setdefault(block.label, [])

    live_in = {block.label: set() for block in program.blocks}
    live_out = {block.label: set() for block in program.blocks}
    vreg_count = max(1, len(mentioned_vregs(program)))
    # Each pass that changes state sets at least one new bit. There are two
    # sets per block and at most one bit per virtual register.
    limit = 2 * len(program.blocks) * vreg_count + 2
    iterations = 0
    changed = True
    while changed:
        changed = False
        iterations += 1
        if iterations > limit:
            raise IRError("liveness analysis did not converge")
        for block in reversed(program.blocks):
            out: set[str] = set()
            for succ in successors[block.label]:
                out |= live_in[succ]
            inn = set(out)
            for inst in reversed(block.instructions):
                if inst.dest is not None:
                    inn.discard(inst.dest)
                inn.update(inst.uses())
            if out != live_out[block.label] or inn != live_in[block.label]:
                live_out[block.label] = out
                live_in[block.label] = inn
                changed = True

    inst_in: dict[str, list[set[str]]] = {}
    inst_out: dict[str, list[set[str]]] = {}
    for block in program.blocks:
        per_in, per_out = _instruction_liveness(block.instructions, live_out[block.label])
        inst_in[block.label] = per_in
        inst_out[block.label] = per_out
        if block.instructions:
            if per_in[0] != live_in[block.label] or per_out[-1] != live_out[block.label]:
                raise IRError(
                    f"instruction liveness does not match the block solution in {block.label}"
                )
        elif live_in[block.label] != live_out[block.label]:
            raise IRError(f"empty block {block.label} has inconsistent liveness")

    return Liveness(live_in, live_out, inst_in, inst_out, iterations)


def _instruction_liveness(instructions: list, live_out: set[str]) -> tuple[list[set[str]], list[set[str]]]:
    per_in: list[set[str] | None] = [None] * len(instructions)
    per_out: list[set[str] | None] = [None] * len(instructions)
    live = set(live_out)
    for index in reversed(range(len(instructions))):
        inst = instructions[index]
        after = set(live)
        if inst.dest is not None:
            live.discard(inst.dest)
        live.update(inst.uses())
        per_out[index] = after
        per_in[index] = set(live)
    return [item for item in per_in if item is not None], [
        item for item in per_out if item is not None
    ]
