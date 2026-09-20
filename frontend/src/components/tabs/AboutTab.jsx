import { MODEL } from "../../lib/scenarios";
import { useAppStore } from "../../lib/store";
import { Info, ShieldAlert, Satellite, Database } from "lucide-react";

const SOURCES = [
  "Sentinel-1 SAR (Copernicus)",
  "SRTM elevation + MERIT Hydro",
  "CHIRPS rainfall reanalysis",
  "ESA WorldCover 2021",
  "Open-Meteo forecast API",
  "WorldTides tide gauges",
  "OpenStreetMap road graph",
];

export default function AboutTab() {
  const coverage = useAppStore((s) => s.coverage);
  const metrics = useAppStore((s) => s.metrics);
  const graph = coverage?.graph;
  const auc = metrics?.roc_auc ?? MODEL.auc;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }} data-testid="tab-about">
      <div>
        <div style={{ fontSize: 18, fontWeight: 600 }}>About</div>
        <div style={{ fontSize: 12, color: "var(--text-dim)" }}>Methodology, data sources, and honest limitations</div>
      </div>

      <div className="card-panel" style={{ padding: 14 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8, color: "var(--accent)", fontSize: 12, letterSpacing: 0.4, textTransform: "uppercase" }}>
          <Satellite size={13} /> Pipeline
        </div>
        <ol style={{ paddingLeft: 18, fontSize: 13, color: "var(--text)", lineHeight: 1.55, margin: 0 }}>
          <li>Sentinel-1 SAR flood-frequency inventory from 20 monsoon passes in 2024–2025.</li>
          <li>Nine-factor terrain, hydrology, and rainfall feature stack over Dakshina Kannada.</li>
          <li>XGBoost susceptibility model — <b className="mono">AUC {Number(auc).toFixed(3)}</b>.</li>
          <li>Five-site district rainfall monitoring modulates static S(x) into dynamic risk R.</li>
          <li>Flood-aware routing on a {graph ? graph.edges.toLocaleString() : "district-wide"}-edge OSM graph.</li>
          <li>Quantum-classical hybrid (QAOA) formulation of hospital→incident assignment.</li>
        </ol>
      </div>

      <div className="card-panel" style={{ padding: 14 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8, color: "var(--accent)", fontSize: 12, letterSpacing: 0.4, textTransform: "uppercase" }}>
          <Database size={13} /> Data sources
        </div>
        <ul style={{ paddingLeft: 18, fontSize: 12, color: "var(--text-dim)", lineHeight: 1.7, margin: 0 }}>
          {SOURCES.map((s) => <li key={s}>{s}</li>)}
        </ul>
      </div>

      <div className="card-panel" style={{ padding: 14, borderColor: "#8a6828", background: "rgba(207,143,28,0.12)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8, color: "#f5b74a", fontSize: 12, letterSpacing: 0.4, textTransform: "uppercase" }}>
          <ShieldAlert size={13} /> Limitations
        </div>
        <ul style={{ paddingLeft: 18, fontSize: 12, color: "#e8d5a8", lineHeight: 1.65, margin: 0 }}>
          <li>Susceptibility is a <b>relative exposure index</b>, not water depth or discharge.</li>
          <li>The impassability threshold is a heuristic pending a proper depth model.</li>
          <li>Peak-exposure chokepoints (river crossings) are irreducible given DK's limited bridges.</li>
          <li>Ambulance animation simulates the routing result, not live GPS.</li>
          <li>Hospital inclusion does not verify current ambulances, emergency capability, or capacity.</li>
          <li>The live trigger is the maximum of five rainfall sites; it is not a continuous rainfall field.</li>
          <li>QAOA results at this 3×3 scale are a scalability demo, not a quantum-supremacy claim.</li>
        </ul>
      </div>

      <div className="card-panel" style={{ padding: 12 }}>
        <div style={{ display: "flex", gap: 8, alignItems: "flex-start", fontSize: 11, color: "var(--text-dim)", lineHeight: 1.55 }}>
          <Info size={13} style={{ marginTop: 1, color: "var(--accent)" }} />
          <span>
            Audience: DK district emergency-management control-room operators. Design bias: one
            obvious action per screen, plain language, honest labels. Not a data-science tool — a
            decision tool.
          </span>
        </div>
      </div>
    </div>
  );
}
