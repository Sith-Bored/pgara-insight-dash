"""Control-flow graph construction.

A conditional branch's true edge goes to its labeled target. Its false edge
is the next block in source order. A block that does not end in ``goto``,
``if``, or ``return`` falls through to the next block. The last block must
end in ``return`` or an explicit ``goto``.
"""

from __future__ import annotations

from dataclasses import dataclass

from pgara.errors import IRError
from pgara.ir import Program, is_terminator


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    kind: str  # fallthrough, branch_true, branch_false, jump


@dataclass
class CFG:
    edges: list[Edge]

    def successors(self) -> dict[str, list[str]]:
        succ: dict[str, list[str]] = {}
        for edge in self.edges:
            succ.setdefault(edge.source, [])
            if edge.target not in succ[edge.source]:
                succ[edge.source].append(edge.target)
        return succ

    def edges_from(self, label: str) -> list[Edge]:
        return [edge for edge in self.edges if edge.source == label]


def build_cfg(program: Program) -> CFG:
    if not program.blocks:
        raise IRError("program has no basic blocks")
    known = {block.label: index for index, block in enumerate(program.blocks)}
    edges: list[Edge] = []
    for index, block in enumerate(program.blocks):
        if not block.instructions:
            _add_fallthrough(program, index, edges, "fallthrough")
            continue
        last = block.instructions[-1]
        if not is_terminator(last):
            _add_fallthrough(program, index, edges, "fallthrough")
            continue
        if last.op == "ret":
            continue
        if last.op == "jmp":
            _require_target(last.target, known, last.line, "jump")
            edges.append(Edge(block.label, last.target, "jump"))  # type: ignore[arg-type]
            continue
        if last.op == "br":
            _require_target(last.target, known, last.line, "conditional branch")
            edges.append(Edge(block.label, last.target, "branch_true"))  # type: ignore[arg-type]
            _add_fallthrough(program, index, edges, "branch_false", line=last.line)
            continue
        raise IRError(f"unhandled terminator {last.op}", last.line)
    return CFG(edges)


def _require_target(
    target: str | None,
    known: dict[str, int],
    line: int | None,
    kind: str,
) -> None:
    if target not in known:
        raise IRError(f"{kind} targets unknown block {target!r}", line)


def _add_fallthrough(
    program: Program,
    index: int,
    edges: list[Edge],
    kind: str,
    line: int | None = None,
) -> None:
    block = program.blocks[index]
    if index + 1 >= len(program.blocks):
        if kind == "branch_false":
            raise IRError(
                f"conditional branch in the final block {block.label} has no "
                "false successor; place another block after it or end with return",
                line,
            )
        raise IRError(
            f"block {block.label} does not end with goto, if, or return, and "
            "there is no following block to fall through to",
            line if line is not None else (
                block.instructions[-1].line if block.instructions else None
            ),
        )
    edges.append(Edge(block.label, program.blocks[index + 1].label, kind))
