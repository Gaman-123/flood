# IEEE Access manuscript - Version 4

This folder is a self-contained Version 4 revision of the latest manuscript from
`../ieee_access_v3`. Version 3 remains unchanged. Version 4 updates the operational
study from the earlier Mangaluru-centred network to the full Dakshina Kannada
district implementation and its regenerated 2026-09-11 artifacts.

## Files

- `access_paper.tex` - editable IEEE Access manuscript source
- `bibliography_ieee.tex` - maintained bibliography mirror (the submission source also contains an inline bibliography)
- `figures/` - all figure and IEEE Access logo assets required by the source
- `access_paper.pdf` - current compiled build
- `IEEE-Access-Submission-v4.pdf` - versioned submission copy of the same build
- `fontsize.py` - retained supporting utility from Version 3

## Build

From this directory, run:

```bash
tectonic access_paper.tex
cp access_paper.pdf IEEE-Access-Submission-v4.pdf
```

The paper uses XeTeX through Tectonic for Times New Roman and Helvetica.

## Version notes

- Version 4 was initialized from `ieee_access_v3` on 2026-09-11.
- Operational coverage now uses the exact Dakshina Kannada district polygon,
  a 25,407-node/59,501-edge road graph, 19 hospital routing origins across nine
  taluks, and 13 scenario points.
- Current reproduced headline results are 0.8594 coastal holdout ROC-AUC; 192 of
  247 routing pairs reachable and 55 severed; 61.7% lower mean exposure among
  survivors at a 63.075-minute mean detour; and A* 13.7% lower node exploration
  but 21.3% slower mean runtime.
- All 13 referenced figures were regenerated from the 2026-09-11 artifacts and
  the Version 4 PDF was rebuilt with Tectonic.
- Before external submission, authors must replace the institutional-email,
  funding, portrait and biography placeholders and complete the outstanding
  manual reference checks documented in `../ieee_access/reference_audit.md`.
- The operating domain now uses the exact district boundary: 25,407 nodes,
  59,501 directed road edges, 19 curated hospital origins across nine taluks,
  and 13 scenario points.
- Validation, routing, sensitivity, search, robustness, and QAOA results were
  replaced with the reproduced 2026-09-11 artifacts; 13 paper figures were
  regenerated from the current data products.
- Two relevant 2026 preprints located through alphaXiv were added to the related
  work, with their limitations carried into the manuscript's framing.
- The 19 hospitals are routing origins, not a verified live emergency-capability
  roster. See `../../data/processed/hospital_audit.json` for provenance.
- Submission is still blocked on the bibliography items marked `UNVERIFIED` in
  `../ieee_access/reference_audit.md` and the author-supplied placeholders below.
- Before submission, replace the institutional-email, membership-grade, and
  funding placeholders in `access_paper.tex` as applicable.
