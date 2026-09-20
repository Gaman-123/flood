import { useEffect, useMemo } from "react";
import { useAppStore, etaKeyFor } from "../../lib/store";
import { SCENARIOS, SCENARIO_ORDER } from "../../lib/scenarios";
import { greedyAssign, dispatchSummary } from "../../lib/dispatch";
import { Play, Pause, RotateCcw, Zap, AlertTriangle, Minus, Plus } from "lucide-react";
import { stateColor } from "../../lib/colors";

export default function SimulateTab() {
  const scenarioId = useAppStore((s) => s.scenarioId);
  const setScenario = useAppStore((s) => s.setScenario);
  const simRunning = useAppStore((s) => s.simRunning);
  const setSimRunning = useAppStore((s) => s.setSimRunning);
  const simTime = useAppStore((s) => s.simTime);
  const simDuration = useAppStore((s) => s.simDuration);
  const simSpeed = useAppStore((s) => s.simSpeed);
  const setSimSpeed = useAppStore((s) => s.setSimSpeed);
  const resetSim = useAppStore((s) => s.resetSim);
  const setFlashActive = useAppStore((s) => s.setFlashActive);

  const hospitals = useAppStore((s) => s.hospitals);
  const incidents = useAppStore((s) => s.incidents);
  const etaAll = useAppStore((s) => s.etaAll);
  const dataLoaded = useAppStore((s) => s.dataLoaded);
  const loadDispatchData = useAppStore((s) => s.loadDispatchData);
  const fleetPerHospital = useAppStore((s) => s.fleetPerHospital);
  const setFleet = useAppStore((s) => s.setFleet);
  const activeIncidents = useAppStore((s) => s.activeIncidents);
  const toggleIncident = useAppStore((s) => s.toggleIncident);
  const setAllIncidents = useAppStore((s) => s.setAllIncidents);

  useEffect(() => { loadDispatchData(); }, [loadDispatchData]);

  const scenario = SCENARIOS[scenarioId];
  const isFlash = scenarioId === "flash5";
  const progress = Math.min(1, simTime / simDuration);
  const T = isFlash ? Math.min(1, 0.15 + progress * 0.9) : scenario.T;
  const stateC = stateColor(T);
  const etaKey = etaKeyFor(scenarioId);

  useEffect(() => { setFlashActive(isFlash); resetSim(); }, [scenarioId, isFlash, setFlashActive, resetSim]);

  const flashCountdown = isFlash ? Math.max(0, 300 - Math.floor(progress * 300)) : 0;
  const mm = String(Math.floor(flashCountdown / 60)).padStart(2, "0");
  const ss = String(flashCountdown % 60).padStart(2, "0");

  const assignments = useMemo(() => {
    if (!dataLoaded || !etaAll[etaKey]) return [];
    return greedyAssign(etaAll[etaKey].aware, hospitals, incidents, activeIncidents, fleetPerHospital);
  }, [dataLoaded, etaAll, etaKey, hospitals, incidents, activeIncidents, fleetPerHospital]);

  const summary = useMemo(() => dispatchSummary(assignments), [assignments]);
  const hById = useMemo(() => Object.fromEntries(hospitals.map((h) => [h.id, h])), [hospitals]);
  const iById = useMemo(() => Object.fromEntries(incidents.map((i) => [i.id, i])), [incidents]);
  const totalAmbulances = hospitals.length * fleetPerHospital;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }} data-testid="tab-simulate">
      <div>
        <div style={{ fontSize: 18, fontWeight: 600 }}>Simulate</div>
        <div style={{ fontSize: 12, color: "var(--text-dim)" }}>Multi-hospital dispatch over the real road network</div>
      </div>

      {/* scenario + run controls */}
      <div className="card-panel" style={{ padding: 14 }}>
        <label style={{ fontSize: 11, color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: 0.4 }}>Scenario</label>
        <select data-testid="scenario-select" value={scenarioId} onChange={(e) => setScenario(e.target.value)}
          style={{ width: "100%", marginTop: 6, padding: "10px 12px", background: "var(--surface)", color: "var(--text)", border: "1px solid var(--shadow-dark)", borderRadius: 8, fontSize: 13, cursor: "pointer" }}>
          {SCENARIO_ORDER.map((id) => <option key={id} value={id}>{SCENARIES_LABEL(id)}</option>)}
        </select>
        <div style={{ marginTop: 8 }}>
          <span className="chip" style={{ background: scenario.kind === "illustrative" ? "#3a2a10" : "rgba(42,169,107,0.10)", borderColor: scenario.kind === "illustrative" ? "#8a6828" : "#1e5a3a", color: scenario.kind === "illustrative" ? "#f5b74a" : "#5ac888" }}>
            {scenario.kind === "illustrative" ? <><Zap size={11} /> illustrative demo</> : <>data-driven</>}
          </span>
        </div>

        <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
          <button data-testid="run-sim" onClick={() => setSimRunning(!simRunning)}
            style={{ flex: 1, padding: "10px 12px", borderRadius: 8, background: simRunning ? "#3a2a10" : "var(--accent)", color: simRunning ? "#f5b74a" : "#e8f4ff", border: `1px solid ${simRunning ? "#8a6828" : "#1a7fbf"}`, fontWeight: 600, fontSize: 13, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 6 }}>
            {simRunning ? <><Pause size={14} /> Pause</> : <><Play size={14} /> Run simulation</>}
          </button>
          <button data-testid="reset-sim" onClick={resetSim} className="chip" style={{ cursor: "pointer", padding: "10px 12px" }}>
            <RotateCcw size={12} /> Reset
          </button>
        </div>

        <div style={{ display: "flex", gap: 4, marginTop: 10 }}>
          {[1, 4, 10].map((sp) => (
            <button key={sp} onClick={() => setSimSpeed(sp)}
              style={{ flex: 1, padding: "6px", borderRadius: 6, border: "1px solid var(--shadow-dark)", background: simSpeed === sp ? "rgba(63,116,201,0.10)" : "transparent", color: simSpeed === sp ? "var(--accent)" : "var(--text-dim)", fontSize: 11, cursor: "pointer", fontWeight: 600 }}>{sp}× speed</button>
          ))}
        </div>

        <div style={{ marginTop: 12, display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--text-dim)" }}>
          <span>Sim clock</span>
          <span className="mono" data-testid="sim-clock">{isFlash ? `T− ${mm}:${ss}` : `${simTime.toFixed(1)} / ${simDuration.toFixed(0)} s`}</span>
        </div>
        <div style={{ height: 4, background: "var(--surface-sunken)", borderRadius: 2, marginTop: 6, overflow: "hidden" }}>
          <div style={{ width: `${progress * 100}%`, height: "100%", background: stateC, transition: "width 0.1s linear" }} />
        </div>
      </div>

      {/* fleet + incidents */}
      <div className="card-panel" style={{ padding: 14 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontSize: 12, color: "var(--text-dim)" }}>Ambulances / hospital</span>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <button className="chip" style={{ cursor: "pointer", padding: 6 }} onClick={() => setFleet(fleetPerHospital - 1)}><Minus size={12} /></button>
            <span className="mono" style={{ minWidth: 18, textAlign: "center", color: "var(--accent)", fontWeight: 700 }}>{fleetPerHospital}</span>
            <button className="chip" style={{ cursor: "pointer", padding: 6 }} onClick={() => setFleet(fleetPerHospital + 1)}><Plus size={12} /></button>
          </div>
        </div>
        <div style={{ fontSize: 10, color: "var(--text-dim)", marginTop: 4 }}>
          {hospitals.length} hospitals · {totalAmbulances} ambulances total
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 12 }}>
          <span style={{ fontSize: 12, color: "var(--text-dim)" }}>Active incidents ({activeIncidents.length})</span>
          <div style={{ display: "flex", gap: 6 }}>
            <button className="chip" style={{ cursor: "pointer", fontSize: 10, padding: "3px 8px" }} onClick={() => setAllIncidents(true)}>All</button>
            <button className="chip" style={{ cursor: "pointer", fontSize: 10, padding: "3px 8px" }} onClick={() => setAllIncidents(false)}>None</button>
          </div>
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8 }}>
          {incidents.map((inc) => {
            const on = activeIncidents.includes(inc.id);
            return (
              <button key={inc.id} onClick={() => toggleIncident(inc.id)}
                style={{ fontSize: 11, padding: "4px 9px", borderRadius: 999, cursor: "pointer",
                  border: `1px solid ${on ? "var(--danger)88" : "var(--shadow-dark)"}`, background: on ? "#2a1418" : "transparent",
                  color: on ? "#ff8f98" : "var(--text-dim)", fontWeight: 600 }}>
                {inc.name}
              </button>
            );
          })}
        </div>
      </div>

      {/* dispatch board */}
      <div className="card-panel" style={{ padding: 14 }}>
        <div style={{ fontSize: 12, color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: 0.4, marginBottom: 10 }}>Dispatch board</div>
        {!dataLoaded && <div style={{ fontSize: 12, color: "var(--text-dim)" }}>Loading routes…</div>}
        {assignments.map((a) => {
          const inc = iById[a.incident];
          const hosp = a.hospital ? hById[a.hospital] : null;
          const remaining = a.eta != null ? Math.max(0, a.eta * (1 - progress)) : null;
          const status = a.status === "unreachable" ? "Severed" : progress >= 1 ? "Arrived" : "En route";
          return (
            <div key={a.incident} data-testid={`dispatch-${a.incident}`} style={{ padding: "10px 0", borderBottom: "1px solid var(--surface-sunken)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div style={{ fontSize: 13, color: "var(--text)" }}>
                  {hosp ? <><span style={{ color: "#5ac888" }}>+</span> {hosp.short}<span style={{ color: "var(--text-dim)", margin: "0 6px" }}>→</span></> : null}
                  <span style={{ color: "#ff8080" }}>⚠</span> {inc?.name}
                </div>
                <StatusPill status={status} />
              </div>
              {a.eta != null ? (
                <div style={{ display: "flex", justifyContent: "space-between", marginTop: 5, fontSize: 11, color: "var(--text-dim)" }}>
                  <span>ETA</span>
                  <span className="mono" style={{ color: "var(--text)" }}>{remaining.toFixed(1)} / {a.eta.toFixed(1)} min</span>
                </div>
              ) : (
                <div style={{ marginTop: 5, fontSize: 11, color: "#ff8f98" }}>No safe route at this flood level</div>
              )}
            </div>
          );
        })}
        <div style={{ marginTop: 10, display: "flex", justifyContent: "space-between", fontSize: 12 }}>
          <span style={{ color: "var(--text-dim)" }}>Fleet time · served</span>
          <span className="mono" style={{ color: "var(--accent)", fontWeight: 600 }}>{summary.totalMin} min · {summary.served}/{assignments.length}</span>
        </div>
        {summary.unserved > 0 && (
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
            <span style={{ color: "var(--text-dim)" }}>Unserved (no unit / severed)</span>
            <span className="mono" style={{ color: "#f59e0b", fontWeight: 600 }}>{summary.unserved}</span>
          </div>
        )}
      </div>

      {isFlash && (
        <div className="card-panel" style={{ padding: 12, borderColor: "#8a6828", background: "rgba(207,143,28,0.12)" }}>
          <div style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
            <AlertTriangle size={16} style={{ color: "#f5b74a", marginTop: 2 }} />
            <div style={{ fontSize: 11, color: "#f5b74a", lineHeight: 1.5 }}>
              <b>Illustrative dramatization.</b> The 5-min countdown is a teaching scenario — the routing/impassability model is real, but the flood-growth timing is scripted for clarity.
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function SCENARIES_LABEL(id) {
  const s = SCENARIOS[id];
  return `${s.label} (T=${s.T.toFixed(2)})`;
}

function StatusPill({ status }) {
  const map = {
    "En route": { c: "var(--accent)", bg: "rgba(63,116,201,0.10)" },
    "Arrived": { c: "#5ac888", bg: "rgba(42,169,107,0.10)" },
    "Severed": { c: "#ef4444", bg: "#3a1010" },
  };
  const st = map[status] || map["En route"];
  return (
    <span style={{ padding: "2px 8px", borderRadius: 999, fontSize: 10, fontWeight: 700, background: st.bg, color: st.c, border: `1px solid ${st.c}44`, letterSpacing: 0.5 }}>{status.toUpperCase()}</span>
  );
}
