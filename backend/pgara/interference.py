"""Interference from simultaneously live virtual registers.

Two live ranges interfere when some instruction boundary contains both of
them. Ranges are not split: each virtual register that is live anywhere
becomes one node whose id equals the register name.
"""

from __future__ import annotations

from dataclasses import dataclass

from pgara.errors import IRError
from pgara.ir import LiveRange, Program, Site
from pgara.liveness import Liveness


@dataclass(frozen=True)
class DeadDef:
    block: str
    index: int
    dest: str


@dataclass
class Interference:
    ranges: dict[str, LiveRange]
    edges: list[tuple[str, str]]
    dead_defs: list[DeadDef]

    def neighbors(self) -> dict[str, set[str]]:
        adj = {name: set() for name in self.ranges}
        for left, right in self.edges:
            adj[left].add(right)
            adj[right].add(left)
        return adj


def build_interference(program: Program, liveness: Liveness) -> Interference:
    ranges: dict[str, LiveRange] = {}
    edge_set: set[tuple[str, str]] = set()
    dead_defs: list[DeadDef] = []

    def ensure(name: str) -> LiveRange:
        live_range = ranges.get(name)
        if live_range is None:
            live_range = LiveRange(id=name, vreg=name, defs=[], uses=[])
            ranges[name] = live_range
        return live_range

    def add_pairs(live: set[str]) -> None:
        ordered = sorted(live)
        for i, left in enumerate(ordered):
            for right in ordered[i + 1 :]:
                edge_set.add((left, right))

    for block in program.blocks:
        live = set(liveness.live_out[block.label])
        add_pairs(live)
        for index in reversed(range(len(block.instructions))):
            inst = block.instructions[index]
            if inst.dest is not None and inst.dest in live:
                ensure(inst.dest).defs.append(Site(block.label, index, "store"))
            elif inst.dest is not None:
                dead_defs.append(DeadDef(block.label, index, inst.dest))
            if inst.dest is not None:
                live.discard(inst.dest)
            for used in inst.uses():
                ensure(used).uses.append(Site(block.label, index, "load"))
                live.add(used)
            add_pairs(live)
        if live != liveness.live_in[block.label]:
            raise IRError(
                f"interference walk disagreed with live-in of block {block.label}"
            )

    for live_range in ranges.values():
        live_range.defs.reverse()
        live_range.uses.reverse()

    missing = {name for pair in edge_set for name in pair} - set(ranges)
    if missing:
        raise IRError(
            "interference mentions virtual registers with no live range: "
            + ", ".join(sorted(missing))
        )
    edges = sorted(edge_set)
    return Interference(ranges, edges, dead_defs)
