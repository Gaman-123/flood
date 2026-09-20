// Practical multi-ambulance dispatch assignment over the REAL aware-route ETA
// matrix. Greedy nearest-available: each active incident is served by the closest
// hospital that still has a free ambulance and a non-severed flood-aware route.

export function greedyAssign(etaAware, hospitals, incidents, activeIds, fleetPerHospital) {
  const avail = {};
  hospitals.forEach((h) => { avail[h.id] = fleetPerHospital; });
  const active = incidents.filter((i) => activeIds.includes(i.id));

  const assignments = [];
  for (const inc of active) {
    let best = null;
    for (const h of hospitals) {
      if (avail[h.id] <= 0) continue;
      const eta = etaAware?.[h.id]?.[inc.id];
      if (eta == null) continue;                       // severed route — skip
      if (!best || eta < best.eta) best = { hospital: h.id, incident: inc.id, eta };
    }
    if (best) { assignments.push({ ...best, status: "assigned" }); avail[best.hospital] -= 1; }
    else assignments.push({ hospital: null, incident: inc.id, eta: null, status: "unreachable" });
  }
  return assignments;
}

// ---------------------------------------------------------------------------
// OPTIMAL assignment (Hungarian / Jonker-Volgenant on a rectangular cost matrix).
//
// This mirrors the research pipeline's dispatch layer: `floodrisk/quantum.py`
// encodes exactly this problem as a QUBO and solves it with QAOA, verified to
// agree with the Hungarian optimum. Greedy is a baseline; THIS is the result the
// paper argues, so the dashboard shows both.
// ---------------------------------------------------------------------------

const BIG = 1e6; // stand-in cost for severed/unavailable pairs

/** Hungarian algorithm (O(n^3), rectangular-safe). Returns rowAssignment[]. */
function hungarian(cost) {
  const n = cost.length, m = cost[0]?.length ?? 0;
  if (!n || !m) return [];
  const dim = Math.max(n, m);
  // pad to square with zero-cost dummies
  const a = Array.from({ length: dim }, (_, i) =>
    Array.from({ length: dim }, (_, j) => (i < n && j < m ? cost[i][j] : 0)));

  const u = new Array(dim + 1).fill(0);
  const v = new Array(dim + 1).fill(0);
  const p = new Array(dim + 1).fill(0);
  const way = new Array(dim + 1).fill(0);

  for (let i = 1; i <= dim; i++) {
    p[0] = i;
    let j0 = 0;
    const minv = new Array(dim + 1).fill(Infinity);
    const used = new Array(dim + 1).fill(false);
    do {
      used[j0] = true;
      const i0 = p[j0];
      let delta = Infinity, j1 = 0;
      for (let j = 1; j <= dim; j++) {
        if (used[j]) continue;
        const cur = a[i0 - 1][j - 1] - u[i0] - v[j];
        if (cur < minv[j]) { minv[j] = cur; way[j] = j0; }
        if (minv[j] < delta) { delta = minv[j]; j1 = j; }
      }
      for (let j = 0; j <= dim; j++) {
        if (used[j]) { u[p[j]] += delta; v[j] -= delta; }
        else minv[j] -= delta;
      }
      j0 = j1;
    } while (p[j0] !== 0);
    do { const j1 = way[j0]; p[j0] = p[j1]; j0 = j1; } while (j0);
  }

  const rowAssign = new Array(n).fill(-1);
  for (let j = 1; j <= dim; j++) {
    const i = p[j] - 1, jj = j - 1;
    if (i >= 0 && i < n && jj < m) rowAssign[i] = jj;
  }
  return rowAssign;
}

/**
 * Optimal fleet assignment minimising TOTAL response time.
 * Each ambulance (hospital replicated `fleetPerHospital` times) is a row;
 * each active incident is a column.
 */
export function optimalAssign(etaAware, hospitals, incidents, activeIds, fleetPerHospital) {
  const active = incidents.filter((i) => activeIds.includes(i.id));
  if (!active.length) return [];

  // one row per ambulance
  const units = [];
  hospitals.forEach((h) => {
    for (let k = 0; k < fleetPerHospital; k++) units.push(h.id);
  });
  if (!units.length) return active.map((inc) => ({ hospital: null, incident: inc.id, eta: null, status: "unreachable" }));

  const cost = units.map((hid) =>
    active.map((inc) => {
      const eta = etaAware?.[hid]?.[inc.id];
      return eta == null ? BIG : eta;
    }));

  const assign = hungarian(cost);
  const byIncident = new Map();
  assign.forEach((col, row) => {
    if (col < 0) return;
    const inc = active[col];
    const eta = etaAware?.[units[row]]?.[inc.id];
    if (eta == null) return;                     // severed — leave unserved
    byIncident.set(inc.id, { hospital: units[row], incident: inc.id, eta, status: "assigned" });
  });

  return active.map((inc) =>
    byIncident.get(inc.id) ?? { hospital: null, incident: inc.id, eta: null, status: "unreachable" });
}

// Total fleet time and how many incidents went unserved (no ambulance / severed).
export function dispatchSummary(assignments) {
  const served = assignments.filter((a) => a.hospital && a.eta != null);
  const totalMin = served.reduce((s, a) => s + a.eta, 0);
  return {
    served: served.length,
    unserved: assignments.length - served.length,
    totalMin: Math.round(totalMin * 10) / 10,
    maxMin: served.length ? Math.max(...served.map((a) => a.eta)) : 0,
  };
}
