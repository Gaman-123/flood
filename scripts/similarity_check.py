"""Local similarity, self-overlap and style analysis for the manuscripts.

This is NOT a substitute for Turnitin/iThenticate. Those compare against
subscription corpora (published literature, student archives, the crawled web)
that are not available here. What this script does measure, exactly and
reproducibly:

  1. SELF-OVERLAP between the conference paper (main.tex) and the journal
     manuscript (paper_journal.tex). This is the single highest-risk similarity
     source for this project, because both describe the same study and a
     screener WILL match them against each other once the conference version is
     indexed. Reported the way a screener reports it: the fraction of journal
     words covered by a matched run of >= N consecutive words.

  2. INTERNAL repetition inside the journal manuscript: near-duplicate sentences
     that a reader (or a reviewer) would notice as padding.

  3. STYLE metrics used as AI-authorship proxies: burstiness (sentence-length
     variance), lexical diversity, and the frequency of constructions that
     cluster in LLM prose. These are proxies, not detection. No classifier is
     being run and no probability of AI authorship is produced, because any such
     number here would be invented.

Usage:  python scripts/similarity_check.py
"""
import json
import os
import re
import statistics
import sys
from collections import Counter

CONF = "paper/main.tex"
JOUR = "paper/paper_journal.tex"
OUT = "data/processed/similarity_report.json"

SHINGLE = 8          # a run of 8+ identical words is what screeners flag
NEAR_DUP = 0.80      # Jaccard above this = near-duplicate sentence


# --------------------------------------------------------------- LaTeX -> prose

def detex(path):
    """Extract running prose from a LaTeX source, dropping markup and non-prose.

    Bibliography, tables, figures, math and code are removed: they legitimately
    overlap between versions (identical numbers, identical citations) and a
    screener that counted them would produce a meaningless score. What remains
    is authored narrative text, which is the thing that actually matters.
    """
    s = open(path, encoding="utf-8").read()

    # strip comments (but not escaped \%)
    s = re.sub(r"(?<!\\)%.*?$", "", s, flags=re.M)

    # drop whole environments that are not prose
    for env in ("thebibliography", "tabular", "table", "table*", "figure",
                "figure*", "tikzpicture", "equation", "equation*", "align",
                "align*", "verbatim", "lstlisting", "itemize", "enumerate"):
        s = re.sub(rf"\\begin\{{{re.escape(env)}\}}.*?\\end\{{{re.escape(env)}\}}",
                   " ", s, flags=re.S)

    s = re.sub(r"\$\$.*?\$\$", " ", s, flags=re.S)
    s = re.sub(r"\$[^$]*\$", " ", s)

    # citations/refs carry no authored prose
    s = re.sub(r"\\(cite|citep|citet|ref|eqref|autoref|label|includegraphics|"
               r"bibitem|href|url|newcommand|usepackage|documentclass|SI|num)"
               r"\s*(\[[^\]]*\])?\s*(\{[^{}]*\})*", " ", s)

    # sectioning: keep the title text, drop the command
    s = re.sub(r"\\(section|subsection|subsubsection|paragraph|title|caption)"
               r"\*?\s*\{", " ", s)

    s = re.sub(r"\\[a-zA-Z@]+\*?", " ", s)      # remaining commands
    s = re.sub(r"[{}\\~^_&]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def words(text):
    return re.findall(r"[a-z0-9]+", text.lower())


def sentences(text):
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z(])", text)
    return [p.strip() for p in parts if len(words(p)) >= 5]


# ------------------------------------------------------------------ overlap

def matched_spans(a_words, b_words, k=SHINGLE):
    """Indices in a_words covered by a run of >= k words also present in b."""
    b_shingles = set()
    for i in range(len(b_words) - k + 1):
        b_shingles.add(tuple(b_words[i:i + k]))
    covered = set()
    hits = []
    for i in range(len(a_words) - k + 1):
        if tuple(a_words[i:i + k]) in b_shingles:
            covered.update(range(i, i + k))
            hits.append(i)
    # merge hit positions into contiguous passages for reporting
    passages, cur = [], None
    for i in sorted(covered):
        if cur and i == cur[1] + 1:
            cur[1] = i
        else:
            if cur:
                passages.append(tuple(cur))
            cur = [i, i]
    if cur:
        passages.append(tuple(cur))
    return covered, passages


def jaccard(a, b):
    sa, sb = set(a), set(b)
    return len(sa & sb) / len(sa | sb) if (sa | sb) else 0.0


# ------------------------------------------------------------------- style

LLM_MARKERS = [
    "rather than", "it is worth noting", "it is important to note", "delve",
    "furthermore", "moreover", "additionally", "in conclusion", "leverage",
    "robust", "comprehensive", "seamless", "underscore", "pivotal",
    "testament", "landscape of", "realm of", "crucial", "notably",
    "genuine", "genuinely", "honest", "honestly", "precisely", "indeed",
]


def style(text):
    sents = sentences(text)
    lens = [len(words(s)) for s in sents]
    w = words(text)
    n = len(w)
    counts = {m: len(re.findall(rf"\b{re.escape(m)}\b", text, flags=re.I))
              for m in LLM_MARKERS}
    counts = {k: v for k, v in counts.items() if v}
    return {
        "words": n,
        "sentences": len(sents),
        "mean_sentence_words": round(statistics.mean(lens), 2) if lens else 0,
        "stdev_sentence_words": round(statistics.pstdev(lens), 2) if lens else 0,
        "burstiness_cv": round(statistics.pstdev(lens) / statistics.mean(lens), 3)
                         if lens and statistics.mean(lens) else 0,
        "type_token_ratio": round(len(set(w)) / n, 4) if n else 0,
        "hapax_fraction": round(
            sum(1 for _, c in Counter(w).items() if c == 1) / len(set(w)), 4)
            if w else 0,
        "em_dashes": text.count("\u2014"),
        "marker_counts": dict(sorted(counts.items(), key=lambda kv: -kv[1])),
        "marker_per_1000_words": {k: round(1000 * v / n, 2)
                                  for k, v in sorted(counts.items(),
                                                     key=lambda kv: -kv[1])[:12]},
    }


def main():
    for p in (CONF, JOUR):
        if not os.path.exists(p):
            sys.exit(f"missing {p}")

    conf_t, jour_t = detex(CONF), detex(JOUR)
    cw, jw = words(conf_t), words(jour_t)
    print(f">> prose extracted: conference {len(cw)} words, journal {len(jw)} words")

    # ---- 1. self-overlap ---------------------------------------------------
    covered, passages = matched_spans(jw, cw)
    pct = 100 * len(covered) / len(jw) if jw else 0
    long_passages = sorted(
        [(e - s + 1, " ".join(jw[s:e + 1])) for s, e in passages],
        reverse=True)[:15]

    print("\n== 1. Conference -> journal self-overlap ==")
    print(f"   journal words inside a {SHINGLE}+-word run shared with the "
          f"conference paper: {len(covered)}/{len(jw)} = {pct:.2f}%")
    print(f"   distinct shared passages: {len(passages)}")
    print("   longest shared passages:")
    for ln, txt in long_passages[:8]:
        print(f"     [{ln:3d} words] {txt[:110]}{'...' if len(txt) > 110 else ''}")

    # ---- 2. internal repetition -------------------------------------------
    js = sentences(jour_t)
    dups = []
    jsw = [words(s) for s in js]
    for i in range(len(js)):
        for k in range(i + 1, len(js)):
            if abs(len(jsw[i]) - len(jsw[k])) > 6:
                continue
            sim = jaccard(jsw[i], jsw[k])
            if sim >= NEAR_DUP:
                dups.append({"similarity": round(sim, 3),
                             "a": js[i][:130], "b": js[k][:130]})
    print(f"\n== 2. Internal near-duplicate sentences (Jaccard >= {NEAR_DUP}) ==")
    if dups:
        for d in dups[:10]:
            print(f"   {d['similarity']}: {d['a'][:95]}")
            print(f"        vs: {d['b'][:95]}")
    else:
        print("   none")

    # ---- 3. style ----------------------------------------------------------
    st_j, st_c = style(jour_t), style(conf_t)
    print("\n== 3. Style metrics (AI-authorship PROXIES, not detection) ==")
    for label, st in (("journal", st_j), ("conference", st_c)):
        print(f"   [{label}] {st['words']} words, {st['sentences']} sentences, "
              f"mean {st['mean_sentence_words']} +/- {st['stdev_sentence_words']} "
              f"(CV {st['burstiness_cv']}), TTR {st['type_token_ratio']}, "
              f"em-dashes {st['em_dashes']}")
    print("   journal marker rate per 1000 words:")
    for k, v in list(st_j["marker_per_1000_words"].items())[:10]:
        print(f"     {k:24s} {st_j['marker_counts'][k]:3d}  ({v}/1k)")

    report = {
        "note": ("Local analysis only. No Turnitin/iThenticate/GPTZero was run; "
                 "those require subscription corpora unavailable here. No AI "
                 "probability is reported because none can be computed here."),
        "shingle_words": SHINGLE,
        "self_overlap": {
            "conference_words": len(cw),
            "journal_words": len(jw),
            "journal_words_matched": len(covered),
            "journal_percent_matched": round(pct, 2),
            "n_shared_passages": len(passages),
            "longest_shared_passages": [
                {"words": ln, "text": txt} for ln, txt in long_passages],
        },
        "internal_near_duplicates": dups,
        "style_journal": st_j,
        "style_conference": st_c,
    }
    os.makedirs("data/processed", exist_ok=True)
    json.dump(report, open(OUT, "w"), indent=2)
    print(f"\n>> Saved -> {OUT}")


if __name__ == "__main__":
    main()
