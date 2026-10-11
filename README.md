# PGARA

PGARA (Profile-Guided Adaptive Register Allocation) is a compiler-design research prototype. This repository contains the milestone-1 analysis backend: a small three-address IR, control-flow and liveness analysis, an interference graph, and three register allocators.

The workspace did not contain a frontend. Nothing here replaces or redesigns one. The HTTP API is the contract a frontend can call. Machine-readable details are in the OpenAPI document at `/docs` while the server is running, and in [docs/API.md](docs/API.md).

## What the allocators do

All three allocators assign each live range either a physical register (`p0`, `p1`, ...) or a spill. A live range is one virtual register. Live-range splitting is not implemented. `LiveRange.id` is the allocation key and currently equals the virtual register name, so a later pass can split one name into several ids without rewriting the allocators.

An assignment is rejected by an internal check if two interfering, non-spilled live ranges share a register. Spilled ranges do not occupy a register.

- **static_greedy** orders ranges by how many spill operations appear in the IR and gives each range the lowest-numbered free register. It does not read execution counts.
- **profile_greedy** uses the same packing rule, but orders ranges by the sum of estimated dynamic spill operations across the profiles you supplied.
- **potential_game** treats each live range as a player. A strategy is a physical register or spilling. Starting from a valid allocation (all spilled, unless you choose another start), it accepts a change of one player only when that change strictly lowers the potential. It stops at a local equilibrium or at the iteration budget. That is not a claim of global optimality.

Estimated spill cost is computed from block execution counts you send. The service does not fill in missing counts, and it does not report those estimates as measured runtime.

`num_registers` may be 0. That is a valid request: every live range spills because no physical register exists. A request that needs more registers than it has is also valid: the extra ranges spill. Negative counts and non-integers are rejected.

## Layout

```
backend/pgara/    analyzer, allocators, and FastAPI app
backend/tests/    pytest suite
docs/API.md       request and response contract
docs/IR.md        textual IR syntax
```

## Run the tests and the API

From the `backend` directory, with Python 3.11 or newer.

### Windows PowerShell

```powershell
cd backend
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest
python -m uvicorn pgara.api:app --host 127.0.0.1 --port 8741
```

If activation is blocked for the current process only:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

`py -3` is the usual Windows launcher. If it is not installed, use `python` in place of `py -3` for the `venv` line.

### bash

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest
python -m uvicorn pgara.api:app --host 127.0.0.1 --port 8741
```

Then open [http://127.0.0.1:8741/docs](http://127.0.0.1:8741/docs) or `GET http://127.0.0.1:8741/api/health`.

A sample call from PowerShell, using a JSON file so newlines in the IR stay intact:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8741/api/allocate -ContentType "application/json" -InFile .\payload.json
```

`payload.json`:

```json
{
  "source": "block entry:\n  a = 1\n  b = 2\n  c = a + b\n  return c\n",
  "num_registers": 1,
  "profiles": [{ "name": "once", "block_counts": { "entry": 1 } }],
  "algorithm": "all",
  "tradeoff": 0.5
}
```

## Connect a frontend

Point the frontend at `http://127.0.0.1:8741`. CORS allows `http://localhost` and `http://127.0.0.1` on any port, including 3000, 4173, 5173, and 8080. Credentials are not enabled. Do not send cookies or `credentials: "include"`.

```javascript
const response = await fetch("http://127.0.0.1:8741/api/allocate", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    source,
    num_registers: 2,
    profiles,
    algorithm: "all",
    tradeoff: 0.5,
    iteration_budget: 200,
    game_initial: "all_spilled"
  })
});
```

A Vite dev server can proxy `/api` instead of calling the other origin directly:

```javascript
// vite.config.js
export default {
  server: {
    proxy: { "/api": "http://127.0.0.1:8741" }
  }
};
```

`GET /api/sample-program` returns a program, two profiles, and two suggested `tradeoff` values. `POST /api/benchmark` with `{}` runs the built-in synthetic suite by actually calling the allocators.

In assignment maps, `null` means spilled. In decision traces, the strategy string is `"spill"` or `"p0"`, `"p1"`, and so on. Compare potentials with `potential_numerator / potential_denominator`. The decimal `potential_float` is only for display.

## Limits that are part of the input policy

| Input | Policy |
| --- | --- |
| `num_registers` | Integer 0 through 256. Zero spills every live range. |
| `tradeoff` | Number from 0 through 1. Weight on the worst profile. |
| `iteration_budget` | Integer 0 through 10000. Zero accepts no game moves. |
| `load_cost`, `store_cost` | Integers 0 through 1000. Default 1. |
| Profiles | At most 32. Every block needs an explicit non-negative integer count. |
| Source | At most 100000 characters, 500 blocks, 5000 instructions. |

`static_greedy` runs without profiles. `profile_greedy` and `potential_game` return HTTP 422 if you request them without a profile. `algorithm: "all"` still runs the static allocator and marks the other two `skipped` rather than inventing counts.
