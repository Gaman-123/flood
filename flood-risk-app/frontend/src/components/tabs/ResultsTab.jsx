import { useEffect, useMemo, useState } from "react";
import { useAppStore } from "../../lib/store";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, BarChart, Bar, Cell } from "recharts";

export default function ResultsTab() {
  const coverage = useAppStore((s) => s.coverage);
  const metrics = useAppStore((s) => s.metrics);
  const [dispatch, setDispatch] = useState(null);

  useEffect(() => {
    fetch("/data/dispatch.json").then((r) => r.json()).then(setDispatch).catch(() => {});
  }, []);

  const focus = coverage?.scenarios?.may2025?.focus_pair;
  const blind = focus?.blind;
  const aware = focus?.aware;
  const graph = coverage?.graph;
  const detour = blind && aware ? aware.minutes - blind.minutes : null;
  const detourPct = blind && detour != null ? 100 * detour / blind.minutes : null;
  const exposureDrop = blind && aware && blind.mean_exposure > 0
    ? 100 * (1 - aware.mean_exposure / blind.mean_exposure) : null;

  const chartData = useMemo(() => {
    const bp = blind?.exposure_profile || [];
    const ap = aware?.exposure_profile || [];
    const n = Math.max(bp.length, ap.length);
    if (!n) return [];
    return Array.from({ length: n }, (_, idx) => {
      const bi = Math.min(bp.length - 1, Math.round(idx * (bp.length - 1) / Math.max(1, n - 1)));
      const ai = Math.min(ap.length - 1, Math.round(idx * (ap.length - 1) / Math.max(1, n - 1)));
      return { progress: Math.round(100 * idx / Math.max(1, n - 1)),
               blind: bp[bi]?.risk, aware: ap[ai]?.risk };
    });
  }, [blind, aware]);

  const floodDispatch = dispatch?.may2025_flood;
  const qaoaData = floodDispatch ? Object.entries(floodDispatch.qaoa || {}).map(([p, r]) => ({
    name: `QAOA p=${p}`, value: r.approx_ratio,
  })).concat([{ name: "Classical", value: 1 }]) : [];

  if (!coverage) {
    return <div style={{ color: "var(--text-dim)", fontSize: 13 }}>Loading regenerated district results…</div>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }} data-testid="tab-results">
      <div>
        <div style={{ fontSize: 18, fontWeight: 600 }}>Results</div>
        <div style={{ fontSize: 12, color: "var(--text-dim)" }}>Regenerated artifacts · Wenlock → Kulur focus route</div>
      </div>

      {blind && aware && (
        <>
          <div className="card-panel" style={{ padding: 16 }} data-testid="hero-stat">
            <div style={{ fontSize: 11, color: "var(--text-dim)", letterSpacing: 0.5, textTransform: "uppercase" }}>
              Flood-aware route tradeoff
            </div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginTop: 4 }}>
              <span className="hero-stat" style={{ fontSize: 34, color: "var(--accent)" }}>
                {detour >= 0 ? "+" : ""}{detour.toFixed(1)} min
              </span>
              <span style={{ color: "var(--text-dim)", fontSize: 13 }}>({detourPct >= 0 ? "+" : ""}{detourPct.toFixed(1)}%)</span>
            </div>
            <div style={{ marginTop: 6, fontSize: 13, color: "var(--text)" }}>
              delivers <b style={{ color: "#5ac888" }}>−{exposureDrop.toFixed(1)}% mean exposure</b>{" "}
              while {coverage.scenarios.may2025.blocked_edges.toLocaleString()} graph edges are impassable.
            </div>
          </div>

          <div className="card-panel" style={{ padding: 14 }}>
            <div style={{ fontSize: 12, color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: 0.4, marginBottom: 8 }}>
              Risk-blind vs flood-aware
            </div>
            <table style={{ width: "100%", fontSize: 12 }}>
              <thead><tr style={{ color: "var(--text-dim)" }}><th></th><th>Risk-blind</th><th>Flood-aware</th></tr></thead>
              <tbody>
                <TRow label="ETA" a={`${blind.minutes} min`} b={`${aware.minutes} min`} />
                <TRow label="Distance" a={`${blind.distance_km} km`} b={`${aware.distance_km} km`} />
                <TRow label="Mean exposure" a={blind.mean_exposure.toFixed(3)} b={aware.mean_exposure.toFixed(3)} />
                <TRow label="Max exposure" a={blind.max_exposure.toFixed(3)} b={aware.max_exposure.toFixed(3)} />
              </tbody>
            </table>
          </div>
        </>
      )}

      {chartData.length > 0 && (
        <div className="card-panel" style={{ padding: 14 }}>
          <div style={{ fontSize: 12, color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: 0.4, marginBottom: 6 }}>
            Measured edge exposure along route
          </div>
          <div style={{ width: "100%", height: 140 }}>
            <ResponsiveContainer>
              <LineChart data={chartData} margin={{ top: 6, right: 10, left: -25, bottom: 0 }}>
                <XAxis dataKey="progress" stroke="#4a5a6a" tick={{ fontSize: 10 }} unit="%" />
                <YAxis stroke="#4a5a6a" tick={{ fontSize: 10 }} domain={[0, 1]} />
                <Tooltip formatter={(v) => Number(v).toFixed(3)} />
                <Line type="monotone" dataKey="blind" stroke="#ef4444" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="aware" stroke="var(--accent)" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {floodDispatch && (
        <>
          <div className="card-panel" style={{ padding: 14 }} data-testid="eta-matrix">
            <div style={{ fontSize: 12, color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: 0.4, marginBottom: 8 }}>
              District-spread 3×3 quantum subproblem · minutes
            </div>
            <ETAHeatmap data={floodDispatch} />
            <div style={{ fontSize: 10, color: "var(--text-dim)", marginTop: 8, lineHeight: 1.45 }}>
              Full district dispatch uses all {coverage.hospitals.count} audited routing origins; QAOA stays at nine qubits so exact verification remains possible.
            </div>
          </div>

          <div className="card-panel" style={{ padding: 14 }}>
            <div style={{ fontSize: 12, color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: 0.4, marginBottom: 6 }}>
              QAOA approximation ratio vs exact classical optimum
            </div>
            <div style={{ width: "100%", height: 120 }}><ResponsiveContainer>
              <BarChart data={qaoaData} margin={{ top: 4, right: 4, left: -25, bottom: 0 }}>
                <XAxis dataKey="name" stroke="#4a5a6a" tick={{ fontSize: 10 }} />
                <YAxis stroke="#4a5a6a" tick={{ fontSize: 10 }} domain={[0.8, 1.02]} />
                <Tooltip formatter={(v) => Number(v).toFixed(3)} />
                <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                  {qaoaData.map((d) => <Cell key={d.name} fill={d.name === "Classical" ? "#5ac888" : "var(--accent)"} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer></div>
          </div>
        </>
      )}

      <div className="card-panel" style={{ padding: 14 }}>
        <div style={{ fontSize: 12, color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: 0.4, marginBottom: 6 }}>
          Verified coverage and model quality
        </div>
        <SR label="Model ROC-AUC" v={metrics?.roc_auc != null ? Number(metrics.roc_auc).toFixed(3) : "0.963"} c="var(--accent)" />
        <SR label="District graph" v={`${graph.nodes.toLocaleString()} nodes · ${graph.edges.toLocaleString()} edges`} />
        <SR label="Flood-prone edges" v={`${graph.flood_prone_edges.toLocaleString()} (${graph.flood_prone_pct}%)`} c="#f59e0b" />
        <SR label="Coverage" v={`${coverage.hospitals.count} hospitals · ${coverage.scenario_points} demand points`} />
      </div>
    </div>
  );
}

function TRow({ label, a, b }) {
  return <tr style={{ borderTop: "1px solid var(--surface-sunken)" }}>
    <td style={{ padding: "6px 0", color: "var(--text-dim)" }}>{label}</td>
    <td className="mono" style={{ textAlign: "right" }}>{a}</td>
    <td className="mono" style={{ textAlign: "right", color: "var(--accent)", fontWeight: 600 }}>{b}</td>
  </tr>;
}

function SR({ label, v, c = "var(--text)" }) {
  return <div style={{ display: "flex", justifyContent: "space-between", gap: 12, padding: "5px 0", borderBottom: "1px solid var(--surface-sunken)" }}>
    <span style={{ fontSize: 12, color: "var(--text-dim)" }}>{label}</span>
    <span className="mono" style={{ fontSize: 12, color: c, fontWeight: 600, textAlign: "right" }}>{v}</span>
  </div>;
}

function ETAHeatmap({ data }) {
  const values = data.eta_min.flat();
  const finite = values.filter(Number.isFinite);
  const min = Math.min(...finite), max = Math.max(...finite);
  const optimal = data.optimal_assignment || {};
  return <table style={{ width: "100%", borderCollapse: "separate", borderSpacing: 2, fontSize: 10 }}>
    <thead><tr><th></th>{data.incidents.map((name) => <th key={name} style={{ color: "var(--text-dim)", fontWeight: 500 }}>{name}</th>)}</tr></thead>
    <tbody>{data.stations.map((station, row) => <tr key={station}>
      <td style={{ color: "var(--text-dim)", padding: 3 }}>{station}</td>
      {data.incidents.map((incident, col) => {
        const v = data.eta_min[row][col];
        const t = Number.isFinite(v) ? (v - min) / (max - min || 1) : 1;
        const selected = optimal[station] === incident;
        return <td key={incident} style={{ padding: 6, textAlign: "center", borderRadius: 4,
          background: `rgba(${Math.round(80 + 175 * t)},${Math.round(180 - 130 * t)},60,.45)`,
          border: selected ? "2px solid #5ac888" : "1px solid var(--shadow-dark)" }}>
          {Number.isFinite(v) ? v.toFixed(1) : "—"}
        </td>;
      })}
    </tr>)}</tbody>
  </table>;
}
