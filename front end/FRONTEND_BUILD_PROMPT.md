# Build Prompt v2 — Redesign the flood-risk dashboard (repo-specific)

You are improving an EXISTING React app: the repo `krishxchowta/flood-risk`
(frontend = CRACO + React + Tailwind + shadcn/ui + MapLibre GL + deck.gl + zustand
+ recharts). **Keep the architecture and file structure — they are good.** Two
things are wrong and are your whole job:

1. **The map data is fake.** `frontend/src/lib/geoData.js` fabricates the
   susceptibility surface (hand-drawn river polylines), a random 12×10 road grid,
   and midpoint-offset "routes." DELETE all of that and wire the REAL exported
   data (provided — see §2). The numbers in `lib/scenarios.js` are already real;
   keep them.
2. **It doesn't look modern.** Redesign the UI to match the attached reference
   ("outletbuddy": dark control-room theme, left list panel with search + filter
   dropdowns + a scrollable entity list, map with circular pins + status badges,
   and a floating detail card that appears on selection). See §4–§5.

Do NOT invent data. Every spatial feature must come from the real asset files.

---

## 1. Ground truth: what the project is

Decision-support dashboard for flood-aware ambulance response in Dakshina Kannada
district (Mangaluru, coastal Karnataka, India). Pipeline behind it (already built):
Sentinel-1 SAR flood inventory → 12-factor ML susceptibility model (test AUC 0.962)
→ live rainfall/tide trigger T(t) → flood-aware routing on the real OSM graph
(11,910 nodes / 28,529 edges) → quantum (QAOA) dispatch allocation. Audience: a
non-technical control-room operator. Design bias: **simple, legible, one obvious
action per screen.**

---

## 1a. Stack decision — stay on MapLibre (do NOT switch to CesiumJS/Resium)

A "Python-Cesium" stack was considered and deliberately rejected for THIS project:
- Cesium's core advantage is rendering water **volume/depth** as a 3D surface. This
  project has NO depth data — the model outputs a relative *susceptibility index*
  and a 2D road graph. Cesium's killer feature has nothing to render here.
- MapLibre GL JS already does real 3D **terrain** (`map.setTerrain` + DEM tiles),
  sky, and globe — the "MapLibre is only 2.5D" claim is outdated. It gives the
  terrain-draped 3D we want with zero engine rewrite.
- Switching engines would rewrite the working `MapCanvas`/deck.gl layers — a direct
  violation of "keep the structure, don't break anything."
- KEEP: FastAPI, Google Earth Engine (offline data prep), Open-Meteo. SKIP: PostGIS
  (static assets don't need a spatial DB at this scale), PyFlo (stormwater pipe
  hydraulics — wrong tool), ML4Floods (duplicates the GEE SAR work already done).
- Cesium is a *future* option ONLY if a genuine water-depth model is added later
  (the depth-regression extension). Not now.

**Enable MapLibre 3D terrain (necessary change, non-breaking):** add a keyless
raster-DEM source and turn on terrain + sky, modest exaggeration:
```js
map.addSource("dem", { type:"raster-dem", tiles:[
  "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"],
  encoding:"terrarium", tileSize:256, maxzoom:14 });
map.setTerrain({ source:"dem", exaggeration:1.4 });
map.setSky({ "sky-color":"#0b1119", "horizon-color":"#0f1826", "fog-color":"#0b1119",
             "sky-type":"atmosphere" });
```
Pitch the camera (~55°) on load so the valley terrain reads in 3D. If AWS Terrarium
tiles are unreliable, MapTiler terrain-RGB (free key in env) is the fallback.

---

## 2. REAL data assets (provided in `web_assets/` — copy to `frontend/public/data/`)

These are genuine model outputs. Load them at runtime; replace `geoData.js` with a
thin loader (`lib/realData.js`) that `fetch`es these from `/data/...`.

| File | Type | Contents |
|---|---|---|
| `susceptibility_overlay.png` | RGBA raster | Turbo-colormapped S(x), 520×743, city bbox |
| `susceptibility_overlay.bounds.json` | JSON | `coordinates` (4 corners for MapLibre `image` source) + `bbox` |
| `roads_light.geojson` | FeatureCollection | **Use this for the risk overlay.** 9,190 risk-bearing edges (s>0.25, incl. all 4,867 flood-prone), 1.76 MB. The base street grid is drawn by MapLibre itself, so only risk edges need deck.gl. |
| `roads.geojson` | FeatureCollection | Full 28,529 LineStrings with `properties.s` (6 MB). Only load if you truly need every edge; otherwise prefer `roads_light`. |
| `routes_<id>.geojson` | FeatureCollection | For each scenario id ∈ {dry,live,aug2024,may2025,flash5}: LineStrings with `properties`: `kind` ("blind"\|"aware"), `hospital`, `incident`, `minutes`, `mean_exposure`, `max_exposure` |
| `blocked_<id>.geojson` | FeatureCollection | Impassable edges at that scenario's T (dry/live/aug2024 = 0; may2025 = 779; flash5 = 2646) |
| `dispatch.json` | JSON | Quantum dispatch: per-scenario ETA matrices, optimal assignment, QAOA approx-ratios |
| `manifest.json` | JSON | `generated`, live T + antecedent rainfall, per-scenario T values |

**MapLibre susceptibility overlay:** add an `image` source using
`bounds.coordinates`, render as a `raster` layer with `raster-opacity` scaled by the
active scenario's T (client-side — this IS R(x,t) = S(x)·T(t); instant on scenario
switch, no refetch).

---

## 3. REAL numbers already in `lib/scenarios.js` (keep) + corrected route facts

Model: AUC 0.962, acc 0.903, prec 0.906, recall 0.90, F1 0.903. Graph 11,910 nodes /
28,529 edges; 17.1% of edges flood-prone (S>0.5). Hospitals: Wenlock (12.8703,
74.8430), AJ Kuntikana (12.8892, 74.8478), KMC Attavar (12.8659, 74.8377).
Incidents: Kottara Chowki, Kulur, Pumpwell. Optimal assignment (unchanged dry→flood):
Wenlock→Kottara, AJ→Kulur, KMC→Pumpwell. QAOA p=1/2/3 ≈ 0.88/0.92/0.93.

**Use the REAL per-route facts from `routes_*.geojson` (not old hardcoded values):**
- may2025 AJ→Kulur: blind 6.7 min / mean-exp 0.310 → aware 19.5 min / mean-exp 0.107
  (the flagship reroute; also has the biggest exposure drop).
- may2025 Wenlock→Kottara & KMC→Pumpwell: blind == aware (route already safe — show
  "no safer alternative needed", do NOT fake a detour).
- flash5 (T=0.85): one hospital→incident pair has NO safe route (only 5 of 6 routes
  exist) — surface this as a red "ROUTE SEVERED" state; it's a real finding.

Read totals/means for the Results tab from the geojson `properties`, not memory.

---

## 4. Visual language — match the "outletbuddy" reference

- **Dark control-room theme.** Near-black panels (`#0a0f14`/`#0d1420`), soft
  1px borders (`#1b2735`), white text, muted secondary text (`#8aa0b6`).
- **Rounded everything:** panels `border-radius: 20px`, list cards 16px, pills full.
- **State colors:** green `#3ddc84` = clear/safe, amber `#f5b544` = watch,
  red `#ff5964` = danger/flooded. Keep the risk *ramp* (turbo overlay) distinct
  from these UI state colors.
- **Circular entity pins** on the map (like the brand logos): a white/colored disc
  with an icon, plus a small dark **status badge** hanging below it (outletbuddy's
  score chips) showing the entity's current number (hospital = assigned ETA;
  incident = flood-risk %).
- **Selected item** gets a bright accent ring (outletbuddy uses green) in BOTH the
  list and on the map pin, in sync.
- Smooth `framer-motion` transitions on card open, pin select, route draw.
- Typography: clean sans (Inter/Geist), tight tracking on headings, generous line
  height in body.

### 4a. Design tokens (define once in `index.css` / Tailwind theme; use everywhere)

```
/* color */
--bg-0:#070b10; --bg-1:#0b1119; --bg-2:#0f1826; --panel:#0d1420cc; /* glassy */
--line:#1b2735; --line-soft:#141d29;
--text:#eef4fb; --text-dim:#8aa0b6; --text-mute:#556b7f;
--accent:#4ea1ff;                 /* primary interactive */
--safe:#3ddc84; --watch:#f5b544; --danger:#ff5964;
--ring: 0 0 0 2px var(--accent);  /* selection ring */
/* radius */  --r-panel:20px; --r-card:16px; --r-chip:999px; --r-btn:12px;
/* space (8pt) */ 4 8 12 16 24 32 48
/* shadow */
--shadow-card: 0 8px 30px -8px #000a, 0 2px 8px -2px #0008;
--shadow-pop:  0 20px 60px -12px #000d, 0 4px 16px -4px #000a;
/* blur */ --glass: blur(14px) saturate(1.1);
/* type scale (px) */ 11 12 13 15 18 22 28   /* line-height 1.15 heads / 1.55 body */
```
- Panels/cards use `backdrop-filter: var(--glass)` over `--panel` for the modern
  glassy control-room feel. Borders are `1px solid var(--line)`, never pure black.
- Never more than one `--accent` element competing for attention per view.

### 4b. Motion system — THE point of this rebuild ("every click smooth")

Use **framer-motion** everywhere; no CSS `transition: all`. Central spring presets
(put in `lib/motion.js`, import them — do not hand-tune per component):

```
export const spring   = { type:"spring", stiffness:420, damping:34, mass:0.9 }; // default UI
export const springSoft= { type:"spring", stiffness:260, damping:30 };           // panels/cards
export const snappy    = { type:"spring", stiffness:600, damping:38 };           // small toggles
export const ease      = [0.22, 1, 0.36, 1];  // easeOutExpo-ish for opacity/tween
export const dur = { xs:0.12, sm:0.18, md:0.28, lg:0.42 };
```

Golden rules (enforce in review):
1. **GPU-only animation.** Animate `transform` + `opacity` + `filter` ONLY. Never
   animate `width/height/top/left/margin` (layout thrash → jank). Use framer
   `layout` / `layoutId` for size/position changes so they're FLIP-composited.
2. **60fps or it's a bug.** Every interaction must hold 60fps on a laptop. Heavy
   lists (`roads_light`) render on deck.gl/canvas, never as DOM.
3. **Instant feedback, <100ms.** Any click paints a state change within 100ms
   (press-scale, ring, skeleton) even if data is still loading. No dead clicks.
4. **Interruptible.** Springs must be re-targetable mid-flight (framer handles this)
   — a user clicking fast never sees a queue of stale animations.
5. **Respect `prefers-reduced-motion`:** collapse to `dur.xs` opacity fades.

Per-interaction choreography (implement exactly):
- **Button/list-item press:** `whileTap={{scale:0.97}}` + `whileHover={{scale:1.02, y:-1}}`
  with `snappy`. Cursor pointer, hover raises `--shadow-card`.
- **Tab switch (icon rail):** active pill slides via `layoutId="rail-active"` +
  `spring`; outgoing tab content exits `opacity→0, x:-8 (dur.sm)`, incoming enters
  `opacity 0→1, x:8→0 (dur.md, ease)`. Use `AnimatePresence mode="wait"`.
- **List item select:** accent ring animates in (`snappy`), item does a subtle
  `layout` lift; the corresponding **map pin** rings in sync (same selected id in
  store → both read it). No full-list re-render (memoize rows).
- **Detail card:** `AnimatePresence`; enter `opacity 0→1, scale 0.96→1, y:8→0`
  with `springSoft`; exit reverse at `dur.sm`. Anchored near the pin; never covers
  it — offset and, if needed, nudge the map with an eased `easeTo`.
- **Route draw:** when a route becomes active, animate the PathLayer as a
  "drawing" line — either deck.gl `TripsLayer` trail sweeping start→end over
  ~900ms, or animate a dash offset. The blue aware-route draws; the red blind-route
  fades in behind at 40% opacity. Never pop in instantly.
- **Scenario change:** susceptibility overlay `raster-opacity` tweens to the new T
  over `dur.lg` (eased), blocked-edges cross-fade, route layers swap under
  `AnimatePresence`. The whole map "breathes" to the new state in <500ms, no reload.
- **Pin hover:** scale 1→1.12 + shadow, badge lifts 2px (`snappy`). Pin select:
  scale 1.18 + accent ring + a one-shot pulse ring that expands & fades (`dur.lg`).
- **Map camera:** all programmatic moves use `map.easeTo/flyTo` with
  `duration:900, easing: t=>1-Math.pow(1-t,3)` (easeOutCubic). No jump-cuts.
- **Sim clock / ETA counters:** animate number changes with a tween (framer
  `animate()` on a motion value), not integer stepping — smooth count-down.
- **Dropdowns/popovers (radix):** wrap content in motion; enter
  `opacity/scale 0.98→1 (dur.sm)`; items stagger `0.02s`.
- **Loading:** skeleton shimmer (opacity pulse 1.2s) for any async panel; the map
  shows a soft radial spinner overlay while assets load — never a blank flash.

### 4c. Polish details that sell "aesthetic"
- Subtle grain/vignette on the map edges (radial `--bg-0` fade) so pins/cards pop.
- Route lines: rounded caps, slight glow (`shadow`/blur under the line), gradient
  from origin color → destination.
- Pins: soft drop shadow, thin white inner ring, brand/role icon centered.
- Status badges hang below pins with a small connector notch (like the reference).
- Focus-visible rings for keyboard users (accessibility, not just mouse).
- Consistent 8pt spacing; optical alignment of icons to text baselines.

---

## 5. Layout — adopt the outletbuddy 3-zone shape

```
┌──────┬──────────────────────────┬──────────────────────────────────┐
│ icon │  LIST PANEL (~380px)     │  MAP (fills remaining)            │
│ rail │  ┌────────────────────┐  │                                   │
│ 64px │  │ 🔍 Search…         │  │     ●Wenlock  [ETA 5.3]          │
│      │  ├─────────┬──────────┤  │        ╲                          │
│ Risk │  │Scenario▾│ Sort by▾ │  │         ╲___ blue route          │
│ Live │  │         │  [Filter]│  │              ●Kottara [risk 59%] │
│ Sim  │  ├────────────────────┤  │   ┌───────────────────────┐      │
│ Rslt │  │ ◉ Wenlock  5.3min  │  │   │ DETAIL CARD (floating)│      │
│ About│  │   clear ✓          │  │   │ Wenlock → Kottara     │      │
│      │  │ ○ AJ → Kulur 19.5' │  │   │ ETA 19.5m · exp −65%  │      │
│      │  │   rerouted ⚠       │  │   │ [More Details]        │      │
│      │  │ ○ KMC → Pumpwell   │  │   └───────────────────────┘      │
│      │  └────────────────────┘  │                                   │
└──────┴──────────────────────────┴──────────────────────────────────┘
```

- **Icon rail (64px, leftmost):** the existing 5 tabs (Risk / Live / Simulate /
  Results / About). Keep `LeftRail.jsx`, restyle to match.
- **List panel (~380px):** the outletbuddy sidebar. Top = search + two dropdowns +
  Filters; below = a scrollable list of **entities** whose meaning depends on the
  tab (see §6). This REPLACES the old fixed right-panel-holds-tab-content model:
  move tab content into this left list panel.
- **Map (fills the rest):** MapLibre 3D (add terrain via free DEM if a token isn't
  present; the repo already imports maplibre-gl). Circular hospital/incident pins
  with status badges. Routes as deck.gl `PathLayer`; animated ambulances as
  `TripsLayer`. Blocked edges as flashing red.
- **Detail card:** a floating, rounded popover over the map (NOT a docked panel)
  that appears when a list item or a map pin is selected — mirrors outletbuddy's
  store card. Must show the RIGHT info for that entity (see §6) and a "More
  Details" button that expands full stats.

---

## 6. Per-tab list contents + what selection reveals

Selection is unified: clicking a **list item** or its **map pin** selects the same
entity, rings both, draws its route(s), and opens the detail card.

### Risk Map
- Top dropdowns: **Scenario** (dry/live/aug2024/may2025/flash5) and **Sort by**
  (Risk ↓ / Name). Filters = layer toggles (Susceptibility, SAR extent, Rivers,
  Roads).
- List = the 3 incident sites + 3 hospitals as points of interest, each card
  showing its **local susceptibility** (sample the overlay / nearest road-edge s)
  as a colored pill.
- Overlay = `susceptibility_overlay.png` at opacity ∝ scenario T. SAR extent from
  `roads.geojson`? no — SAR polygons layer (if you have them; else omit gracefully).
- **Select an entity →** card: name, local risk pill, one-line plain-language
  explanation ("Low-lying, near Gurupura confluence — floods in heavy monsoon").
  Legend: *"Relative flood-risk exposure index (0–1) from satellite + terrain — not
  water depth."*

### Live
- List = live "vital signs": Trigger (from `manifest.json` live T + `/api/trigger`),
  24h/72h rainfall with IMD category, tide height/trend. Auto-refresh 10 min.
- One plain status headline, colored by T: e.g. "WATCH — 36 mm/72h, valley
  corridors elevated."
- Map shows R = S·T at the live trigger.
- **Optional supplementary layer — Google Flood Forecasting API:** if a key is
  present in env, add a small toggle "Google Flood Hub" that overlays Google's
  official flood forecast/gauge status for the region as an INDEPENDENT cross-check.
  Label it clearly as an external reference, secondary to this project's own SAR
  model (the model is the contribution; Google's API is corroboration, not the
  source of truth). If no key, hide the toggle gracefully — never hard-fail.

### Simulate  ← centerpiece
- Top: **Scenario dropdown** (primary control) + **▶ Run / ⏸ / ⟲** + speed 1×/4×/10×
  (the store already has a sim clock — reuse `simTime`, `tick`, `simSpeed`).
- List = the **3 dispatch pairs** (hospital→incident) as cards: origin→dest, live
  ETA counting down during a run, an exposure bar, and a status pill
  (En route / Rerouted / Arrived / **Severed**).
- Map: overlay morphs to scenario R; `blocked_<id>.geojson` edges flash red;
  ambulances animate from all hospitals to incidents along the **aware** route
  (blue), with the **blind** route (red, faint) alongside. Pins show live ETA.
- **⚡ Flash flood in 5 minutes** scenario (id `flash5`, mark it *illustrative*):
  a 5:00 countdown; the flood/blocked-edge set grows over the countdown (interpolate
  toward `blocked_flash5.geojson`); at least one incident pin drops; show a red
  route getting **cut** ("ROUTE SEVERED" — this is real at T=0.85) while another
  reroutes to higher ground and still arrives. End card ties to the −65% exposure
  reduction on the AJ→Kulur reroute.
- **Select a dispatch pair →** card: route stats from `routes_<id>.geojson`
  (blind vs aware minutes, mean/max exposure, "% exposure avoided"), assigned unit,
  arrival status.

### Results
- Read from `routes_<id>.geojson` + `dispatch.json`. Hero stat: for may2025 AJ→Kulur,
  "+12.8 min buys −65% mean flood exposure" (compute from the real props). Also the
  headline district stat: 17.1% of roads flood-prone.
- Exposure-vs-route sparkline (recharts) per selected route.
- Quantum panel: 3×3 ETA heatmap from `dispatch.json`, optimal assignment
  highlighted, QAOA approx-ratio bars (0.88/0.92/0.93) vs classical optimum = 1.0.
  Honest caption: *"At 3×3 the classical Hungarian solver is optimal and instant;
  QAOA demonstrates the scalable hybrid quantum-classical formulation."*

### About
- Plain-language method + data sources (Sentinel-1, Copernicus DEM, CHIRPS, ESA
  WorldCover, Open-Meteo, WorldTides, OpenStreetMap). Limitations, verbatim in
  spirit: susceptibility is a relative exposure index, NOT water depth; the
  impassability threshold is a heuristic pending a depth model; peak-exposure
  chokepoints are irreducible (limited river crossings); ambulance animation
  simulates the routing result, not live GPS.

---

## 7. Backend (`backend/server.py` — extend, don't rebuild)

Keep existing status/Mongo endpoints. Add:
- `GET /api/trigger` → live T + antecedent rainfall + tide (mirror `manifest.json`;
  wire to the real `floodrisk.live` module if the Python env is available, else
  serve the manifest value).
- `GET /api/scenario/{id}` → `{ T, routes_url, blocked_url, dispatch }`.
Everything spatial is served statically from `public/data/`.

---

## 8. Acceptance criteria

- `geoData.js` synthetic generators are gone; the map renders ONLY real assets.
- Susceptibility overlay opacity tracks scenario T; switching scenarios is instant.
- Selecting any hospital/incident/dispatch (list OR pin) rings both and opens a
  detail card with the CORRECT real info for that entity.
- Simulate animates ambulances on the REAL aware routes; may2025 AJ→Kulur visibly
  detours; flash5 shows a severed route.
- Every on-screen number traces to a real file (`routes_*`, `dispatch.json`,
  `scenarios.js`); nothing fabricated.
- Honest labels present (exposure-index-not-depth; simulation-not-GPS; QAOA-is-demo).
- Looks like the outletbuddy reference: dark, rounded, list+map+floating card,
  circular pins with status badges, accent-ring selection, smooth motion.
- No secrets in code; MapLibre needs no token (Mapbox token, if used, from env only).

### Motion/feel acceptance (hard pass/fail — the point of this rebuild)
- Every interaction in §4b is implemented with the shared springs from `lib/motion.js`
  (no ad-hoc `transition: all`, no animating width/height/top/left).
- Chrome DevTools Performance: interactions hold **60fps**; no long tasks >50ms on
  click; no layout-shift on hover/select.
- Every click shows feedback within **100ms** (press-scale + ring), even mid-load.
- Tab switch, list↔pin select, detail-card open, route draw, and scenario morph are
  all animated and interruptible — clicking rapidly never queues stale animations
  or flashes blank panels.
- `prefers-reduced-motion` collapses motion to quick fades without breaking layout.
- No dead states: async panels show skeletons; the map shows a spinner while assets
  load; there is never a blank white flash.
```
