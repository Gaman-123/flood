import { useAppStore } from "../../lib/store";
import { Crosshair, Loader2, Siren, BellRing, Ambulance, Route } from "lucide-react";

// Pinpoint Emergency: click the map to drop an incident. The backend snaps it to the
// road graph, routes from every hospital under the current flood scenario, dispatches
// the optimal one, and notifies the nearest few. The Dijkstra-vs-A* panel shows how
// the live route was actually computed.

export default function EmergencyTab() {
  const res = useAppStore((s) => s.emergencyResult);
  const loading = useAppStore((s) => s.emergencyLoading);
  const error = useAppStore((s) => s.emergencyError);
  const pin = useAppStore((s) => s.emergency);
  const clear = useAppStore((s) => s.clearEmergency);
  const showSearch = useAppStore((s) => s.showSearch);
  const toggleSearch = useAppStore((s) => s.toggleSearch);
  const scenario = useAppStore((s) => s.scenarioId);

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <Siren size={16} style={{ color: "var(--danger)" }} />
        <div style={{ fontSize: 15, fontWeight: 600 }}>Pinpoint Emergency</div>
      </div>
      <div style={{ fontSize: 12, color: "var(--text-dim)", marginTop: 4, lineHeight: 1.5 }}>
        Click anywhere on the map to drop an emergency. The nearest hospital with a
        passable route is dispatched and neighbours are alerted, under the{" "}
        <b style={{ color: "var(--text)" }}>{scenario}</b> flood scenario.
      </div>

      {!pin && !res && (
        <div className="panel-sunken" style={{ marginTop: 14, padding: 16, textAlign: "center",
             color: "var(--text-dim)", fontSize: 12 }}>
          <Crosshair size={22} style={{ opacity: 0.5 }} />
          <div style={{ marginTop: 8 }}>Click the map to place an emergency</div>
        </div>
      )}

      {loading && (
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 14,
             color: "var(--text-dim)", fontSize: 12 }}>
          <Loader2 size={14} className="spin" /> routing from every hospital…
        </div>
      )}

      {error && <div style={{ marginTop: 14, fontSize: 12, color: "var(--danger)" }}>{error}</div>}

      {res && !res.reachable && (
        <div className="panel-sunken" style={{ marginTop: 14, padding: 14, borderLeft: "3px solid var(--danger)" }}>
          <div style={{ fontWeight: 600, color: "var(--danger)", fontSize: 13 }}>No route available</div>
          <div style={{ fontSize: 12, color: "var(--text-dim)", marginTop: 5, lineHeight: 1.5 }}>
            {res.message}
          </div>
        </div>
      )}

      {res && res.reachable && (
        <>
          {/* dispatched */}
          <div className="panel-sunken" style={{ marginTop: 14, padding: 14 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 7, color: "var(--safe)",
                 fontSize: 10, letterSpacing: 0.5 }}>
              <Ambulance size={13} /> AMBULANCE DISPATCHED
            </div>
            <div style={{ fontSize: 15, fontWeight: 600, marginTop: 6 }}>{res.optimal.name}</div>
            <div style={{ display: "flex", gap: 18, marginTop: 8 }}>
              <div>
                <div style={{ fontSize: 9.5, color: "var(--text-mute)" }}>ETA</div>
                <div className="mono" style={{ fontSize: 18, color: "var(--accent)" }}>{res.optimal.eta_min} min</div>
              </div>
              <div>
                <div style={{ fontSize: 9.5, color: "var(--text-mute)" }}>ROUTE</div>
                <div className="mono" style={{ fontSize: 18, color: "var(--text)" }}>flood-aware</div>
              </div>
            </div>
          </div>

          {/* notified */}
          <div style={{ marginTop: 14 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 10,
                 color: "var(--text-mute)", letterSpacing: 0.5, marginBottom: 7 }}>
              <BellRing size={11} /> HOSPITALS NOTIFIED ({res.notified.length})
            </div>
            {res.notified.map((n, i) => (
              <div key={n.id} style={{ display: "flex", justifyContent: "space-between",
                   alignItems: "center", fontSize: 12, padding: "5px 0",
                   color: i === 0 ? "var(--text)" : "var(--text-dim)" }}>
                <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span style={{ width: 6, height: 6, borderRadius: "50%",
                        background: i === 0 ? "var(--safe)" : "var(--accent)" }} />
                  {n.name}{i === 0 && <b style={{ color: "var(--safe)", fontSize: 10 }}> · dispatched</b>}
                </span>
                <span className="mono" style={{ color: "var(--text-dim)" }}>{n.eta_min} min</span>
              </div>
            ))}
            <div style={{ fontSize: 9.5, color: "var(--text-mute)", marginTop: 4 }}>
              Each receives a “notification received” alert on the map.
            </div>
          </div>

          {/* how the route was computed */}
          <div style={{ marginTop: 16 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center",
                 fontSize: 10, color: "var(--text-mute)", letterSpacing: 0.5, marginBottom: 8 }}>
              <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <Route size={11} /> HOW THE ROUTE WAS FOUND
              </span>
              <button className="chip" onClick={toggleSearch}
                style={{ cursor: "pointer", fontSize: 9.5, padding: "3px 9px",
                         color: showSearch ? "var(--accent)" : "var(--text-dim)" }}>
                {showSearch ? "hide search" : "show search"}
              </button>
            </div>
            <AlgoBar label="Dijkstra" sub="uniform search — no direction"
              nodes={res.algorithms.dijkstra.explored} max={res.algorithms.dijkstra.explored}
              ms={res.algorithms.dijkstra.ms} color="var(--watch)" />
            <AlgoBar label="A*" sub="guided by straight-line-time heuristic"
              nodes={res.algorithms.astar.explored} max={res.algorithms.dijkstra.explored}
              ms={res.algorithms.astar.ms} color="var(--accent)" />
            <div style={{ fontSize: 10.5, color: "var(--text-dim)", marginTop: 8, lineHeight: 1.5 }}>
              Both return the <b style={{ color: "var(--text)" }}>same optimal route</b>, but A*
              settled <b style={{ color: "var(--accent)" }}>{res.algorithms.speedup}× fewer</b> nodes
              by searching toward the goal — the reason live routing stays fast at city scale.
            </div>
          </div>

          <button className="chip" onClick={clear}
            style={{ cursor: "pointer", marginTop: 16 }}>Clear emergency</button>
        </>
      )}
    </div>
  );
}

function AlgoBar({ label, sub, nodes, max, ms, color }) {
  const w = Math.max(4, Math.min(100, (nodes / (max || 1)) * 100));
  return (
    <div style={{ marginBottom: 9 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11.5 }}>
        <span style={{ color: "var(--text)", fontWeight: 500 }}>{label}</span>
        <span className="mono" style={{ color: "var(--text-dim)" }}>
          {nodes.toLocaleString()} nodes · {ms} ms
        </span>
      </div>
      <div style={{ height: 6, background: "var(--surface-sunken)", borderRadius: 3,
           marginTop: 4, overflow: "hidden", boxShadow: "var(--neo-in-sm)" }}>
        <div style={{ width: `${w}%`, height: "100%", background: color,
             transition: "width .5s cubic-bezier(.22,1,.36,1)" }} />
      </div>
      <div style={{ fontSize: 9.5, color: "var(--text-mute)", marginTop: 2 }}>{sub}</div>
    </div>
  );
}
