# Milestone 1 plan

The repository at the start of this work contained only an empty initial commit. There was no frontend to preserve, so this milestone adds the analysis backend and a documented API instead of a new UI.

## Pipeline

1. Parse textual IR, or accept the same program as structured JSON.
2. Validate labels, instruction shapes, terminator placement, and profile counts.
3. Build a control-flow graph. A conditional branch's false edge is the next block in source order.
4. Compute may-liveness by repeating a backward transfer until block live-in and live-out stop changing.
5. Build an interference edge for every pair of virtual registers that are live at the same instruction boundary. One live range per virtual register. The range id is the allocation key, which leaves room for splitting later.
6. Estimate spill cost from live definitions and uses. Profile estimates multiply those sites by the supplied block counts. Static estimates count IR sites and ignore profiles.
7. Allocate with static greedy, profile-weighted greedy, and the potential-game search.

## Allocators

Greedy considers ranges in decreasing spill weight, with the live-range id as a tie break. Static weight is the static spill-operation count. Profile weight is the sum of estimated dynamic spill operations across the supplied profiles. The first free physical register in order `p0`, `p1`, ... is used. If none is free, the range spills.

The game starts from a valid allocation. The default start is every range spilled. Each step evaluates feasible unilateral changes and keeps the change with the strictly lowest potential. The potential is `(1 - tradeoff) * average + tradeoff * worst` over the per-profile estimated spill costs. The search stops when no improving move remains or the iteration budget is exhausted. The trace stores the move and both costs. The stopping reason is reported. The result is not described as globally optimal.

`num_registers = 0` is valid and spills every range. A clique larger than the register file spills the ranges that do not receive a register. Negative register counts are rejected.

## API

`GET /api/health`, `GET /api/sample-program`, `POST /api/allocate`, and `POST /api/benchmark`. Benchmark cases are fixed synthetic programs. The endpoint runs the allocators and returns those runs, including allocator time. CORS allows local development origins and does not use credentials.

The contract is frozen as API 1.0 in `backend/pgara/schemas.py` and `docs/API.md`.
