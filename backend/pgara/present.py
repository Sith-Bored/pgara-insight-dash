"""Convert analysis results into the documented API models."""

from __future__ import annotations

from fractions import Fraction

from pgara.allocate import Allocation, Decision
from pgara.engine import EngineResult, SkippedAllocation
from pgara.ir import format_instruction
from pgara.policy import API_VERSION, COST_SUMMARY
from pgara.schemas import (
    AlgorithmOut,
    AllocateResponse,
    BlockOut,
    CostModelOut,
    DeadDefOut,
    DecisionOut,
    InstructionOut,
    InterferenceEdgeOut,
    InterferenceOut,
    LiveRangeOut,
    ProfileCostOut,
    SiteOut,
    SuccessorOut,
)


def present_allocation(
    result: EngineResult,
    *,
    tradeoff: Fraction,
    load_cost: int,
    store_cost: int,
) -> AllocateResponse:
    return AllocateResponse(
        api_version=API_VERSION,
        cost_model=_cost_model(tradeoff, load_cost, store_cost),
        undefined_uses=list(result.undefined_uses),
        dead_definitions=_dead_defs(result),
        blocks=_blocks(result),
        interference=_interference(result),
        live_ranges=_live_ranges(result),
        liveness_iterations=result.liveness.iterations,
        results=[
            present_algorithm(item, result.timings_ms[item.algorithm])
            for item in result.results
        ],
    )


def present_algorithm(
    item: Allocation | SkippedAllocation,
    execution_time_ms: float,
) -> AlgorithmOut:
    if isinstance(item, SkippedAllocation):
        return AlgorithmOut(
            algorithm=item.algorithm,  # type: ignore[arg-type]
            status="skipped",
            skip_reason=item.skip_reason,
            assignments={},
            spills=[],
            physical_registers=list(item.physical_registers),
            valid=None,
            static_spill_operations=None,
            per_profile_costs=[],
            potential=None,
            potential_numerator=None,
            potential_denominator=None,
            potential_float=None,
            execution_time_ms=execution_time_ms,
            iterations=0,
            stopping_reason=None,
            initial_allocation=None,
            decision_trace=[],
            notes=list(item.notes),
        )
    potential_text, numerator, denominator, as_float = _fraction_parts(item.potential_value)
    return AlgorithmOut(
        algorithm=item.algorithm,  # type: ignore[arg-type]
        status="ok",
        skip_reason=None,
        assignments=dict(item.assignments),
        spills=list(item.spills),
        physical_registers=list(item.physical_registers),
        valid=True,
        static_spill_operations=item.static_spill_operations,
        per_profile_costs=_profile_costs(item.per_profile_costs),
        potential=potential_text,
        potential_numerator=numerator,
        potential_denominator=denominator,
        potential_float=as_float,
        execution_time_ms=execution_time_ms,
        iterations=item.iterations,
        stopping_reason=item.stopping_reason,  # type: ignore[arg-type]
        initial_allocation=None
        if item.initial_allocation is None
        else dict(item.initial_allocation),
        decision_trace=[_decision(step) for step in item.trace],
        notes=list(item.notes),
    )


def _blocks(result: EngineResult) -> list[BlockOut]:
    views: list[BlockOut] = []
    for block in result.program.blocks:
        instructions = []
        for index, inst in enumerate(block.instructions):
            instructions.append(
                InstructionOut(
                    index=index,
                    line=inst.line,
                    text=format_instruction(inst),
                    op=inst.op,
                    dest=inst.dest,
                    uses=inst.uses(),
                    live_in=sorted(result.liveness.inst_live_in[block.label][index]),
                    live_out=sorted(result.liveness.inst_live_out[block.label][index]),
                )
            )
        views.append(
            BlockOut(
                label=block.label,
                successors=[
                    SuccessorOut(target=edge.target, kind=edge.kind)  # type: ignore[arg-type]
                    for edge in result.cfg.edges_from(block.label)
                ],
                live_in=sorted(result.liveness.live_in[block.label]),
                live_out=sorted(result.liveness.live_out[block.label]),
                instructions=instructions,
            )
        )
    return views


def _interference(result: EngineResult) -> InterferenceOut:
    nodes = sorted(result.interference.ranges)
    degrees = {node: 0 for node in nodes}
    edges = []
    for left, right in result.interference.edges:
        edges.append(InterferenceEdgeOut(a=left, b=right))
        degrees[left] += 1
        degrees[right] += 1
    return InterferenceOut(nodes=nodes, edges=edges, degrees=degrees)


def _live_ranges(result: EngineResult) -> list[LiveRangeOut]:
    views = []
    for live_id in sorted(result.interference.ranges):
        live_range = result.interference.ranges[live_id]
        views.append(
            LiveRangeOut(
                id=live_range.id,
                vreg=live_range.vreg,
                static_spill_operations=result.live_range_static_costs[live_id],
                per_profile_estimated_spill_operations=_profile_costs(
                    result.live_range_profile_costs[live_id]
                ),
                defs=[SiteOut(block=site.block, index=site.index, kind=site.kind) for site in live_range.defs],  # type: ignore[arg-type]
                uses=[SiteOut(block=site.block, index=site.index, kind=site.kind) for site in live_range.uses],  # type: ignore[arg-type]
            )
        )
    return views


def _dead_defs(result: EngineResult) -> list[DeadDefOut]:
    order = {label: index for index, label in enumerate(result.program.labels())}
    dead = sorted(
        result.interference.dead_defs,
        key=lambda item: (order[item.block], item.index, item.dest),
    )
    return [DeadDefOut(block=item.block, index=item.index, dest=item.dest) for item in dead]


def _decision(step: Decision) -> DecisionOut:
    previous_text, previous_num, previous_den, _previous_float = _fraction_parts(
        step.previous_potential
    )
    new_text, new_num, new_den, _new_float = _fraction_parts(step.new_potential)
    return DecisionOut(
        step=step.step,
        live_range=step.live_range,
        action=step.action,  # type: ignore[arg-type]
        previous_strategy=step.previous_strategy,
        strategy=step.strategy,
        previous_potential=previous_text,
        previous_potential_numerator=previous_num,
        previous_potential_denominator=previous_den,
        new_potential=new_text,
        new_potential_numerator=new_num,
        new_potential_denominator=new_den,
        previous_profile_costs=None
        if step.previous_profile_costs is None
        else _profile_costs(step.previous_profile_costs),
        new_profile_costs=None
        if step.new_profile_costs is None
        else _profile_costs(step.new_profile_costs),
        reason=step.reason,
    )


def _profile_costs(costs: list[tuple[str, int]] | tuple[tuple[str, int], ...]) -> list[ProfileCostOut]:
    return [
        ProfileCostOut(profile=name, estimated_spill_operations=value)
        for name, value in costs
    ]


def _cost_model(tradeoff: Fraction, load_cost: int, store_cost: int) -> CostModelOut:
    return CostModelOut(
        load_cost=load_cost,
        store_cost=store_cost,
        tradeoff=str(tradeoff),
        tradeoff_numerator=tradeoff.numerator,
        tradeoff_denominator=tradeoff.denominator,
        summary=COST_SUMMARY,
    )


def _fraction_parts(
    value: Fraction | None,
) -> tuple[str | None, int | None, int | None, float | None]:
    if value is None:
        return None, None, None, None
    return str(value), value.numerator, value.denominator, float(value)
