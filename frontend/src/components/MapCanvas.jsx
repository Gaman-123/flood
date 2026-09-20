import { useEffect, useRef, useState, useMemo } from "react";
import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";
import { useAppStore, etaKeyFor } from "../lib/store";
import { SCENARIOS } from "../lib/scenarios";
import { loadOverlay, loadRoads, loadBlocked, loadRoutes, splitRoutes, positionAlong } from "../lib/realData";
import { droneFlyTo, followRoute, cancelCinematic } from "../lib/cinematicCamera";
import { greedyAssign } from "../lib/dispatch";
import { riskColorCss } from "../lib/colors";
import GestureControl from "./GestureControl";
import ExplainPanel from "./ExplainPanel";

const MAPBOX_TOKEN = process.env.REACT_APP_MAPBOX_TOKEN || "";
if (MAPBOX_TOKEN) {
  mapboxgl.accessToken = MAPBOX_TOKEN;
}

const OSM_STYLE = {
  version: 8,
  sources: {
    "osm-raster-tiles": {
      type: "raster",
      tiles: [
        "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png",
        "https://b.tile.openstreetmap.org/{z}/{x}/{y}.png",
        "https://c.tile.openstreetmap.org/{z}/{x}/{y}.png"
      ],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors"
    }
  },
  layers: [
    {
      id: "osm-raster-layer",
      type: "raster",
      source: "osm-raster-tiles",
      minzoom: 0,
      maxzoom: 19
    }
  ]
};

const STYLE = MAPBOX_TOKEN ? "mapbox://styles/mapbox/light-v11" : OSM_STYLE;

const EMPTY = { type: "FeatureCollection", features: [] };
const ROAD_COLOR = ["interpolate", ["linear"], ["get", "s"],
  0.0, "#1e64b4", 0.25, "#46aac8", 0.5, "#f0dc5a", 0.75, "#f08c32", 1.0, "#dc2828"];

export default function MapCanvas() {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const readyRef = useRef(false);
  const dataRef = useRef({ awareByPair: {}, blindByPair: {} });
  const markersRef = useRef([]);
  const [, force] = useState(0);
  const [explainPoint, setExplainPoint] = useState(null);   // click-to-explain target
  const chaseRef = useRef(null);                            // active follow-route handle

  const activeTab = useAppStore((s) => s.activeTab);
  const scenarioId = useAppStore((s) => s.scenarioId);
  const uiLayers = useAppStore((s) => s.layers);
  const simTime = useAppStore((s) => s.simTime);
  const simDuration = useAppStore((s) => s.simDuration);
  const flashActive = useAppStore((s) => s.flashActive);
  const hospitals = useAppStore((s) => s.hospitals);
  const incidents = useAppStore((s) => s.incidents);
  const etaAll = useAppStore((s) => s.etaAll);
  const fleetPerHospital = useAppStore((s) => s.fleetPerHospital);
  const activeIncidents = useAppStore((s) => s.activeIncidents);
  const setSelected = useAppStore((s) => s.setSelected);
  const loadDispatchData = useAppStore((s) => s.loadDispatchData);
  const mapAction = useAppStore((s) => s.mapAction);
  const clearMapAction = useAppStore((s) => s.clearMapAction);
  const setMapAction = useAppStore((s) => s.setMapAction);
  const setCinematicLabel = useAppStore((s) => s.setCinematicLabel);
  const cinematicLabel = useAppStore((s) => s.cinematicLabel);
  const runEmergency = useAppStore((s) => s.runEmergency);
  const emergencyResult = useAppStore((s) => s.emergencyResult);
  const showSearch = useAppStore((s) => s.showSearch);

  const activeTabRef = useRef(activeTab);           // latest tab for the one-shot click handler
  useEffect(() => { activeTabRef.current = activeTab; }, [activeTab]);
  const emMarkersRef = useRef([]);                  // emergency pin + notification badges
  const emRafRef = useRef(null);                    // ambulance animation frame

  useEffect(() => { loadDispatchData(); }, [loadDispatchData]);

  const T = SCENARIOS[scenarioId].T;
  const flashProgress = flashActive ? Math.min(1, simTime / simDuration) : 0;
  const effT = scenarioId === "flash5" ? Math.min(1, 0.15 + flashProgress * 0.9) : T;
  const etaKey = etaKeyFor(scenarioId);

  const assignments = useMemo(() => {
    if (!hospitals.length || !etaAll[etaKey]) return [];
    return greedyAssign(etaAll[etaKey].aware, hospitals, incidents, activeIncidents, fleetPerHospital);
  }, [hospitals, incidents, etaAll, etaKey, activeIncidents, fleetPerHospital]);

  // ---- init map ----
  useEffect(() => {
    if (mapRef.current) return;
    const map = new mapboxgl.Map({
      container: containerRef.current, style: STYLE, center: [74.84, 12.87],
      zoom: 11, pitch: 30, bearing: 0, antialias: true, maxPitch: 80,
    });
    mapRef.current = map;
    if (process.env.NODE_ENV !== "production") window.__orionMap = map;  // dev introspection
    map.addControl(new mapboxgl.NavigationControl({ visualizePitch: true }), "top-right");

    // Track container size continuously (panel slide, window resize, etc.)
    const ro = new ResizeObserver(() => map.resize());
    ro.observe(containerRef.current);

    map.on("style.load", async () => {
      if (MAPBOX_TOKEN) {
        try {
          if (!map.getSource("mapbox-dem")) {
            map.addSource("mapbox-dem", { type: "raster-dem", url: "mapbox://mapbox.mapbox-terrain-dem-v1", tileSize: 512, maxzoom: 14 });
          }
          map.setTerrain({ source: "mapbox-dem", exaggeration: 1.5 });
        } catch (err) {
          console.warn("DEM terrain disabled:", err);
        }
        try {
          map.setFog({ range: [6, 18], color: "#eef1f6", "high-color": "#dbe6f5",
                       "horizon-blend": 0.08, "space-color": "#e6ecf5", "star-intensity": 0 });
        } catch {}

        if (map.getLayer("water")) map.setPaintProperty("water", "fill-color", "#a8c4e2");
        if (map.getLayer("waterway")) map.setPaintProperty("waterway", "line-color", "#8fb0d6");

        try {
          const firstSymbol = map.getStyle().layers.find((l) => l.type === "symbol")?.id;
          if (!map.getLayer("hillshade") && map.getSource("mapbox-dem")) {
            map.addLayer({
              id: "hillshade", type: "hillshade", source: "mapbox-dem",
              paint: {
                "hillshade-exaggeration": 0.9,
                "hillshade-shadow-color": "#8ba3c2",
                "hillshade-highlight-color": "#ffffff",
                "hillshade-accent-color": "#a9bad0",
              },
            }, firstSymbol);
          }
        } catch {}
      }
      // faint tint on vegetated/park land so it is not pure white
      ["landuse", "national-park"].forEach((id) => {
        if (!map.getLayer(id)) return;
        try {
          map.setPaintProperty(id, "fill-color", "#e4ebe3");
          map.setPaintProperty(id, "fill-opacity", 0.55);
        } catch { /* layer paint shape varies by style */ }
      });

      if (MAPBOX_TOKEN) {
        try {
          const lbl = map.getStyle().layers.find((l) => l.type === "symbol" && l.layout?.["text-field"])?.id;
          map.addLayer({
            id: "buildings-3d", type: "fill-extrusion", source: "composite", "source-layer": "building",
            minzoom: 13, filter: ["==", ["get", "extrude"], "true"],
            paint: { "fill-extrusion-color": "#cdd4e0", "fill-extrusion-height": ["get", "height"], "fill-extrusion-base": ["get", "min_height"], "fill-extrusion-opacity": 0.85 },
          }, lbl);
        } catch {}
      }

      try {
        const ov = await loadOverlay();
        map.addSource("susc", { type: "image", url: ov.url, coordinates: ov.coordinates });
        const beforeLayer = map.getLayer("buildings-3d") ? "buildings-3d" : undefined;
        map.addLayer({ id: "susc", type: "raster", source: "susc", paint: { "raster-opacity": 0.72, "raster-resampling": "linear", "raster-fade-duration": 300 } }, beforeLayer);
      } catch (e) { console.warn("overlay", e); }

      try {
        const roads = await loadRoads();
        map.addSource("roads", { type: "geojson", data: roads });
        map.addLayer({ id: "roads", type: "line", source: "roads", layout: { visibility: uiLayers.roads ? "visible" : "none", "line-cap": "round" }, paint: { "line-color": ROAD_COLOR, "line-width": ["interpolate", ["linear"], ["zoom"], 10, 0.6, 15, 2.2], "line-opacity": 0.9 } });
      } catch (e) { console.warn("roads", e); }

      try {
        const sar = await fetch("/data/sar_extent.geojson").then((r) => {
          if (!r.ok) throw new Error(`sar_extent.geojson ${r.status} — run scripts/export_sar_extent.py`);
          return r.json();
        });
        if (sar) {
          map.addSource("sar", { type: "geojson", data: sar });
          map.addLayer({ id: "sar", type: "fill", source: "sar", layout: { visibility: uiLayers.sar ? "visible" : "none" }, paint: { "fill-color": "#3f74c9", "fill-opacity": 0.28, "fill-outline-color": "#7fe0ff" } });
        }
      } catch (e) {
        // Ground-truth layer is credibility-critical — never fail silently.
        console.error("SAR observed-flood layer failed to load:", e);
      }

      for (const id of ["blind", "aware", "blocked", "ambu",
                        "em-explored-d", "em-explored-a", "em-route", "em-ambu"])
        map.addSource(id, { type: "geojson", data: EMPTY });
      map.addLayer({ id: "blind", type: "line", source: "blind", paint: { "line-color": "#d94459", "line-width": 3, "line-opacity": 0.5, "line-dasharray": [2, 1.5] } });
      map.addLayer({ id: "aware", type: "line", source: "aware", paint: { "line-color": "#3f74c9", "line-width": 5, "line-opacity": 0.95 } });
      map.addLayer({ id: "blocked", type: "line", source: "blocked", paint: { "line-color": "#d94459", "line-width": 3.5, "line-opacity": 0.9 } });
      map.addLayer({ id: "ambu", type: "circle", source: "ambu", paint: { "circle-radius": 7, "circle-color": "#ffffff", "circle-stroke-color": "#3f74c9", "circle-stroke-width": 3 } });

      // Pinpoint-Emergency layers: the search-frontier viz + the dispatched route + ambulance.
      map.addLayer({ id: "em-explored-d", type: "circle", source: "em-explored-d", layout: { visibility: "none" }, paint: { "circle-radius": 2.4, "circle-color": "#cf8f1c", "circle-opacity": 0.5 } });
      map.addLayer({ id: "em-explored-a", type: "circle", source: "em-explored-a", layout: { visibility: "none" }, paint: { "circle-radius": 2.6, "circle-color": "#3f74c9", "circle-opacity": 0.7 } });
      map.addLayer({ id: "em-route", type: "line", source: "em-route", paint: { "line-color": "#3f74c9", "line-width": 6, "line-opacity": 0.95, "line-cap": "round" } });
      map.addLayer({ id: "em-ambu", type: "circle", source: "em-ambu", paint: { "circle-radius": 8, "circle-color": "#ffffff", "circle-stroke-color": "#d94459", "circle-stroke-width": 4 } });

      readyRef.current = true;
      force((n) => n + 1);
      applyScenario();
      applyTabVisibility();
    });

    // Bare-map click. In the Pinpoint-Emergency tab it drops an emergency and dispatches;
    // everywhere else it explains why the point is risky. (Markers stopPropagation.)
    map.on("click", (e) => {
      const lat = +e.lngLat.lat.toFixed(5), lon = +e.lngLat.lng.toFixed(5);
      if (activeTabRef.current === "emergency") runEmergency(lat, lon);
      else setExplainPoint({ lat, lon });
    });
    map.getCanvas().style.cursor = "crosshair";
  }, []); // eslint-disable-line

  // ---- markers (rebuild when hospital/incident data loads) ----
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !readyRef.current || !hospitals.length) return;
    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];
    hospitals.forEach((h) => markersRef.current.push(mkMarker(map, h.lon, h.lat, h.short, "var(--safe)", "H", () => { setSelected({ kind: "hospital", id: h.id }); setMapAction({ action: "fly_to", lat: h.lat, lon: h.lon, label: h.name || h.short, zoom: 14.5 }); })));
    incidents.forEach((i) => markersRef.current.push(mkMarker(map, i.lon, i.lat, i.name, "var(--danger)", "!", () => { setSelected({ kind: "incident", id: i.id }); setMapAction({ action: "fly_to", lat: i.lat, lon: i.lon, label: i.name, zoom: 15 }); })));
    applyTabVisibility();
  }, [hospitals, incidents, readyRef.current]); // eslint-disable-line

  // ---- scenario / assignment -> routes ----
  async function applyScenario() {
    const map = mapRef.current;
    if (!map || !readyRef.current) return;
    if (map.getLayer("susc")) map.setPaintProperty("susc", "raster-opacity", 0.35 + 0.5 * effT);
    if (map.getLayer("roads")) map.setPaintProperty("roads", "line-opacity", 0.4 + 0.55 * effT);
    try {
      const routesFC = await fetch(`/data/routes_all_${etaKey}.geojson`).then((r) => r.json());
      dataRef.current.awareByPair = {}; dataRef.current.blindByPair = {};
      for (const f of routesFC.features) {
        const key = `${f.properties.hospital}_${f.properties.incident}`;
        if (f.properties.kind === "aware") dataRef.current.awareByPair[key] = f;
        else dataRef.current.blindByPair[key] = f;
      }
      const blockedFC = await loadBlocked(scenarioId).catch(() => EMPTY);
      map.getSource("blocked")?.setData(blockedFC);
      drawRoutes();
    } catch (e) { console.warn("routes", e); }
  }
  useEffect(() => { applyScenario(); }, [scenarioId, effT]); // eslint-disable-line

  function drawRoutes() {
    const map = mapRef.current;
    if (!map || !readyRef.current) return;
    const aware = [], blind = [];
    for (const a of assignments) {
      if (!a.hospital) continue;
      const key = `${a.hospital}_${a.incident}`;
      if (dataRef.current.awareByPair[key]) aware.push(dataRef.current.awareByPair[key]);
      if (dataRef.current.blindByPair[key]) blind.push(dataRef.current.blindByPair[key]);
    }
    map.getSource("aware")?.setData({ type: "FeatureCollection", features: aware });
    map.getSource("blind")?.setData({ type: "FeatureCollection", features: blind });
  }
  useEffect(() => { drawRoutes(); }, [assignments]); // eslint-disable-line

  // ---- tab visibility + camera ----
  function applyTabVisibility() {
    const map = mapRef.current;
    if (!map || !readyRef.current) return;
    const simOrRes = activeTab === "simulate" || activeTab === "results";
    const emergency = activeTab === "emergency";
    const vis = (id, on) => map.getLayer(id) && map.setLayoutProperty(id, "visibility", on ? "visible" : "none");
    vis("susc", uiLayers.susceptibility); vis("roads", uiLayers.roads); vis("sar", uiLayers.sar);
    if (map.getLayer("waterway")) map.setLayoutProperty(
      "waterway", "visibility", uiLayers.rivers ? "visible" : "none");
    vis("blind", simOrRes); vis("aware", simOrRes);
    vis("blocked", activeTab === "simulate"); vis("ambu", activeTab === "simulate");
    // emergency route/ambulance only in the Pinpoint tab
    vis("em-route", emergency); vis("em-ambu", emergency);
    // hospital markers visible where dispatch is shown (incident pins stay to simulate/results)
    document.querySelectorAll(".hi-marker").forEach((el) => { el.style.display = (simOrRes || emergency) ? "flex" : "none"; });
  }
  useEffect(() => {
    applyTabVisibility();
    const map = mapRef.current; if (!map) return;
    // District overview by default; entity clicks and emergency results zoom to the
    // local route without losing the full-coverage entry point.
    const cams = {
      risk: { center: [75.20, 12.82], zoom: 8.75, pitch: 38, bearing: -10 },
      live: { center: [75.20, 12.82], zoom: 8.75, pitch: 38, bearing: -10 },
      simulate: { center: [75.20, 12.82], zoom: 8.65, pitch: 42, bearing: -12 },
      emergency: { center: [75.20, 12.82], zoom: 8.65, pitch: 42, bearing: -12 },
      results: { center: [75.20, 12.82], zoom: 8.65, pitch: 36, bearing: -8 },
      about: { center: [75.20, 12.82], zoom: 8.55, pitch: 32, bearing: -8 },
    };
    map.easeTo({ ...cams[activeTab], duration: 1000, easing: (t) => 1 - Math.pow(1 - t, 3) });
  }, [activeTab, uiLayers]); // eslint-disable-line

  // ---- ambulance animation along assigned aware routes ----
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !readyRef.current || activeTab !== "simulate") return;
    const t = Math.min(1, simTime / simDuration);
    const feats = assignments.map((a) => {
      if (!a.hospital) return null;
      const f = dataRef.current.awareByPair[`${a.hospital}_${a.incident}`];
      if (!f) return null;
      return { type: "Feature", geometry: { type: "Point", coordinates: positionAlong(f.geometry.coordinates, t) }, properties: {} };
    }).filter(Boolean);
    map.getSource("ambu")?.setData({ type: "FeatureCollection", features: feats });
    if (map.getLayer("blocked")) map.setPaintProperty("blocked", "line-opacity", 0.5 + 0.4 * Math.abs(Math.sin(simTime * 3)));
  }, [simTime, activeTab, assignments, simDuration]);

  // ---- execute cinematic camera directives from voice / NL commands ----
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !readyRef.current || !mapAction) return;
    let cancelled = false;

    (async () => {
      chaseRef.current?.stop();
      cancelCinematic(map);

      if (mapAction.action === "fly_to") {
        setCinematicLabel(mapAction.label || null);
        await droneFlyTo(map, { lat: mapAction.lat, lon: mapAction.lon },
                         { zoom: mapAction.zoom || 15.6 });
        if (!cancelled) setTimeout(() => setCinematicLabel(null), 1200);
      }

      if (mapAction.action === "follow_route") {
        const key = mapAction.scenario === "dry" ? "dry" : "may2025";
        try {
          const fc = await loadRoutes(`all_${key}`);
          const feat = fc.features.find(
            (f) => f.properties.kind === "aware" &&
                   f.properties.hospital === mapAction.hospital &&
                   f.properties.incident === mapAction.incident);
          if (!feat) throw new Error("route not found");

          const coords = feat.geometry.coordinates;
          setCinematicLabel(mapAction.label || null);
          // Draw the route being followed, and hide the risk-blind comparison.
          map.getSource("aware")?.setData({ type: "FeatureCollection", features: [feat] });
          map.getSource("blind")?.setData(EMPTY);

          const chase = followRoute(map, coords, {
            durationMs: Math.min(26000, Math.max(9000, coords.length * 45)),
            onProgress: (t, pos) => {
              map.getSource("ambu")?.setData({
                type: "FeatureCollection",
                features: [{ type: "Feature", properties: {},
                             geometry: { type: "Point", coordinates: pos } }],
              });
            },
          });
          chaseRef.current = chase;
          await chase.promise;
          if (!cancelled) setTimeout(() => setCinematicLabel(null), 1200);
        } catch (e) {
          console.error("follow_route failed:", e);
          setCinematicLabel(null);
        }
      }
      if (!cancelled) clearMapAction();
    })();

    return () => { cancelled = true; };
  }, [mapAction]); // eslint-disable-line

  useEffect(() => () => { chaseRef.current?.stop(); }, []);

  // ---- Pinpoint Emergency: dispatch choreography ----
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !readyRef.current) return;
    const res = emergencyResult;

    // clear previous emergency markers + animation
    emMarkersRef.current.forEach((m) => m.remove());
    emMarkersRef.current = [];
    cancelAnimationFrame(emRafRef.current);
    ["em-route", "em-ambu", "em-explored-d", "em-explored-a"].forEach((id) => map.getSource(id)?.setData(EMPTY));
    if (!res) return;

    const ptsFC = (pts) => ({ type: "FeatureCollection", features: (pts || []).map((c) => ({ type: "Feature", geometry: { type: "Point", coordinates: c }, properties: {} })) });

    // the emergency pin (pulsing) always shows
    emMarkersRef.current.push(emergencyPin(map, res.emergency.lon, res.emergency.lat));

    if (!res.reachable) {
      map.flyTo({ center: [res.emergency.lon, res.emergency.lat], zoom: 13.6, pitch: 55, duration: 1600, essential: true });
      setCinematicLabel("No passable route — approaches flooded");
      setTimeout(() => setCinematicLabel(null), 2600);
      return;
    }

    const route = res.optimal.route;
    map.getSource("em-route").setData({ type: "FeatureCollection", features: [{ type: "Feature", geometry: { type: "LineString", coordinates: route }, properties: {} }] });
    map.getSource("em-explored-d").setData(ptsFC(res.algorithms.explored_dijkstra));
    map.getSource("em-explored-a").setData(ptsFC(res.algorithms.explored_a || res.algorithms.explored_astar));

    // close-up framing on the whole route
    const b = new mapboxgl.LngLatBounds();
    route.forEach((c) => b.extend(c));
    map.fitBounds(b, { padding: 90, pitch: 62, bearing: -18, duration: 1800, essential: true });
    setCinematicLabel(`Dispatching → ${res.optimal.name} · ${res.optimal.eta_min} min`);
    setTimeout(() => setCinematicLabel(null), 3200);

    // notified hospitals get a staggered "notification received" badge
    res.notified.forEach((n, i) => {
      const h = hospitals.find((x) => x.id === n.id);
      if (!h) return;
      const t = setTimeout(() => {
        emMarkersRef.current.push(notifyBadge(map, h.lon, h.lat, i === 0));
      }, 900 + i * 550);
      emMarkersRef.current.push({ remove: () => clearTimeout(t) });
    });

    // ambulance drives the route once the camera has settled
    const startAt = performance.now() + 2000;
    const dur = Math.min(9000, Math.max(3500, route.length * 28));
    const step = (now) => {
      const tt = Math.max(0, Math.min(1, (now - startAt) / dur));
      map.getSource("em-ambu")?.setData(ptsFC([positionAlong(route, tt)]));
      if (tt < 1) emRafRef.current = requestAnimationFrame(step);
    };
    emRafRef.current = requestAnimationFrame(step);
  }, [emergencyResult]); // eslint-disable-line

  // toggle the Dijkstra/A* search-frontier overlay
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !readyRef.current) return;
    const vis = showSearch && activeTab === "emergency" ? "visible" : "none";
    ["em-explored-d", "em-explored-a"].forEach((id) => map.getLayer(id) && map.setLayoutProperty(id, "visibility", vis));
  }, [showSearch, activeTab, emergencyResult]);

  useEffect(() => () => { emMarkersRef.current.forEach((m) => m.remove()); cancelAnimationFrame(emRafRef.current); }, []);

  return (
    <div style={{ position: "absolute", inset: 0 }}>
      <div ref={containerRef} className="map-canvas" style={{ position: "absolute", inset: 0 }} data-testid="map-canvas" />
      <MapLegend />
      <CameraPresets mapRef={mapRef} />
      <GestureControl mapRef={mapRef} />
      <ExplainPanel point={explainPoint} scenario={scenarioId} onClose={() => setExplainPoint(null)} />
      {cinematicLabel && (
        <div className="cine-caption" data-testid="cinematic-label"
          style={{ position: "absolute", left: "50%", top: 22, transform: "translateX(-50%)",
                   zIndex: 9, padding: "7px 16px", borderRadius: 999,
                   background: "var(--surface)cc", backdropFilter: "blur(14px) saturate(1.1)",
                   border: "1px solid var(--shadow-dark)", color: "var(--text)", fontSize: 12.5,
                   letterSpacing: 0.3, pointerEvents: "none",
                   boxShadow: "0 8px 30px -8px rgba(150,160,175,0.30)" }}>
          {cinematicLabel}
        </div>
      )}
    </div>
  );
}

function mkMarker(map, lon, lat, label, color, glyph, onClick) {
  const el = document.createElement("div");
  el.className = "hi-marker";
  el.style.cssText = "display:flex;align-items:center;gap:6px;cursor:pointer;transform:translateY(-2px);";
  const disc = document.createElement("div");
  disc.style.cssText = `width:22px;height:22px;border-radius:50%;background:${color};display:flex;align-items:center;justify-content:center;color:var(--surface-sunken);font-weight:800;font-size:12px;box-shadow:0 3px 10px rgba(150,160,175,0.30);border:2px solid #fff9;`;
  disc.textContent = glyph;
  const tag = document.createElement("div");
  tag.style.cssText = "background:var(--surface-raised)ee;color:var(--text);font-size:11px;font-weight:600;padding:2px 7px;border-radius:8px;border:1px solid var(--shadow-dark);white-space:nowrap;";
  tag.textContent = label;
  el.appendChild(disc); el.appendChild(tag);
  el.addEventListener("click", (e) => { e.stopPropagation(); onClick(); });
  return new mapboxgl.Marker({ element: el, anchor: "left" }).setLngLat([lon, lat]).addTo(map);
}

// Pulsing red emergency pin.
function emergencyPin(map, lon, lat) {
  const el = document.createElement("div");
  el.style.cssText = "position:relative;width:20px;height:20px;";
  el.innerHTML =
    '<span class="em-pulse"></span>' +
    '<span style="position:absolute;inset:4px;border-radius:50%;background:var(--danger);' +
    'box-shadow:0 2px 8px rgba(217,68,89,0.6);border:2px solid #fff;"></span>';
  return new mapboxgl.Marker({ element: el, anchor: "center" }).setLngLat([lon, lat]).addTo(map);
}

// "Notification received" badge on a notified hospital.
function notifyBadge(map, lon, lat, isDispatched) {
  const el = document.createElement("div");
  el.className = "notify-pop";
  el.style.cssText = "display:flex;flex-direction:column;align-items:center;gap:3px;transform:translateY(-4px);pointer-events:none;";
  const accent = isDispatched ? "var(--safe)" : "var(--accent)";
  el.innerHTML =
    `<div style="background:var(--surface-raised);color:${accent};font-size:10px;font-weight:600;` +
    `padding:3px 8px;border-radius:999px;box-shadow:var(--neo-out-sm);white-space:nowrap;">` +
    `${isDispatched ? "🚑 dispatched" : "🔔 notification received"}</div>` +
    `<div style="width:12px;height:12px;border-radius:50%;background:${accent};border:2px solid #fff;` +
    `box-shadow:0 2px 6px rgba(150,160,175,0.5);"></div>`;
  return new mapboxgl.Marker({ element: el, anchor: "bottom" }).setLngLat([lon, lat]).addTo(map);
}

function MapLegend() {
  return (
    <div data-testid="map-legend" className="card-panel" style={{ position: "absolute", left: 16, bottom: 16, zIndex: 5, padding: 12, borderRadius: 10, minWidth: 260 }}>
      <div style={{ fontSize: 11, color: "var(--text-dim)", marginBottom: 6, fontWeight: 500, letterSpacing: 0.4, textTransform: "uppercase" }}>Relative flood-risk exposure (0–1)</div>
      <div style={{ height: 10, borderRadius: 5, background: `linear-gradient(90deg, ${riskColorCss(0)}, ${riskColorCss(0.35)}, ${riskColorCss(0.6)}, ${riskColorCss(1)})` }} />
      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4, fontSize: 10, color: "var(--text-dim)" }}><span>Low</span><span>Elevated</span><span>High</span></div>
      <div style={{ marginTop: 8, fontSize: 10, color: "var(--text-dim)", lineHeight: 1.4 }}>Terrain + climate model. <b style={{ color: "var(--text)" }}>Not water depth.</b></div>
    </div>
  );
}

function CameraPresets({ mapRef }) {
  const go = (opts) => () => mapRef.current && mapRef.current.easeTo({ ...opts, duration: 1000, easing: (t) => 1 - Math.pow(1 - t, 3) });
  return (
    <div style={{ position: "absolute", right: 110, top: 16, zIndex: 5, display: "flex", gap: 6 }} data-testid="camera-presets">
      <button data-testid="preset-district" onClick={go({ center: [74.85, 12.90], zoom: 10.6, pitch: 55, bearing: 0 })} className="chip" style={{ cursor: "pointer" }}>District</button>
      <button data-testid="preset-city" onClick={go({ center: [74.845, 12.87], zoom: 13.2, pitch: 70, bearing: -25 })} className="chip" style={{ cursor: "pointer" }}>City close-up</button>
    </div>
  );
}
