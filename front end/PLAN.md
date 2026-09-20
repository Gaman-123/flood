# Decision Support Dashboard — Plan (no code yet)

The final unbuilt block of the architecture diagram: a 3D map dashboard that
showcases (a) the overall flood risk assessment and (b) simulation of specific
emergency-response cases (May 2025, Aug 2024, live-now), on Mapbox.

---

## 1. What it must demonstrate (paper-driven, not feature-driven)

1. **Static susceptibility S(x)** — the district map draped on 3D terrain, so the
   valley-corridor pattern is visibly tied to topography (the whole point of 3D).
2. **Dynamic risk R(x,t) = S(x) × T(t)** — scenario switcher morphs the same
   surface between dry / live / Aug-2024 / May-2025 states.
3. **Emergency-response simulation** — animated ambulance on risk-blind (red) vs
   flood-aware (blue) routes, with live metrics: ETA, mean/max exposure,
   impassable-edge count. The "+3.8 min buys −54% exposure" story, interactive.
4. **Live mode** — current trigger from Open-Meteo + WorldTides, auto-refresh.

Non-goals for v1: auth, DBs, mobile, quantum toggle, multi-city.

## 2. Stack

| Layer | Choice | Why |
|---|---|---|
| Map | **Mapbox GL JS v3** | Native 3D terrain (`setTerrain` + DEM tiles), sky/fog, camera fly-throughs |
| Framework | **React 18 + Vite + TypeScript** | Fast dev loop; typed GeoJSON/state |
| Route/animation overlay | **deck.gl `TripsLayer`** (interleaved with Mapbox) | Ambulance trail animation over 3D terrain |
| Charts/panels | Recharts (small) | Trigger gauge, exposure-vs-time sparkline |
| State | Zustand (tiny) | Scenario/time state shared map ↔ panels |
| Backend | **FastAPI (Python)** in `backend/` | Reuses `floodrisk/` venv directly — live trigger, routing on demand |

Mapbox needs an access token → **you create the free Mapbox account + token
yourself** (50k map loads/mo free tier is plenty); token goes in
`front end/.env.local`, gitignored, never in code.

## 3. Data flow: precomputed vs live

**Precomputed once (export scripts, added to `scripts/`):**
- `susceptibility_district.png` + bounds JSON → Mapbox raster image overlay
  (already have the GeoTIFF; re-export colorized RGBA at ~90 m for the district,
  30 m for the city bbox)
- `routes_{scenario}.geojson` — both routes per scenario with per-edge risk,
  travel time, cumulative time (drives the animation + exposure sparkline)
- `blocked_edges_{scenario}.geojson` — the 789 May-2025 impassable segments
- `flood_extent_sar.geojson` — observed SAR flood polygons (ground-truth layer,
  toggleable — this is what makes it credible, not just model output)
- `metrics.json` — the comparison table numbers

**Live (FastAPI, thin):**
- `GET /api/trigger` → current T(t), antecedent rainfall, tide (calls
  `floodrisk.live`; cache 10 min)
- `GET /api/route?scenario=live` → recompute flood-aware route at current T
  (loads GraphML once at startup; ~1 s response)
- Everything else served static.

Risk morphing trick: ship S(x) once as the overlay; apply T(t) client-side via
`raster-opacity` / color-ramp interpolation. No server round-trip per scenario —
instant slider response, and it exactly mirrors R = S × T.

## 4. UI layout

```
┌──────────────────────────────────────────────┬───────────────┐
│                                              │  SCENARIO     │
│         3D MAP (Mapbox, terrain 1.5×)        │  ○ Dry        │
│                                              │  ● Live now   │
│  Layers: ☑ Susceptibility  ☑ SAR extent      │  ○ Aug 2024   │
│          ☑ Routes  ☑ Blocked edges           │  ○ May 2025   │
│                                              │  ─────────    │
│  [ambulance animating along blue route]      │  Trigger gauge│
│                                              │  T = 0.70     │
│                                              │  rain 24h/72h │
│                                              │  tide 0.49 m  │
│                                              │  ─────────    │
│                                              │  ROUTE PANEL  │
│                                              │  blind 13.6'  │
│                                              │  aware 17.4'  │
│                                              │  exposure −54%│
│                                              │  ▶ Simulate   │
└──────────────────────────────────────────────┴───────────────┘
```

- Camera presets: District overview → Mangaluru city → route fly-along.
- "Simulate" replays both ambulances simultaneously with a clock; exposure
  sparkline fills in as they drive; blocked edges flash where the red route
  would have crossed.

## 5. Folder structure

```
front end/
  PLAN.md            ← this file
  backend/           FastAPI app (imports ../floodrisk via path or editable install)
    main.py  routes.py  cache.py
  web/               Vite + React + TS
    src/
      map/           MapView, terrain setup, layers/, camera presets
      panels/        ScenarioPicker, TriggerGauge, RoutePanel, LayerToggle
      state/         store.ts (scenario, time, animation clock)
      api/           client.ts (typed fetchers)
    public/data/     precomputed exports (geojson, overlay png, metrics.json)
  .env.local         VITE_MAPBOX_TOKEN=...   (gitignored)
```

## 6. Build order (when we start)

1. Export scripts → `public/data/` artifacts (half the work, zero frontend risk)
2. Vite+React shell, Mapbox 3D terrain with satellite style, camera presets
3. Susceptibility overlay + SAR ground-truth layer + layer toggles
4. Scenario state + client-side T(t) morphing + trigger gauge (live API)
5. Routes layer + metrics panel
6. deck.gl ambulance animation + exposure sparkline
7. Polish: fly-throughs, legend, about-panel with model metrics (AUC, VIF story)

Estimated: steps 1–5 are one solid session; 6–7 a second.

## 7. Risks / honest notes

- **Mapbox token is the only external dependency** — free tier fine; if you'd
  rather avoid signup entirely, MapLibre + free DEM tiles (Terrarium/AWS) is the
  fallback, at the cost of slightly worse terrain/sky polish.
- 3D terrain exaggeration is presentation, not analysis — the paper figures stay
  the 2D matplotlib/GEE exports; dashboard is the demo layer.
- Ambulance animation is a *simulation of the routing result*, not live vehicle
  tracking — label it as such in the UI to keep the demo honest.
```
