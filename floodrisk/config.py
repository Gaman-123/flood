"""Shared configuration for the Dakshina Kannada flood-risk pipeline."""

# --- Earth Engine auth ---
EE_PROJECT = "gen-lang-client-0909626996"
EE_SERVICE_ACCOUNT = "flood-pipeline@gen-lang-client-0909626996.iam.gserviceaccount.com"
EE_KEY_PATH = ".secrets/ee-service-account.json"

# --- Area of interest: Dakshina Kannada district ---
# lon_min, lat_min, lon_max, lat_max. These bounds enclose the current
# administrative polygon returned by OpenStreetMap Nominatim and the FAO GAUL
# level-2 feature used in Earth Engine. They are deliberately a filter/extent;
# analysis and routing are clipped to the district polygon wherever possible.
DK_BBOX = [74.77, 12.45, 75.68, 13.19]
DK_PLACE_QUERY = "Dakshina Kannada, Karnataka, India"

# District-scale operational artifacts. One 120 m predictor stack drives both
# local SHAP explanations and the road-risk surface. Using the serialized
# XGBoost here removes the former GEE Random Forest approximation and keeps the
# full-district multi-band download within Earth Engine's synchronous limit.
ROUTING_RASTER_SCALE_M = 120
EXPLAIN_RASTER_SCALE_M = 120
DISTRICT_BOUNDARY_PATH = "data/processed/dakshina_kannada_boundary.geojson"
ROAD_GRAPH_PATH = "data/processed/dakshina_kannada_roads.graphml"
ROUTING_SUSCEPTIBILITY_PATH = "data/processed/susceptibility_dk.tif"

# --- Sentinel-1 acquisition geometry over DK (verified 2026-07-20) ---
# Only one orbit covers the district: relative orbit 63, descending, S1A, ~12-day revisit.
S1_ORBIT_PASS = "DESCENDING"
S1_REL_ORBIT = 63

# --- Monsoon windows used to build the multi-temporal SAR inventory ---
MONSOON_WINDOWS = [
    ("2024-06-01", "2024-09-30"),
    ("2025-05-15", "2025-09-30"),
]

# Dry-season reference window (low-flow, for a non-flood baseline backscatter)
DRY_WINDOWS = [
    ("2024-01-01", "2024-02-28"),
    ("2025-01-01", "2025-02-28"),
]

# --- SAR water detection parameters ---
SPECKLE_RADIUS_M = 30       # focal-median speckle filter radius
VV_WATER_THRESH_DB = -16.0  # VV backscatter below this => open/standing water (C-band)
VH_WATER_THRESH_DB = -22.0  # optional VH constraint

# JRC Global Surface Water: occurrence (%) at/above this = treat as permanent water, exclude
JRC_PERMANENT_OCCURRENCE = 80

# Floodable-lowland domain (from flood-pixel 90th percentiles): restricts BOTH classes
# so non-flood negatives are elevation/HAND-matched, not easy forested uplands.
DOMAIN_ELEV_MAX = 280   # metres
DOMAIN_HAND_MAX = 80    # metres above nearest drainage

# --- Output ---
OUTPUT_DIR = "data/processed"
