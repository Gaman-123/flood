# Data provenance and regeneration

`.gitignore` deliberately excludes `data/`, `models/`, and `web_assets/`: they are
derived artifacts, not sources. This file records where each one comes from and
how to rebuild it, so the repository stays small without the results becoming
unverifiable.

## What is and is not in version control

| Path | Tracked | Size | Notes |
|---|---|---|---|
| `floodrisk/`, `scripts/`, `tests/` | yes | ~200 KB | All analysis code |
| `paper/*.tex`, `paper/figures/*.pdf` | yes | ~11 MB | The manuscript and every figure in it |
| `data/processed/` | no | ~23 MB | Derived artifacts (see below) |
| `models/` | no | ~4 MB | Trained classifier |
| `web_assets/` | no | ~15 MB | Dashboard exports + predictor stack |
| `data/external/` | no | ~50 MB | Natural Earth outlines, redownloadable |
| `.secrets/` | **never** | — | Credentials. Excluded by three separate rules |

## Credentials required

Full regeneration is **not** possible from this repository alone, and we state
that plainly rather than implying otherwise:

- **Google Earth Engine** account with a service-account key at
  `.secrets/ee-service-account.json`. Required for the SAR inventory, the
  predictor stack, and the wall-to-wall susceptibility raster. EE access is free
  for research but must be requested per user.
- **WorldTides** API key in `.secrets/live_api.env` as `WORLDTIDES_API_KEY`.
  Optional: tide data is acquired for the live dashboard only and does **not**
  enter any reported result.
- Open-Meteo and the Overpass API are keyless.

Everything downstream of `data/processed/training.parquet` and
`data/processed/dakshina_kannada_roads.graphml` runs without any credential. A reviewer
wanting to check the analysis rather than the acquisition can therefore verify
most of the paper from those two files alone.

## Rebuild order

```bash
make setup          # venv + pinned deps + editable floodrisk install
make all            # full pipeline: EE ingestion -> training -> assets
make journal-analyses # validation/sensitivity artifacts for manuscript revision
```

The current manuscript still contains pre-expansion Mangaluru-only values. Update
`paper/paper_journal_v2.tex` using `docs/district_upgrade_audit.md` before running
the manuscript-generation scripts or treating a PDF as submission-ready.

Stage by stage:

| Artifact | Built by | Needs EE |
|---|---|---|
| `data/processed/flood_freq_dk.png` | `scripts/build_sar_inventory.py` | yes |
| `data/processed/training.parquet` | `scripts/build_training_table.py` | yes |
| `models/susceptibility_best.joblib` | `scripts/train_susceptibility.py` | no |
| `data/processed/susceptibility_map.png` | `scripts/build_susceptibility_map.py` | yes |
| `web_assets/predictor_stack.tif` | `scripts/export_predictor_stack.py` | yes |
| `data/processed/susceptibility_dk.tif` | `scripts/build_road_graph.py` (local model inference) | no |
| `data/processed/dakshina_kannada_boundary.geojson` | `scripts/build_road_graph.py` | no (Nominatim) |
| `data/processed/dakshina_kannada_roads.graphml` | `scripts/build_road_graph.py` | no (Overpass) |
| `data/processed/hospital_audit.json` | `scripts/audit_hospitals.py` | no |
| `web_assets/sar_extent.geojson` | `scripts/export_sar_extent.py` | yes |
| `data/processed/quantum_dispatch.json` | `scripts/quantum_dispatch.py` | no |

Analyses added for the journal manuscript, none of which need Earth Engine:

| Artifact | Built by |
|---|---|
| `routing_benchmark.json` | `scripts/benchmark_routing.py` |
| `sensitivity_sweep.json` | `scripts/sensitivity_sweep.py` |
| `spatial_validation.json` | `scripts/spatial_validation.py` |
| `sar_validation.json` | `scripts/sar_validation.py` |
| `calibration_prior.json` | `scripts/calibration_prior.py` |
| `robustness.json` | `scripts/robustness.py` |
| `qaoa_depth_study.json` | `scripts/qaoa_depth_study.py` |
| `trigger_table.json`, `trigger_sweep.json` | `scripts/trigger_table.py`, `trigger_sweep.py` (network) |
| `paper/figures/*.pdf` | `scripts/make_maps.py`, `make_analysis_figures.py`, `make_paper_figures.py` |

## Determinism

Model training, sampling and the QAOA optimiser are seeded. Two stages are not
bit-reproducible:

- **Earth Engine** results can shift if an upstream collection is reprocessed by
  the provider.
- **Open-Meteo / ERA5** archive values may be revised; the trigger scripts refetch
  live rather than caching, so a rerun months later can differ slightly.

Both are properties of the upstream services, not of this code. `pytest` asserts
the invariants that must hold regardless (see `tests/test_journal_analyses.py`).

## Upstream data licences

| Source | Licence |
|---|---|
| Sentinel-1 / Sentinel-2 (Copernicus) | Free, full and open |
| SRTM (USGS/NASA) | Public domain |
| MERIT Hydro | CC-BY-NC 4.0 / ODbL (see provider terms) |
| CHIRPS (UCSB/USGS) | Public domain |
| JRC Global Surface Water | CC-BY 4.0 |
| ESA WorldCover | CC-BY 4.0 |
| OpenStreetMap | ODbL 1.0 |
| Natural Earth | Public domain |
| Open-Meteo / ERA5 | CC-BY 4.0 |

Note that MERIT Hydro and OpenStreetMap carry share-alike or non-commercial
terms; any redistribution of derived products must respect them. This is one
reason the repository ships code rather than bundled data.
