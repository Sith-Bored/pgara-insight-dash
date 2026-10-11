"""HTTP request and response models. This is the frontend contract for API 1.0."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

from pgara.policy import (
    API_VERSION,
    DEFAULT_ITERATION_BUDGET,
    DEFAULT_LOAD_COST,
    DEFAULT_STORE_COST,
    MAX_ITERATION_BUDGET,
    MAX_PROFILES,
    MAX_REGISTERS,
    MAX_SOURCE_CHARS,
    MAX_SPILL_WEIGHT,
)

AlgorithmName = Literal["static_greedy", "profile_greedy", "potential_game"]
RequestedAlgorithm = Literal["static_greedy", "profile_greedy", "potential_game", "all"]
GameInitial = Literal["all_spilled", "static_greedy", "profile_greedy"]
StopReason = Literal["single_pass", "no_improving_move", "iteration_budget"]


class ProfileIn(BaseModel):
    """One execution profile. Every basic block needs an explicit count."""

    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80)
    block_counts: dict[str, StrictInt]

    @field_validator("name")
    @classmethod
    def name_has_no_surrounding_space(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("profile name must not have leading or trailing whitespace")
        return value

    @field_validator("block_counts")
    @classmethod
    def counts_are_non_negative(cls, value: dict[str, int]) -> dict[str, int]:
        for label, count in value.items():
            if count < 0:
                raise ValueError(f"execution count for block {label!r} is negative")
        return value


class OperandIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["reg", "imm"]
    name: str | None = None
    value: int | None = None


class InstructionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    op: Literal["const", "mov", "add", "sub", "mul", "div", "br", "jmp", "ret"]
    dest: str | None = None
    operands: list[OperandIn] = Field(default_factory=list)
    target: str | None = None


class BlockIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str
    instructions: list[InstructionIn]


class ProgramIn(BaseModel):
    """Structured IR. Use this or `source`, not both."""

    model_config = ConfigDict(extra="forbid")
    blocks: list[BlockIn]


class AllocateRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "source": "block entry:\n  a = 1\n  b = 2\n  c = a + b\n  return c\n",
                    "num_registers": 1,
                    "profiles": [{"name": "once", "block_counts": {"entry": 1}}],
                    "algorithm": "all",
                    "tradeoff": 0.5,
                    "iteration_budget": 20,
                    "game_initial": "all_spilled",
                }
            ]
        },
    )
    source: str | None = Field(
        default=None,
        description="Textual three-address IR. Provide exactly one of source or program.",
    )
    program: ProgramIn | None = None
    num_registers: StrictInt = Field(
        ge=0,
        le=MAX_REGISTERS,
        description=(
            "How many physical registers exist. Zero is valid and spills every "
            "live range. Values above the maximum are rejected."
        ),
    )
    profiles: list[ProfileIn] = Field(default_factory=list)
    algorithm: RequestedAlgorithm = "all"
    tradeoff: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description=(
            "Weight on the worst profile inside the potential. "
            "0 uses the average estimated spill cost. 1 uses only the worst profile."
        ),
    )
    iteration_budget: StrictInt = Field(
        default=DEFAULT_ITERATION_BUDGET,
        ge=0,
        le=MAX_ITERATION_BUDGET,
        description="Maximum accepted potential-game moves. Zero performs no moves.",
    )
    load_cost: StrictInt = Field(default=DEFAULT_LOAD_COST, ge=0, le=MAX_SPILL_WEIGHT)
    store_cost: StrictInt = Field(default=DEFAULT_STORE_COST, ge=0, le=MAX_SPILL_WEIGHT)
    game_initial: GameInitial = "all_spilled"

    @model_validator(mode="after")
    def exactly_one_program(self) -> AllocateRequest:
        has_source = self.source is not None
        has_program = self.program is not None
        if has_source == has_program:
            raise ValueError("provide exactly one of source or program")
        if self.source is not None and len(self.source) > MAX_SOURCE_CHARS:
            raise ValueError(f"source exceeds {MAX_SOURCE_CHARS} characters")
        if len(self.profiles) > MAX_PROFILES:
            raise ValueError(f"at most {MAX_PROFILES} profiles are accepted")
        names = [profile.name for profile in self.profiles]
        if len(names) != len(set(names)):
            raise ValueError("profile names must be unique")
        return self


class BenchmarkRequest(BaseModel):
    """Re-run the built-in synthetic suite. An empty object uses each case's own tradeoff."""

    model_config = ConfigDict(extra="forbid")
    tradeoff: float | None = Field(default=None, ge=0.0, le=1.0)
    iteration_budget: StrictInt | None = Field(default=None, ge=0, le=MAX_ITERATION_BUDGET)
    load_cost: StrictInt = Field(default=DEFAULT_LOAD_COST, ge=0, le=MAX_SPILL_WEIGHT)
    store_cost: StrictInt = Field(default=DEFAULT_STORE_COST, ge=0, le=MAX_SPILL_WEIGHT)
    game_initial: GameInitial = "all_spilled"


class ProfileCostOut(BaseModel):
    profile: str
    estimated_spill_operations: int = Field(
        description="Estimated dynamic spill operations. Not measured runtime."
    )


class DecisionOut(BaseModel):
    step: int
    live_range: str
    action: Literal["assign", "spill", "move"]
    previous_strategy: str | None = None
    strategy: str = Field(description="Physical register name such as p0, or the string spill.")
    previous_potential: str | None = None
    previous_potential_numerator: int | None = None
    previous_potential_denominator: int | None = None
    new_potential: str | None = None
    new_potential_numerator: int | None = None
    new_potential_denominator: int | None = None
    previous_profile_costs: list[ProfileCostOut] | None = None
    new_profile_costs: list[ProfileCostOut] | None = None
    reason: str


class AlgorithmOut(BaseModel):
    algorithm: AlgorithmName
    status: Literal["ok", "skipped"]
    skip_reason: str | None = None
    assignments: dict[str, str | None] = Field(
        description="Live range id to physical register. JSON null means spilled."
    )
    spills: list[str]
    physical_registers: list[str]
    valid: bool | None = None
    static_spill_operations: int | None = None
    per_profile_costs: list[ProfileCostOut]
    potential: str | None = None
    potential_numerator: int | None = None
    potential_denominator: int | None = None
    potential_float: float | None = None
    execution_time_ms: float
    iterations: int
    stopping_reason: StopReason | None = None
    initial_allocation: dict[str, str | None] | None = None
    decision_trace: list[DecisionOut]
    notes: list[str]


class SuccessorOut(BaseModel):
    target: str
    kind: Literal["fallthrough", "branch_true", "branch_false", "jump"]


class InstructionOut(BaseModel):
    index: int
    line: int | None
    text: str
    op: str
    dest: str | None
    uses: list[str]
    live_in: list[str]
    live_out: list[str]


class BlockOut(BaseModel):
    label: str
    successors: list[SuccessorOut]
    live_in: list[str]
    live_out: list[str]
    instructions: list[InstructionOut]


class InterferenceEdgeOut(BaseModel):
    a: str
    b: str


class InterferenceOut(BaseModel):
    nodes: list[str]
    edges: list[InterferenceEdgeOut]
    degrees: dict[str, int]


class SiteOut(BaseModel):
    block: str
    index: int
    kind: Literal["load", "store"]


class LiveRangeOut(BaseModel):
    id: str
    vreg: str
    static_spill_operations: int
    per_profile_estimated_spill_operations: list[ProfileCostOut]
    defs: list[SiteOut]
    uses: list[SiteOut]


class DeadDefOut(BaseModel):
    block: str
    index: int
    dest: str


class CostModelOut(BaseModel):
    load_cost: int
    store_cost: int
    tradeoff: str
    tradeoff_numerator: int
    tradeoff_denominator: int
    summary: str


class AllocateResponse(BaseModel):
    api_version: Literal["1.0"]
    cost_model: CostModelOut
    undefined_uses: list[str]
    dead_definitions: list[DeadDefOut]
    blocks: list[BlockOut]
    interference: InterferenceOut
    live_ranges: list[LiveRangeOut]
    liveness_iterations: int
    results: list[AlgorithmOut]


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: Literal["pgara"]
    api_version: Literal["1.0"] = API_VERSION
    version: str


class SuggestedRun(BaseModel):
    tradeoff: float
    game_initial: GameInitial
    note: str


class SampleResponse(BaseModel):
    api_version: Literal["1.0"]
    name: str
    description: str
    source: str
    num_registers: int
    profiles: list[ProfileIn]
    iteration_budget: int
    suggested_runs: list[SuggestedRun]
    notes: list[str]


class BenchmarkCaseOut(BaseModel):
    name: str
    description: str
    num_registers: int
    tradeoff: str
    results: list[AlgorithmOut]


class BenchmarkResponse(BaseModel):
    api_version: Literal["1.0"]
    note: str
    cases: list[BenchmarkCaseOut]
