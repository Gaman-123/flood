import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useAppStore } from "../lib/store";
import ExplainPanel from "./ExplainPanel";

const API = (process.env.REACT_APP_BACKEND_URL || "http://localhost:8000") + "/api";

export default function MapCanvas() {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const layersRef = useRef({ roads: null, routes: null, markers: [], ambMarkers: [] });
  
  const [startPoint, setStartPoint] = useState({ lat: 12.8700, lon: 74.8400 });
  const [targetPoint, setTargetPoint] = useState({ lat: 12.9100, lon: 74.8600 });
  const [benchResult, setBenchResult] = useState(null);
  const [loadingBench, setLoadingBench] = useState(false);
  const [explainPoint, setExplainPoint] = useState(null);

  const activeTab = useAppStore((s) => s.activeTab);
  const scenarioId = useAppStore((s) => s.scenarioId);
  const hospitals = useAppStore((s) => s.hospitals);
  const incidents = useAppStore((s) => s.incidents);
  const loadDispatchData = useAppStore((s) => s.loadDispatchData);

  useEffect(() => { loadDispatchData(); }, [loadDispatchData]);

  // ---- 1. Initialize Leaflet Map ----
  useEffect(() => {
    if (mapRef.current || !containerRef.current) return;

    const map = L.map(containerRef.current, {
      center: [12.87, 74.84],
      zoom: 12,
      zoomControl: false,
    });

    L.control.zoom({ position: "topright" }).addTo(map);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "© OpenStreetMap contributors",
    }).addTo(map);

    mapRef.current = map;

    // Click handler for 2-point routing
    map.on("click", (e) => {
      const lat = +e.latlng.lat.toFixed(5);
      const lon = +e.latlng.lng.toFixed(5);

      setStartPoint((prevStart) => {
        if (!prevStart) return { lat, lon };
        setTargetPoint({ lat, lon });
        return prevStart;
      });
    });
  }, []);

  // ---- 2. Run 3-Algorithm Benchmark when points change ----
  useEffect(() => {
    if (!startPoint || !targetPoint) return;
    setLoadingBench(true);

    fetch(`${API}/benchmark_2points?start_lat=${startPoint.lat}&start_lon=${startPoint.lon}&target_lat=${targetPoint.lat}&target_lon=${targetPoint.lon}`)
      .then((r) => r.json())
      .then((data) => {
        setBenchResult(data);
        drawBenchmarkPath(data.path);
      })
      .catch((err) => console.warn("Benchmark fetch failed:", err))
      .finally(() => setLoadingBench(false));
  }, [startPoint, targetPoint]);

  // ---- 3. Draw Path on Leaflet ----
  function drawBenchmarkPath(coords) {
    const map = mapRef.current;
    if (!map || !coords) return;

    if (layersRef.current.routes) {
      map.removeLayer(layersRef.current.routes);
    }

    const polyline = L.polyline(coords, {
      color: "#2563eb",
      weight: 5,
      opacity: 0.9,
      dashArray: "4, 6",
    }).addTo(map);

    layersRef.current.routes = polyline;
    map.fitBounds(polyline.getBounds(), { padding: [50, 50] });
  }

  // ---- 4. Render Markers for Hospitals & Incidents ----
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    // Clean existing markers
    layersRef.current.markers.forEach((m) => map.removeLayer(m));
    layersRef.current.markers = [];

    // Hospitals
    hospitals.forEach((h) => {
      const icon = L.divIcon({
        className: "custom-leaflet-marker",
        html: `<div style="background:#10b981;color:white;border-radius:50%;width:26px;height:26px;display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:12px;border:2px solid white;box-shadow:0 2px 6px rgba(0,0,0,0.3);">H</div>`,
        iconSize: [26, 26],
      });
      const m = L.marker([h.lat, h.lon], { icon }).addTo(map);
      m.bindPopup(`<b>${h.name || h.short}</b><br>Hospital Node`);
      layersRef.current.markers.push(m);
    });

    // Incidents
    incidents.forEach((i) => {
      const icon = L.divIcon({
        className: "custom-leaflet-marker",
        html: `<div style="background:#ef4444;color:white;border-radius:50%;width:26px;height:26px;display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:12px;border:2px solid white;box-shadow:0 2px 6px rgba(0,0,0,0.3);">!</div>`,
        iconSize: [26, 26],
      });
      const m = L.marker([i.lat, i.lon], { icon }).addTo(map);
      m.bindPopup(`<b>${i.name}</b><br>Emergency Call Location`);
      layersRef.current.markers.push(m);
    });

    // Start & Target Pins
    if (startPoint) {
      const sIcon = L.divIcon({
        html: `<div style="background:#3b82f6;color:white;padding:4px 8px;border-radius:12px;font-weight:bold;font-size:11px;border:2px solid white;box-shadow:0 2px 6px rgba(0,0,0,0.3);">🟢 Start</div>`,
        iconSize: [60, 24],
      });
      const sm = L.marker([startPoint.lat, startPoint.lon], { icon: sIcon }).addTo(map);
      layersRef.current.markers.push(sm);
    }

    if (targetPoint) {
      const tIcon = L.divIcon({
        html: `<div style="background:#dc2626;color:white;padding:4px 8px;border-radius:12px;font-weight:bold;font-size:11px;border:2px solid white;box-shadow:0 2px 6px rgba(0,0,0,0.3);">🔴 Destination</div>`,
        iconSize: [85, 24],
      });
      const tm = L.marker([targetPoint.lat, targetPoint.lon], { icon: tIcon }).addTo(map);
      layersRef.current.markers.push(tm);
    }

  }, [hospitals, incidents, startPoint, targetPoint]);

  return (
    <div style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
      {/* Map Container */}
      <div ref={containerRef} style={{ width: "100%", height: "100%", zIndex: 1 }} />

      {/* Floating 3-Algorithm Benchmark Panel */}
      <div style={{
        position: "absolute",
        left: 20,
        top: 20,
        zIndex: 1000,
        background: "rgba(255, 255, 255, 0.95)",
        backdropFilter: "blur(10px)",
        padding: "16px 20px",
        borderRadius: "14px",
        boxShadow: "0 10px 30px rgba(0,0,0,0.15)",
        maxWidth: 360,
        fontFamily: "system-ui, sans-serif"
      }}>
        <div style={{ fontWeight: 700, fontSize: 14, color: "#1e293b", marginBottom: 4 }}>
          ⚡ 3-Algorithm Performance Benchmark
        </div>
        <div style={{ fontSize: 11, color: "#64748b", marginBottom: 12 }}>
          Click anywhere on the map to set Start 🟢 and Destination 🔴 points.
        </div>

        {loadingBench ? (
          <div style={{ fontSize: 12, color: "#2563eb", fontWeight: 600 }}>Calculating optimal path...</div>
        ) : benchResult ? (
          <div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginBottom: 12 }}>
              <div style={{ background: "#eff6ff", padding: 8, borderRadius: 8, textAlign: "center", border: "1px solid #bfdbfe" }}>
                <div style={{ fontSize: 10, color: "#1e40af", fontWeight: 600 }}>Tsinghua C++</div>
                <div style={{ fontSize: 14, fontWeight: 800, color: "#1d4ed8" }}>{benchResult.benchmark?.tsinghua_c_ms} ms</div>
              </div>
              <div style={{ background: "#f8fafc", padding: 8, borderRadius: 8, textAlign: "center", border: "1px solid #e2e8f0" }}>
                <div style={{ fontSize: 10, color: "#475569", fontWeight: 600 }}>Dijkstra</div>
                <div style={{ fontSize: 14, fontWeight: 700, color: "#334155" }}>{benchResult.benchmark?.dijkstra_ms} ms</div>
              </div>
              <div style={{ background: "#f8fafc", padding: 8, borderRadius: 8, textAlign: "center", border: "1px solid #e2e8f0" }}>
                <div style={{ fontSize: 10, color: "#475569", fontWeight: 600 }}>A* Search</div>
                <div style={{ fontSize: 14, fontWeight: 700, color: "#334155" }}>{benchResult.benchmark?.astar_ms} ms</div>
              </div>
            </div>

            <div style={{ fontSize: 12, color: "#334155", display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
              <span>Best Path Distance:</span>
              <strong style={{ color: "#0f172a" }}>{benchResult.distance_km} km</strong>
            </div>
            <div style={{ fontSize: 12, color: "#334155", display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
              <span>Estimated Travel Time:</span>
              <strong style={{ color: "#0f172a" }}>{benchResult.estimated_mins} mins</strong>
            </div>
            <div style={{ fontSize: 12, color: "#334155", display: "flex", justifyContent: "space-between" }}>
              <span>Graph Hops:</span>
              <strong style={{ color: "#0f172a" }}>{benchResult.hops} nodes</strong>
            </div>
          </div>
        ) : null}
      </div>

      <ExplainPanel point={explainPoint} scenario={scenarioId} onClose={() => setExplainPoint(null)} />
    </div>
  );
}
