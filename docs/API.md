# PGARA API 1.0

Base URL when the backend is running locally: `http://127.0.0.1:8741`.

The response models in `backend/pgara/schemas.py` are the source of truth. This document is the reading version for the frontend. OpenAPI at `/docs` is generated from those models.

Assignments use JSON `null` for a spill. Decision-trace strategies use the string `"spill"` or a physical register name `p0`, `p1`, ... Virtual registers in the IR may also be named `p0`; only the assignment values are physical registers.

Potentials are exact rationals. Compare `numerator / denominator`. `potential_float` is a display convenience and can be a binary approximation.

`estimated_spill_operations` is not measured runtime. It is `load_cost` times the supplied execution counts of blocks where a spilled range is used, plus `store_cost` times the supplied execution counts of blocks where that range has a live definition. The total for a profile sums the spilled ranges. Static spill cost is the same formula with one occurrence per IR site and does not use execution counts.

The potential of an allocation is:

```
(1 - tradeoff) * average(profile costs) + tradeoff * max(profile costs)
```

`tradeoff` is limited to a rational with denominator at most 1000000. `0.5` is stored as `1/2`.

## Endpoints

### `GET /api/health`

```json
{ "status": "ok", "service": "pgara", "api_version": "1.0", "version": "0.1.0" }
```

### `GET /api/sample-program`

Returns the tradeoff sample: source text, `num_registers: 1`, two profiles (`skew` and `quiet_b`), and two suggested runs.

With `load_cost = store_cost = 1`, the estimated spill cost of `a` is 10 on both profiles. The estimated spill cost of `b` is 19 on `skew` and 0 on `quiet_b`. The ranges interfere. With one register and `game_initial: "all_spilled"`:

- `tradeoff: 0` keeps `a` (`p0`) and spills `b`.
- `tradeoff: 1` keeps `b` and spills `a`.

Those counts are written in the sample. They are not inferred.

### `POST /api/allocate`

Provide exactly one of `source` (text, see [IR.md](IR.md)) or `program` (structured blocks).

```json
{
  "source": "block entry:\n  a = 1\n  return a\n",
  "num_registers": 2,
  "profiles": [
    { "name": "once", "block_counts": { "entry": 10 } }
  ],
  "algorithm": "all",
  "tradeoff": 0.5,
  "iteration_budget": 200,
  "load_cost": 1,
  "store_cost": 1,
  "game_initial": "all_spilled"
}
```

`algorithm` is `static_greedy`, `profile_greedy`, `potential_game`, or `all`. Defaults are `all`, tradeoff `0.5`, budget `200`, load and store cost `1`, and `game_initial` `all_spilled`.

`game_initial` is `all_spilled`, `static_greedy`, or `profile_greedy`. The default start is all spilled, because a cost that depends only on which ranges spill has no improving single-register move once a greedy packing has already filled every feasible register. Starting from a greedy allocation can therefore stop immediately even when a two-range swap would look better. The response says which start was used, and it does not call that state globally optimal.

Structured instructions use `op` of `const`, `mov`, `add`, `sub`, `mul`, `div`, `br`, `jmp`, or `ret`. Operands are `{ "kind": "reg", "name": "a" }` or `{ "kind": "imm", "value": 1 }`. `br` and `jmp` set `target`.

The response contains:

- `cost_model` — weights, the tradeoff rational, and the cost definition.
- `blocks` — instructions, text, per-instruction live-in and live-out, and CFG successors (`fallthrough`, `branch_true`, `branch_false`, `jump`).
- `interference` — nodes, undirected edges `{ "a", "b" }` in lexicographic order, and degrees.
- `live_ranges` — id, virtual register, static cost, per-profile cost if that range were spilled, and load/store sites.
- `undefined_uses` and `dead_definitions`.
- `liveness_iterations` — how many passes the fixpoint ran.
- `results` — one entry per algorithm, in the order static, profile, game when `algorithm` is `all`.

Each result includes `assignments`, `spills`, `physical_registers`, `valid`, `static_spill_operations`, `per_profile_costs`, the potential rational, `execution_time_ms`, `iterations`, `stopping_reason`, `initial_allocation` (game only), `decision_trace`, and `notes`.

Stopping reasons:

| Reason | Meaning |
| --- | --- |
| `single_pass` | Greedy finished its one packing pass. |
| `no_improving_move` | No unilateral change strictly lowers the potential. |
| `iteration_budget` | The search accepted `iteration_budget` moves and did not look further. A budget of 0 accepts nothing. |

`execution_time_ms` is time spent inside that allocator on this machine. It is not the spill estimate.

A skipped result (`status: "skipped"`) is used when `algorithm` is `all` and no profile was sent. `profile_greedy` and `potential_game` are not run. Requesting either algorithm by itself without a profile is HTTP 422 with `detail.error` set to `input_error`.

IR and profile problems are HTTP 422 with:

```json
{ "detail": { "error": "ir_validation_error", "message": "line 2: ...", "line": 2 } }
```

Pydantic schema failures are also HTTP 422, with FastAPI's usual `detail` list. Extra JSON fields are rejected.

### `POST /api/benchmark`

```json
{}
```

Runs eight synthetic programs through the three allocators. Each case has its own register count, profiles, and tradeoff unless the body overrides `tradeoff` or `iteration_budget`. `load_cost`, `store_cost`, and `game_initial` can also be set; their defaults match `/api/allocate`.

The cases include a reuse example, a branch, a loop, a program where static greedy and profile-weighted greedy choose different ranges, the same tradeoff program at tradeoff 0 and tradeoff 1, a zero-register run, and a program whose interference clique does not fit in one register.

`execution_time_ms` and the assignments come from those executions. The top-level `note` says the spill figures are not measured runtime and that the game results are not claimed to be globally optimal.

## Input policy

- `num_registers` integer, 0 through 256. Zero spills every live range. Too few registers for the interference graph also spills. Neither case is an error.
- Profile counts are integers greater than or equal to 0. Every block label must appear. Unknown labels are errors. Counts are not invented.
- At most 32 profiles, 500 blocks, 5000 instructions, and 100000 source characters.
- `iteration_budget` integer, 0 through 10000.
- `load_cost` and `store_cost` integers, 0 through 1000. If both are 0, the game accepts no move from an all-spilled start, because the potential does not strictly fall. Greedy can still pack registers; it is not searching the potential.

## Game trace

Each accepted move records the live range, the previous strategy, the new strategy, the previous and new profile-cost vectors, and the previous and new potential. Every accepted move satisfies `new_potential < previous_potential` exactly on the rationals. The scan order is live-range id, then `p0`, `p1`, ..., then spill. An equal potential does not replace an earlier candidate and is not accepted.

## What this milestone does not do

It does not split live ranges, coalesce copies, rewrite instructions into spill code, or prove that a register is initialized on every path. Liveness is may-liveness. The game neighborhood is one live range at a time, so some cheaper assignments are unreachable from a given start.
