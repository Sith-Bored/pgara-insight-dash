"""FastAPI surface for the PGARA milestone-1 analyzers."""

from __future__ import annotations

from fractions import Fraction

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from pgara import __version__
from pgara.engine import analyze
from pgara.errors import AllocationError, InputError, IRError, PGARAError
from pgara.parser import parse
from pgara.policy import API_VERSION, COST_SUMMARY, PROFILES_REQUIRED
from pgara.present import present_algorithm, present_allocation
from pgara.samples import BENCHMARK_CASES, SAMPLE_PROGRAM
from pgara.schemas import (
    AllocateRequest,
    AllocateResponse,
    BenchmarkCaseOut,
    BenchmarkRequest,
    BenchmarkResponse,
    HealthResponse,
    ProfileIn,
    SampleResponse,
    SuggestedRun,
)
from pgara.structured import program_from_structured

BENCHMARK_NOTE = (
    "Each case was allocated by executing the analyzers on a deterministic "
    "synthetic program. execution_time_ms is allocator time on this machine, "
    "not a measured spill penalty. per_profile_costs are estimated spill "
    "operations from the case's supplied block execution counts, not measured "
    "runtime. The potential-game results are local equilibria of unilateral "
    "moves, or budget cutoffs, and are not claimed to be globally optimal."
)

LOCAL_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
]


def create_app() -> FastAPI:
    app = FastAPI(
        title="PGARA",
        version=__version__,
        description=(
            "Profile-Guided Adaptive Register Allocation research prototype. "
            "Spill figures are estimates from supplied block execution counts, "
            "not measured runtime. The potential-game search reports a local "
            "equilibrium of unilateral moves and does not claim global optimality."
        ),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=LOCAL_ORIGINS,
        allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.exception_handler(IRError)
    @app.exception_handler(InputError)
    async def handle_client_error(_request, exc: PGARAError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "detail": {
                    "error": exc.error,
                    "message": str(exc),
                    "line": exc.line,
                }
            },
        )

    @app.exception_handler(AllocationError)
    async def handle_allocation_defect(_request, exc: AllocationError) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={"detail": {"error": exc.error, "message": str(exc), "line": exc.line}},
        )

    @app.get("/")
    def root() -> dict[str, str]:
        return {
            "service": "pgara",
            "api_version": API_VERSION,
            "health": "/api/health",
            "docs": "/docs",
            "sample_program": "/api/sample-program",
        }

    @app.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", service="pgara", version=__version__)

    @app.get("/api/sample-program", response_model=SampleResponse)
    def sample_program() -> SampleResponse:
        return SampleResponse(
            api_version=API_VERSION,
            name=SAMPLE_PROGRAM.name,
            description=SAMPLE_PROGRAM.description,
            source=SAMPLE_PROGRAM.source,
            num_registers=SAMPLE_PROGRAM.num_registers,
            profiles=[
                ProfileIn(name=name, block_counts=dict(counts))
                for name, counts in SAMPLE_PROGRAM.profiles
            ],
            iteration_budget=SAMPLE_PROGRAM.iteration_budget,
            suggested_runs=[
                SuggestedRun(
                    tradeoff=0.0,
                    game_initial="all_spilled",
                    note=(
                        "Average estimated spill cost. With one register the "
                        "game keeps a."
                    ),
                ),
                SuggestedRun(
                    tradeoff=1.0,
                    game_initial="all_spilled",
                    note=(
                        "Worst-profile estimated spill cost. With one register "
                        "the game keeps b."
                    ),
                ),
            ],
            notes=[
                "Block execution counts in profiles are part of the sample. They are not inferred.",
                COST_SUMMARY,
                "The new value of `b = b + 1` is unused, so that instruction contributes a load of b and not a store.",
                "Send this source to POST /api/allocate with the profiles and num_registers from this response.",
            ],
        )

    @app.post("/api/allocate", response_model=AllocateResponse)
    def allocate(body: AllocateRequest) -> AllocateResponse:
        program = (
            parse(body.source)
            if body.source is not None
            else program_from_structured(body.program)  # type: ignore[arg-type]
        )
        tradeoff = Fraction(body.tradeoff).limit_denominator(1_000_000)
        algorithms, allow_skip = _algorithms(body.algorithm, len(body.profiles))
        result = analyze(
            program,
            num_registers=body.num_registers,
            profiles=[(profile.name, dict(profile.block_counts)) for profile in body.profiles],
            algorithms=algorithms,
            tradeoff=tradeoff,
            iteration_budget=body.iteration_budget,
            load_cost=body.load_cost,
            store_cost=body.store_cost,
            game_initial=body.game_initial,
            allow_skip=allow_skip,
        )
        return present_allocation(
            result,
            tradeoff=tradeoff,
            load_cost=body.load_cost,
            store_cost=body.store_cost,
        )

    @app.post("/api/benchmark", response_model=BenchmarkResponse)
    def benchmark(body: BenchmarkRequest | None = None) -> BenchmarkResponse:
        request = body or BenchmarkRequest()
        cases: list[BenchmarkCaseOut] = []
        for case in BENCHMARK_CASES:
            tradeoff = (
                Fraction(request.tradeoff).limit_denominator(1_000_000)
                if request.tradeoff is not None
                else case.tradeoff
            )
            budget = (
                request.iteration_budget
                if request.iteration_budget is not None
                else case.iteration_budget
            )
            program = parse(case.source)
            result = analyze(
                program,
                num_registers=case.num_registers,
                profiles=[(name, dict(counts)) for name, counts in case.profiles],
                algorithms=["static_greedy", "profile_greedy", "potential_game"],
                tradeoff=tradeoff,
                iteration_budget=budget,
                load_cost=request.load_cost,
                store_cost=request.store_cost,
                game_initial=request.game_initial,
                allow_skip=False,
            )
            cases.append(
                BenchmarkCaseOut(
                    name=case.name,
                    description=case.description,
                    num_registers=case.num_registers,
                    tradeoff=str(tradeoff),
                    results=[
                        present_algorithm(item, result.timings_ms[item.algorithm])
                        for item in result.results
                    ],
                )
            )
        return BenchmarkResponse(api_version=API_VERSION, note=BENCHMARK_NOTE, cases=cases)

    return app


def _algorithms(requested: str, profile_count: int) -> tuple[list[str], bool]:
    if requested == "all":
        return ["static_greedy", "profile_greedy", "potential_game"], True
    if requested != "static_greedy" and profile_count == 0:
        raise InputError(PROFILES_REQUIRED)
    return [requested], False


app = create_app()
