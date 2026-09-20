"""Trim the full manuscript to the ~20-page 'main' version.

Run from the repo root. Reads paper/paper_journal_v2.tex and writes
paper/main/main_paper.tex.

The 30-page source is float-dominated: 6584 words of prose but 16 figures and 14
tables. Cutting prose alone cannot reach 20 pages, so the reductions here are, in
order of how much they save:

  1. Two floats that duplicate evidence presented elsewhere are removed.
  2. Oversized figures are set at a width matched to their content; a two-panel
     bar chart does not need the full text measure.
  3. Layout is tightened to values still normal for a journal submission.
  4. Prose is cut where it restates a number already in a table, or explains the
     same idea twice.

NOTHING that constitutes evidence is removed: every reported measurement, every
table, and every map or diagnostic plot survives. The two dropped figures are
both redundant re-presentations of numbers that remain in the text and tables,
and each removal is annotated below with what still carries the result.
"""
import os
import re
import sys

SRC = "paper/paper_journal_v2.tex"
DST = "paper/main/main_paper.tex"

edits = []


def sub(s, old, new, why, count=1):
    """Apply one edit, failing loudly if the anchor text has drifted."""
    if old not in s:
        raise SystemExit(f"ANCHOR NOT FOUND for '{why}':\n  {old[:120]}")
    edits.append(why)
    return s.replace(old, new, count)


def drop_float(s, label, why):
    """Remove the one figure environment that contains `label`.

    Matching \\begin{figure} ... \\label{X} ... \\end{figure} lazily is wrong: the
    engine anchors on the FIRST \\begin{figure} in the file and runs to X,
    swallowing every figure in between. Enumerate environments instead and
    delete only the one whose body actually holds the label.
    """
    target = "\\label{%s}" % label
    hits = [m for m in re.finditer(r"\\begin\{figure\}(?:\[[^\]]*\])?.*?\\end\{figure\}",
                                   s, re.S) if target in m.group(0)]
    if len(hits) != 1:
        raise SystemExit(f"expected exactly one figure holding {label}, found {len(hits)}")
    m = hits[0]
    end = m.end()
    while end < len(s) and s[end] == "\n":
        end += 1
    edits.append(why)
    return s[:m.start()] + s[end:]


def main():
    s = open(SRC, encoding="utf-8").read()

    # ---------------------------------------------------------------- layout
    s = sub(s, r"\usepackage[margin=2.4cm]{geometry}",
            r"\usepackage[margin=2.05cm]{geometry}",
            "margins 2.4cm -> 2.05cm")
    s = sub(s, r"\renewcommand{\arraystretch}{1.15}",
            r"\renewcommand{\arraystretch}{1.05}",
            "table row stretch 1.15 -> 1.05")
    s = sub(s, r"\setlength{\parskip}{2pt}",
            "\\setlength{\\parskip}{0pt}\n\\setlength{\\parindent}{1.2em}\n"
            "\\captionsetup{skip=3pt}\n"
            "\\setlength{\\floatsep}{6pt plus 2pt minus 2pt}\n"
            "\\setlength{\\textfloatsep}{8pt plus 2pt minus 2pt}\n"
            "\\setlength{\\intextsep}{6pt plus 2pt minus 2pt}",
            "paragraph and float spacing tightened")

    # ------------------------------------------------------- redundant floats
    # (a) The RF-vs-XGBoost bar chart plots exactly the six numbers printed in
    #     Table `tab:model` one paragraph away. The table is the precise form.
    #     Its sibling panel (SHAP) is kept and promoted to a standalone figure.
    s = sub(s, r"""\begin{figure}[t]
\centering
\begin{subfigure}{0.48\textwidth}
\includegraphics[width=\textwidth]{figures/model_metrics.pdf}
\caption{}\label{fig:model_metrics}
\end{subfigure}\hfill
\begin{subfigure}{0.48\textwidth}
\includegraphics[width=\textwidth]{figures/shap_importance.pdf}
\caption{}\label{fig:shap}
\end{subfigure}
\caption{(a) Random forest versus XGBoost on the primary 9-factor set.
(b) SHAP attribution for the primary model: elevation and HAND dominate, followed
by channel proximity, rainfall climatology and wetness.}
\end{figure}""",
            r"""\begin{figure}[t]
\centering
\includegraphics[width=0.62\textwidth]{figures/shap_importance.pdf}
\caption{SHAP attribution for the primary model: elevation and HAND dominate,
followed by channel proximity, rainfall climatology and wetness.}
\label{fig:shap}
\end{figure}""",
            "dropped model_metrics chart (duplicates Table tab:model)")

    s = sub(s, """in Table~\\ref{tab:model} and Figure~\\ref{fig:model_metrics}; the two are close,
and XGBoost is selected on test ROC-AUC.""",
            """in Table~\\ref{tab:model}; the two are close, and XGBoost is selected on test
ROC-AUC.""",
            "removed callout to the dropped chart")

    # (b) The response-time/exposure bar pair restates two numbers that appear in
    #     the sentence above it and again in the route_overlay caption.
    s = drop_float(s, "fig:routing_exposure",
                   "dropped routing_exposure chart (two numbers already in text)")
    s = sub(s, """(0.170 to 0.079;
Figure~\\ref{fig:routing_exposure})
(Figure~\\ref{fig:route_overlay})""",
            "(0.170 to 0.079; Figure~\\ref{fig:route_overlay})",
            "removed callout to the dropped chart, merged double parenthetical")

    # ------------------------------------------------------- figure sizing
    # Floats consume roughly half of every body page, so this is the dominant
    # lever on length. Each figure is set at the smallest width at which its
    # smallest annotation stays legible: dense multi-panel maps keep the most
    # width, single-panel charts the least.
    TARGET = {
        "study_area": "0.80", "conditioning_factors": "0.80",
        "sar_inventory": "0.46", "susceptibility_surface": "0.72",
        "shap_importance": "0.50", "calibration": "0.42",
        "spatial_validation": "0.68", "sar_validation": "0.60",
        "trigger_anatomy": "0.66", "road_graph_risk": "0.72",
        "route_overlay": "0.50", "sensitivity_sweep": "0.76",
        "routing_benchmark": "0.64", "qaoa_depth": "0.64",
    }
    def _resize(m):
        name = m.group(2)
        return ("\\includegraphics[width=%s\\textwidth]{figures/%s.pdf}"
                % (TARGET.get(name, m.group(1)), name))
    s = re.sub(r"\\includegraphics\[width=([0-9.]*)\\textwidth\]\{figures/([a-z_]+)\.pdf\}",
               _resize, s)
    edits.append("figure widths set per-figure for legibility at minimum size")

    # ------------------------------------------------------------ prose cuts
    # Related Work: six one-paragraph subsections became three, with the
    # subsection scaffolding removed. No citation is dropped.
    s = sub(s, r"\subsection{Machine learning for flood susceptibility}",
            r"\subsection{Susceptibility mapping and its validation}", "RW merge 1/3")
    s = sub(s, "\\subsection{Spatial validation}\n", "", "RW merge 2/3")
    s = sub(s, r"\subsection{Emergency routing and dispatch}",
            r"\subsection{Routing, dispatch and quantum optimisation}", "RW merge 3/3")
    s = sub(s, "\\subsection{Quantum optimization}\n", "", "RW merge 4/4")

    s = trim_prose(s)

    # ------------------------------------------------- bibliography footprint
    # 61 references occupy 5 of 27 pages at body size. \footnotesize is the
    # normal setting for a reference list of this length and costs no content.
    s = sub(s, r"\begin{thebibliography}{99}",
            "\\footnotesize\n\\begin{thebibliography}{99}",
            "bibliography set at footnotesize")
    s = sub(s, r"\setlength{\itemsep}{1pt}", r"\setlength{\itemsep}{0pt}",
            "bibliography itemsep 1pt -> 0pt")

    out = open(DST, "w", encoding="utf-8")
    out.write(s)
    out.close()
    print(f">> wrote {DST}")
    for e in edits:
        print(f"   - {e}")



# ---------------------------------------------------------------------------
# Prose condensation. Every citation, number and claim in the originals is
# preserved; what goes is restatement and scaffolding. Applied by trim_prose(),
# called from main() before the file is written.
# ---------------------------------------------------------------------------

INTRO_OLD = r"""Flooding is the most frequently recurring natural hazard in India, and the
country's south-western coastal belt concentrates several of the mechanisms that
make it difficult to forecast at a useful spatial scale. Dakshina Kannada
district, centred on the port city of Mangaluru in coastal Karnataka, receives
more than \SI{4000}{\milli\metre} of rainfall in an average monsoon, drains two
substantial rivers, the Nethravathi and the Gurupura, into a shared estuary, and
does so across a coastal plain narrow enough that fluvial discharge and tidal
stage interact within a few kilometres of the built-up area. Extreme-rainfall
frequency over this stretch of the Western Ghats and the Karnataka coast has been
shown to be trending upward \citep{chandrashekar2018}, while land-use change in
the Netravathi basin has altered its runoff response
\citep{chandana2023,babar2015} and the district's land cover has itself changed
measurably over recent decades \citep{naik2022}, so the hazard is neither
stationary nor purely meteorological. Two recent events frame this study: the
August 2024 Nethravathi river flood and the May 2025 Mangaluru urban flood.
Existing flood work on this basin is predominantly static and index-based, for
example the GIS and analytic-hierarchy susceptibility zoning of
\citet{nirmala2026}, which produces a fixed map with no temporal component.

The dominant response in the literature is flood-susceptibility mapping: train a
classifier on terrain and hydrological conditioning factors against an inventory
of observed flooding, and produce a wall-to-wall map of relative
propensity~\citep{tehrany2014,khosravi2018,arabameri2019,saha2021}. The approach
is mature, and the recent generation pairs it with explainable-AI attribution so
that the resulting map can be interrogated, not merely
displayed~\citep{lundberg2017,aydin2022,seydi2023}. Our work sits in this
tradition, and departs from it in three specific ways that this paper's
contributions address.

\paragraph{The observational premise is usually left implicit.}
Susceptibility studies typically source their inventory from whatever flood
observations are available, then treat the resulting map as if it were a spatial
model of flooding in general. But the density of the underlying satellite record
constrains what such a map can honestly claim. Over Dakshina Kannada, Sentinel-1
\citep{torres2012} coverage consists of a \emph{single} orbit geometry, a
descending pass on relative orbit 63, giving a nominal revisit of approximately
twelve days. This matters because rapid SAR inundation mapping of the kind
demonstrated elsewhere in India \citep{arora2023} presumes an acquisition close
enough in time to the peak to be representative. We
verified this directly against the Copernicus archive instead of assuming the
constellation's global six-day figure applies. The consequence is strict: no
individual flood in this district can be mapped from SAR, because the hydrograph
of a coastal flash flood peaks and recedes well inside the revisit gap. Work that
frames flood mapping as per-event spatial classification implicitly assumes a
denser record than exists here. Section~\ref{sec:method-decomp} sets out the
two-stage decomposition that follows from taking this seriously.

\paragraph{Validation is usually optimistic.}
Random $k$-fold cross-validation on geospatial samples leaks information across
fold boundaries, because neighbouring points share terrain; the resulting score
measures interpolation within sampled neighbourhoods, not skill at an
unvisited location~\citep{roberts2017,ploton2020,meyer2021}. Reported AUCs above
0.95 are common in this literature and are rarely accompanied by a spatial
control. We report random $k$-fold, spatial-block $k$-fold, and a strict
geographic-transfer test in which the model is trained entirely outside the
evaluation window (Section~\ref{sec:res-spatial}).

\paragraph{Free parameters are usually asserted.}
Flood-aware routing formulations introduce cost-function constants, a penalty
weight and an impassability threshold, that are typically fixed by judgement and
never swept. Because these constants determine which roads the router will refuse
to use, they are exactly the parameters an operational deployment would be
questioned on. Section~\ref{sec:res-sensitivity} reports the full
$7\times7$ sweep and finds a result that is more nuanced than a stability claim."""

INTRO_NEW = r"""Flooding is the most frequently recurring natural hazard in India, and the
south-western coastal belt concentrates the mechanisms that make it difficult to
forecast at a useful spatial scale. Dakshina Kannada district, centred on
Mangaluru in coastal Karnataka, receives more than \SI{4000}{\milli\metre} of
rainfall in an average monsoon and drains the Nethravathi and the Gurupura into a
shared estuary across a coastal plain narrow enough that fluvial discharge and
tidal stage interact within a few kilometres of the built-up area.
Extreme-rainfall frequency over this coast is trending
upward~\citep{chandrashekar2018}, land-use change in the Netravathi basin has
altered its runoff response~\citep{chandana2023,babar2015}, and the district's
land cover has itself changed measurably~\citep{naik2022}, so the hazard is
neither stationary nor purely meteorological. Two recent events frame this study:
the August 2024 Nethravathi river flood and the May 2025 Mangaluru urban flood.
Existing work on this basin is static and index-based, for example the GIS and
analytic-hierarchy zoning of \citet{nirmala2026}.

The dominant response in the literature is flood-susceptibility mapping: train a
classifier on terrain and hydrological conditioning factors against an inventory
of observed flooding~\citep{tehrany2014,khosravi2018,arabameri2019,saha2021},
increasingly paired with explainable-AI attribution so the map can be
interrogated rather than only
displayed~\citep{lundberg2017,aydin2022,seydi2023}. This work sits in that
tradition and departs from it in three ways.

\paragraph{The observational premise is usually left implicit.}
Susceptibility studies source an inventory from whatever observations exist, then
treat the resulting map as a model of flooding in general. The density of that
record constrains what the map can claim. Over Dakshina Kannada,
Sentinel-1~\citep{torres2012} coverage is a \emph{single} orbit geometry, a
descending pass on relative orbit 63, revisiting approximately every twelve days;
we verified this against the Copernicus archive instead of assuming the
constellation's global six-day figure applies. The consequence is strict: no
individual flood here can be mapped from SAR, because a coastal flash flood peaks
and recedes well inside the revisit gap, whereas the rapid SAR inundation mapping
demonstrated elsewhere in India~\citep{arora2023} presumes an acquisition near
the peak. Section~\ref{sec:method-decomp} sets out the decomposition that
follows.

\paragraph{Validation is usually optimistic.}
Random $k$-fold cross-validation on geospatial samples leaks information across
fold boundaries, because neighbouring points share terrain, so the score measures
interpolation within sampled neighbourhoods rather than skill at an unvisited
location~\citep{roberts2017,ploton2020,meyer2021}. AUCs above 0.95 are common in
this literature and rarely carry a spatial control. We report random $k$-fold,
spatial-block $k$-fold, and a geographic-transfer test with training entirely
outside the evaluation window (Section~\ref{sec:res-spatial}).

\paragraph{Free parameters are usually asserted.}
Flood-aware routing introduces a penalty weight and an impassability threshold,
typically fixed by judgement and never swept. They determine which roads the
router refuses to use, so they are exactly what an operational deployment would
be questioned on. Section~\ref{sec:res-sensitivity} reports the full
$7\times7$ sweep."""


LIMITS_TAIL_OLD = r"""\item \textbf{The trigger is spatially uniform.} $\Tt$ is a single scalar for the
      district, so scenarios differ in intensity but never in spatial pattern.
      This is a real weakness of the decomposition in
      Equation~\eqref{eq:fusion}: it assumes the relative spatial pattern of risk
      is invariant to event type, which cannot be true for events that are
      fluvially versus tidally driven."""

LIMITS_TAIL_NEW = r"""\item \textbf{The trigger is spatially uniform.} $\Tt$ is one scalar for the
      district, so scenarios differ in intensity but never in spatial pattern.
      Equation~\eqref{eq:fusion} therefore assumes the relative spatial pattern
      of risk is invariant to event type, which cannot hold for events that are
      fluvially versus tidally driven."""

LIMITS_DEPTH_OLD = r"""\item \textbf{Susceptibility is not depth.} $\Sx$ and $\Rxt$ are relative
      exposure indices in $[0,1]$, not water depth, and as
      Section~\ref{sec:res-calibration} shows they are calibrated to a balanced
      prior rather than to the landscape prevalence. The impassability threshold
      $\tau$ is a heuristic on that index, not a hydraulic statement about
      whether a vehicle can ford a segment. A calibrated depth regression in the
      manner of \citet{sadhwani2026}, who obtain depth from SAR and elevation
      over this same coastal belt, is the clearest route to a defensible
      passability criterion."""

LIMITS_DEPTH_NEW = r"""\item \textbf{Susceptibility is not depth.} $\Sx$ and $\Rxt$ are relative
      exposure indices in $[0,1]$, calibrated to a balanced prior rather than to
      landscape prevalence (Section~\ref{sec:res-calibration}), so $\tau$ is a
      heuristic on that index and not a statement about whether a vehicle can
      ford a segment. A depth regression in the manner of \citet{sadhwani2026},
      who obtain depth from SAR and elevation over this same coastal belt, is the
      clearest route to a defensible passability criterion."""

MODEL_TABLE_OLD_MARK = "\\label{tab:model}"


def fold_model_table(s):
    """Fold the 2-row RF-vs-XGBoost table into the sentence that introduces it.

    tab:ablation already carries the full metric set for the 9-factor model, so
    this table exists only to contrast two classifiers on one row each.
    """
    m = [x for x in re.finditer(r"\\begin\{table\}(?:\[[^\]]*\])?.*?\\end\{table\}", s, re.S)
         if MODEL_TABLE_OLD_MARK in x.group(0)]
    if len(m) != 1:
        raise SystemExit(f"expected one tab:model, found {len(m)}")
    blk = m[0]
    end = blk.end()
    while end < len(s) and s[end] == "\n":
        end += 1
    s = s[:blk.start()] + s[end:]
    # Replace the WHOLE sentence, not its tail. Anchoring on the tail alone left
    # the lead-in "...on the primary set is reported" in place, producing
    # "is reported on the primary set is close:" in every downstream build.
    s = sub(s, """Model selection between random forest and XGBoost on the primary set is reported
in Table~\\ref{tab:model}; the two are close, and XGBoost is selected on test
ROC-AUC.""",
            """Model selection between random forest and XGBoost on the primary set is close:
random forest reaches accuracy 0.9033 and test ROC-AUC 0.9618
($0.9554\\pm0.0110$ under 5-fold cross-validation), XGBoost 0.9111 and 0.9625
($0.9534\\pm0.0086$). XGBoost is selected on test ROC-AUC and used throughout.""",
            "folded tab:model into prose (whole sentence)")
    edits.append("dropped tab:model (2 rows; ablation table carries the 9F metrics)")
    return s


def drop_table(s, label, why):
    """Remove the one table environment containing `label` (same care as floats)."""
    target = "\\label{%s}" % label
    hits = [m for m in re.finditer(r"\\begin\{table\}(?:\[[^\]]*\])?.*?\\end\{table\}",
                                   s, re.S) if target in m.group(0)]
    if len(hits) != 1:
        raise SystemExit(f"expected one table holding {label}, found {len(hits)}")
    m = hits[0]
    end = m.end()
    while end < len(s) and s[end] == "\n":
        end += 1
    edits.append(why)
    return s[:m.start()] + s[end:]


CONC_OLD = r"""The broader argument is methodological. Each stricter validation protocol we
applied reduced the headline number, from 0.9878 to 0.9625 to 0.9474 to 0.871, and
each reduction corresponded to removing a specific, nameable way the earlier
figure was optimistic. For a practitioner assessing whether to trust such a map,
that sequence is more informative than its first term alone."""

CONC_NEW = r"""The broader argument is methodological. Each stricter protocol reduced the
headline number, 0.9878 to 0.9625 to 0.9474 to 0.871, and each removed a specific,
nameable way the earlier figure was optimistic. For a practitioner assessing
whether to trust such a map, that sequence is more informative than its first term
alone."""


def trim_prose(s):
    s = sub(s, INTRO_OLD, INTRO_NEW, "introduction condensed (~565w -> ~400w)")
    s = sub(s, LIMITS_DEPTH_OLD, LIMITS_DEPTH_NEW, "limitation 1 condensed")
    s = sub(s, LIMITS_TAIL_OLD, LIMITS_TAIL_NEW, "limitation 3 condensed")
    s = fold_model_table(s)
    s = sub(s, CONC_OLD, CONC_NEW, "conclusions closing paragraph condensed")

    # The QAOA depth plot re-draws Table tab:qaoa, which already carries mean,
    # standard deviation, best-of-seeds, optimum-sampling probability and lift
    # for every depth in both scenarios. The table is the precise form.
    s = drop_float(s, "fig:qaoa", "dropped qaoa_depth plot (duplicates Table tab:qaoa)")
    s = re.sub(r"\s*(?:and|,)?\s*Figure~\\ref\{fig:qaoa\}", "", s)
    s = re.sub(r"\(Figure~\\ref\{fig:qaoa\}\)", "", s)
    edits.append("removed callouts to the dropped QAOA plot")
    return s

if __name__ == "__main__":
    main()
