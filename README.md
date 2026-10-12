# Pgara Insight Dash

Interactive research dashboard for **PGARA — Profile-Guided Adaptive Register Allocation**, a compiler-design project.

The Lovable frontend lives at the repository root. The milestone-1 compiler analysis backend lives in `backend/`. API details are in [docs/API.md](docs/API.md) and the IR syntax is in [docs/IR.md](docs/IR.md).

This project was built with [Lovable](https://lovable.dev).

## Build with Lovable

Continue developing this project in the [Lovable editor](https://lovable.dev/projects/2ba5c651-f3ca-46f5-9fd6-a73cd49562c8).

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: every change made in Lovable is committed straight to this repository.
- **Full ownership**: this code is yours. Push to `main` on GitHub and your changes sync back into Lovable, ready for your next prompt.

## Frontend

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```

The dashboard starts in sample mode. Those numbers are a fixed illustration. They do not change when you edit the program, and they are not measurements.

To call the analyzer, start the backend (below) and switch **Connection settings** to the FastAPI backend. The default URL is `http://127.0.0.1:8741`. Override it with `VITE_PGARA_API_URL` (see `.env.example`). Changing the register count, program, profiles, algorithms, or tradeoff does not call the API. **Run Allocation Experiment** sends `POST /api/allocate`, then `POST /api/benchmark`.

`GET /api/health` updates the connection status. **Load sample** in backend mode reads `GET /api/sample-program` into the editor and does not allocate until you run.

The request uses the register count, the program text, one execution count per basic block, the selected algorithms, and the robustness slider as `tradeoff`. The potential game starts from `all_spilled` with iteration budget 200. Spill figures in backend mode are estimates. The synthetic suite on the benchmark page is a set of allocator runs on built-in programs, not measured application runtime.

### Windows PowerShell

Use two terminals.

```powershell
# Terminal 1 — analyzer
cd backend
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest
python -m uvicorn pgara.api:app --host 127.0.0.1 --port 8741
```

```powershell
# Terminal 2 — dashboard
Copy-Item .env.example .env
npm install
npm run dev
```

Open the URL Vite prints. In the dashboard, open Connection settings, choose FastAPI backend, check the connection, apply, then run an experiment.

## Backend

The analyzer parses a small three-address IR, builds a control-flow graph, runs iterative liveness and interference, and allocates registers with static greedy, profile-weighted greedy, and a potential-game search. Spill figures are estimates from execution counts you supply. They are not measured runtime. The game search stops at a local equilibrium or the iteration budget. It does not claim global optimality.

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

Then open [http://127.0.0.1:8741/docs](http://127.0.0.1:8741/docs). CORS allows `http://localhost` and `http://127.0.0.1` on any port. Credentials are not enabled.

Point the dashboard at `http://127.0.0.1:8741`, or proxy `/api` to that address. `GET /api/sample-program` returns a program and profiles. In assignment maps, `null` means spilled.
