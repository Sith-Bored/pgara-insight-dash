"""Regression tests for the generated reproducibility record and API consistency."""

from fastapi.testclient import TestClient

from pgara.api import app
from pgara.samples import BENCHMARK_CASES
from scripts.generate_verified_results import build_results


def test_generated_results_cover_every_benchmark_and_algorithm():
    document = build_results()

    assert document["project"] == "PGARA"
    assert document["results_status"] == "generated_pending_manuscript_check"
    assert len(document["experiments"]) == len(BENCHMARK_CASES) == 8

    expected_algorithms = {
        "static_greedy",
        "profile_greedy",
        "potential_game",
    }
    for experiment in document["experiments"]:
        assert set(experiment["algorithms"]) == expected_algorithms
        assert experiment["input"]["source"]
        assert len(experiment["input"]["source_sha256"]) == 64
        assert experiment["configuration"]["register_count"] >= 0
        assert experiment["configuration"]["profiles"]
        for result in experiment["algorithms"].values():
            assignments = result["assignments"]
            spills_from_assignments = sorted(
                live_range
                for live_range, register in assignments.items()
                if register is None
            )
            assert result["spilled_ranges"] == spills_from_assignments
            assert set(result["estimated_spill_cost"]["by_profile"]) == {
                profile["name"]
                for profile in experiment["configuration"]["profiles"]
            }
            assert result["iterations"] >= 0
            assert result["stopping_reason"]


def test_generated_result_file_matches_actual_benchmark_api_results():
    generated = build_results()
    by_name = {case["benchmark"]: case for case in generated["experiments"]}

    with TestClient(app) as client:
        response = client.post("/api/benchmark", json={})

    assert response.status_code == 200
    api_cases = {case["name"]: case for case in response.json()["cases"]}
    assert set(api_cases) == set(by_name)

    for name, experiment in by_name.items():
        api_case = api_cases[name]
        assert api_case["num_registers"] == experiment["configuration"]["register_count"]
        assert api_case["tradeoff"] == experiment["configuration"]["tradeoff"]
        api_algorithms = {item["algorithm"]: item for item in api_case["results"]}
        assert set(api_algorithms) == set(experiment["algorithms"])

        for algorithm_name, generated_result in experiment["algorithms"].items():
            api_result = api_algorithms[algorithm_name]
            assert api_result["assignments"] == generated_result["assignments"]
            assert api_result["spills"] == generated_result["spilled_ranges"]
            assert {
                item["profile"]: item["estimated_spill_operations"]
                for item in api_result["per_profile_costs"]
            } == generated_result["estimated_spill_cost"]["by_profile"]
            assert api_result["iterations"] == generated_result["iterations"]
            assert api_result["stopping_reason"] == generated_result["stopping_reason"]
