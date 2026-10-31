# PGARA Benchmark Dataset

## Overview
PGARA uses deterministic synthetic benchmark programs to evaluate three register allocation algorithms: Static Greedy, Profile-Weighted Greedy, and Potential Game.

## Dataset Source
The benchmark cases are defined in:

`backend/pgara/samples.py`

## Benchmark Cases
1. Sequential Reuse
2. Diamond Control Flow
3. Loop
4. Profile Versus Static Weighting
5. Average-Cost Trade-off
6. Worst-Profile Trade-off
7. Zero Registers
8. Insufficient Registers

## Data Generation
The benchmark inputs are generated programmatically. Basic block execution counts and profile information are explicitly defined in the benchmark configurations.

## Preprocessing
No external dataset or separate preprocessing pipeline is required. The synthetic programs and execution profiles are passed directly to the PGARA analysis engine.

## Reproducibility
To regenerate the benchmark results, follow the instructions in the main README and run:

`python scripts/generate_verified_results.py`

from the `backend` directory.
