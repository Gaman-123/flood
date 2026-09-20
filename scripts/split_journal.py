"""Split the single-file journal manuscript into two IEEE-format companion papers.

Part I  covers the risk model: SAR inventory under the single-orbit constraint,
        confound-controlled susceptibility, the validation ladder, calibration
        and the temporal trigger.
Part II covers the operational layer: the flood-aware graph, the routing
        benchmark, the cost-function sweep and hybrid quantum dispatch.

The split is done here rather than by hand so it stays reproducible: rerunning
this after an edit to paper_journal_v2.tex regenerates both parts. Section
bodies are lifted verbatim, and only the connective tissue (preamble, abstract,
introduction, conclusions) is authored per part.

Each part gets its own bibliography containing exactly the works it cites,
ordered by first appearance so the numbering runs 1, 2, 3 through the text.

Output: paper/journal_part1/part1.tex, paper/journal_part2/part2.tex
"""
import os
import re
import sys

SRC = "paper/paper_journal_v2.tex"
P1 = "paper/journal_part1/part1.tex"
P2 = "paper/journal_part2/part2.tex"

TITLE1 = ("Spatiotemporal Flood Risk Modelling Under a Single-Orbit SAR "
          "Constraint, Part~I: Confound-Controlled Susceptibility and a "
          "Three-Stage Validation Ladder")
TITLE2 = ("Spatiotemporal Flood Risk Modelling Under a Single-Orbit SAR "
          "Constraint, Part~II: Flood-Aware Emergency Routing and Hybrid "
          "Quantum Dispatch")

# Tables/figures that must span both columns in IEEEtran's two-column layout.
WIDE = {"tab:study", "tab:data", "tab:factors", "tab:ablation", "tab:shapcmp",
        "tab:model", "tab:transfer", "tab:trigger", "tab:triggersweep",
        "tab:sweep", "tab:qaoa", "tab:compare", "tab:algo",
        "tab:spatial", "tab:sensitivity", "tab:prior", "tab:comparison",
        "tab:triggersweep", "tab:factors",
        "fig:study_area", "fig:factors", "fig:conditioning", "fig:susceptibility",
        "fig:spatialval", "fig:sarval", "fig:trigger", "fig:roadgraph",
        "fig:sweep", "fig:benchmark", "fig:qaoa"}


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def sections(body):
    """Split the body into (kind, title, text) blocks at \\section boundaries."""
    idx = [m.start() for m in re.finditer(r"(?m)^\\section\{", body)]
    idx.append(len(body))
    out = []
    for a, b in zip(idx[:-1], idx[1:]):
        chunk = body[a:b]
        title = re.match(r"\\section\{([^}]*)\}", chunk).group(1)
        out.append((title, chunk))
    return out


def subsections(text):
    """Split one section into its leading text plus (title, text) subsections."""
    idx = [m.start() for m in re.finditer(r"(?m)^\\subsection\{", text)]
    if not idx:
        return text, []
    lead = text[:idx[0]]
    idx.append(len(text))
    subs = []
    for a, b in zip(idx[:-1], idx[1:]):
        chunk = text[a:b]
        title = re.match(r"\\subsection\{([^}]*)\}", chunk).group(1)
        subs.append((title, chunk))
    return lead, subs


def pick(subs, wanted):
    """Return the subsection chunks whose titles match, in the order given."""
    by = {t: c for t, c in subs}
    got = []
    for w in wanted:
        hit = [t for t in by if w.lower() in t.lower()]
        if not hit:
            print(f"    WARN: no subsection matching {w!r}", file=sys.stderr)
            continue
        got.append(by[hit[0]])
    return "".join(got)


def widen(text):
    """Promote wide floats to their starred, two-column-spanning form."""
    def f(m):
        env, opt, inner = m.group(1), m.group(2) or "", m.group(3)
        lab = re.search(r"\\label\{([^}]+)\}", inner)
        if lab and lab.group(1) in WIDE:
            return (f"\\begin{{{env}*}}[!t]{inner}\\end{{{env}*}}")
        return m.group(0)
    return re.sub(r"\\begin\{(table|figure)\}(\[[^\]]*\])?(.*?)\\end\{\1\}",
                  f, text, flags=re.S)


def fix_widths(text):
    """\\textwidth spans the page; inside a one-column float it overflows by the
    gutter plus a column. \\linewidth adapts to whichever context it lands in."""
    return re.sub(r"(\\includegraphics\[[^\]]*?)\\textwidth", r"\1\\linewidth", text)


def resolve_crossrefs(text, other_part, other_key):
    """Rewrite references to sections that now live in the companion paper.

    Splitting a manuscript strands every \\ref whose target moved. Rather than
    leave a '??' in the PDF, point the reader at the companion paper explicitly.
    Raises if anything is still unresolved, so a dangling reference cannot ship.
    """
    labels = set(re.findall(r"\\label\{([^}]+)\}", text))
    refs = set(re.findall(r"\\ref\{([^}]+)\}", text))
    dangling = refs - labels
    for lab in dangling:
        text = re.sub(r"(?:Section|Sections|\u00a7)~?\\ref\{" + re.escape(lab) + r"\}",
                      f"{other_part}~\\\\cite{{{other_key}}}", text)
        text = re.sub(r"\\ref\{" + re.escape(lab) + r"\}",
                      f"{other_part}~\\\\cite{{{other_key}}}", text)
    still = set(re.findall(r"\\ref\{([^}]+)\}", text)) - labels
    if still:
        raise SystemExit(f"unresolved references remain: {sorted(still)}")
    if dangling:
        print(f"    redirected {len(dangling)} cross-part reference(s) to "
              f"{other_part}: {sorted(dangling)}")
    return text


EQ_TRIGGER_OLD = r"""\Tt \;=\; \min\!\Bigl(
\underbrace{0.5\,\frac{\min(P_{24},\,\theta_{\mathrm{VH}})}{\theta_{\mathrm{VH}}}}_{\text{daily intensity}}
+\underbrace{0.3\,\frac{\min(P_{72},\,\theta_{\mathrm{sat}})}{\theta_{\mathrm{sat}}}}_{\text{catchment saturation}}
+\underbrace{0.2\,\frac{\min(P_{6},\,\theta_{\mathrm{H}})}{\theta_{\mathrm{H}}}}_{\text{short burst}},
\;1\Bigr),"""

# Set on one line the equation spans a full page; an IEEE column is half that.
EQ_TRIGGER_NEW = r"""\begin{aligned}
\Tt \;=\; \min\Bigl(\;
&\underbrace{0.5\,\tfrac{\min(P_{24},\,\theta_{\mathrm{VH}})}{\theta_{\mathrm{VH}}}}_{\text{daily intensity}}
\;+\; \underbrace{0.3\,\tfrac{\min(P_{72},\,\theta_{\mathrm{sat}})}{\theta_{\mathrm{sat}}}}_{\text{catchment saturation}} \\[2pt]
&+\; \underbrace{0.2\,\tfrac{\min(P_{6},\,\theta_{\mathrm{H}})}{\theta_{\mathrm{H}}}}_{\text{short burst}},
\;\; 1 \Bigr),
\end{aligned}"""


EQ_CONT_OLD = r"""\mathrm{POD}=\frac{\mathrm{TP}}{\mathrm{TP}+\mathrm{FN}},\qquad
\mathrm{FAR}=\frac{\mathrm{FP}}{\mathrm{TP}+\mathrm{FP}},\qquad
\mathrm{CSI}=\frac{\mathrm{TP}}{\mathrm{TP}+\mathrm{FP}+\mathrm{FN}},"""

EQ_CONT_NEW = r"""\begin{aligned}
\mathrm{POD}&=\tfrac{\mathrm{TP}}{\mathrm{TP}+\mathrm{FN}}, \qquad
\mathrm{FAR}=\tfrac{\mathrm{FP}}{\mathrm{TP}+\mathrm{FP}}, \\[2pt]
\mathrm{CSI}&=\tfrac{\mathrm{TP}}{\mathrm{TP}+\mathrm{FP}+\mathrm{FN}},
\end{aligned}"""


EQ_QUBO_OLD = r"""\min_{x\in\{0,1\}^{n^2}}\;
\sum_{a,i} C_{ai}x_{ai}
\;+\; P\sum_{a}\Bigl(\sum_i x_{ai}-1\Bigr)^{2}
\;+\; P\sum_{i}\Bigl(\sum_a x_{ai}-1\Bigr)^{2},"""

EQ_QUBO_NEW = r"""\begin{aligned}
\min_{x\in\{0,1\}^{n^2}}\; \sum_{a,i} C_{ai}x_{ai}
\;&+\; P\sum_{a}\Bigl(\sum_i x_{ai}-1\Bigr)^{2} \\[2pt]
&+\; P\sum_{i}\Bigl(\sum_a x_{ai}-1\Bigr)^{2},
\end{aligned}"""


def fix_wide_math(text):
    """Rewrite display equations that were set for a full-width page."""
    n = 0
    for old, new in ((EQ_TRIGGER_OLD, EQ_TRIGGER_NEW),
                     (EQ_CONT_OLD, EQ_CONT_NEW),
                     (EQ_QUBO_OLD, EQ_QUBO_NEW)):
        if old in text:
            text = text.replace(old, new)
            n += 1
    if n:
        print(f"    reflowed {n} display equation(s) for a two-column measure")
    return text


def fix_paragraph_headings(text):
    """IEEEtran adds its own colon after a run-in \\paragraph heading, so a
    heading whose text already ends in a period renders as '.:'."""
    return re.sub(r"(\\paragraph\{[^{}]*?)\.\}", r"\1}", text)


def shrink_tables(text):
    """IEEE columns are narrow; drop table body font a step and tighten rows."""
    def f(m):
        inner = m.group(2)
        if "\\footnotesize" in inner or "\\scriptsize" in inner:
            return m.group(0)
        inner = inner.replace("\\centering", "\\centering\\footnotesize", 1)
        return m.group(1) + inner + m.group(3)
    return re.sub(r"(\\begin\{table\*?\}(?:\[[^\]]*\])?)(.*?)(\\end\{table\*?\})",
                  f, text, flags=re.S)


PREAMBLE = r"""%%=============================================================================
%%  %(part)s
%%  IEEE journal format (IEEEtran, two column).
%%
%%  Build:  tectonic %(fname)s
%%
%%  Generated by scripts/split_journal.py from paper/paper_journal_v2.tex.
%%  Every number and figure traces to a script in ../../scripts; none is entered
%%  by hand. Edit the source manuscript and re-run the splitter, not this file.
%%=============================================================================
\documentclass[journal]{IEEEtran}

\usepackage[T1]{fontenc}
\usepackage{amsmath,amssymb,amsfonts}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{multirow}
\usepackage{array}
\usepackage{xcolor}
\usepackage{tikz}
\usetikzlibrary{positioning,arrows.meta,fit,backgrounds}
\usepackage{caption}
\usepackage{subcaption}
\captionsetup[sub]{font=small}
\usepackage[numbers,sort&compress]{natbib}
\usepackage[hidelinks]{hyperref}
\usepackage{siunitx}
\sisetup{detect-all,group-separator={,}}
\usepackage{balance}

\renewcommand{\arraystretch}{1.15}

\newcommand{\Sx}{S(\mathbf{x})}
\newcommand{\Tt}{T(t)}
\newcommand{\Rxt}{R(\mathbf{x},t)}

\begin{document}

\title{%(title)s}

%% Author identities removed for anonymous review. Restore before camera-ready.
\author{}

\maketitle

\begin{abstract}
%(abstract)s
\end{abstract}

\begin{IEEEkeywords}
%(keywords)s
\end{IEEEkeywords}

"""


ABSTRACT1 = r"""Over Dakshina Kannada, Karnataka, exactly one Sentinel-1 orbit
covers the district on a strict twelve-day cycle, so no individual flood there
can be mapped from synthetic aperture radar (SAR): a flash flood rises and
recedes inside the revisit gap. This paper, the first of two, treats that
constraint as the design premise and builds the static half of a two-stage risk
model, $\Rxt=\Sx\cdot\Tt$. A multi-temporal SAR flood-\emph{frequency} inventory
replaces the single-event map that the revisit interval forbids. A
remote-sensing confound is then identified and removed: a model given land cover
and NDVI reaches ROC-AUC 0.9878, but SHAP shows it has learned that closed
canopy hides water from SAR, not flood physics. The terrain-and-rainfall model
scores 0.9625 on a random split, 0.9474 under spatial-block cross-validation,
and 0.871 transferring to a held-out city window never seen in training, where
its highest-susceptibility tenth contains 49.5\% of all SAR-observed flooding.
We show the calibrated score is tied to the balanced training prior and must not
be read as a flood probability without correction. The dynamic trigger $\Tt$,
keyed to India Meteorological Department rainfall categories and fitted to no
event, ranks two documented floods above ordinary and dry conditions but
separates a flood from a heavy-rain non-flood day by only 0.011, a margin
governed almost entirely by its antecedent-saturation term. Each stricter
validation protocol lowers the headline number, and we report the descent rather
than the first figure. Part~II applies the resulting risk surface to emergency
routing and dispatch."""

ABSTRACT2 = r"""Part~I of this work derived a calibrated, confound-controlled
flood-risk surface $\Rxt=\Sx\cdot\Tt$ for Dakshina Kannada, Karnataka, under a
twelve-day single-orbit Sentinel-1 constraint. This paper applies that surface
to emergency response over a real 11{,}910-node, 28{,}529-edge OpenStreetMap
road graph of Mangaluru, of which 17.1\% of edges are flood-prone. Flood-aware
routing cuts mean route exposure by 33.0\%, from 0.171 to 0.114, across the 42
hospital-incident pairs routable under both policies, for a mean detour of
3.8 minutes; the reduction holds at 31.4\% over 200 randomly sampled incident
sites, so it is not an artefact of the chosen locations. A survivorship-corrected
$7\times7$ sweep of the two cost-function constants separates them: the penalty
weight $\kappa$ is immaterial above $\approx 6$, while the impassability
threshold $\tau$ governs a step change in connectivity, with 0, 7 and 29 severed
pairs at $\tau\ge0.65$, $0.55$--$0.60$ and $\le0.50$ respectively, so $\tau$ is
a policy choice about acceptable risk and not a convention. Dijkstra and
A$^\ast$ are implemented explicitly to expose their explored sets: across 42
pairs A$^\ast$ returns the identical optimal path every time while settling a
median 31.1\% fewer nodes, yet is faster in wall-clock on only 25 of them,
because heuristic evaluation costs more in interpreted Python than the
expansions it avoids. A 9-qubit QUBO/QAOA dispatch layer reproduces the
Hungarian optimum exactly and improves with circuit depth over five seeds, with
no advantage claimed at this scale. Robustness to the choice of incident sites
is tested on 200 randomly sampled nodes."""

KEYWORDS1 = (r"Flood susceptibility, synthetic aperture radar, Sentinel-1, "
             r"spatial cross-validation, explainable AI, probability "
             r"calibration, Google Earth Engine.")
KEYWORDS2 = (r"Flood-aware routing, emergency dispatch, shortest-path "
             r"algorithms, QUBO, quantum approximate optimization algorithm, "
             r"sensitivity analysis, road networks.")


def build_part1(secs):
    d = dict(secs)
    out = []

    intro_lead, intro_subs = subsections(d["Introduction"])
    out.append(intro_lead)
    out.append(r"""\subsection{Contributions of Part~I}
This paper is the first of a two-part study. Part~I establishes the risk model
and the evidence for trusting it; Part~II~\cite{partii} applies that model to
emergency routing and dispatch over a real road network. The contributions of
this part are:
\begin{enumerate}
\item A SAR flood-\emph{frequency} inventory that is explicit about the
      single-orbit revisit limit and about what it therefore cannot claim.
\item Identification and removal of a remote-sensing confound in which land
      cover and NDVI let the model learn SAR detectability instead of flood
      hazard, quantified by ablation.
\item A three-stage validation ladder, random split to spatial-block
      cross-validation to geographic transfer, reporting the full descent of the
      headline metric rather than its first value.
\item A prior-correction analysis showing that a balanced-sample calibrated
      score is not a deployment-prevalence flood probability.
\item A temporal trigger built only from published rainfall categories, with its
      discriminative failure mode sought adversarially and reported.
\end{enumerate}

Figure~\ref{fig:architecture} maps the full two-part pipeline; the shaded stages
are the subject of this paper.
""")

    rel_lead, rel_subs = subsections(d["Related Work"])
    out.append(rel_lead)   # lead already contains the \section line
    out.append(pick(rel_subs, ["Machine learning for flood susceptibility",
                               "Spatial validation", "SAR flood mapping", "Gap"]))

    out.append(d["Study Area and Data"])

    m_lead, m_subs = subsections(d["Methodology"])
    out.append(m_lead)   # lead already contains the \section line
    out.append(pick(m_subs, ["Why the risk model is decomposed",
                             "SAR flood-frequency inventory",
                             "Conditioning factors",
                             "Sampling with terrain-matched negatives",
                             "A remote-sensing confound",
                             "Classifier, calibration and explanation",
                             "The validation ladder",
                             "Dynamic trigger",
                             "Implementation"]))

    r_lead, r_subs = subsections(d["Results and Discussion"])
    out.append(r_lead)   # lead already contains the \section line
    out.append(pick(r_subs, ["Feature-set ablation",
                             "Probability calibration",
                             "Spatial validation",
                             "Trigger validation"]))
    out.append(r"""\subsection{Comparison with prior work}
Reported flood-susceptibility AUCs in the literature cluster between 0.85 and
0.95~\cite{tehrany2014,khosravi2018,arabameri2019,saha2021,aydin2022}. Our
confounded 12-factor model would sit above that range at 0.9878, and our
primary model sits inside it at 0.9625. We regard the second number as the
comparable one, and note that most reported figures are random-split values
whose spatial-block and transfer equivalents are unknown, which is precisely the
comparison Section~\ref{sec:res-spatial} argues the field should be making.

\subsection{Limitations}
\label{sec:limitations}
\begin{itemize}
\item \textbf{Susceptibility is not depth.} $\Sx$ and $\Rxt$ are relative
      exposure indices in $[0,1]$, not water depth. A calibrated depth
      regression, in the direction of Sadhwani and Eldho~\cite{sadhwani2026},
      is the clearest strengthening step.
\item \textbf{The calibrated score is prior-dependent.} It is calibrated to the
      balanced training prior, not to landscape prevalence, and must be
      prior-corrected before being read as a probability.
\item \textbf{The trigger is a single regional scalar} and uses rainfall only;
      tide is acquired by the live system but does not enter $\Tt$. Scenarios
      therefore differ in intensity, not in spatial pattern.
\item \textbf{The trigger's free constants are its weakest point.} Three weights
      and a saturation reference are author-chosen, and the flood versus
      heavy-rain margin is governed almost entirely by the saturation term.
\item \textbf{Geographic transfer here is within-district}, across a city
      boundary rather than across a climatic or geomorphic regime.
\item \textbf{SAR absence is not evidence of dryness.} The inventory is a lower
      bound set by a twelve-day revisit.
\end{itemize}
""")

    out.append(r"""\section{Conclusions}
This paper built the static half of a two-stage flood-risk model for a district
where the satellite record forbids per-event mapping, and then spent most of its
effort trying to falsify it.

\begin{enumerate}
\item \textbf{A 12-factor model reaching ROC-AUC 0.9878 was discarded.} SHAP
      attribution ranked land cover and NDVI first, and the non-flooded lowland
      of this district is predominantly closed canopy, so the model was learning
      where SAR can see the ground. Removing the confound costs 0.025 AUC and is
      mandatory.
\item \textbf{Stricter validation lowered the number three times.} 0.9625 on a
      random split, 0.9474 under spatial-block cross-validation, 0.871 on
      geographic transfer. The last of these is the one an operational
      deployment would experience, and its highest-susceptibility tenth still
      contains 49.5\% of observed flooding.
\item \textbf{The calibrated score is not a flood probability.} Isotonic
      calibration on a balanced sample targets a 50\% prior against a landscape
      prevalence of 1.11\%; the correction changes what the number means without
      changing the ranking.
\item \textbf{The trigger orders real events without being fitted to them},
      but separates a documented flood from a heavy-rain non-flood day by only
      0.011, and the diagnostic identifies the 72-hour saturation term as the
      variable carrying the signal.
\end{enumerate}

The broader claim is methodological: each protocol we applied removed a specific,
nameable way the previous figure was optimistic, and the sequence is more useful
to a practitioner than its first term. Part~II~\cite{partii} takes the resulting
risk surface into the emergency-response layer, where the same discipline is
applied to routing and dispatch.
""")
    return "".join(out)


def build_part2(secs):
    d = dict(secs)
    out = []

    out.append(r"""\section{Introduction}
\label{sec:intro}
Part~I of this study~\cite{parti} addressed a constraint that shapes every
flood-mapping effort over Dakshina Kannada, Karnataka: exactly one Sentinel-1
orbit geometry covers the district, on a nominal twelve-day revisit, so no
individual flood can be mapped from SAR because a coastal flash flood rises and
recedes inside the gap. That paper responded by decomposing risk into a static,
SAR-trained susceptibility surface $\Sx$ and a dynamic, rainfall-driven trigger
$\Tt$, fused as $\Rxt=\Sx\cdot\Tt$, and subjected the static term to a
three-stage validation ladder that lowered its headline ROC-AUC from 0.9878 to
0.871 as each source of optimism was removed.

A risk surface is not by itself an operational product. The question this paper
addresses is what that surface is worth once it has to move an ambulance. We
couple $\Rxt$ to a real drivable road network for Mangaluru city, obtained from
OpenStreetMap, and ask three things of it: how much exposure flood-aware routing
actually removes and at what cost in response time; how sensitive that trade is
to the two constants in the edge-cost function, which the conference version of
this work fixed without justification; and whether the assignment of vehicles to
incidents, the one stage small enough for near-term quantum simulation, can be
posed and solved as a QUBO with a verifiable classical reference.

Throughout we keep the reporting discipline of Part~I. Where a result runs
against the expected direction we report it as measured: A$^\ast$ explores
strictly fewer nodes than Dijkstra on every benchmarked pair and is nonetheless
slower on a majority of them, and the optimal dispatch assignment does not
change between dry and flood conditions even though we expected re-allocation.

\subsection{Contributions of Part~II}
\begin{enumerate}
\item A flood-aware routing formulation over a real 28{,}529-edge network,
      with exposure and detour measured across all hospital-incident pairs
      rather than on a single illustrative route.
\item A survivorship-corrected sensitivity analysis of the edge-cost constants
      that distinguishes a genuinely immaterial parameter from one sitting
      beside a topological discontinuity.
\item A search-transparent Dijkstra and A$^\ast$ benchmark that instruments the
      explored set, reporting a wall-clock result that contradicts the
      node-count result and explaining the mechanism.
\item A hybrid QUBO/QAOA dispatch layer verified against the exact classical
      optimum and scoped explicitly as a feasibility demonstration.
\item A robustness check over 200 randomly sampled incident sites, testing
      whether the benchmark depends on the choice of the seven named ones.
\end{enumerate}
""")

    rel_lead, rel_subs = subsections(d["Related Work"])
    out.append("\\section{Related Work}\n")
    out.append(pick(rel_subs, ["Emergency routing and dispatch",
                               "Quantum optimization"]))

    out.append(r"""\section{Study Area and Network}
The study area, the coastal district of Dakshina Kannada centred on Mangaluru,
is described in full in Part~I~\cite{parti}, together with the satellite,
terrain and climate inputs behind the risk surface used here. This paper adds
one dataset: the drivable road network for the Mangaluru routing window,
obtained from OpenStreetMap through the Overpass API with
\texttt{osmnx}~\cite{boeing2017} and acquired independently of the Earth Engine
pipeline. It comprises 11{,}910 nodes and 28{,}529 directed edges. Each edge
carries an OSM-derived free-flow travel time and is sampled against the
susceptibility raster at its midpoint, giving a per-edge $S(e)$. Under the
static surface, 4{,}873 edges, or 17.1\% of the network, are flood-prone at
$S(e)>0.5$ (Figure~\ref{fig:roadgraph}).

Seven hospitals and seven incident sites in flood-affected localities give the
49 origin-destination pairs used throughout. The hospitals are real facilities;
the incident sites are chosen by us, and Section~\ref{sec:res-routing} tests
whether that choice matters by resampling them at random.
""")

    m_lead, m_subs = subsections(d["Methodology"])
    out.append("\\section{Methodology}\n")
    out.append(pick(m_subs, ["Flood-aware graph and routing",
                             "Hybrid quantum dispatch",
                             "Implementation"]))

    r_lead, r_subs = subsections(d["Results and Discussion"])
    out.append("\\section{Results and Discussion}\n")
    out.append(pick(r_subs, ["Flood-aware routing",
                             "Sensitivity of the routing constants",
                             "Dijkstra versus",
                             "Hybrid quantum dispatch"]))

    out.append(r"""\subsection{Limitations}
\label{sec:limitations}
\begin{itemize}
\item \textbf{The impassability threshold is a heuristic, not hydraulics.}
      $\tau$ marks a susceptibility level, not a fordable water depth, and the
      sweep shows the routing outcome turns on it.
\item \textbf{Travel times are free-flow.} No traffic model, no signal delay and
      no weather effect on speed is included, so absolute response times are
      optimistic even where the relative comparison holds.
\item \textbf{The wall-clock comparison reflects an interpreted implementation}
      chosen for search transparency; a compiled router would convert the
      node-count advantage into time saved.
\item \textbf{The quantum layer is a feasibility demonstration} at $3\times3$.
      The Hungarian algorithm is optimal and effectively instantaneous at this
      size, and no quantum advantage is claimed.
\item \textbf{Dispatch is single-shot.} Vehicles are assigned once, with no
      queueing, no re-routing in flight and no fleet dynamics.
\end{itemize}

\subsection{Comparison with prior work}
Risk-weighted routing under flooding is established~\cite{zhang2019,yin2016},
and QAOA has been applied to vehicle routing and assignment at comparable
scale~\cite{farhi2014,lucas2014,zhou2020}. What is different here is the
provenance of the weights: the per-edge risk is not an assumed inundation
scenario but a SAR-grounded, calibration-audited surface carried over from
Part~I, and the cost constants that convert it into a route are swept rather
than asserted.
""")

    out.append(r"""\section{Conclusions}
This paper took the risk surface built in Part~I into the response layer and
measured what it buys.

\begin{enumerate}
\item \textbf{Flood-aware routing removes a third of mean route exposure} across
      all hospital-incident pairs, for a detour of a few minutes on a
      representative route. The gain is real but bounded by the network: both
      the risk-blind and the flood-aware route must cross the same small number
      of river crossings.
\item \textbf{The two cost constants are not equally consequential.} The penalty
      weight is immaterial above $\kappa\approx6$; the impassability threshold
      governs a step change in connectivity and must therefore be set by policy
      on acceptable risk, not by convention. Comparing sweep cells naively
      invites survivorship bias, because an aggressive threshold silently drops
      the hardest pairs, so cells are compared on the subset routable
      everywhere.
\item \textbf{Search-transparent benchmarking exposes a trade single examples
      hide.} A$^\ast$ returned the identical optimal path on all 42 pairs and
      explored a median 31.1\% fewer nodes, yet was faster in wall-clock time on
      only 25 of them, because heuristic evaluation costs more in interpreted
      Python than the expansions it avoids.
\item \textbf{The QUBO/QAOA dispatch layer reproduces the Hungarian optimum
      exactly} and improves with circuit depth over five seeds, at a problem
      size where it offers no advantage. We report it as a feasibility result
      and nothing more.
\end{enumerate}

Future work follows from the limitations of both parts. A calibrated depth
regression would replace the heuristic impassability threshold with a hydraulic
criterion and make $\tau$ a physical quantity. A spatially resolved rainfall
field would make the trigger genuinely spatiotemporal. A compiled routing
implementation would isolate the algorithmic advantage of A$^\ast$ from
interpreter overhead, and executing the QAOA circuits on physical hardware would
characterise the noise behaviour exact simulation cannot.
""")
    return "".join(out)


CROSSREF = {
    "parti": (r"\bibitem[Companion(2026a)]{parti} Authors. "
              r"Spatiotemporal flood risk modelling under a single-orbit SAR "
              r"constraint, Part~I: Confound-controlled susceptibility and a "
              r"three-stage validation ladder. \emph{Companion paper, "
              r"submitted}."),
    "partii": (r"\bibitem[Companion(2026b)]{partii} Authors. "
               r"Spatiotemporal flood risk modelling under a single-orbit SAR "
               r"constraint, Part~II: Flood-aware emergency routing and hybrid "
               r"quantum dispatch. \emph{Companion paper, submitted}."),
}


def bibliography(body, allbib):
    """Emit only the entries this part cites, ordered by first appearance."""
    order, seen = [], set()
    for m in re.finditer(r"\\cite[a-zA-Z]*\s*(?:\[[^\]]*\])?\s*\{([^}]+)\}", body):
        for k in (x.strip() for x in m.group(1).split(",")):
            if k and k not in seen:
                seen.add(k)
                order.append(k)
    missing = [k for k in order if k not in allbib and k not in CROSSREF]
    if missing:
        raise SystemExit(f"cited but no bibitem: {missing}")
    items = [CROSSREF[k] if k in CROSSREF else allbib[k] for k in order]
    return ("\\begin{thebibliography}{99}\n\\setlength{\\itemsep}{1pt}\n\n"
            + "\n\n".join(items) + "\n\n\\end{thebibliography}\n")


def main():
    src = read(SRC)
    head, rest = src.split(r"\begin{thebibliography}", 1)
    _, bibbody = rest.split("\n", 1)
    bibbody = bibbody.split(r"\end{thebibliography}")[0]

    allbib = {}
    for blk in re.split(r"(?m)^(?=\\bibitem)", bibbody):
        m = re.match(r"\\bibitem\[[^\]]*\]\{([^}]+)\}", blk.strip())
        if m:
            allbib[m.group(1)] = blk.rstrip("\n")
    print(f">> source: {len(allbib)} bibitems")

    body = head.split(r"\maketitle", 1)[1]
    body = body.split(r"\begin{abstract}")[0] + \
        body[body.index(r"\end{abstract}") + len(r"\end{abstract}"):]
    secs = sections(body)
    print(f"   sections: {', '.join(t for t, _ in secs)}")

    for path, title, abstract, keywords, builder, fname, other, okey in (
        (P1, TITLE1, ABSTRACT1, KEYWORDS1, build_part1, "part1.tex",
         "Part~II", "partii"),
        (P2, TITLE2, ABSTRACT2, KEYWORDS2, build_part2, "part2.tex",
         "Part~I", "parti"),
    ):
        print(f">> building {path}")
        text = builder(secs)
        text = fix_widths(text)
        text = fix_wide_math(text)
        text = fix_paragraph_headings(text)
        text = resolve_crossrefs(text, other, okey)
        text = widen(shrink_tables(text))
        pre = PREAMBLE % {"part": title.split(",")[1].strip(), "fname": fname,
                          "title": title, "abstract": abstract,
                          "keywords": keywords}
        doc = pre + text + "\n\\balance\n" + bibliography(text, allbib) + \
            "\n\\end{document}\n"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(doc)
        nref = doc.count("\\bibitem")
        nfig = len(set(re.findall(r"includegraphics\[[^\]]*\]\{([^}]+)\}", doc)))
        ntab = len(re.findall(r"\\begin\{table\*?\}", doc))
        print(f">> {path}: {nref} refs, {nfig} figures, {ntab} tables")


if __name__ == "__main__":
    main()
