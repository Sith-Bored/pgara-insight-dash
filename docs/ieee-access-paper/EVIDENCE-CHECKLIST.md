# Evidence checklist

This checklist records what the compiled draft actually supports, where `Paper-Template-2.docx` conflicts with the IEEE Access template, and what is still missing. It is not a list of results.

## Template source

`Paper Template-2.docx` was not in the repository when the draft was first written. It was supplied later and is now stored in this folder. Its section outline matches the manuscript: title and abstract, introduction, related work, proposed work, implementation and result analysis, conclusion, references, author contributions, acknowledgments, funding, competing interests, and data and code availability.

IEEE Access rules were kept where the brief conflicts with them:

- The abstract is one paragraph of 210 words. The journal asks for 150–250 words. The brief asked for a longer line-by-line abstract. Those topics are expanded in the introduction. The current draft is a fresh article that includes the React workspace as part of the system.
- Citations are IEEE numbered entries via `IEEEtran`. The brief's examples use author-year form (Filippini and Hunt, 2011, and similar). That form is not used.
- The brief asked for about 30 references, all dated 2018–2024, split as 10 from the introduction, 15 from related work, 2 tool sources, and 2–3 comparison papers. This bibliography has 26 entries. Nine are scholarly or preprint works from 2022–2025. The rest are foundational register-allocation and potential-game papers from before 2018, or tool and author-instruction pages accessed 13 October 2026. Unrelated hits (including oil-spill papers) were not added to reach 30.
- The introduction cites the recent works that could be verified. It does not contain 15 papers from the last five years, because that many relevant records with usable abstracts were not verified.
- Related work discusses each included paper's proposal, method, reported result, and gap relative to PGARA, but only from the retrieved title and abstract. The brief asked for two methodology paragraphs and named tools for every paper. Those details were not invented when the abstract did not state them.
- Jeong and colleagues, *Journal of Systems Architecture*, 2024, DOI `10.1016/j.sysarc.2024.103099`, was seen as a candidate and omitted because no usable abstract was retrieved. A different OpenAlex hit (TEA-RC, DOI `10.1109/access.2022.3196149`) is not that paper and is not cited. Callahan and colleagues, DOI `10.1145/113445.113455`, is program slicing and is not cited as register allocation. DOI `10.1145/989393.989424` is a reprint of Briggs's coloring heuristics, not a second paper.

## Verified results used in the tables

All of the following come from analyzer version 0.1.0, load and store weights 1, potential search started from the all-spilled assignment. Dashboard rows use tradeoff 3/5. Suite rows use each case's own tradeoff.

Dashboard sample, ten live ranges, three profiles (Hot loop, Balanced, Cold-heavy):

| Registers | Spill set | Per-profile estimates | Sum | Static count | Assigned |
| --- | --- | --- | --- | --- | --- |
| 2 | c, d, t2, t4 | 5850, 5500, 5200 | 16550 | 7 | 6 |
| 3 | d | 1000, 1000, 1000 | 3000 | 1 | 9 |
| 4, 5, 6 | none | 0, 0, 0 | 0 | 0 | 10 |

At six registers the spill sets match and the assignments do not. Static greedy places t1 on p0, t3 on p1, and t5 on p0. Profile-weighted greedy and the potential search place t1 on p1, t3 on p0, and t5 on p1. The estimated cost ignores that difference.

Built-in suite, shared spill sets:

| Case | Tradeoff | Sum | Static | Spilled |
| --- | --- | --- | --- | --- |
| sequential_reuse | 1/2 | 0 | 0 | none |
| diamond | 1/2 | 3 | 3 | b |
| loop | 1/2 | 40 | 4 | s |
| zero_registers | 1/2 | 6 | 6 | a, b, c |
| insufficient_registers | 1/2 | 8 | 8 | b, c, d, f |

Cases that separate a decision:

| Case | Tradeoff | Static greedy | Profile-weighted and, where noted, the search |
| --- | --- | --- | --- |
| profile_versus_static | 0 | spill b, sum 101, static 2 | spill a, sum 8, static 8 |
| game_average | 0 | spill b, sum 19 | all three spill b, sum 19; the search keeps a on p0 |
| game_worst | 1 | spill b, sum 19, static 2 | search spills a, sum 20, static 4 |

The sample-mode fixture values 4200, 1800, and 1200 are not measurements and are not in the tables.

The zero-cost chart annotation and the empty benchmark request body are implementation corrections. They are not experimental findings. Before the empty-body correction, a robustness slider of 0.6 ran both game cases at tradeoff 3/5, and the potential search spilled `a` with sum 20 in both.

## Five metrics, and what was not measured

Supported, and shown in the tables or in Figure 6:

1. Estimated spill operations (dimensionless counts from the profile model).
2. Static spill operations.
3. Number of spilled live ranges.
4. Allocation validity (interference check). Every tabulated result passed. The export file records stopping reasons, not a separate validity column; the analyzer rejects an illegal assignment before it returns.
5. Spill-set agreement across the three algorithms.

Not measured, so not reported as performance:

- Application or SPEC runtime, code size, or retired loads and stores. Spill code is not inserted.
- A comparison against LLVM, GCC, or the numbers published by Burroughs, Pereira and Palsberg, or the RL4ReAl preprint. Those setups do not compute this estimate.
- Speedup, confidence intervals, or statistical significance.
- A hardware model or a repeated timing study. `execution_time_ms` exists in the API and is checked only as a nonnegative field in a unit test. The export sets it to null.
- Sweeps of load weight, store weight, iteration budget, or the game's starting assignment.
- Live-range splitting, coalescing, or a path-sensitive liveness analysis. None of these is implemented.
- Evidence that the potential search lowers estimated cost on a broad program set. On the programs that were run, it matches greedy except `game_worst`, where the summed estimate rises from 19 to 20 while the worst profile falls.
- A screenshot. No image was captured from a running dashboard session, so none was inserted. The brief asked for one implementation screenshot. Figure 2 is a module diagram, not a screen capture.

## Proposed experiments

1. Recompute the eight suite cases and the dashboard sample on a named machine, with a stated repetition count, and publish `execution_time_ms` only after that protocol exists.
2. Sweep load weight, store weight, iteration budget, and the three legal game starts on the tradeoff program, and report when the spill set changes.
3. Emit spill instructions and count them. Until that exists, do not compare with papers that count dynamic loads and stores.
4. Add programs beyond the eight synthetic cases before claiming that tradeoff 1 is typical.
5. If a production-compiler comparison is required, define a shared metric first. Estimated spill operations on this intermediate representation are not SPEC compile time and are not LLVM spill counts.

## Information the authors must supply

- Author names, IEEE membership if any, affiliations, city, country, and the corresponding author's email.
- A biography, and a photograph only if one is provided.
- Author-contribution statements that meet the journal's authorship criteria.
- Acknowledgments of people. The current acknowledgment states that a coding agent helped prepare the draft and must be replaced by the disclosure the authors approve.
- Funding: grant numbers, sponsors, or an explicit statement that there was none.
- Competing interests: a real declaration, not a placeholder.
- A public code or data archive and its DOI, if the authors will share one.
- The assigned DOI, volume, and year. The PDF currently prints `Not assigned` and volume `--`, year `--`.
- Confirmation that every citation and number was read against the source, not only against the abstracts used here.

Section III, Proposed Work, occupies pages 3--6 of the compiled 10-page draft, and Section IV starts on page 7. That span covers formulation, architecture, the dashboard, the client request, flow, liveness, equations, and algorithms.

## Compilation note

`main.pdf` is produced by pdfLaTeX and BibTeX in this directory. Figure paths use `\graphicspath{{figures/}}` and the class `\Figure` macro. Do not switch the figures back to a raw `figure` environment: the class caption code expects `\xfigwd`, which `\Figure` sets.
