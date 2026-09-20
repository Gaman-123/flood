# Reproducible pipeline for the Dakshina Kannada flood-risk study.
#
# Make is a file-dependency DAG engine: each target declares the artifacts it
# needs, so re-running only rebuilds what actually changed. No orchestrator,
# no scheduler, no server.
#
#   make setup     install the pinned research env + the floodrisk package
#   make all       reproduce every artifact behind the paper
#   make assets    just the web assets the dashboard serves
#   make test      invariant tests (no network)
#   make clean     delete generated artifacts
#
# Stages marked (EE) call Google Earth Engine and need .secrets/ee-service-account.json.

PY := .venv/bin/python
PROC := data/processed
ASSETS := web_assets
APPDATA := flood-risk-app/frontend/public/data

.PHONY: all setup assets test clean help train app-data experiments paper-figures
.DEFAULT_GOAL := help

# ---------------------------------------------------------------- environment
setup:
	python3 -m venv .venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -e ".[api,dev]"

# ---------------------------------------------------------------- 1. SAR inventory (EE)
$(PROC)/flood_freq_dk.png: floodrisk/sar.py floodrisk/config.py scripts/build_sar_inventory.py
	$(PY) scripts/build_sar_inventory.py

# ---------------------------------------------------------------- 2. training table (EE)
$(PROC)/training.parquet: floodrisk/predictors.py floodrisk/sampling.py floodrisk/sar.py \
                          floodrisk/config.py scripts/build_training_table.py
	$(PY) scripts/build_training_table.py

# ---------------------------------------------------------------- 3. model
$(PROC)/model_metrics.json models/susceptibility_best.joblib $(PROC)/feature_importance.csv: \
		$(PROC)/training.parquet scripts/train_susceptibility.py floodrisk/predictors.py
	$(PY) scripts/train_susceptibility.py

train: $(PROC)/model_metrics.json

# ---------------------------------------------------------------- 4. susceptibility map (EE)
$(PROC)/susceptibility_map.png: floodrisk/susceptibility.py scripts/build_susceptibility_map.py \
                                $(PROC)/training.parquet
	$(PY) scripts/build_susceptibility_map.py

# ---------------------------------------------------------------- 5. road graph + risk raster (EE)
$(PROC)/dakshina_kannada_roads.graphml $(PROC)/susceptibility_dk.tif: \
		models/susceptibility_best.joblib $(ASSETS)/predictor_stack.tif \
		floodrisk/config.py floodrisk/locations.py scripts/build_road_graph.py
	$(PY) scripts/build_road_graph.py

# ---------------------------------------------------------------- 6. routing + dispatch
$(PROC)/route_comparison.png: $(PROC)/dakshina_kannada_roads.graphml scripts/flood_aware_route.py floodrisk/live.py
	$(PY) scripts/flood_aware_route.py

$(PROC)/quantum_dispatch.json: $(PROC)/dakshina_kannada_roads.graphml scripts/quantum_dispatch.py floodrisk/quantum.py
	$(PY) scripts/quantum_dispatch.py

# ---------------------------------------------------------------- 7. web assets
$(ASSETS)/roads_light.geojson $(ASSETS)/susceptibility_overlay.png: \
		$(PROC)/dakshina_kannada_roads.graphml $(PROC)/susceptibility_dk.tif \
		$(PROC)/quantum_dispatch.json scripts/export_web_assets.py
	$(PY) scripts/export_web_assets.py

$(ASSETS)/eta_all_may2025.json $(ASSETS)/hospitals.json: \
		$(PROC)/dakshina_kannada_roads.graphml scripts/export_multi_routes.py floodrisk/locations.py
	$(PY) scripts/export_multi_routes.py

$(ASSETS)/sar_extent.geojson: floodrisk/sar.py scripts/export_sar_extent.py
	$(PY) scripts/export_sar_extent.py

# Multi-band predictor raster — powers per-location SHAP explanation (/api/explain).
$(ASSETS)/predictor_stack.tif: floodrisk/predictors.py scripts/export_predictor_stack.py
	$(PY) scripts/export_predictor_stack.py

assets: $(ASSETS)/roads_light.geojson $(ASSETS)/eta_all_may2025.json \
        $(ASSETS)/sar_extent.geojson $(ASSETS)/predictor_stack.tif

# Training-run history / ablation comparison
experiments:
	$(PY) scripts/show_experiments.py

# Routing benchmark + all paper figures (real data only)
paper-figures:
	$(PY) scripts/benchmark_routing.py
	$(PY) scripts/make_paper_figures.py

# ---------------------------------------------------------------- journal paper
# Natural Earth outlines for the study-area map (public domain, ~15 MB, once).
NE_BASE = https://naciscdn.org/naturalearth
maps-data:
	mkdir -p data/external
	@test -f data/external/ne_110m_admin_0_countries.zip || \
	  curl -sSL -o data/external/ne_110m_admin_0_countries.zip \
	  $(NE_BASE)/110m/cultural/ne_110m_admin_0_countries.zip
	@test -f data/external/ne_10m_admin_1_states_provinces.zip || \
	  curl -sSL -o data/external/ne_10m_admin_1_states_provinces.zip \
	  $(NE_BASE)/10m/cultural/ne_10m_admin_1_states_provinces.zip
	@echo "Natural Earth outlines cached -> data/external/"

# The analyses added for the journal manuscript. Each writes a JSON artifact
# under data/processed that the figure and table generators read.
$(PROC)/sensitivity_sweep.json: scripts/sensitivity_sweep.py $(PROC)/dakshina_kannada_roads.graphml
	$(PY) scripts/sensitivity_sweep.py

$(PROC)/spatial_validation.json: scripts/spatial_validation.py $(PROC)/training.parquet
	$(PY) scripts/spatial_validation.py

$(PROC)/sar_validation.json: scripts/sar_validation.py $(PROC)/training.parquet
	$(PY) scripts/sar_validation.py

$(PROC)/qaoa_depth_study.json: scripts/qaoa_depth_study.py $(PROC)/quantum_dispatch.json
	$(PY) scripts/qaoa_depth_study.py

# Needs network (Open-Meteo ERA5 archive), so it is not a file-dependency target.
trigger-table:
	$(PY) scripts/trigger_table.py

$(PROC)/calibration_prior.json: scripts/calibration_prior.py $(PROC)/sar_validation.json
	$(PY) scripts/calibration_prior.py

$(PROC)/robustness.json: scripts/robustness.py $(PROC)/training.parquet
	$(PY) scripts/robustness.py

# Depends on trigger-table (network), so it is a phony target too.
trigger-sweep: trigger-table
	$(PY) scripts/trigger_sweep.py

journal-analyses: $(PROC)/sensitivity_sweep.json $(PROC)/spatial_validation.json \
                  $(PROC)/sar_validation.json $(PROC)/qaoa_depth_study.json \
                  $(PROC)/calibration_prior.json $(PROC)/robustness.json \
                  trigger-table trigger-sweep

journal-figures: journal-analyses maps-data
	$(PY) scripts/make_maps.py
	$(PY) scripts/make_analysis_figures.py

# Full journal manuscript: analyses -> figures -> typeset.
journal: paper-figures journal-figures
	cd paper && tectonic paper_journal.tex
	@echo "OK paper/paper_journal.pdf rebuilt from source data"

# Copy exported assets into the dashboard's served directory.
app-data: assets
	mkdir -p $(APPDATA)
	cp $(ASSETS)/*.json $(ASSETS)/*.geojson $(ASSETS)/*.png $(APPDATA)/
	@echo "dashboard data refreshed -> $(APPDATA)"

# ---------------------------------------------------------------- everything
all: $(PROC)/flood_freq_dk.png train $(PROC)/susceptibility_map.png \
     $(PROC)/route_comparison.png $(PROC)/quantum_dispatch.json app-data
	@echo "✓ full pipeline reproduced"

# ---------------------------------------------------------------- quality
test:
	$(PY) -m pytest -m "not network" -q

test-all:
	$(PY) -m pytest -q

clean:
	rm -rf $(PROC)/*.png $(PROC)/*.json $(PROC)/*.parquet $(PROC)/*.csv \
	       $(PROC)/*.graphml $(PROC)/*.tif models/*.joblib $(ASSETS)/*
	@echo "cleaned generated artifacts (source untouched)"

help:
	@echo "Dakshina Kannada flood-risk pipeline"
	@echo "  make setup     create .venv and install pinned deps + floodrisk"
	@echo "  make all       reproduce every artifact (needs Earth Engine creds)"
	@echo "  make train     retrain the susceptibility model only"
	@echo "  make assets    rebuild the dashboard's web assets"
	@echo "  make app-data  rebuild assets and copy into the dashboard"
	@echo "  make experiments  show training-run history / ablations"
	@echo "  make journal   rebuild the journal manuscript end-to-end"
	@echo "  make journal-analyses  run the sensitivity/validation analyses"
	@echo "  make maps-data download Natural Earth outlines for the maps"
	@echo "  make test      run invariant tests (no network)"
	@echo "  make clean     remove generated artifacts"
