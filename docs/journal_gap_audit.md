# Journal manuscript: claim-to-artifact audit

> **Superseded for current numeric claims (2026-09-11).** This audit describes
> the earlier Mangaluru-only operational graph. The software now covers the full
> Dakshina Kannada district, and the regenerated figures and manuscript values
> listed in `docs/district_upgrade_audit.md` must replace the values below.

Every quantitative claim in `paper/paper_journal.tex` and the script that
produces it. Regenerate everything with `make journal`.

## 1. Claim provenance

| Claim in manuscript | Value | Produced by | Artifact |
|---|---|---|---|
| Sentinel-1 single covering orbit, 12-day revisit | rel. orbit 63, descending | `scripts/check_s1_passes.py`, `check_s1_cadence.py` | console (verified against Copernicus) |
| Monsoon passes in inventory | 20 | `scripts/build_sar_inventory.py` | `data/processed/flood_freq_dk.png` |
| SAR polygons / area | 201 / 2.86 km² (UTM 43N) | `scripts/export_sar_extent.py` | `web_assets/sar_extent.geojson` |
| Training sample | 1500 + 1500, domain-confined | `scripts/build_training_table.py` | `data/processed/training.parquet` |
| VIF with SPI / without | 16.22, 14.50 / all < 3.5 | inline in audit run | `data/processed/vif.json` |
| Ablation 12F / 11F / 9F AUC | 0.9878 / 0.9872 / 0.9625 | `scripts/spatial_validation.py` | `data/processed/spatial_validation.json` |
| SHAP top-5 per feature set | see table | `scripts/spatial_validation.py` | same |
| RF vs XGBoost test metrics | table | `scripts/train_susceptibility.py` | `data/processed/model_metrics.json` |
| Calibration Brier 0.0697 → 0.0683 | — | `scripts/train_susceptibility.py` | same |
| Random vs spatial-block CV | 0.9585 → 0.9474 (−1.16%) | `scripts/spatial_validation.py` | `spatial_validation.json` |
| Geographic-transfer AUC | 0.871 | `scripts/sar_validation.py` | `data/processed/sar_validation.json` |
| POD / FAR / CSI | 0.942 / 0.970 / 0.030 | `scripts/sar_validation.py` | same |
| Success-rate curve (10%→49.5%, 20%→77.6%) | — | `scripts/sar_validation.py` | same |
| Trigger values (0.701, 0.562, 0.551, 0.133, 0.000) | — | `scripts/trigger_table.py` | `data/processed/trigger_table.json` |
| Rainfall inputs per scenario | 6/24/72 h totals | `scripts/trigger_table.py` | same |
| Trigger monotonicity | PASS | `scripts/trigger_table.py` | same |
| Road graph 11,910 / 28,529 | — | `scripts/build_road_graph.py` | `data/processed/mangaluru_roads.graphml` |
| Flood-prone edges 4,873 (17.1%) | — | `scripts/make_maps.py` | figure + graph |
| Single-pair routing 13.6→17.4 min, 0.170→0.079 | — | `scripts/make_maps.py` | `data/processed/route_overlay_stats.json` |
| All-pairs exposure 0.171→0.114 (33.0%) | — | `scripts/sensitivity_sweep.py` | `data/processed/sensitivity_sweep.json` |
| κ saturation above ≈6 | — | `scripts/sensitivity_sweep.py` | same |
| Severed pairs 29 / 7 / 0 by τ | — | `scripts/sensitivity_sweep.py` | same |
| Dijkstra vs A*: 3,349 vs 2,933 nodes | — | `scripts/benchmark_routing.py` | `data/processed/routing_benchmark.json` |
| Median node reduction 31.1%, range 0.03–52.9% | — | `scripts/benchmark_routing.py` | same |
| A* faster on 25/42, identical path 42/42 | — | `scripts/benchmark_routing.py` | same |
| QUBO = Hungarian (20.900 / 22.130 min) | — | `scripts/qaoa_depth_study.py` | `data/processed/qaoa_depth_study.json` |
| QAOA ratio p=1→5, 5 seeds | — | `scripts/qaoa_depth_study.py` | same |
| Assignment unchanged dry vs flood | False | `scripts/qaoa_depth_study.py` | same |
| Test count 79 | — | `pytest` | `tests/` |

## 2. Prose promoted to equation / table / figure

| Was prose in the conference version | Now |
|---|---|
| SAR water thresholding described in words | Eq. 2–4 |
| VIF screening asserted | Eq. 5 + Table 3 (measured values) |
| Floodable-lowland domain described | Eq. 6 |
| Trigger described qualitatively | Eq. 11 + Table 8 (full inputs) |
| Brier score named | Eq. 8 |
| SHAP named | Eq. 9 |
| A* admissibility asserted | Eq. 13–14 |
| QUBO described | Eq. 15 |
| Ising mapping mentioned | Eq. 16 |
| QAOA ansatz mentioned | Eq. 17 |
| Approximation ratio used | Eq. 18 |
| Contingency metrics implied | Eq. 10 |
| NDVI/LULC confound in prose only | Table 4 + Fig. 6 (full ablation) |
| Trigger values in a figure only | Table 8 (with raw inputs) |
| QAOA depths in a figure only | Table 11 (5 seeds, mean ± s.d.) |
| "constants not swept" (stated limitation) | Section 5.6, Fig. 12, Table 10 |
| No spatial validation | Section 5.3, Tables 6–7, Figs. 7–8 |
| No maps at all | Figs. 2, 4, 5, 9, 13, 14 |

## 3. Claims that changed under stricter measurement

These are cases where the added analysis **contradicted or qualified** the
conference version. Each was rewritten rather than retained.

1. **"Monotonic improvement" in QAOA approximation ratio.** True only when
   averaged over seeds. A single seed gives a non-monotone sequence. The
   manuscript now reports 5-seed mean ± s.d. and says so explicitly.
2. **54% exposure reduction.** That is the single representative pair. Across
   all 42 pairs the reduction is 34.5%. The all-pairs figure is now the headline.
3. **A* explores fewer nodes on 41/42 pairs.** Recomputation gives strictly fewer
   on 42/42, but A* is *faster in wall-clock* on only 25/42. Both are reported.
4. **Median node reduction 31.3%.** Recomputed exactly: 31.1%.
5. **Trigger "correctly orders events".** True against ordinary and dry
   conditions, but the margin over a heavy-rain non-flood day is only 0.011.
   This limitation is now a named result, not omitted.
6. **17.1% flood-prone edges.** `web_assets/roads_light.geojson` is a decimated
   web subset that gives 53%. All road statistics now come from the graphml.

## 4. Corrections made in response to peer review

Six issues where a reviewer showed the manuscript was wrong or unsupported.
Each is now backed by a script, an artifact, and a regression test.

| # | Issue | Resolution | Artifact |
|---|---|---|---|
| 1 | Abstract/intro/Fig.2/Table 2 claimed tide entered `T(t)`; Eq. 11 is rainfall-only | Claims purged; tide named as the top limitation and future extension | text only |
| 2 | "Read as a probability" was false — model trained at a 50% prior, deployed at 1.11% | Claim retracted; Elkan/Saerens prior correction added (Eq. 19, Table 6). 0.5 cut flags 34.3% → 3.66% | `calibration_prior.json` |
| 3 | Sensitivity heatmap averaged over self-selected survivors | All cells now aggregated over the 20 pairs routable in **every** cell. Neighbourhood spread 15.9% → 2.4% | `sensitivity_sweep.json` |
| 4 | Four unswept trigger constants, while routing constants were swept | 231 weight triples × 5 θ_sat swept. Ordering robust in 1155/1155; adversarial margin positive in only 374 | `trigger_sweep.json` |
| 5 | Ref. [3] misattributed (wrong co-author, title, volume, year) | Corrected to Aydin & Iban, *Nat. Hazards* 116:2957–2991, 2023, verified via Crossref. Saha author list also corrected | bibliography |
| 6 | SAR area 2.9 → 3.0 km² unexplained | **Our bug**: area computed in Web Mercator, which inflates by sec²(lat) = 1.05× at 12.9°N. Now UTM 43N; 2.86 km² | `make_maps.py` |

Additional review-driven analyses:

- **`rain_annual` as a partial proxy** — only 17 distinct CHIRPS values over 292,125 pixels; correlation with distance-to-coast 0.73. Retained (leave-one-out cost 0.0063 AUC, second-largest) but explicitly flagged as partly positional. → `robustness.json`
- **Incident-site robustness** — 200 random road nodes give a 31.4% exposure reduction against 33.0% for the seven curated sites, so the benchmark is not an artifact of site selection. → `robustness.json`
- **QAOA monotonicity softened** — p=4→5 increments (+0.0010, +0.0011) are an order of magnitude below the seed standard deviations. Now "saturates near p=3–4"; optimum-sampling probability explicitly reported as non-monotone.
- **3×3 vs 7×7 reconciled** — n² qubit scaling stated; 7×7 = 49 qubits ≈ 9 PB of statevector. Sub-instance selection rule given.

## 5. Known gaps (not resolved)

- **Reference count: 46, target was 65–75.** Every entry is verified; six were
  added this round against Crossref records. Padding was declined.
- **Regional coverage is still thin** — two Karnataka/Western Ghats references
  (Chandrashekar & Shetty 2018; Chandana & Chandan 2023) plus Sadhwani & Eldho
  2026. A reviewer wanting 8–12 regional citations is not yet satisfied.
- **Abstract is 304 words** — under most journals' 250 limit but over MDPI's 200.
- **Tide is still not in the trigger.** Now declared rather than implied.
- **Depth regression, spatially resolved trigger, cross-district transfer** —
  unchanged from the previous revision.
