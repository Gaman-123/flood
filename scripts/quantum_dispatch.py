"""Step 6: hybrid quantum-classical dispatch (QUBO + QAOA).

Classical layer: flood-aware Dijkstra on the risk-annotated OSM graph gives
risk-aware ETAs from each ambulance station to each incident site, per scenario.
Quantum layer: 3x3 assignment as a 9-qubit QUBO solved by QAOA (exact
statevector simulation), verified against brute force and Hungarian.

The result to watch: does the OPTIMAL DISPATCH PLAN change between calm and
May-2025 flood conditions? If yes, risk-aware dispatch is not just re-routing —
it re-allocates the fleet.
"""
import json
import os
import sys
from datetime import datetime, timezone

import networkx as nx
import numpy as np
import osmnx as ox
from scipy.optimize import linear_sum_assignment

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from floodrisk import config, live, locations, quantum  # noqa: E402

GRAPH = config.ROAD_GRAPH_PATH
OUT = "data/processed/quantum_dispatch.json"

PENALTY_W = 8.0
BLOCK = 0.60

_H = locations.by_id(locations.HOSPITALS)
_I = locations.by_id(locations.INCIDENTS)

# A district-spread 3x3 sub-instance keeps exact statevector simulation feasible
# while the classical dispatch layer uses all audited hospitals and demand points.
STATIONS = {_H[k]["name"]: (_H[k]["lat"], _H[k]["lon"])
            for k in locations.QUANTUM_HOSPITAL_IDS}
INCIDENTS = {_I[k]["name"]: (_I[k]["lat"], _I[k]["lon"])
             for k in locations.QUANTUM_INCIDENT_IDS}

SCENARIOS = {"drycalm": None,  # T = 0
             "may2025_flood": ("2025-05-25", "2025-06-02", "2025-05-30T06:00")}


def trigger_for(spec):
    if spec is None:
        return 0.0
    s, e, peak = spec
    t, p = live.fetch_openmeteo_archive(12.87, 74.84, s, e)
    when = datetime.fromisoformat(peak).replace(tzinfo=timezone.utc)
    return live.rainfall_trigger(live.antecedent_rainfall(t, p, now=when))


def eta_matrix(G, T, s_nodes, i_nodes):
    """Risk-aware ETA (minutes) station x incident under trigger T."""
    H = G.copy()
    removed = 0
    for u, v, k, d in list(H.edges(keys=True, data=True)):
        r = d.get("susceptibility", 0.0) * T
        if r >= BLOCK:
            H.remove_edge(u, v, k); removed += 1
        else:
            d["cost"] = d.get("travel_time", 0.0) * (1 + PENALTY_W * r)
    C = np.zeros((len(s_nodes), len(i_nodes)))
    for a, sn in enumerate(s_nodes):
        lengths = nx.single_source_dijkstra_path_length(H, sn, weight="cost")
        for i, dn in enumerate(i_nodes):
            if dn not in lengths:
                C[a, i] = 120.0  # unreachable sentinel (minutes)
            else:
                # report actual travel TIME on that risk-optimal path
                path = nx.dijkstra_path(H, sn, dn, weight="cost")
                t = sum(min(H[u][v].values(), key=lambda e: e.get("cost", 1e9))
                        .get("travel_time", 0.0) for u, v in zip(path[:-1], path[1:]))
                C[a, i] = t / 60.0
    return C, removed


def main():
    print(">> Step 6: hybrid quantum-classical dispatch (9-qubit QUBO/QAOA)")
    G = ox.io.load_graphml(GRAPH, edge_dtypes={"susceptibility": float})
    s_nodes = [ox.distance.nearest_nodes(G, lon, lat) for lat, lon in STATIONS.values()]
    i_nodes = [ox.distance.nearest_nodes(G, lon, lat) for lat, lon in INCIDENTS.values()]
    snames, inames = list(STATIONS), list(INCIDENTS)

    results = {}
    for scen, spec in SCENARIOS.items():
        T = trigger_for(spec)
        C, removed = eta_matrix(G, T, s_nodes, i_nodes)
        print(f"\n   === {scen} (T={T:.3f}, {removed} edges impassable) ===")
        print("   ETA matrix (min):")
        for a, sn in enumerate(snames):
            print(f"      {sn:24s} " + "  ".join(f"{C[a,i]:5.1f}" for i in range(len(inames))))

        # classical exact (Hungarian)
        rows, cols = linear_sum_assignment(C)
        hung = {snames[a]: inames[i] for a, i in zip(rows, cols)}
        hung_cost = float(C[rows, cols].sum())

        # QUBO + brute force + QAOA
        Q, off = quantum.build_assignment_qubo(C)
        bf = quantum.brute_force(Q, off)
        X = np.array(bf["bits"]).reshape(len(snames), len(inames))
        qubo_assign = {snames[a]: inames[int(np.argmax(X[a]))] for a in range(len(snames))}
        assert qubo_assign == hung, "QUBO optimum disagrees with Hungarian!"
        print(f"   Optimal dispatch (Hungarian == QUBO brute-force, {hung_cost:.1f} min total):")
        for k, v in hung.items():
            print(f"      {k:24s} -> {v}")

        qaoa, warm = {}, None
        for p in (1, 2, 3):
            r = quantum.qaoa_run(Q, off, p=p, init=warm)
            warm = quantum.interp_params(r["params"])
            qaoa[p] = r
            print(f"   QAOA p={p}: approx_ratio={r['approx_ratio']:.3f}  "
                  f"P(optimal)={r['prob_optimal']:.3f}  P(feasible)={r['prob_feasible']:.3f}")

        results[scen] = {"trigger": T, "removed_edges": removed,
                         "eta_min": C.tolist(), "stations": snames, "incidents": inames,
                         "optimal_assignment": hung, "optimal_cost_min": hung_cost,
                         "qaoa": {str(p): {k: v for k, v in r.items() if k != "top_states"}
                                  for p, r in qaoa.items()}}

    a0 = results["drycalm"]["optimal_assignment"]
    a1 = results["may2025_flood"]["optimal_assignment"]
    changed = {k for k in a0 if a0[k] != a1[k]}
    print("\n   Dispatch plan change dry -> flood:",
          ("NONE (same assignment)" if not changed else
           ", ".join(f"{k}: {a0[k]} -> {a1[k]}" for k in sorted(changed))))
    results["plan_changed"] = sorted(changed)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(results, open(OUT, "w"), indent=2)
    print(f"\n>> Saved: {OUT}")


if __name__ == "__main__":
    main()
