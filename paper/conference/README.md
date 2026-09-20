# Conference paper (anonymised)

Self-contained IEEE conference version, 8 pages. Everything needed to build it is
in this folder.

```
conference/
  conference_paper.tex     IEEEtran source, anonymised
  conference_paper.pdf     compiled output, 8 pages
  figures/                 the 8 figures the paper references
```

## Build

```bash
tectonic conference_paper.tex
```

Any LaTeX toolchain with `IEEEtran` works; `pdflatex conference_paper.tex` run
twice also produces correct cross-references.

## What was removed for anonymous review

Two things, both marked with a comment in the source at the point of removal so
they are easy to find and restore:

1. **Author block** — the `\IEEEauthorblockN` / `\IEEEauthorblockA` block after
   `\title`. The file now has a bare `\author{}`.
2. **Acknowledgment section** — it named an author and the institution, so
   leaving it would have defeated the anonymisation.

Verified by extracting the text of the compiled PDF and searching it: no author
name, institution, or acknowledgment heading survives in the rendered output,
not only in the source.

Restore both before camera-ready. The removed text is in this repository's
history if you need it verbatim.

## Relationship to the journal version

This is the short version of the same study. The full-length manuscript is
`../paper_journal.tex`. Measured prose overlap between the two is 1.42%, with
the longest shared run being 15 words that name the two study events. If you
submit both, disclose the conference paper in the journal cover letter as the
normal extension-of-prior-work declaration.

## Figures

All eight are generated from pipeline artifacts by `scripts/make_paper_figures.py`
in the repository root. They are copied here rather than referenced across
directories so this folder can be zipped and submitted on its own.
