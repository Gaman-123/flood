"""Rebuild the bibliography in IEEE reference style.

Metadata comes from Crossref, queried by DOI where the entry has one and by
title otherwise, with an 0.80 title-similarity floor. Nothing is invented: an
entry that Crossref cannot confirm keeps its existing metadata, is reformatted
structurally only, and is listed in the audit output for author checking.

Journal names are written out in full rather than abbreviated. IEEE prefers the
abbreviation, but guessing one is a fabrication risk and a full name is never
wrong; abbreviating is left as optional polish.

Reads  /tmp/xref_out.json  (produced by the resolution step)
       paper/ieee_access/access_paper.tex  (for the existing entries and order)
Writes paper/ieee_access/bibliography_ieee.tex
       paper/ieee_access/reference_audit.md
"""
import html
import json
import re

MONTH = {1:"Jan.",2:"Feb.",3:"Mar.",4:"Apr.",5:"May",6:"Jun.",
         7:"Jul.",8:"Aug.",9:"Sep.",10:"Oct.",11:"Nov.",12:"Dec."}



# Crossref returns real Unicode (U+2010 hyphen, curly quotes, dashes) that the
# Times New Roman text font does not cover under XeTeX. Map to TeX equivalents.
UNI = {
    "\u2010": "-", "\u2011": "-", "\u2012": "--", "\u2013": "--",
    "\u2014": "---", "\u2018": "`", "\u2019": "'", "\u201c": "``",
    "\u201d": "''", "\u2026": "...", "\u00a0": " ", "\u2212": "-",
}


def clean(t):
    """Unicode -> TeX, decode XML entities, escape LaTeX specials.

    Crossref serves XML-escaped text ("Science &amp; Engineering"), and a bare
    & is an alignment tab in LaTeX, which aborts the build.
    """
    t = html.unescape(t)
    for a, b in UNI.items():
        t = t.replace(a, b)
    t = re.sub(r"(?<!\\)&", r"\\&", t)
    t = re.sub(r"(?<!\\)%", r"\\%", t)
    return t


def tex_escape_doi(d):
    """DOIs legitimately contain _ % # &, which are LaTeX specials."""
    for a, b in (("\\", "/"), ("_", "\\_"), ("%", "\\%"),
                 ("#", "\\#"), ("&", "\\&")):
        d = d.replace(a, b)
    return d


# Entries Crossref cannot serve, written directly from metadata already present
# in the manuscript. Nothing here is new information.
MANUAL = {
    "farhi2014": ("E. Farhi, J. Goldstone, and S. Gutmann, ``A quantum "
                  "approximate optimization algorithm,'' 2014, "
                  "arXiv:1411.4028."),
}


def initials(name):
    """'Charles R. Harris' -> 'C. R. Harris'."""
    parts = name.split()
    if len(parts) < 2:
        return name
    sur = parts[-1]
    given = parts[:-1]
    ini = " ".join((p[0] + ".") if not p.endswith(".") else p for p in given if p)
    return f"{ini} {sur}".strip()


def author_list(authors):
    a = [initials(x) for x in authors if x.strip()]
    if not a:
        return ""
    if len(a) > 6:                      # IEEE: more than six -> first + et al.
        return a[0] + " et al."
    if len(a) == 1:
        return a[0]
    return ", ".join(a[:-1]) + (", and " if len(a) > 2 else " and ") + a[-1]


def locator(m):
    """pp. / Art. no., taken from Crossref rather than inferred."""
    if m.get("page"):
        pg = m["page"].replace("-", "--")
        return ("pp. " if "--" in pg else "p. ") + pg
    if m.get("artno"):
        return "Art. no. " + str(m["artno"])
    return None


def fmt(entry, meta, key):
    """One IEEE-style reference body (without the \\bibitem wrapper)."""
    au = author_list(meta["authors"])
    title = clean(meta["title"]).rstrip(".")
    venue = clean(meta["venue"])
    bits = []
    if au:
        bits.append(au)
    conf = (meta.get("type") or "").startswith("proceedings")
    q = "``%s,''" % title
    bits.append(q)
    if venue:
        bits.append(("in \\emph{%s}" if conf else "\\emph{%s}") % venue)
    tail = []
    if meta.get("volume"):
        tail.append("vol. " + str(meta["volume"]))
    if meta.get("issue"):
        tail.append("no. " + str(meta["issue"]))
    loc = locator(meta)
    if loc:
        tail.append(loc)
    date = ""
    if meta.get("month") and meta.get("year"):
        date = "%s %s" % (MONTH.get(meta["month"], ""), meta["year"])
    elif meta.get("year"):
        date = str(meta["year"])
    if date:
        tail.append(date)
    out = ", ".join(bits[:1]) + ", " + " ".join(bits[1:2]) + " " + " ".join(bits[2:])
    out = out.strip()
    if tail:
        out += ", " + ", ".join(tail)
    if entry.get("doi"):
        out += ", doi: %s" % tex_escape_doi(entry["doi"])
    return clean(re.sub(r"\s+", " ", out).strip().rstrip(",")) + "."


# The body uses \citet for textual citations ("Tehrany et al. [6] established").
# In numeric mode natbib takes the author name from the \bibitem OPTIONAL
# argument, not from the formatted entry, and prints a literal "(author?)" when
# it is absent. The label is never printed in numeric mode, so carrying it
# across is invisible in the PDF and required for \citet to resolve.
def natbib_labels(path="paper/paper_journal_v2.tex"):
    import re as _re
    src = open(path, encoding="utf-8").read()
    return {m.group(2): m.group(1)
            for m in _re.finditer(r"\\bibitem\[([^\]]*)\]\{([^}]+)\}", src)}



def main():
    _labels = natbib_labels()
    xref = {r["key"]: r for r in json.load(open("/tmp/xref_out.json"))}
    # Read order and original metadata from the UPSTREAM manuscript, not from
    # access_paper.tex, which this script itself rewrites (circular otherwise).
    tex = open("paper/main/main_paper_2col.tex", encoding="utf-8").read()
    bib = tex.split(r"\begin{thebibliography}")[1].split(r"\end{thebibliography}")[0]

    order, raw = [], {}
    for blk in re.split(r"(?m)^(?=\\bibitem)", bib):
        m = re.match(r"\\bibitem(?:\[[^\]]*\])?\{([^}]+)\}(.*)", blk, re.S)
        if m:
            order.append(m.group(1))
            raw[m.group(1)] = " ".join(m.group(2).split())

    lines, audit = [], []
    for k in order:
        r = xref.get(k, {})
        if k in MANUAL:
            lines.append("\\bibitem[%s]{%s}\n%s\n"
                         % (_labels.get(k, k), k, MANUAL[k]))
            audit.append((k, "manual (not in Crossref)", "manuscript metadata"))
            continue
        if r.get("meta"):
            body = fmt(r, r["meta"], k)
            src = "DOI" if r["status"] == "doi" else "title match " + r["status"][5:]
            audit.append((k, "reformatted", src))
        else:
            # keep the existing text; restructure only what is unambiguous
            t = raw[k]
            t = re.sub(r"\s*\\href\{[^}]*\}\{doi:([^}]*)\}\.?\s*$", r", doi: \1.", t)
            t = re.sub(r"\.\s*,\s*doi:", ", doi:", t)      # no ". , doi:"
            body = clean(t)
            audit.append((k, "UNVERIFIED - author check", r.get("status", "n/a")))
        lines.append("\\bibitem[%s]{%s}\n%s\n"
                     % (_labels.get(k, k), k, body))

    out = ("\\begin{thebibliography}{99}\n\\setlength{\\itemsep}{0pt}\n\n"
           + "\n".join(lines) + "\n\\end{thebibliography}\n")
    open("paper/ieee_access/bibliography_ieee.tex", "w", encoding="utf-8").write(out)

    n_ok = sum(1 for a in audit if a[1] == "reformatted")
    with open("paper/ieee_access/reference_audit.md", "w", encoding="utf-8") as f:
        f.write("# Reference audit\n\n")
        f.write(f"{len(order)} references. {n_ok} rebuilt from Crossref metadata; "
                f"{len(order)-n_ok} could not be confirmed and keep their existing "
                "metadata, reformatted structurally only.\n\n")
        f.write("| # | Key | Status | Source |\n|---|---|---|---|\n")
        for i, (k, st, src) in enumerate(audit, 1):
            f.write(f"| {i} | `{k}` | {st} | {src} |\n")
    print(f">> {len(order)} entries: {n_ok} Crossref-verified, {len(order)-n_ok} flagged")
    for k, st, src in audit:
        if st != "reformatted":
            print("   FLAG:", k, "-", src)


if __name__ == "__main__":
    main()
