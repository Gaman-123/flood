import { useAppStore } from "../../lib/store";
import { MODEL } from "../../lib/scenarios";
import { Info } from "lucide-react";

export default function RiskTab() {
  const layers = useAppStore((s) => s.layers);
  const toggle = useAppStore((s) => s.toggleLayer);
  const coverage = useAppStore((s) => s.coverage);
  const metrics = useAppStore((s) => s.metrics);
  const graph = coverage?.graph;
  const auc = metrics?.roc_auc ?? MODEL.auc;

  const rows = [
    { k: "susceptibility", label: "Susceptibility overlay S(x)", hint: "Model-derived relative risk" },
    { k: "sar",            label: "SAR observed flood extent",   hint: "Sentinel-1 historic water" },
    { k: "rivers",         label: "Rivers",                       hint: "Nethravathi, Gurupura" },
    { k: "roads",          label: "Road network (risk-colored)",
      hint: graph ? `${graph.flood_prone_pct}% flood-prone district-wide` : "District OSM network" },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }} data-testid="tab-risk">
      <SectionTitle title="Risk assessment" subtitle="Static exposure model draped on terrain" />
      <p style={{ fontSize: 13, color: "var(--text-dim)", lineHeight: 1.55, margin: 0 }}>
        The district view links coastal flooding, the Nethravathi and Gurupura valleys,
        and the Western Ghats runoff corridors to the operational road network.
      </p>

      <div className="card-panel" style={{ padding: 14 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 10, fontSize: 12, color: "var(--text-dim)", letterSpacing: 0.4, textTransform: "uppercase" }}>
          <Info size={12} /> Layers
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {rows.map(({ k, label, hint }) => (
            <label
              key={k}
              data-testid={`layer-toggle-${k}`}
              style={{ display: "flex", alignItems: "flex-start", gap: 10, cursor: "pointer", padding: 6, borderRadius: 6 }}
            >
              <input
                type="checkbox"
                checked={layers[k]}
                onChange={() => toggle(k)}
                style={{ marginTop: 3, accentColor: "var(--accent)" }}
              />
              <div>
                <div style={{ fontSize: 13, color: "var(--text)" }}>{label}</div>
                <div style={{ fontSize: 11, color: "var(--text-dim)" }}>{hint}</div>
              </div>
            </label>
          ))}
        </div>
      </div>

      <div className="card-panel" style={{ padding: 14 }}>
        <div style={{ fontSize: 12, color: "var(--text-dim)", letterSpacing: 0.4, textTransform: "uppercase", marginBottom: 8 }}>
          Model quality
        </div>
        <StatRow label="ROC-AUC" value={Number(auc).toFixed(3)} accent="var(--accent)" />
        <StatRow label="Road edges" value={graph ? graph.edges.toLocaleString() : "loading"} />
        <StatRow label="Flood-prone edges" value={graph ? `${graph.flood_prone_edges.toLocaleString()} (${graph.flood_prone_pct}%)` : "loading"} accent="#f59e0b" />
      </div>

      <div style={{ fontSize: 11, color: "var(--text-dim)", lineHeight: 1.5, padding: "8px 4px" }}>
        <b style={{ color: "var(--text-dim)" }}>What am I looking at?</b> A relative flood-risk exposure
        index (0–1) from a satellite-trained terrain/climate model — <b>not water depth</b>.
      </div>
    </div>
  );
}

function SectionTitle({ title, subtitle }) {
  return (
    <div>
      <div style={{ fontSize: 18, fontWeight: 600, letterSpacing: 0.2 }}>{title}</div>
      <div style={{ fontSize: 12, color: "var(--text-dim)" }}>{subtitle}</div>
    </div>
  );
}

function StatRow({ label, value, accent = "var(--text)" }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "5px 0", borderBottom: "1px solid var(--surface-sunken)" }}>
      <span style={{ fontSize: 12, color: "var(--text-dim)" }}>{label}</span>
      <span className="mono" style={{ fontSize: 13, color: accent, fontWeight: 600 }}>{value}</span>
    </div>
  );
}
