"""Typeset the manuscript to the IEEE Access 2024 template specification.

Every dimension and font below was extracted from Access-Template-2024.docx by
unzipping it and reading word/document.xml and word/styles.xml, not from memory
or from a description of the template. The measurements, in twips (1440 = 1 in):

  page          w=11520 h=15660          ->  8.000 x 10.875 in  (NOT Letter/A4)
  margins       top=1300 bottom=1040     ->  0.903 / 0.722 in
                left=740 right=740       ->  0.514 in
  first page    top=1280                 ->  0.889 in
  columns       num=2 space=400          ->  0.278 in gutter
  header/footer header=360 footer=640    ->  0.250 / 0.444 in

Resulting text block: 6.972 in wide, 9.250 in tall, columns 3.347 in each.

Styles (w:sz is half-points):

  Normal/base   Times New Roman
  PARA          10 pt, justified, w:line=240 lineRule=exact -> 12 pt fixed leading
  PaperTitle    Helvetica 22 pt bold, colour #00629B
  AU            Helvetica 10 pt bold, right indent 1380 tw
  PI            7.5 pt, right indent 1600 tw, 9 pt fixed leading
  Abstract      10 pt justified, right indent 1380 tw
  IT            10 pt, right indent 1380 tw
  H1            Helvetica 9 pt bold, colour #00629B
  H2            Helvetica 9 pt bold italic, colour #58595B
  H3            Helvetica 9 pt caps, colour #58595B
  FigCaption    Helvetica 7 pt bold
  TableCaption  Helvetica 7 pt bold
  TableTitle    8 pt small caps, centred
  References    8 pt justified, left indent 360 tw
  Equation      10 pt, left indent 1600 tw

The run-in words ABSTRACT and INDEX TERMS use the H5CharChar character style,
which is Helvetica in #00629B.

Tectonic runs XeTeX, so fontspec loads the genuine macOS Times New Roman and
Helvetica rather than metric substitutes.

Reads  paper/main/main_paper_2col.tex   (content only)
Writes paper/ieee_access/access_paper.tex
"""
import os
import re

import sys

SRC = "paper/main/main_paper_2col.tex"
# Output directory is selectable so a new revision never overwrites the one
# already handed over. Pass a directory as argv[1]; default is the v3 build.
OUT_DIR = sys.argv[1] if len(sys.argv) > 1 else "paper/ieee_access_v3"
DST = os.path.join(OUT_DIR, "access_paper.tex")

# Template: avoid abbreviations in the title, and IEEE sets American English.
# "SAR" is therefore spelled out and "Modelling" becomes "Modeling".
TITLE = (r"Spatiotemporal Flood Risk Modeling Under a Single-Orbit Synthetic "
         r"Aperture Radar Constraint: Confound-Controlled Susceptibility and "
         r"Flood-Aware Emergency Routing")

# Placeholder author block. Names only, as requested; affiliation, membership
# grades, ORCIDs, funding and the corresponding e-mail are left as clearly
# marked placeholders so nothing fabricated reaches a submission.
# Access prints the membership grade beside the name and does not print "Dr." in
# the author line; the doctorate belongs in the biography. The grade below is a
# placeholder because it was not supplied and must not be guessed.
AUTHORS = r"""\textbf{MUSTAFA BASTHIKODI}\textsuperscript{1}, ([MEMBERSHIP GRADE], IEEE),
\textbf{KRISH P. CHOWTA}\textsuperscript{1},
\textbf{ADVAITH SHAJEENDRAN}\textsuperscript{1},
\textbf{DHRITHI K. S.}\textsuperscript{1},
and \textbf{GAMAN A. RAI}\textsuperscript{1}"""

AFFIL = r"""\textsuperscript{1}Department of Computer Science and Engineering, Sahyadri College of Engineering and Management, Adyar, Mangaluru 575007, Karnataka, India

Corresponding author: Mustafa Basthikodi (e-mail: [INSTITUTIONAL EMAIL])."""

ABSTRACT = (
    "Coastal districts of southwestern India flood every monsoon, yet the "
    "satellite record available for mapping those floods is thinner than the "
    "modeling literature usually assumes. Over Dakshina Kannada, Karnataka, "
    "exactly one Sentinel-1 orbit covers the district on a strict twelve-day "
    "cycle, so no individual flood there can be mapped from radar imagery: a "
    "flash flood rises and recedes inside the revisit gap. We treat that "
    "constraint as a design premise and decompose risk into a static "
    "susceptibility surface, trained on a multi-temporal radar flood-frequency "
    "inventory, and a dynamic rainfall trigger. A remote-sensing confound is "
    "identified and removed: a model given land cover and a vegetation index "
    "reaches an area under the curve of 0.9878, but attribution analysis shows "
    "it has learned that closed canopy hides water from radar, not flood "
    "physics. The terrain-and-rainfall model scores 0.9625 on a random split, "
    "0.9474 under spatial-block cross-validation, and 0.871 transferring to a "
    "held-out city window never seen in training, where its highest-"
    "susceptibility tenth contains 49.5 percent of all observed flooding. The "
    "calibrated score is shown to be tied to the balanced training prior and "
    "must not be read as a flood probability without correction. Over a road "
    "graph of 28,529 edges, flood-aware routing cuts mean route exposure by "
    "33.0 percent for a 3.8-minute detour, and a survivorship-corrected "
    "parameter sweep separates an immaterial penalty weight from an "
    "impassability threshold that governs connectivity. A quantum dispatch "
    "layer is reported only as a feasibility check, with no advantage claimed.")

FOOTNOTE = (r"This work was supported by [FUNDING SOURCE / grant number, or "
            r"delete this sentence if the work received no external funding].")

PREAMBLE = r"""%%=============================================================================
%%  IEEE ACCESS submission format.
%%
%%  Build:  tectonic access_paper.tex        (tectonic runs XeTeX -> fontspec)
%%
%%  Layout reproduces Access-Template-2024.docx exactly. Every dimension here was
%%  read out of that .docx (word/document.xml, word/styles.xml); see
%%  scripts/make_ieee_access.py for the extracted values in twips.
%%=============================================================================
\documentclass[10pt,twocolumn]{article}

%% ---- page geometry: 8.000 x 10.875 in, the Access trim size -----------------
\usepackage[
  paperwidth=8.0in, paperheight=10.875in,
  top=0.903in, bottom=0.722in, left=0.514in, right=0.514in,
  headsep=12pt, footskip=0.444in,
  columnsep=0.278in
]{geometry}

%% ---- genuine template fonts via XeTeX --------------------------------------
\usepackage{amsmath}
\usepackage{fontspec}
\setmainfont{Times New Roman}
\newfontfamily\helv{Helvetica}[Scale=MatchLowercase]
%% Times-compatible math to sit with Times New Roman text. TeX Gyre Termes Math
%% is the free Times math companion; if it is unavailable the fallback below
%% keeps the default math font rather than failing the build.
\usepackage{unicode-math}
%% STIX Two Math is the Times-metric math companion shipped with macOS; Latin
%% Modern Math lacks glyphs used here (e.g. U+2216 set minus) and drops them.
\IfFontExistsTF{TeX Gyre Termes Math}
  {\setmathfont{TeX Gyre Termes Math}}
  {\IfFontExistsTF{STIX Two Math}
    {\setmathfont{STIX Two Math}}
    {\IfFontExistsTF{Latin Modern Math}{\setmathfont{Latin Modern Math}}{}}}

%% amssymb must NOT be loaded alongside unicode-math: both define \eth and the
%% duplicate definition aborts the build. unicode-math supplies those symbols.
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{multirow}
\usepackage{array}
\usepackage[table]{xcolor}
\usepackage{tikz}
\usetikzlibrary{positioning,arrows.meta,fit,backgrounds}
\usepackage{caption}
\usepackage{subcaption}
\usepackage[numbers,sort&compress]{natbib}
\usepackage{siunitx}
\sisetup{detect-all,group-separator={,}}
%% \MakeUppercase breaks on headings containing math (e.g. "A$^\ast$").
%% textcase's \MakeTextUppercase leaves math mode untouched.
\usepackage{textcase}
\usepackage{titlesec}
\usepackage{balance}
\usepackage[hidelinks]{hyperref}

%% ---- Access palette ---------------------------------------------------------
\definecolor{accessblue}{HTML}{00629B}
\definecolor{accessgrey}{HTML}{58595B}

%% ---- body text: 10 pt on exactly 12 pt, justified ---------------------------
\renewcommand{\normalsize}{\fontsize{10}{12}\selectfont}
\normalsize
\setlength{\parindent}{10pt}      %% PARAIndent firstLine=200tw = 10pt
\setlength{\parskip}{0pt}
\frenchspacing

%% ---- headings ---------------------------------------------------------------
%% H1  Helvetica 9pt bold, #00629B, caps, roman numeral
%% "Tables should be numbered with Roman Numerals." Figures stay Arabic.
\renewcommand{\thetable}{\Roman{table}}
\renewcommand{\thesection}{\Roman{section}}
%% IEEE writes a cross-reference as "Section V-H" while the heading itself
%% shows only "H.". \thesubsection feeds BOTH \ref and the heading, so it carries
%% the compound form and titlesec below prints just the letter. Without this,
%% every subsection reference renders as a bare "Section H", which is ambiguous
%% because the letters restart in each section.
\renewcommand{\thesubsection}{\thesection-\Alph{subsection}}
\renewcommand{\thesubsubsection}{\arabic{subsubsection})}
\titleformat{\section}{\helv\fontsize{9}{11}\bfseries\color{accessblue}\MakeTextUppercase}
            {\thesection.}{0.5em}{}
\titlespacing*{\section}{0pt}{12pt}{4pt}
%% H2  Helvetica 9pt bold italic, #58595B
\titleformat{\subsection}{\helv\fontsize{9}{11}\bfseries\itshape\color{accessgrey}\MakeTextUppercase}
            {\Alph{subsection}.}{0.5em}{}
\titlespacing*{\subsection}{0pt}{13pt}{3pt}
%% H3  Helvetica 9pt, #58595B
\titleformat{\subsubsection}{\helv\fontsize{9}{11}\color{accessgrey}}
            {\thesubsubsection}{0.5em}{}
\titlespacing*{\subsubsection}{0pt}{4pt}{2pt}
\titleformat{\paragraph}[runin]{\itshape}{}{0pt}{}[:]

%% ---- captions: Helvetica 7pt bold, "FIGURE n." / "TABLE n." -----------------
\captionsetup{font={rm,footnotesize},labelfont=bf,justification=raggedright,
              singlelinecheck=false,skip=4pt}
\captionsetup[figure]{name=FIGURE,labelsep=period,
  font={stretch=1.0},labelfont={bf},
  textfont={},format=plain}
\renewcommand{\figurename}{FIGURE}
\renewcommand{\tablename}{TABLE}
\DeclareCaptionFont{acccap}{\helv\fontsize{7}{8.5}\selectfont}
\captionsetup[figure]{font=acccap,labelfont={acccap,bf}}
\captionsetup[table]{font=acccap,labelfont={acccap,bf},position=top}

%% ---- floats -----------------------------------------------------------------
\setlength{\floatsep}{8pt plus 2pt minus 2pt}
\setlength{\textfloatsep}{10pt plus 2pt minus 2pt}
\setlength{\dblfloatsep}{8pt plus 2pt minus 2pt}
\setlength{\dbltextfloatsep}{10pt plus 2pt minus 2pt}
\renewcommand{\arraystretch}{1.05}

%% ---- references: 8 pt --------------------------------------------------------
\renewcommand{\bibfont}{\fontsize{8}{9.5}\selectfont}

\newcommand{\Sx}{S(\mathbf{x})}
\newcommand{\Tt}{T(t)}
\newcommand{\Rxt}{R(\mathbf{x},t)}

%% ---- header and footer, as the template actually sets them ------------------
%% The template carries the IEEE Access logo at the top right with a rule under
%% it, and NO author running head: that is added by IEEE at production. The
%% footer is Helvetica 6 pt, "VOLUME XX, 2017" left and the page number right.
%% Logo assets are the ones shipped inside the template (word/media), printed at
%% their template size: 383 px at 299 ppi = 1.281 in on page one, 322 px on the
%% rest.
\usepackage{fancyhdr}
\pagestyle{fancy}
\fancyhf{}
\renewcommand{\headrulewidth}{0.5pt}
\renewcommand{\footrulewidth}{0pt}
\fancyhead[R]{\includegraphics[width=1.077in]{figures/ieee_access_logo.jpeg}}
\fancyfoot[L]{\helv\fontsize{6}{8}\selectfont VOLUME XX, 2017}
\fancyfoot[R]{\helv\fontsize{6}{8}\selectfont\thepage}
\setlength{\headheight}{22pt}

\fancypagestyle{accessfirst}{%
  \fancyhf{}%
  \renewcommand{\headrulewidth}{0.5pt}%
  \fancyhead[R]{\includegraphics[width=1.281in]{figures/ieee_access_logo_p1.jpeg}}%
  \fancyfoot[L]{\helv\fontsize{6}{8}\selectfont VOLUME XX, 2017}%
  \fancyfoot[R]{\helv\fontsize{6}{8}\selectfont\thepage}%
}

\begin{document}
"""


# Author biographies. IEEE Access papers carry these (style AUBios: 8 pt,
# justified) with a 1.00 x 1.25 in photograph per author. Left as placeholders
# with the photo box drawn to the exact printed size, so nothing is invented.
BIOS = r"""
\vspace{10pt}
{\helv\fontsize{9}{11}\bfseries\color{accessblue}\MakeTextUppercase{Author Biographies}\par}
\vspace{4pt}
{\fontsize{8}{9.5}\selectfont

\noindent\begin{minipage}[t]{1.0in}\vspace{0pt}%%
\fbox{\parbox[c][1.25in][c]{0.97in}{\centering\tiny PHOTO\\1.00 x 1.25 in}}
\end{minipage}\hfill
\begin{minipage}[t]{\dimexpr\columnwidth-1.1in\relax}\vspace{0pt}%%
\textbf{MUSTAFA BASTHIKODI} [AUTHOR TO SUPPLY: degree(s) with field, awarding institution and year; current position or programme; research interests; IEEE membership grade if any. Delete these brackets.]
\end{minipage}

\vspace{6pt}

\noindent\begin{minipage}[t]{1.0in}\vspace{0pt}%%
\fbox{\parbox[c][1.25in][c]{0.97in}{\centering\tiny PHOTO\\1.00 x 1.25 in}}
\end{minipage}\hfill
\begin{minipage}[t]{\dimexpr\columnwidth-1.1in\relax}\vspace{0pt}%%
\textbf{KRISH P. CHOWTA} [AUTHOR TO SUPPLY: degree(s) with field, awarding institution and year; current position or programme; research interests; IEEE membership grade if any. Delete these brackets.]
\end{minipage}

\vspace{8pt}
\noindent\begin{minipage}[t]{1.0in}\vspace{0pt}%%
\fbox{\parbox[c][1.25in][c]{0.97in}{\centering\tiny PHOTO\\1.00 x 1.25 in}}
\end{minipage}\hfill
\begin{minipage}[t]{\dimexpr\columnwidth-1.1in\relax}\vspace{0pt}%%
\textbf{ADVAITH SHAJEENDRAN} [AUTHOR TO SUPPLY: degree(s) with field, awarding institution and year; current position or programme; research interests; IEEE membership grade if any. Delete these brackets.]
\end{minipage}

\vspace{8pt}
\noindent\begin{minipage}[t]{1.0in}\vspace{0pt}%%
\fbox{\parbox[c][1.25in][c]{0.97in}{\centering\tiny PHOTO\\1.00 x 1.25 in}}
\end{minipage}\hfill
\begin{minipage}[t]{\dimexpr\columnwidth-1.1in\relax}\vspace{0pt}%%
\textbf{DHRITHI K. S.} [AUTHOR TO SUPPLY: degree(s) with field, awarding institution and year; current position or programme; research interests; IEEE membership grade if any. Delete these brackets.]
\end{minipage}

\vspace{8pt}
\noindent\begin{minipage}[t]{1.0in}\vspace{0pt}%%
\fbox{\parbox[c][1.25in][c]{0.97in}{\centering\tiny PHOTO\\1.00 x 1.25 in}}
\end{minipage}\hfill
\begin{minipage}[t]{\dimexpr\columnwidth-1.1in\relax}\vspace{0pt}%%
\textbf{GAMAN A. RAI} [AUTHOR TO SUPPLY: degree(s) with field, awarding institution and year; current position or programme; research interests; IEEE membership grade if any. Delete these brackets.]
\end{minipage}

\vspace{6pt}
\noindent\rule{\columnwidth}{0.4pt}\\
{\fontsize{7}{8.5}\selectfont\itshape VOLUME 12, 2024\hfill}
}
"""


def title_block(abstract, keywords):
    """Full-width title block: Access sets these across both columns."""
    return r"""
\thispagestyle{accessfirst}
\twocolumn[
\begin{@twocolumnfalse}
\vspace*{-2pt}

%% The template prints a publication-date line above the DOI; IEEE fills both.
{\fontsize{7.5}{9}\selectfont
Date of publication xxxx 00, 0000, date of current version xxxx 00, 0000.\par}
{\fontsize{6}{8}\selectfont\itshape
Digital Object Identifier 10.1109/ACCESS.2024.DOI\par}

\vspace{18pt}

{\helv\fontsize{22}{25}\bfseries\color{accessblue}\raggedright
%(title)s\par}

\vspace{12pt}

%% AU: Helvetica 10pt bold, indented 1380tw (0.958in) from the right
\begin{minipage}{\dimexpr\textwidth-0.958in\relax}
{\helv\fontsize{10}{12}\selectfont\raggedright
%(authors)s\par}

\vspace{5pt}

%% PI: 7.5pt on 9pt fixed
{\fontsize{7.5}{9}\selectfont\raggedright
%(affil)s\par}
\end{minipage}

\vspace{10pt}

{\fontsize{7}{9}\selectfont
%(footnote)s\par}

\vspace{12pt}

%% Abstract: 10pt justified, right indent 1380tw, run-in label in Access blue
\begin{minipage}{\dimexpr\textwidth-0.958in\relax}
{\fontsize{10}{12}\selectfont
{\helv\bfseries\color{accessblue}ABSTRACT }%(abstract)s\par}

\vspace{9pt}

{\fontsize{10}{12}\selectfont\raggedright
{\helv\bfseries\color{accessblue}INDEX TERMS }%(keywords)s\par}
\end{minipage}

\vspace{16pt}
\end{@twocolumnfalse}
]
""" % {"title": TITLE, "authors": AUTHORS, "affil": AFFIL,
       "footnote": FOOTNOTE, "abstract": abstract, "keywords": keywords}



def _rx(body, pattern, repl, why, expect=1):
    """Whitespace-tolerant single replacement that fails loudly if it drifts."""
    rx = re.compile(pattern.replace(" ", r"\s+"), re.S)
    n = len(rx.findall(body))
    if n != expect:
        raise SystemExit(f"IEEE-STYLE ANCHOR '{why}': expected {expect} match(es), found {n}")
    return rx.sub(repl.replace("\\", "\\\\"), body, count=expect)


# Standard expansions. Nothing here is invented: each is the accepted long form
# of the acronym as used by the cited source.
ACRONYM_FIXES = [
    (r"the GIS and analytic-hierarchy",
     "the geographic information system (GIS) and analytic-hierarchy", "GIS"),
    (r"can be mapped from SAR, because",
     "can be mapped from synthetic aperture radar (SAR), because", "SAR"),
    (r"A hybrid QUBO/QAOA dispatch layer",
     "A hybrid quadratic unconstrained binary optimization (QUBO) and quantum "
     "approximate optimization algorithm (QAOA) dispatch layer", "QUBO/QAOA"),
    (r"established the SVM-and-frequency-ratio baseline",
     "established the support vector machine (SVM) and frequency-ratio baseline", "SVM"),
    (r"introduced SHAP;",
     "introduced Shapley additive explanations (SHAP);", "SHAP"),
    (r"reached a test ROC-AUC of 0\.9878",
     "reached a test area under the receiver operating characteristic curve "
     "(ROC-AUC) of 0.9878", "ROC-AUC"),
    (r"by COBYLA~\\citep\{powell1994\}",
     "by constrained optimization by linear approximation (COBYLA)"
     "~\\citep{powell1994}", "COBYLA"),
    (r"does not characterise NISQ behaviour",
     "does not characterize noisy intermediate-scale quantum (NISQ) behavior", "NISQ"),
    (r"Collinearity was screened by variance inflation factor,",
     "Collinearity was screened by the variance inflation factor (VIF),", "VIF"),
]

# Acronyms whose first appearance is inside a table are defined in a note under
# that table, which is where a reader meets them.
TABLE_NOTES = [
    (r"tab:study",
     "SRTM: Shuttle Radar Topography Mission; CHIRPS: Climate Hazards group "
     "Infrared Precipitation with Stations; IMD: India Meteorological "
     "Department; FAO GAUL: Food and Agriculture Organization Global "
     "Administrative Unit Layers; HAND: height above nearest drainage.", 3),
    (r"tab:data",
     "GRD: ground range detected; IW: interferometric wide swath; VV/VH: "
     "co-polarized and cross-polarized channels; JRC GSW: Joint Research "
     "Centre Global Surface Water; NDVI: normalized difference vegetation "
     "index; ERA5: fifth-generation ECMWF reanalysis.", 4),
]

# British to American, IEEE house style. Restricted to an explicit list so that
# siunitx macros (\metre) and proper nouns (Ising) are never touched.
SPELLING = [
    ("modelling", "modeling"), ("Modelling", "Modeling"),
    ("modelled", "modeled"), ("Modelled", "Modeled"),
    ("artefact", "artifact"), ("artefacts", "artifacts"),
    ("neighbouring", "neighboring"), ("neighbourhood", "neighborhood"),
    ("neighbourhoods", "neighborhoods"),
    ("labelled", "labeled"), ("normalised", "normalized"),
    ("Normalised", "Normalized"),
    ("characterise", "characterize"), ("characterised", "characterized"),
    ("minimising", "minimizing"), ("behaviour", "behavior"),
    ("coloured", "colored"), ("optimisation", "optimization"),
    ("factorisation", "factorization"), ("standardised", "standardized"),
    ("formalised", "formalized"), ("recognised", "recognized"),
    ("summarises", "summarizes"), ("optimised", "optimized"),
    ("generalises", "generalizes"), ("maximise", "maximize"),
    ("realised", "realized"), ("Vectorising", "Vectorizing"),
    ("favourably", "favorably"), ("optimiser", "optimizer"),
    ("utilise", "utilize"), ("analyse", "analyze"), ("analysed", "analyzed"),
    ("south-western", "southwestern"), ("south-west", "southwest"),
    ("north-western", "northwestern"), ("north-east", "northeast"),
    ("South-west", "Southwest"),
]


def ieee_style(body):
    """Apply the template's written style rules to the body text."""
    for pat, rep, why in ACRONYM_FIXES:
        body = _rx(body, pat, rep, why)

    # Abbreviation notes beneath the tables where the acronyms first appear.
    for label, note, ncol in TABLE_NOTES:
        rx = re.compile(r"(\\label\{" + label + r"\}.*?\\bottomrule\n)", re.S)
        if not rx.search(body):
            raise SystemExit(f"table {label} not found for abbreviation note")
        body = rx.sub(
            r"\1" + "\\\\multicolumn{%d}{@{}l@{}}{\\\\footnotesize %s}\\\\\\\\\n"
            % (ncol, note), body, count=1)

    # Whole-word spelling only, and never inside a LaTeX control sequence.
    for br, am in SPELLING:
        body = re.sub(r"(?<![A-Za-z\\])" + br + r"(?![A-Za-z])", am, body)

    # IEEE: mid-sentence references to an equation are the bare number; only a
    # sentence-initial reference is written out. Three are mid-sentence here.
    for pat, rep in (
        (r"three components of Equation~\\eqref", "three components of~\\eqref"),
        (r"admissibility of Equation~\\eqref", "admissibility of~\\eqref"),
        (r"strongest assumption in Equation~\\eqref", "strongest assumption in~\\eqref"),
    ):
        body = _rx(body, pat, rep, "equation reference " + pat[:28])

    # The quantum layer is a feasibility demonstration, not a contribution: at
    # 3x3 the Hungarian algorithm is exact and immediate. Remove it from the
    # numbered contribution list and state it plainly afterwards instead.
    body = _rx(body,
        r"\\item A hybrid quadratic unconstrained binary optimization \(QUBO\) and quantum "
        r"approximate optimization algorithm \(QAOA\) dispatch layer verified against the exact classical\s*"
        r"optimum, scoped explicitly as a feasibility demonstration\.\s*\\end\{enumerate\}\s*"
        r"Fig\.~\\ref\{fig:architecture\} maps the full pipeline\.",
        "\\end{enumerate}\n\n"
        "Fig.~\\ref{fig:architecture} maps the full pipeline. A hybrid quadratic\n"
        "unconstrained binary optimization (QUBO) and quantum approximate optimization\n"
        "algorithm (QAOA) dispatch layer is also implemented and verified against the\n"
        "exact classical optimum. It is reported in Section~\\ref{sec:res-qaoa} as a\n"
        "feasibility check rather than as a contribution: at the problem size studied\n"
        "here the classical assignment solver is exact and effectively instantaneous,\n"
        "and no quantum advantage is claimed.",
        "quantum demoted out of the contribution list")

    # Section titles: name it for what it is.
    body = body.replace(r"\subsection{Hybrid quantum dispatch}",
                        r"\subsection{Quantum dispatch: formulation}", 1)
    body = body.replace(r"\subsection{Hybrid quantum dispatch}",
                        r"\subsection{Quantum dispatch: a feasibility check}", 1)

    # Template heading is singular.
    body = body.replace(r"\section{Conclusions}", r"\section{Conclusion}")

    # Singular subject: "Table N reports", not "report". The three other
    # "... report" sites have two floats as their subject and are correct.
    body = _rx(body, r"Table~\\ref\{tab:qaoa\} report the depth study",
               "Table~\\ref{tab:qaoa} reports the depth study",
               "verb agreement, tab:qaoa")

    # Multi-panel figures drawn 7 in wide are illegible in a 3.347 in column:
    # at that scale their 8 pt labels set at roughly 3.5 pt. Promote them to the
    # full-width float so they render near their design size.
    #
    # Enumerate figure environments and pick the one that actually holds the
    # label. A lazy \begin{figure}...\label{X}...\end{figure} match anchors on
    # the FIRST figure in the file and swallows every figure up to X.
    for lab, w in (("fig:spatial", None), ("fig:sar_val", None),
                   ("fig:sensitivity", None), ("fig:routing_benchmark", "0.8"),
                   ("fig:route_overlay", "0.62")):
        target = "\\label{%s}" % lab
        hits = [m for m in re.finditer(
            r"\\begin\{figure\}(?:\[[^\]]*\])?.*?\\end\{figure\}", body, re.S)
            if target in m.group(0)]
        if len(hits) != 1:
            raise SystemExit(f"promote {lab}: expected 1 figure, found {len(hits)}")
        m = hits[0]
        blk = m.group(0)
        inner = re.sub(r"^\\begin\{figure\}(?:\[[^\]]*\])?", "", blk)
        inner = re.sub(r"\\end\{figure\}$", "", inner)
        if w:
            inner = inner.replace("width=\\linewidth", "width=%s\\linewidth" % w)
        body = body[:m.start()] + "\\begin{figure*}[!t]" + inner + \
            "\\end{figure*}" + body[m.end():]
    return body



BIB_IEEE = "paper/ieee_access/bibliography_ieee.tex"


def bibliography():
    """Prefer the IEEE-style bibliography if it has been built.

    scripts/ieee_bibliography.py rebuilds every entry from Crossref metadata and
    writes that file. If it is absent the inherited list is used unchanged, so
    the build never silently drops references.
    """
    if os.path.exists(BIB_IEEE):
        return open(BIB_IEEE, encoding="utf-8").read()
    raise SystemExit(f"missing {BIB_IEEE}: run scripts/ieee_bibliography.py first")


def main():
    s = open(SRC, encoding="utf-8").read()

    head, rest = s.split(r"\begin{thebibliography}", 1)
    _, bibbody = rest.split("\n", 1)
    bibbody = bibbody.split(r"\end{thebibliography}")[0]

    body = head.split(r"\maketitle", 1)[1]

    m = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", body, re.S)
    # The template requires 150-250 words, self-contained and WITHOUT
    # abbreviations. The inherited abstract was 314 words and used SAR, NDVI,
    # ROC-AUC, QUBO and QAOA, so it is replaced rather than trimmed.
    abstract = ABSTRACT
    _ = " ".join(m.group(1).split())
    body = body[:m.start()] + body[m.end():]

    k = re.search(r"\\begin\{IEEEkeywords\}(.*?)\\end\{IEEEkeywords\}", body, re.S)
    # Template: "Enter key words or phrases in alphabetical order".
    keywords = ("Emergency dispatch, explainable artificial intelligence, "
                "flood-aware routing, flood susceptibility, spatial "
                "cross-validation, synthetic aperture radar.")
    _ = " ".join(k.group(1).split())
    body = body[:k.start()] + body[k.end():]

    body = body.replace(r"\balance", "")

    # Template: "it is recommended that figures are not sized less than column
    # width". The inherited fractional widths came from a page-count reduction
    # on another build and are restored to full column / full page width here.
    body = re.sub(r"\\includegraphics\[width=[0-9.]*\\linewidth\]",
                  r"\\includegraphics[width=\\linewidth]", body)

    # Template: use "Fig." in text, even starting a sentence; do not abbreviate
    # "Table". Caption labels stay FIGURE / TABLE, which is the Access style.
    body = body.replace("Figures~\\ref", "Figs.~\\ref")
    body = body.replace("Figure~\\ref", "Fig.~\\ref")

    # The single-column source drew a rule under its abstract block. Access has
    # no such rule, and here it lands stranded above the first section heading.
    body = body.replace("\\vspace{4pt}\n\\hrule\n\\vspace{10pt}", "")

    # The Access column (3.347 in) is narrower than IEEEtran's, so two equations
    # that fitted before now overrun. Break each onto a second line.
    body = body.replace(
        r"""\qquad R(e) = S(e)\cdot T,
\label{eq:edgecost}""",
        r"""\\[2pt]
R(e) &= S(e)\cdot T,
\label{eq:edgecost}""").replace(
        r"""\begin{equation}
c(e) \;=\;
\begin{cases}""",
        r"""\begin{align}
c(e) \;&=\;
\begin{cases}""").replace(
        r"""\end{cases}
\\[2pt]
R(e) &= S(e)\cdot T,
\label{eq:edgecost}
\end{equation}""",
        r"""\end{cases} \nonumber\\[2pt]
R(e) &= S(e)\cdot T,
\label{eq:edgecost}
\end{align}""")

    body = body.replace(
        r"""\lvert +\rangle^{\otimes n^2},
\qquad H_B=\sum_j \sigma^x_j,""",
        r"""\lvert +\rangle^{\otimes n^2},
\;\; H_B=\sum_j \sigma^x_j,""")


    # A heading containing math breaks the uppercasing that Access headings need
    # ("Improper alphabetic constant"). Only one heading is affected, and "A*"
    # set as text is the ordinary way to write the algorithm name in a title.
    body = body.replace(r"\subsection{Dijkstra versus A$^\ast$: a multi-query benchmark}",
                        r"\subsection{Dijkstra versus A* : a multi-query benchmark}")


    body = ieee_style(body)

    # IEEEtran's starred full-width floats carry over to article unchanged.
    doc = (PREAMBLE
           + title_block(abstract, keywords)
           + body
           + "\n\\balance\n"
           + "{\\fontsize{8}{9.5}\\selectfont\n"
           + bibliography()
           + "}\n"
           + BIOS
           + "\n\\end{document}\n")

    os.makedirs(os.path.dirname(DST), exist_ok=True)
    open(DST, "w", encoding="utf-8").write(doc)

    nfig = len(re.findall(r"\\begin\{figure", doc))
    ntab = len(re.findall(r"\\begin\{table", doc))
    # Guard: the IEEE bibliography is a separate pre-built file, so a citation
    # added to the manuscript after that file was generated would silently ship
    # as an undefined reference. Fail the build instead.
    _cited = set()
    for _m in re.finditer(r"\\cite[a-zA-Z]*\s*(?:\[[^\]]*\])?\s*\{([^}]+)\}",
                          doc.split(r"\begin{thebibliography}")[0]):
        _cited.update(x.strip() for x in _m.group(1).split(","))
    # must accept both \bibitem{key} and \bibitem[Author(year)]{key}
    _have = set(re.findall(r"\\bibitem(?:\[[^\]]*\])?\{([^}]+)\}", doc))
    _missing = sorted(_cited - _have)
    _unused = sorted(_have - _cited)
    if _missing:
        raise SystemExit(
            "cited but absent from %s: %s\n"
            "Re-run scripts/ieee_bibliography.py, or add the entries by hand."
            % (BIB_IEEE, _missing))
    if _unused:
        raise SystemExit("in %s but never cited: %s" % (BIB_IEEE, _unused))

    # \citet resolves the author name from the \bibitem optional argument. If a
    # bibliography is swapped in without those labels, natbib silently typesets
    # "(author?)" in the running text and the build still succeeds. Checking for
    # "??" does not catch it, because the citation number itself resolves fine.
    if "\\citet" in doc:
        _unlabelled = re.findall(r"\\bibitem\{([^}]+)\}", doc)
        if _unlabelled:
            raise SystemExit(
                "%d \\bibitem entries carry no [Author(year)] label while the body "
                "uses \\citet; natbib would typeset \"(author?)\". First few: %s"
                % (len(_unlabelled), _unlabelled[:5]))

    nref = doc.count("\\bibitem")
    print(f">> wrote {DST}")
    print(f"   {nfig} figures, {ntab} tables, {nref} references")


if __name__ == "__main__":
    main()
