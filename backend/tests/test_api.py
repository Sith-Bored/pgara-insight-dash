"""API schemas, validation policy, and benchmark execution."""

from fractions import Fraction

import pytest
from fastapi.testclient import TestClient

from pgara.api import app
from pgara.engine import analyze
from pgara.parser import parse
from pgara.samples import SAMPLE_PROGRAM, TRADEOFF_SOURCE
from pgara.schemas import AllocateResponse, BenchmarkResponse, HealthResponse, SampleResponse


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_health_schema(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = HealthResponse.model_validate(response.json())
    assert body.status == "ok"
    assert body.service == "pgara"
    assert body.api_version == "1.0"


def test_openapi_lists_the_four_endpoints(client):
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]
    assert set(paths) >= {
        "/api/health",
        "/api/sample-program",
        "/api/allocate",
        "/api/benchmark",
    }


def test_sample_program_is_allocatable(client):
    sample = SampleResponse.model_validate(client.get("/api/sample-program").json())
    assert sample.source == SAMPLE_PROGRAM.source
    response = client.post(
        "/api/allocate",
        json={
            "source": sample.source,
            "num_registers": sample.num_registers,
            "profiles": [profile.model_dump() for profile in sample.profiles],
            "algorithm": "potential_game",
            "tradeoff": 0,
            "iteration_budget": sample.iteration_budget,
        },
    )
    assert response.status_code == 200
    body = AllocateResponse.model_validate(response.json())
    assert body.results[0].assignments == {"a": "p0", "b": None}
    assert "not measured runtime" in body.cost_model.summary


def test_allocate_response_matches_schema_and_live_pairs(client):
    response = client.post(
        "/api/allocate",
        json={
            "source": TRADEOFF_SOURCE,
            "num_registers": 1,
            "profiles": [
                {"name": "skew", "block_counts": {"def_a": 2, "def_b": 9, "use_a": 3, "use_b": 10, "exit": 2}},
                {"name": "quiet_b", "block_counts": {"def_a": 2, "def_b": 0, "use_a": 3, "use_b": 0, "exit": 2}},
            ],
            "algorithm": "all",
            "tradeoff": 1,
        },
    )
    assert response.status_code == 200
    body = AllocateResponse.model_validate(response.json())
    edges = {(edge.a, edge.b) for edge in body.interference.edges}
    assert ("a", "b") in edges
    co_live = set()
    for block in body.blocks:
        for instruction in block.instructions:
            for live in (instruction.live_in, instruction.live_out):
                ordered = sorted(live)
                for index, left in enumerate(ordered):
                    for right in ordered[index + 1 :]:
                        co_live.add((left, right))
    assert co_live == edges
    game = next(item for item in body.results if item.algorithm == "potential_game")
    assert game.valid is True
    assert game.assignments == {"a": None, "b": "p0"}
    assert game.stopping_reason == "no_improving_move"
    for step in game.decision_trace:
        assert step.previous_potential_numerator is not None
        assert step.new_potential_numerator is not None
        left = step.new_potential_numerator * step.previous_potential_denominator
        right = step.previous_potential_numerator * step.new_potential_denominator
        assert left < right
    for item in body.results:
        if item.status != "ok":
            continue
        for edge in body.interference.edges:
            left = item.assignments[edge.a]
            right_reg = item.assignments[edge.b]
            assert left is None or left != right_reg
        assert item.execution_time_ms >= 0


def test_all_without_profiles_skips_profile_algorithms(client):
    response = client.post(
        "/api/allocate",
        json={"source": "block entry:\n  return 0\n", "num_registers": 2, "algorithm": "all"},
    )
    assert response.status_code == 200
    body = AllocateResponse.model_validate(response.json())
    by_name = {item.algorithm: item for item in body.results}
    assert by_name["static_greedy"].status == "ok"
    assert by_name["profile_greedy"].status == "skipped"
    assert by_name["potential_game"].status == "skipped"
    assert by_name["profile_greedy"].physical_registers == ["p0", "p1"]
    assert "does not invent" in by_name["profile_greedy"].skip_reason
    assert by_name["profile_greedy"].execution_time_ms == 0


def test_profile_algorithm_without_profiles_is_rejected(client):
    response = client.post(
        "/api/allocate",
        json={
            "source": "block entry:\n  return 0\n",
            "num_registers": 1,
            "algorithm": "profile_greedy",
        },
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error"] == "input_error"
    assert "does not invent" in detail["message"]


def test_malformed_ir_is_422(client):
    response = client.post(
        "/api/allocate",
        json={"source": "block entry:\n  goto missing\n", "num_registers": 1},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "ir_validation_error"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"num_registers": 1},
        {"source": "block entry:\n  return 0\n", "program": {"blocks": []}, "num_registers": 1},
        {"source": "block entry:\n  return 0\n", "num_registers": -1},
        {"source": "block entry:\n  return 0\n", "num_registers": True},
        {"source": "block entry:\n  return 0\n", "num_registers": 1, "tradeoff": 1.5},
        {
            "source": "block entry:\n  return 0\n",
            "num_registers": 1,
            "profiles": [{"name": "once", "block_counts": {"entry": 1.5}}],
        },
        {
            "source": "block entry:\n  return 0\n",
            "num_registers": 1,
            "profiles": [{"name": "once", "block_counts": {"entry": -3}}],
        },
    ],
)
def test_schema_rejects_bad_requests(client, payload):
    response = client.post("/api/allocate", json=payload)
    assert response.status_code == 422


def test_missing_and_unknown_profile_blocks(client):
    source = "block entry:\n  goto next\nblock next:\n  return 0\n"
    missing = client.post(
        "/api/allocate",
        json={
            "source": source,
            "num_registers": 1,
            "profiles": [{"name": "once", "block_counts": {"entry": 1}}],
        },
    )
    unknown = client.post(
        "/api/allocate",
        json={
            "source": source,
            "num_registers": 1,
            "profiles": [{"name": "once", "block_counts": {"entry": 1, "next": 1, "other": 4}}],
        },
    )
    assert missing.status_code == 422
    assert unknown.status_code == 422
    assert missing.json()["detail"]["error"] == "input_error"
    assert "missing execution counts" in missing.json()["detail"]["message"]
    assert "unknown blocks" in unknown.json()["detail"]["message"]


def test_zero_registers_policy(client):
    response = client.post(
        "/api/allocate",
        json={
            "source": "block entry:\n  a = 1\n  return a\n",
            "num_registers": 0,
            "profiles": [{"name": "once", "block_counts": {"entry": 4}}],
            "algorithm": "all",
        },
    )
    body = AllocateResponse.model_validate(response.json())
    for item in body.results:
        assert item.status == "ok"
        assert item.assignments == {"a": None}
        assert item.spills == ["a"]
        assert item.physical_registers == []
        assert item.valid is True
    profile = next(item for item in body.results if item.algorithm == "profile_greedy")
    assert profile.per_profile_costs[0].estimated_spill_operations == 8


def test_structured_program_matches_source(client):
    source_response = client.post(
        "/api/allocate",
        json={"source": "block entry:\n  a = 1\n  return a\n", "num_registers": 1, "algorithm": "static_greedy"},
    )
    structured = client.post(
        "/api/allocate",
        json={
            "program": {
                "blocks": [
                    {
                        "label": "entry",
                        "instructions": [
                            {"op": "const", "dest": "a", "operands": [{"kind": "imm", "value": 1}]},
                            {"op": "ret", "operands": [{"kind": "reg", "name": "a"}]},
                        ],
                    }
                ]
            },
            "num_registers": 1,
            "algorithm": "static_greedy",
        },
    )
    assert structured.status_code == 200
    assert (
        structured.json()["results"][0]["assignments"]
        == source_response.json()["results"][0]["assignments"]
    )


def test_cors_allows_local_frontend_and_rejects_other_origins(client):
    allowed = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    other_port = client.get("/api/health", headers={"Origin": "http://127.0.0.1:8742"})
    blocked = client.get("/api/health", headers={"Origin": "https://example.com"})
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert other_port.headers["access-control-allow-origin"] == "http://127.0.0.1:8742"
    assert "access-control-allow-origin" not in blocked.headers
    assert allowed.headers.get("access-control-allow-credentials") is None


def test_benchmark_executes_allocators(client):
    response = client.post("/api/benchmark", json={})
    assert response.status_code == 200
    body = BenchmarkResponse.model_validate(response.json())
    assert "not measured runtime" in body.note
    assert "not claimed to be globally optimal" in body.note
    by_name = {case.name: case for case in body.cases}
    assert by_name["game_average"].results[2].assignments["a"] == "p0"
    assert by_name["game_worst"].results[2].assignments["b"] == "p0"
    direct = analyze(
        parse(SAMPLE_PROGRAM.source),
        num_registers=1,
        profiles=[(name, dict(counts)) for name, counts in SAMPLE_PROGRAM.profiles],
        algorithms=["potential_game"],
        tradeoff=Fraction(0),
        iteration_budget=SAMPLE_PROGRAM.iteration_budget,
        load_cost=1,
        store_cost=1,
        game_initial="all_spilled",
        allow_skip=False,
    )
    assert by_name["game_average"].results[2].assignments == direct.results[0].assignments
    assert by_name["game_average"].results[2].iterations == direct.results[0].iterations
    for case in body.cases:
        for item in case.results:
            assert item.execution_time_ms >= 0
            assert item.status == "ok"

    stopped = client.post("/api/benchmark", json={"iteration_budget": 0})
    stopped_body = BenchmarkResponse.model_validate(stopped.json())
    for case in stopped_body.cases:
        game = next(item for item in case.results if item.algorithm == "potential_game")
        static = next(item for item in case.results if item.algorithm == "static_greedy")
        assert game.iterations == 0
        assert game.stopping_reason == "iteration_budget"
        assert static.stopping_reason == "single_pass"
        assert all(register is None for register in game.assignments.values())
