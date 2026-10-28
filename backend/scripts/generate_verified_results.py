"""Generate a reproducible JSON record from the actual PGARA benchmark implementation.

Run from the backend directory:
    python scripts/generate_verified_results.py
    python scripts/generate_verified_results.py --check

The output is deliberately marked pending until it has been compared to the
manuscript's tables and figures. Generation and unit tests cannot perform that
external manuscript comparison.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from pgara import __version__
from pgara.allocate import Allocation
from pgara.engine import analyze
from pgara.parser import parse
from pgara.samples import BENCHMARK_CASES

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ALGORITHMS = ("static_greedy", "profile_greedy", "potential_game")
RESULTS_STATUS_PENDING = "generated_pending_manuscript_check"


def _distribution_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _commit_sha() -> str | None:
    supplied = os.environ.get("GITHUB_SHA")
    if supplied:
        return supplied
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    return completed.stdout.strip() or None


def build_results() -> dict[str, Any]:
    experiments: list[dict[str, Any]] = []
    for case in BENCHMARK_CASES:
        tradeoff = case.tradeoff
        output = analyze(
            parse(case.source),
            num_registers=case.num_registers,
            profiles=[(name, dict(counts)) for name, counts in case.profiles],
            algorithms=list(ALGORITHMS),
            tradeoff=tradeoff,
            iteration_budget=case.iteration_budget,
            load_cost=1,
            store_cost=1,
            game_initial=case.game_initial,
            allow_skip=False,
        )
        algorithm_results: dict[str, Any] = {}
        for allocation in output.results:
            if not isinstance(allocation, Allocation):
                raise RuntimeError(
                    f"Benchmark {case.name!r} unexpectedly skipped "
                    f"{allocation.algorithm}"
                )
            profile_costs = {
                profile_name: estimated_cost
                for profile_name, estimated_cost in allocation.per_profile_costs
            }
            potential = allocation.potential_value
            algorithm_results[allocation.algorithm] = {
                "assignments": allocation.assignments,
                "spilled_ranges": allocation.spills,
                "static_spill_operations": allocation.static_spill_operations,
                "estimated_spill_cost": {
                    "by_profile": profile_costs,
                    "sum_across_profiles": sum(profile_costs.values()),
                },
                "potential": (
                    {
                        "numerator": potential.numerator,
                        "denominator": potential.denominator,
                    }
                    if potential is not None
                    else None
                ),
                "iterations": allocation.iterations,
                "stopping_reason": allocation.stopping_reason,
            }

        if set(algorithm_results) != set(ALGORITHMS):
            raise RuntimeError(
                f"Benchmark {case.name!r} did not return all expected algorithms"
            )

        experiments.append(
            {
                "benchmark": case.name,
                "description": case.description,
                "input": {
                    "source": case.source,
                    "source_sha256": hashlib.sha256(
                        case.source.encode("utf-8")
                    ).hexdigest(),
                },
                "configuration": {
                    "register_count": case.num_registers,
                    "profiles": [
                        {"name": name, "block_counts": dict(counts)}
                        for name, counts in case.profiles
                    ],
                    "tradeoff": (
                        f"{tradeoff.numerator}/{tradeoff.denominator}"
                        if tradeoff.denominator != 1
                        else str(tradeoff.numerator)
                    ),
                    "iteration_budget": case.iteration_budget,
                    "load_cost": 1,
                    "store_cost": 1,
                    "game_initial": case.game_initial,
                },
                "algorithms": algorithm_results,
            }
        )

    return {
        "schema_version": 1,
        "project": "PGARA",
        "analyzer_version": __version__,
        "results_status": RESULTS_STATUS_PENDING,
        "verification_note": (
            "Generated from the repository implementation. Not yet compared "
            "against the manuscript's tables and figures; do not describe these "
            "results as manuscript-verified until that comparison is complete."
        ),
        "generated_from_commit": _commit_sha(),
        "environment": {
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "dependencies": {
                name: _distribution_version(name)
                for name in ("fastapi", "uvicorn", "pydantic", "pytest", "httpx")
            },
        },
        "generation": {
            "entrypoint": "backend/scripts/generate_verified_results.py",
            "benchmark_source": "backend/pgara/samples.py::BENCHMARK_CASES",
            "execution_time_ms_included": False,
        },
        "experiments": experiments,
    }


def _comparison_errors(expected: dict[str, Any], actual: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in ("schema_version", "project", "analyzer_version", "experiments"):
        if expected.get(key) != actual.get(key):
            errors.append(key)
    return errors


def write_results(path: Path, generated: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            previous = {}
        # Preserve a human-verified status only when the inputs and all computed
        # experiment results are unchanged. New or changed results reset to pending.
        if (
            previous.get("results_status") == "verified"
            and previous.get("experiments") == generated["experiments"]
            and previous.get("analyzer_version") == generated["analyzer_version"]
        ):
            generated["results_status"] = "verified"
            generated["verification_note"] = previous.get(
                "verification_note",
                "Manually compared against the manuscript.",
            )
            if "manuscript_verification" in previous:
                generated["manuscript_verification"] = previous[
                    "manuscript_verification"
                ]
    path.write_text(
        json.dumps(generated, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=REPOSITORY_ROOT / "verified-results.json",
        help="output path (default: repository-root verified-results.json)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare generated experiment data with the file without overwriting it",
    )
    args = parser.parse_args()
    generated = build_results()
    output_path = args.output if args.output.is_absolute() else Path.cwd() / args.output

    if args.check:
        try:
            existing = json.loads(output_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            print(f"Cannot check {output_path}: {error}", file=sys.stderr)
            return 1
        errors = _comparison_errors(existing, generated)
        if errors:
            print(
                "Generated benchmark data differs from the checked-in file "
                f"for: {', '.join(errors)}. Regenerate the file and review the "
                "manuscript comparison status.",
                file=sys.stderr,
            )
            return 1
        print(
            f"Checked {len(generated['experiments'])} benchmark cases and their "
            "three algorithm outputs against the current implementation."
        )
        if existing.get("results_status") != "verified":
            print(
                "Manuscript comparison is still pending; generated results are "
                "not marked verified."
            )
        return 0

    write_results(output_path, generated)
    saved = json.loads(output_path.read_text(encoding="utf-8"))
    print(
        f"Wrote {len(generated['experiments'])} benchmark cases to {output_path}. "
        f"Status: {saved['results_status']}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
