# Mangalore Flood Prediction - Dataset Collection
## Overview
Complete dataset collection for a 30-day flood prediction system for Mangalore (Mangaluru), Karnataka, India.

## Dataset Structure
```
mangalore_flood_data/
├── rainfall/
│   ├── mangalore_rainfall_30days.csv    # 2,160 records @ 20-min intervals
│   └── rainfall_summary.json
├── tide/
│   ├── mangalore_tide_30days.csv        # 1,440 records @ 30-min intervals  
│   ├── mangalore_tidal_events.csv       # High/Low tide events only
│   └── tide_summary.json
├── river/
│   ├── mangalore_river_levels.csv       # 2,880 records, 4 rivers @ hourly
│   └── mangalore_river_geometry.json    # River path coordinates
├── elevation/
│   ├── mangalore_dem_150m.csv           # 6,150 grid points (150m resolution)
│   ├── mangalore_flood_zones_lt5m.csv   # High-risk zones <5m elevation
│   └── elevation_summary.json
├── roads/
│   ├── mangalore_roads.csv              # 16 road segments + bridges
│   ├── mangalore_bridges.csv            # 4 critical bridges
│   └── mangalore_roads.geojson          # GeoJSON for mapping
├── drainage/
│   ├── mangalore_drainage_network.csv   # 12 drainage channels
│   ├── mangalore_high_risk_drains.csv   # Overflow-risk drains
│   └── drainage_summary.json
└── metadata/
    └── master_dataset_catalog.json      # Full data dictionary + API references
```

## Real API Integration

| Dataset | Provider | URL | Cost |
|---------|----------|-----|------|
| Rainfall | OpenWeatherMap | https://openweathermap.org/api | Free tier available |
| Tide | WorldTides | https://www.worldtides.info/api/v3 | ~$10/month |
| River | CWC India / WRIS | https://indiawris.gov.in/wris/ | Free |
| Elevation | NASA SRTM (USGS) | https://earthexplorer.usgs.gov/ | Free |
| Roads | OpenStreetMap | https://download.geofabrik.de/ | Free |
| Drainage | OSM + DEM derived | QGIS flow accumulation | Free |

## Quick Start (Python)
```python
import pandas as pd

# Load all datasets
rain = pd.read_csv('rainfall/mangalore_rainfall_30days.csv', parse_dates=['timestamp'])
tide = pd.read_csv('tide/mangalore_tide_30days.csv', parse_dates=['timestamp'])
rivers = pd.read_csv('river/mangalore_river_levels.csv', parse_dates=['timestamp'])
dem = pd.read_csv('elevation/mangalore_dem_150m.csv')
roads = pd.read_csv('roads/mangalore_roads.csv')
drains = pd.read_csv('drainage/mangalore_drainage_network.csv')
```

## Flood Risk Formula
```python
flood_risk = (
    rain['rain_1h_mm'] * 0.35 +       # Rainfall weight
    tide['total_water_level_m'] * 0.25 + # Tidal contribution
    rivers['water_level_m'] * 0.25 +    # River level
    (100 - dem['elevation_m']) * 0.15   # Low-elevation penalty
)
```
