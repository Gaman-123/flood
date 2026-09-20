# Main version — one paper, target 20 pages

Two builds of the same manuscript. **`main_paper_2col.pdf` (17 pages) is the one
that meets the brief.**

| File | Layout | Pages | Content |
|---|---|---|---|
| `main_paper_2col.tex` / `.pdf` | Two-column, IEEEtran | **17** | complete |
| `main_paper.tex` / `.pdf` | Single-column, article | 25 | complete |

Both carry the same 14 figures, 13 tables and 61 references.

## Build

```bash
tectonic main_paper_2col.tex
```

## Why there are two

The 30-page source was trimmed in two stages.

**Stage 1, removing redundancy** (`scripts/trim_main.py`). This is content that
genuinely earned removal, not padding chosen to hit a number:

- the RandomForest-vs-XGBoost bar chart, which plotted exactly the numbers in the
  table one paragraph away; the table is the precise form, and the numbers are
  now in the sentence that introduced it
- that table itself, folded into prose, since the ablation table already carries
  the full metric set for the 9-factor model
- the response-time/exposure bar pair, whose two values appear in the sentence
  above it and again in the route-overlay caption
- the QAOA depth plot, which redraws a table already giving mean, standard
  deviation, best-of-seeds, optimum-sampling probability and lift at every depth
- the Introduction, Limitations and Conclusions, condensed where they restated a
  number already tabulated
- six Related Work subsections merged into three; no citation dropped
- figure widths set per figure, and the 61-item bibliography set at
  `\footnotesize`

That took 30 pages to 25.

**Stage 2, layout** (`scripts/main_twocolumn.py`). 25 pages would not reach 20 in
one column. The arithmetic is in the script header: 6704 words and 27 floats
leave about 0.14 of a page per float at 20 pages, roughly 4 cm including the
caption, which a multi-panel map or a ten-row table cannot fit into. The only
single-column routes to 20 were cutting about 40% of the prose or dropping about
ten floats, both of which discard evidence.

Two columns halve the measure, so the same content sets in 17 pages. Nothing was
removed to get from 25 to 17.

The single-column build is kept because some venues require it, and because it is
the direct descendant of `../paper_journal_v2.tex`.

## Regenerating

```bash
python scripts/trim_main.py        # paper_journal_v2.tex -> main/main_paper.tex
python scripts/main_twocolumn.py   # main_paper.tex       -> main/main_paper_2col.tex
```

Both scripts fail loudly if an anchor they edit has moved, so a silent
mis-application is not possible. Edit `paper/paper_journal_v2.tex` and re-run;
do not edit the generated files.

## Verified

- 0 compile errors, no `??`, no duplicate section headings
- every figure and table referenced in the text
- 61 bibliography entries: no duplicates, none uncited, none cited-but-missing.
  This is a structural check, not source verification; the separate IEEE Access
  audit has 10 `UNVERIFIED` entries plus one manual, non-Crossref entry.
- worst overfull box 10.9 pt
