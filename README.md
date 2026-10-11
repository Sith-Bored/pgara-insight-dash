# Pgara Insight Dash

Build a polished, interactive research dashboard for a Computer Science compiler-design project called **PGARA — Profile-Guided Adaptive Register Allocation**.

This is an academic compiler visualization tool, not a generic SaaS dashboard and not just a landing page.

### Visual design

Create a professional dark developer interface inspired by compiler tooling, IDEs, and scientific visualization. Use a near-black background, restrained blue and violet accents, subtle borders, compact typography, and clean data visualizations. Avoid excessive gradients, glowing effects, oversized headings, and unnecessary animations.

The application should look credible in a university professor demonstration.

### Main layout

Create a persistent sidebar with:
- Overview
- Program Editor
- Allocation Lab
- Interference Graph
- Benchmark Comparison
- Algorithm Trace

The main overview should contain:
- A concise project description.
- Register allocation configuration.
- A sample three-address-code program.
- An execution profile panel.
- An algorithm comparison area.
- A results and decision-trace section.

### Program Editor

Provide a code editor-like input area for a small three-address intermediate representation. Include a Load Sample Program button and editable sample code with labeled basic blocks, assignments, arithmetic, conditional branches, and return statements.

### Configuration controls

Allow the user to configure:
- Number of available physical registers.
- Execution-frequency profile.
- Allocation algorithms to compare.
- The multi-profile robustness parameter.

Provide a button labeled Run Allocation Experiment.

### Allocation results

Design sections for:
- Virtual register to physical register assignments.
- Spilled live ranges.
- Estimated dynamic spill operations.
- Allocation execution time.
- Interference graph.
- Profile-by-profile cost.
- Game-inspired allocation decision trace.

Use tables, charts, and a graph visualization where appropriate. Show clear labels and units.

### Comparison algorithms

Provide three options:
1. Static Greedy
2. Profile-Weighted Greedy
3. Multi-Profile Potential Game

### Technical implementation requirements

Use React, TypeScript, Tailwind CSS, and reusable components.

Create a separate typed API service module so the application can later connect to a Python FastAPI backend. Keep the visualization components separate from the data-fetching logic.

For the first UI iteration, use a clearly identified sample dataset only to demonstrate the layout. Do not present sample metrics as real benchmark results. Make it straightforward to replace sample data with actual API responses.

Add loading states, empty states, validation errors, and backend connection error handling.

Do not add authentication, a database, Supabase, or unrelated product features. This is an academic single-user research prototype.

Create the complete initial frontend, make the principal navigation and controls interactive, and ensure the layout works on a laptop screen. The next stage will connect it to our real compiler-analysis backend.

This project was built with [Lovable](https://lovable.dev).

## Build with Lovable

Continue developing this project in the [Lovable editor](https://lovable.dev/projects/2ba5c651-f3ca-46f5-9fd6-a73cd49562c8).

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: every change made in Lovable is committed straight to this repository.
- **Full ownership**: this code is yours. Push to `main` on GitHub and your changes sync back into Lovable, ready for your next prompt.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```
