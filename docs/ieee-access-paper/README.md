# IEEE Access manuscript (PGARA)

This folder is a self-contained IEEE Access manuscript for the profile-guided register-allocation prototype. Upload the whole folder to Overleaf and set `main.tex` as the main file.

## What is included

- `main.tex` — article source. It uses `\documentclass{ieeeaccess}`, not the IEEE conference class.
- `references.bib` — verified bibliography, IEEE numbered style via `IEEEtran`.
- `ieeeaccess.cls`, `IEEEtran.cls` — class files from the 2019 IEEE Access author-template distribution vendored by the public repository `hasantahir/Preparation-of-Papers-for-IEEE-ACCESS` (6 July 2019). Replace them with a fresh download from the [IEEE Template Selector](https://template-selector.ieee.org/) if the journal asks for the current zip.
- `Logo.png`, `notaglineLogo.png`, `bullet.png` — images the class loads from this directory.
- `figures/` — seven PDF figures referenced by the template `\Figure` macro, including the workspace path.
- `verified-results.json` — estimates recomputed with analyzer version 0.1.0 on Python 3.12.3. Wall-clock times were not saved.
- `Paper-Template-2.docx` — the uploaded manuscript brief. Content coverage follows that brief where it does not conflict with IEEE Access rules. Conflicts are listed in `EVIDENCE-CHECKLIST.md`.
- `EVIDENCE-CHECKLIST.md` — missing experiments, citation shortfalls, and fields the authors must supply.

The vendored class hard-coded the footer year 2016 in four places. Those four strings now use `\theyear`. `main.tex` sets the volume, year, and DOI to explicit placeholders (`--`, `--`, and `Not assigned`) because none were supplied.

## Compile

From this directory:

```bash
pdflatex -interaction=nonstopmode main.tex
bibtex main
pdflatex -interaction=nonstopmode main.tex
pdflatex -interaction=nonstopmode main.tex
```

On Overleaf, use the pdfLaTeX compiler. TeX Live may warn that font shapes `T1/ptm/n/n`, `T1/phv/n/n`, and `T1/pcr/n/n` are undefined and substitute the medium series. That warning comes from the class selecting series `n`. The PDF still builds.

## Before submission

Replace every placeholder: author names, affiliations, membership, corresponding-author email, biography, funding, acknowledgments, competing interests, author contributions, the generative-AI disclosure, the DOI, and the volume and year. Do not leave `Author Name Not Supplied` in the byline.
