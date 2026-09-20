# IEEE Access submission build

`IEEE-Access-Submission.pdf` (18 pages) is the deliverable. `access_paper.tex` is
its source; `access_paper.pdf` is the identical build output.

## Build

```bash
tectonic access_paper.tex
```

Tectonic runs XeTeX, which is required here: the layout loads the genuine
**Times New Roman** and **Helvetica** through `fontspec` rather than metric
substitutes. A pdfLaTeX build would silently fall back to different fonts.

## How the format was derived

Not from memory. `Access-Template-2024.docx` was unzipped and its
`word/document.xml` and `word/styles.xml` read directly. Values in twips
(1440 twips = 1 inch), with what was implemented:

| Template property | Value in .docx | Implemented |
|---|---|---|
| Page size | `w=11520 h=15660` | 8.000 × 10.875 in |
| Top / bottom margin | `1300` / `1040` | 0.903 / 0.722 in |
| Left / right margin | `740` / `740` | 0.514 in |
| Columns | `num=2 space=400` | 2 cols, 0.278 in gutter |
| Header / footer | `header=360 footer=640` | 0.250 / 0.444 in |
| Body (`PARA`) | 10 pt, `line=240 exact`, justified | 10 pt on 12 pt fixed |
| Title (`PaperTitle`) | Helvetica 22 pt bold, `#00629B`, no `w:jc` | as specified, ragged right |
| Authors (`AU`) | Helvetica 10 pt bold, right indent 1380 | as specified |
| Affiliation (`PI`) | 7.5 pt, 9 pt fixed leading | as specified |
| Abstract | 10 pt justified, right indent 1380 | as specified |
| Section (`H1`) | Helvetica 9 pt bold, `#00629B` | as specified, Roman numeral |
| Subsection (`H2`) | Helvetica 9 pt bold italic, `#58595B` | as specified |
| Sub-subsection (`H3`) | Helvetica 9 pt, `#58595B` | as specified |
| Figure/table caption | Helvetica 7 pt bold | as specified |
| References | 8 pt justified | as specified |
| Biographies (`AUBios`) | 8 pt justified, photo 1.00 × 1.25 in | as specified |

The run-in `ABSTRACT` and `INDEX TERMS` labels use the `H5CharChar` character
style, Helvetica in `#00629B`.

## Column structure, verified

The template runs **one column for the front matter and two equal columns for the
body**. Confirmed by walking the section breaks in `word/document.xml`: section 1
ends after INDEX TERMS and carries `<w:cols w:space="720"/>` with no `w:num`,
i.e. one column; every later section carries `<w:cols w:num="2" w:space="400"/>`.
There are no explicit `<w:col>` children, so the two columns are equal width.
Reproduced with a full-width `\twocolumn[...]` title block over a two-column body.

Alignment follows the styles rather than assumption: `PaperTitle`, `AU`, `PI` and
`IT` have no `w:jc` and so set ragged right; `Abstract`, `PARA`, `References` and
`AUBios` are `w:jc="both"` and set justified.

## Verified against the rendered PDF

- page size **576 × 783 pt = 8.000 × 10.875 in**, exact
- text block **6.972 in** wide, left and right margins **0.514 in**, exact
- column 1 spans **37.0 to 278.0 pt**, column 2 **298.0 to 539.0 pt**: both
  **3.347 in** wide with a **0.278 in** gutter, exact
- embedded fonts: `TimesNewRomanPSMT`, `TimesNewRomanPS-BoldMT`,
  `TimesNewRomanPS-ItalicMT`, `Helvetica`, `Helvetica-Bold`,
  `Helvetica-Oblique`, `Helvetica-BoldOblique`
- 61 references: no duplicates, none uncited, none cited-but-missing
- every figure and table referenced in the text
- no `??`, no compile errors, worst overfull box 7.6 pt

`DejaVuSans` also appears in the font list. That is carried inside the
matplotlib-generated figure PDFs, not used by the page layout.

## Is it one column or two?

Two, for the body. The template states it in section VIII-B:

> "The manuscript should be prepared in a **double column, single-spaced**
> format using a required IEEE Access template."

The front matter is one column and the body is two. Confirmed three ways:
by walking the section breaks in `word/document.xml` (section 1 ends after
INDEX TERMS with `<w:cols w:space="720"/>`, no `w:num`; later sections carry
`<w:cols w:num="2" w:space="400"/>`), by that sentence in the template's own
text, and by converting the template to PDF and looking at it, where page 1
shows sections I and II side by side.

## Rules from the template's own text, and what they changed

The template is not only a layout: its body text states rules. Reading them
found four things wrong with the first build.

| Rule (quoted from the template) | Was | Now |
|---|---|---|
| "The abstract must be between 150-250 words." | 314 words | **244 words** |
| "the abstract must be self-contained, without abbreviations" | used SAR, NDVI, ROC-AUC, QUBO, QAOA | **no abbreviations** |
| "Enter key words or phrases in alphabetical order" | unordered | **alphabetical** |
| "figures are not sized less than column width" | 8 figures below column width | **all at column or page width** |
| "Tables should be numbered with Roman Numerals" | Arabic (TABLE 3) | **Roman (TABLE III)** |
| "use the abbreviation 'Fig.' even at the beginning of a sentence" | "Figure 7" | **"Fig. 7"** |

The figure widths were inherited from a page-count reduction done for a
different build. The template also says "Do not change the font sizes or line
spacing to squeeze more text into a limited number of pages", so that reduction
had no place here and was reverted. The paper is 19 pages as a result, one more
than before, which is the correct trade.

Two further corrections came from rendering the template with LibreOffice and
looking at it, rather than reading its XML alone:

- the template carries the **IEEE Access logo** top right with a rule beneath,
  on every page, and **no author running head**. The first build had an invented
  "Author et al.:" running head. The logos now used are the exact assets from
  the template's own `word/media`, printed at their template size (383 px at
  299 ppi = 1.281 in on page one, 322 px on later pages).
- the footer is Helvetica 6 pt, `VOLUME XX, 2017` left and the page number
  right. The first build centred the page number.
- a **"Date of publication"** line sits above the DOI line; it was missing.

## Submission mechanics the template specifies

- "A Word or LaTeX file **and** a PDF file are both required upon submission."
  `access_paper.tex` plus its `figures/` directory satisfies the source
  requirement; `IEEE-Access-Submission.pdf` is the PDF.
- "Figures should be submitted **individually**, separate from the manuscript."
  They are already separate files in `figures/`.
- Submission goes through the IEEE Author Portal; see https://ieeeaccess.ieee.org/.

Verified against the template's other float rules: figure captions sit below
figures, table titles above tables, and no borders are drawn around figures.

## What you must fill in before submitting

The author block deliberately contains placeholders rather than invented
details. Search `access_paper.tex` for square brackets:

- `[INSTITUTIONAL EMAIL]` for the corresponding author. IEEE Access expects an
  institutional address; a personal one is not filled in automatically
- `[FUNDING SOURCE / grant number, ...]` in the first footnote, or delete that
  sentence entirely
- `[biography]` for each of the four authors, plus the four author photographs
  at exactly 1.00 × 1.25 in
- the DOI line, which IEEE fills at acceptance

Author order is currently Chowta, Shajeendran, Dhrithi, Rai; change it in
`AUTHORS` in `scripts/make_ieee_access.py` if that is not the intended order.

## Known deviation

Mathematics is set in **Latin Modern Math**, not a Times-matched math font.
`TeX Gyre Termes Math` is the Times companion and would be closer, but it is not
in this machine's TeX bundle, so the build falls back. Body text, headings and
captions are unaffected. If you want Times-matched math, install `tex-gyre-math`
and the existing `\IfFontExistsTF` check will pick it up with no edit.

## Regenerating

```bash
python scripts/make_ieee_access.py   # main/main_paper_2col.tex -> access_paper.tex
tectonic access_paper.tex
```

Edit `paper/paper_journal_v2.tex` (the source of truth) and re-run the chain,
rather than editing `access_paper.tex`, which is generated and will be
overwritten.
