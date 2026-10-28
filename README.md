# PGARA Insight Dash

Interactive research dashboard for **PGARA — Profile-Guided Adaptive Register Allocation**.

The frontend is in the repository root. The analyzer and FastAPI service are in `backend/`. The API contract is documented in [docs/API.md](docs/API.md), and the supported three-address IR is documented in [docs/IR.md](docs/IR.md).

## Reproducing the Experiments

### Prerequisites

- Git.
- Python 3.11 or newer. The reproducibility workflow uses Python 3.12.
- Bun 1.4.4 for the frontend; the repository uses `bun.lock` as its dependency lockfile.

### Fresh clone and install

Clone the public repository and install the backend dependencies:

```bash
git clone https://github.com/Sith-Bored/pgara-insight-dash.git
cd pgara-insight-dash
cd backend
python -m venv .venv
```

Activate the virtual environment.

**Windows PowerShell**

```powershell
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux**

```bash
source .venv/bin/activate
```

Then, from the `backend/` directory:

```bash
python -m pip install -r requirements.txt
python -m pytest
python scripts/generate_verified_results.py
```

The generator writes `verified-results.json` at the repository root. It runs the actual analyzers against the deterministic cases in `backend/pgara/samples.py`; it does not use the dashboard's illustrative sample figures. Results include the benchmark source, a SHA-256 input digest, register count, profiles and block counts, tradeoff, iteration budget, algorithm assignments, spilled ranges, estimated cost by profile, and stopping reason. Execution-time measurements are intentionally excluded from the results file because they vary by machine and run.

The generator labels results `generated_pending_manuscript_check` until the numeric outputs and configuration have been compared with the manuscript's tables and figures. Do not change that status to `verified` before that comparison. The provided reviewer checklist does not contain the manuscript's tables/figures, so generation alone is not proof of manuscript agreement.

To check that the checked-in result data matches the current implementation without overwriting the file, run from `backend/`:

```bash
python scripts/generate_verified_results.py --check
```

### Frontend tests and build

From the repository root, using Bun 1.4.4:

```bash
bun install --frozen-lockfile
bun test
bun run build
```

The same backend tests, frontend tests, frontend build, and generated-results consistency check are run by the GitHub Actions workflow in `.github/workflows/reproducibility.yml`. On pushes to `main` or `reproducibility/**`, the workflow regenerates `verified-results.json` after the tests and build pass and commits it if the generated experiment data changed. On pull requests, it checks the committed results against the current implementation.

### Run the backend and dashboard

Use two terminals. Keep the backend virtual environment activated in the first terminal:

```bash
# Terminal 1 — from backend/
python -m uvicorn pgara.api:app --host 127.0.0.1 --port 8741
```

In the second terminal, from the repository root:

```bash
bun run dev
```

Open the local URL printed by Vite. The backend API docs are at [http://127.0.0.1:8741/docs](http://127.0.0.1:8741/docs). The dashboard's connection setting defaults to `http://127.0.0.1:8741`; this can be overridden using `VITE_PGARA_API_URL` in a local `.env` file.

For the Windows PowerShell workflow, create and activate the virtual environment with:

```powershell
# From the repository root
py -3 -m venv backend\.venv
backend\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
python -m pytest -c backend\pytest.ini backend\tests
python backend\scripts\generate_verified_results.py
python -m uvicorn pgara.api:app --app-dir backend --host 127.0.0.1 --port 8741
```

### Configuration used for the built-in benchmark suite

The default suite is defined in `backend/pgara/samples.py` as `BENCHMARK_CASES`. It contains eight deterministic synthetic programs: sequential reuse, diamond control flow, a loop, profile-versus-static weighting, average-cost tradeoff, worst-profile tradeoff, zero registers, and insufficient registers. Each case supplies its own IR source, register count, profile counts, tradeoff, and iteration budget. The built-in suite uses load and store weights of 1 and starts potential-game search from `all_spilled`.

To rerun the suite through the HTTP API, start the backend and send an empty JSON object to `POST /api/benchmark`, for example:

```bash
curl -X POST http://127.0.0.1:8741/api/benchmark \
  -H "Content-Type: application/json" \
  -d '{}'
```

The result generator calls the same analyzer implementation and uses the same benchmark-case definitions as the API. A backend test compares the generated records with API benchmark responses so assignments and spill costs do not silently diverge.

### Interpreting the cost model

The reported spill costs are estimates, not measured execution time, memory traffic, or hardware performance. Static greedy counts IR load/store sites without profile counts. Profile-weighted greedy uses the explicitly supplied block execution counts to estimate dynamic spill operations. The potential-game allocator combines the average estimated profile cost and the worst estimated profile cost according to the tradeoff parameter. Its search accepts only strictly improving one-live-range moves and may stop at a local equilibrium or the iteration budget; it does not guarantee a global optimum. Execution counts are supplied inputs, never inferred by the analyzer.

Only the implemented and tested algorithms are included: Static Greedy, Profile-Weighted Greedy, and Potential Game. Linear Scan and Chaitin–Briggs are not reported because they are not part of the current backend implementation.

### Manuscript version and release tag

No release tag is declared as the manuscript version yet. Once the generated values have been compared with the manuscript's tables/figures, the results status has been updated appropriately, the backend tests and frontend build pass, and a fresh-clone reproduction succeeds, create and push an annotated tag on that exact commit. Record that tag in the manuscript's Code and Experimental Reproducibility / Data and Code Availability statement. Do not tag an unverified results file as the manuscript release.

## Architecture

- `backend/pgara/`: parser, control-flow graph, liveness analysis, interference graph, spill-cost model, allocation strategies, presentation layer, and API.
- `backend/tests/`: automated tests for parsing, liveness, interference, allocation correctness, spill costs, API behavior, and result reproducibility.
- `src/features/pgara/` and `src/services/`: dashboard workspaces, experiment controls, typed API integration, and response mapping.
- `verified-results.json`: machine-generated benchmark outputs plus the configuration and software environment used to generate them.
- `docs/API.md` and `docs/IR.md`: API and input-language contracts.

Sample mode in the dashboard is an explicitly labeled fixed illustration. It does not calculate new allocations when inputs change. Backend mode sends requests to FastAPI and shows results from the analyzer.
