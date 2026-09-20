# Dakshina Kannada district upgrade and manuscript audit

Audit date: 2026-09-11. This is the current claim-to-artifact handoff after the
operational system was expanded from a Mangaluru-centred window to the exact
Dakshina Kannada administrative boundary.

## Implemented system changes

- Exact OpenStreetMap/Nominatim district polygon: bounds 74.776108–75.670642 E,
  12.460086–13.185163 N.
- District-scale 120 m, nine-factor predictor raster evaluated by the serialized
  local XGBoost model. Raster no-data cells are nearest-neighbour filled solely
  for road sampling; out-of-bounds roads receive a conservative 0.75 value.
- Drivable graph: 25,407 nodes and 59,501 directed edges. Of these, 9,886
  (16.61%) have static susceptibility S > 0.5.
- Nineteen curated hospital routing origins and thirteen named scenario points
  spanning Bantwal, Belthangady, Kadaba, Mangaluru, Moodbidri, Mulki, Puttur,
  Sullia and Ullal.
- Emergency coordinates are rejected outside the exact district polygon.
- Live rainfall is sampled at Mangaluru, Moodbidri, Bantwal, Puttur and Sullia;
  the conservative maximum trigger is applied district-wide. Tide is reported
  separately and is not an input to the trigger.
- Dashboard panels now read generated coverage, routing and quantum JSON rather
  than synthetic route series or hard-coded headline numbers.

Hospital entries are routing origins, not a verified operational roster. The
audit does not establish current ambulance availability, emergency-department
status, bed capacity or referral capability. See
`data/processed/hospital_audit.json` for OSM element identifiers and provenance.

## Current reproduced results

| Claim | Current value | Artifact |
|---|---:|---|
| Primary 9-factor XGBoost held-out ROC-AUC | 0.9625 | `model_metrics.json` |
| Isotonic ROC-AUC / Brier | 0.9648 / 0.0683 | `model_metrics.json` |
| Spatial-block CV ROC-AUC | 0.9474 | `spatial_validation.json` |
| Coastal geographic-transfer ROC-AUC | 0.8594 | `sar_validation.json` |
| Coastal holdout points, train / withheld | 2,589 / 411 | `sar_validation.json` |
| SAR POD / FAR / CSI | 0.9507 / 0.9778 / 0.0221 | `sar_validation.json` |
| Flooding captured in top 10% / 20% | 49.26% / 75.37% | `sar_validation.json` |
| Balanced / prior-shifted fraction above 0.5 | 40.76% / 5.7524% | `calibration_prior.json` |
| May-2025 routable pairs | 192 / 247 | `coverage.json` |
| May-2025 blocked directed edges at T=0.70 | 4,019 | `coverage.json` |
| Wenlock–Kulur ETA, blind / aware | 9.5 / 16.7 min | `coverage.json` |
| Wenlock–Kulur mean exposure, blind / aware | 0.193 / 0.073 | `coverage.json` |
| Operating-point mean exposure, routed pairs | 0.0655 | `sensitivity_sweep.json` |
| Operating-point mean detour, routed pairs | 63.075 min | `sensitivity_sweep.json` |
| Pairs severed at kappa=8, block=0.60 | 55 / 247 | `sensitivity_sweep.json` |
| A* mean node reduction | 13.7% | `routing_benchmark.json` |
| Dijkstra / A* mean runtime | 29.715 / 36.033 ms | `routing_benchmark.json` |
| District 3x3 exact dispatch cost, dry / flood | 124.7229 / 250.8706 min | `qaoa_depth_study.json` |
| Exact assignment changes under flood | false | `qaoa_depth_study.json` |

The SAR false-alarm ratio is an upper bound: a non-flood SAR pixel means “not
observed flooded during the available revisits,” not verified dry land. The
routing detour average is conditional on the 192 pairs that remain connected;
the 55 severed pairs must always be reported alongside it.

## Required manuscript changes before submission

The authoritative editable source is `paper/paper_journal_v2.tex`; the files in
`paper/main/` are generated descendants. Do not submit the existing PDFs without
regenerating them.

1. Replace every Mangaluru-only operational graph claim with the exact district
   polygon, 25,407 nodes, 59,501 edges, 9,886 S>0.5 edges, 19 hospital origins,
   13 scenario points and nine-taluk coverage.
2. Replace the old 42-pair routing analysis with the 247-pair district design;
   report 192 reachable and 55 severed at the operating point. Do not compare
   route averages without stating the survivor set.
3. Replace the old A* claim. The algorithms match on all 192 reachable pairs;
   A* explores 13.7% fewer nodes but is 21.3% slower on average here.
4. Replace the geographic-transfer table, abstract and conclusions with the
   0.8594 AUC, 2,589/411 split, 21,365 valid pixels, 203 observed-flood pixels,
   POD 0.9507, FAR 0.9778, CSI 0.0221 and updated success-rate curve.
5. Replace prior-correction figures with 0.95% SAR-observed prevalence and
   40.76% to 5.7524% of the coastal holdout above a 0.5 cut.
6. Replace QUBO costs and stations with Wenlock/Puttur/Sullia to
   Mulki/Belthangady/Subrahmanya. State that the exact assignment did not change
   under the tested flood scenario and that QAOA depth performance is
   non-monotone.
7. Regenerate the study-area, road-network, route, sensitivity, validation and
   QAOA figures from current JSON/GeoJSON. `make_paper_figures.py` still contains
   several earlier hard-coded city values and must be made artifact-driven first.
8. State that the operational raster is 120 m, rainfall is aggregated by the
   maximum of five monitoring sites, the trigger remains spatially uniform after
   aggregation, and tide is excluded from T(t).
9. Add the hospital-roster caveat and an “OSM snapshot / audit date” field. Do not
   describe the 19 origins as 19 available ambulances or verified emergency units.
10. Resolve the 10 bibliography entries marked `UNVERIFIED` and manually verify
    the one non-Crossref entry in `paper/ieee_access/reference_audit.md` before
    submission.

## Legacy college report

`major_project_report__2signeswecooked (1).pdf` should not be used as the source
of technical truth. It describes a PyTorch LSTM, genetic algorithm, a 40-hospital
5 km setup, SRTM proxy labels and near-perfect 99.59% / AUC 1.0 results that do
not match the current repository. It also contains inconsistent environment
details and an unrelated “Coral Reef Health Monitoring” line. The report needs a
method/results rewrite from the current artifacts, not a small numerical patch.

## Reproduction status

Successfully rerun: Earth Engine training-table acquisition, XGBoost/RF training,
district predictor export, district graph annotation, hospital audit, dry/flood
route matrices, exact QUBO/Hungarian dispatch, QAOA depth study, routing benchmark,
49-cell routing sensitivity sweep, spatial validation, coastal SAR transfer,
prior correction, trigger audit/sweep and 200-random-incident robustness.
