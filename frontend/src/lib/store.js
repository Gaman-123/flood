import { create } from "zustand";

// Which precomputed routing solution each scenario uses. Only `dry` and `may2025`
// were solved on the real OSM graph; the others REUSE the nearest-trigger solution.
// This is surfaced in the UI (see etaIsShared) rather than silently implying every
// scenario has its own routing run.
export const ETA_SOURCE = {
  dry: "dry",
  live: "dry",          // live T is low (~0.1) -> dry-condition routing applies
  aug2024: "may2025",   // flood-condition routing
  may2025: "may2025",
  flash5: "may2025",
};

export const etaKeyFor = (scenarioId) => ETA_SOURCE[scenarioId] ?? "may2025";

/** True when the scenario displays a routing solution computed for a different scenario. */
export const etaIsShared = (scenarioId) => etaKeyFor(scenarioId) !== scenarioId;

export const useAppStore = create((set, get) => ({
  activeTab: "risk",
  setTab: (t) => set({ activeTab: t }),

  scenarioId: "may2025",
  setScenario: (s) => set({ scenarioId: s }),

  layers: {
    susceptibility: true,
    sar: true,
    rivers: true,
    roads: false,
  },
  toggleLayer: (k) =>
    set((state) => ({ layers: { ...state.layers, [k]: !state.layers[k] } })),

  // simulation clock in seconds
  simRunning: false,
  simTime: 0,
  simDuration: 25, // seconds of real time for a normal run
  simSpeed: 1,
  setSimRunning: (v) => set({ simRunning: v }),
  setSimSpeed: (v) => set({ simSpeed: v }),
  tick: (dt) => {
    const { simTime, simDuration, simSpeed, simRunning } = get();
    if (!simRunning) return;
    const next = simTime + dt * simSpeed;
    if (next >= simDuration) {
      set({ simTime: simDuration, simRunning: false });
    } else {
      set({ simTime: next });
    }
  },
  resetSim: () => set({ simTime: 0, simRunning: false }),

  // Flash-flood scripted state
  flashActive: false,
  setFlashActive: (v) => set({ flashActive: v }),

  // ---- expanded dispatch data (loaded once from /data) ----
  hospitals: [],
  incidents: [],
  etaAll: {}, // { dry:{blind,aware}, may2025:{blind,aware} }
  coverage: null,
  metrics: null,
  dataLoaded: false,
  async loadDispatchData() {
    if (get().dataLoaded) return;
    try {
      const [hospitals, incidents, etaDry, etaMay, coverage] = await Promise.all([
        fetch("/data/hospitals.json").then((r) => r.json()),
        fetch("/data/incidents.json").then((r) => r.json()),
        fetch("/data/eta_all_dry.json").then((r) => r.json()),
        fetch("/data/eta_all_may2025.json").then((r) => r.json()),
        fetch("/data/coverage.json").then((r) => r.json()),
      ]);
      set({
        hospitals, incidents, coverage,
        etaAll: { dry: etaDry, may2025: etaMay },
        activeIncidents: incidents.map((i) => i.id),
        dataLoaded: true,
      });
      const API = process.env.REACT_APP_BACKEND_URL || "http://localhost:8000";
      fetch(`${API}/api/metrics`).then((r) => r.ok ? r.json() : null)
        .then((metrics) => metrics && set({ metrics }))
        .catch(() => {});
    } catch (e) { console.warn("dispatch data load failed", e); }
  },

  // ---- flexible simulation controls ----
  fleetPerHospital: 1,
  setFleet: (n) => set({ fleetPerHospital: Math.max(1, Math.min(4, n)) }),
  activeIncidents: [],
  toggleIncident: (id) =>
    set((s) => ({
      activeIncidents: s.activeIncidents.includes(id)
        ? s.activeIncidents.filter((x) => x !== id)
        : [...s.activeIncidents, id],
    })),
  setAllIncidents: (on) =>
    set((s) => ({ activeIncidents: on ? s.incidents.map((i) => i.id) : [] })),

  // Camera directive from a voice/NL command ({action:"fly_to"|"follow_route", ...}).
  // MapCanvas consumes it and clears it, so each command fires exactly once.
  mapAction: null,
  setMapAction: (a) => set({ mapAction: a }),
  clearMapAction: () => set({ mapAction: null }),
  cinematicLabel: null,                    // caption shown during a cinematic move
  setCinematicLabel: (l) => set({ cinematicLabel: l }),

  // selected entity (hospital/incident) for detail popup + route highlight
  selected: null, // { kind:"hospital"|"incident", id }
  setSelected: (sel) => set({ selected: sel }),

  // right panel collapse (map-only view)
  panelOpen: true,
  togglePanel: () => set((s) => ({ panelOpen: !s.panelOpen })),

  // ---- Pinpoint Emergency ----
  emergency: null,           // { lat, lon } the dropped pin
  emergencyResult: null,     // dispatch response from /api/emergency
  emergencyLoading: false,
  emergencyError: null,
  showSearch: false,         // overlay the Dijkstra/A* explored nodes on the map
  toggleSearch: () => set((s) => ({ showSearch: !s.showSearch })),
  clearEmergency: () => set({ emergency: null, emergencyResult: null, emergencyError: null }),
  async runEmergency(lat, lon) {
    const API = process.env.REACT_APP_BACKEND_URL || "http://localhost:8000";
    set({ emergency: { lat, lon }, emergencyResult: null, emergencyError: null, emergencyLoading: true });
    try {
      const scenario = get().scenarioId;
      const r = await fetch(`${API}/api/emergency?lat=${lat}&lon=${lon}&scenario=${scenario}`,
                            { method: "POST" });
      if (!r.ok) throw new Error(`dispatch failed (${r.status})`);
      set({ emergencyResult: await r.json(), emergencyLoading: false });
    } catch (e) {
      set({ emergencyError: e.message || String(e), emergencyLoading: false });
    }
  },
}));
