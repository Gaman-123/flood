"""Export REAL all-pairs routes for an expanded hospital/incident set.

Enables flexible multi-ambulance simulation: every hospital->incident route is
precomputed (flood-aware + risk-blind) on the real OSM graph, so the frontend can
assign any number of ambulances to any incidents and draw genuine routes without a
live routing server.

Outputs (into web_assets/):
  hospitals.json, incidents.json
  routes_all_<scenario>.geojson   (kind, hospital, incident, minutes, mean_exposure)
  eta_all_<scenario>.json         (minutes[hospital][incident], per kind)
"""
import json
import os
import sys

import numpy as np
import osmnx as ox
from shapely.geometry import LineString

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from floodrisk import config, locations  # noqa: E402

PROC = "data/processed"
OUT = "web_assets"
GRAPH = config.ROAD_GRAPH_PATH
PENALTY, BLOCK = 8.0, 0.60

HOSPITALS = locations.HOSPITALS
INCIDENTS = locations.INCIDENTS
SCENARIOS = {"dry": 0.00, "may2025": 0.70}


def edge_geom(G, u, v, weight="travel_time"):
    d = min(G[u][v].values(), key=lambda e: e.get(weight, 1e9))
    if "geometry" in d:
        coords = list(d["geometry"].coords)
        ux, uy = G.nodes[u]["x"], G.nodes[u]["y"]
        if ((coords[-1][0] - ux) ** 2 + (coords[-1][1] - uy) ** 2
                < (coords[0][0] - ux) ** 2 + (coords[0][1] - uy) ** 2):
            coords.reverse()
        return [[round(x, 5), round(y, 5)] for x, y in coords]
    return [[round(G.nodes[u]["x"], 5), round(G.nodes[u]["y"], 5)],
            [round(G.nodes[v]["x"], 5), round(G.nodes[v]["y"], 5)]]


def route_feature(G, route, kind, hid, iid, T):
    pts, mins, exp, dist_m = [], 0.0, [], 0.0
    cumulative_km = []
    for a, b in zip(route[:-1], route[1:]):
        edge_weight = "cost" if kind == "aware" else "travel_time"
        d = min(G[a][b].values(), key=lambda e: e.get(edge_weight, 1e9))
        for p in edge_geom(G, a, b, edge_weight):
            if not pts or p != pts[-1]:
                pts.append(p)
        mins += d.get("travel_time", 0.0) / 60.0
        dist_m += d.get("length", 0.0)
        exp.append(d.get("susceptibility", 0.0) * T)
        cumulative_km.append(round(dist_m / 1000.0, 3))
    props = {"kind": kind, "hospital": hid, "incident": iid,
             "minutes": round(mins, 1),
             "distance_km": round(dist_m / 1000.0, 2),
             "mean_exposure": round(float(np.mean(exp)) if exp else 0.0, 3),
             "max_exposure": round(float(max(exp)) if exp else 0.0, 3)}
    # Keep the full evidence profile for the dashboard's real-data results chart
    # only on its named focus pair; repeating it for every matrix cell bloats the
    # static asset without adding analytical value.
    if hid == "wenlock" and iid == "kulur":
        step = max(1, len(exp) // 80)
        props["exposure_profile"] = [
            {"distance_km": cumulative_km[j], "risk": round(float(exp[j]), 4)}
            for j in range(0, len(exp), step)
        ]
    # Three-to-five metre visual simplification keeps the all-pairs browser
    # assets tractable without altering ETA, distance or exposure calculations.
    if len(pts) > 2:
        pts = [[round(x, 5), round(y, 5)]
               for x, y in LineString(pts).simplify(0.00004).coords]
    return {
        "type": "Feature",
        "properties": props,
        "geometry": {"type": "LineString", "coordinates": pts},
    }, round(mins, 1)


def main():
    os.makedirs(OUT, exist_ok=True)
    print(">> Expanded multi-hospital route export")
    G = ox.io.load_graphml(GRAPH, edge_dtypes={
        "susceptibility": float, "travel_time": float, "length": float})
    print(f"   graph {G.number_of_nodes()} nodes / {G.number_of_edges()} edges")

    hnode = {h["id"]: ox.distance.nearest_nodes(G, h["lon"], h["lat"]) for h in HOSPITALS}
    inode = {i["id"]: ox.distance.nearest_nodes(G, i["lon"], i["lat"]) for i in INCIDENTS}

    json.dump(HOSPITALS, open(f"{OUT}/hospitals.json", "w"), indent=2)
    json.dump(INCIDENTS, open(f"{OUT}/incidents.json", "w"), indent=2)

    scenario_summary = {}
    for sid, T in SCENARIOS.items():
        # aware graph: prune blocked edges + cost weights (build once per scenario)
        Ga = G.copy()
        removed = 0
        for a, b, k, dd in list(Ga.edges(keys=True, data=True)):
            r = dd.get("susceptibility", 0.0) * T
            if r >= BLOCK:
                Ga.remove_edge(a, b, k); removed += 1
            else:
                dd["cost"] = dd.get("travel_time", 0.0) * (1 + PENALTY * r)

        feats, eta = [], {"blind": {}, "aware": {}}
        for h in HOSPITALS:
            eta["blind"][h["id"]], eta["aware"][h["id"]] = {}, {}
            for i in INCIDENTS:
                try:
                    rb = ox.routing.shortest_path(G, hnode[h["id"]], inode[i["id"]], weight="travel_time")
                    fb, mb = route_feature(G, rb, "blind", h["id"], i["id"], T)
                    feats.append(fb); eta["blind"][h["id"]][i["id"]] = mb
                except Exception:
                    eta["blind"][h["id"]][i["id"]] = None
                try:
                    ra = ox.routing.shortest_path(Ga, hnode[h["id"]], inode[i["id"]], weight="cost")
                    fa, ma = route_feature(Ga, ra, "aware", h["id"], i["id"], T)
                    feats.append(fa); eta["aware"][h["id"]][i["id"]] = ma
                except Exception:
                    eta["aware"][h["id"]][i["id"]] = None
        json.dump({"type": "FeatureCollection", "features": feats},
                  open(f"{OUT}/routes_all_{sid}.geojson", "w"), separators=(",", ":"))
        json.dump(eta, open(f"{OUT}/eta_all_{sid}.json", "w"))
        got = sum(1 for h in HOSPITALS for i in INCIDENTS if eta["aware"][h["id"]][i["id"]] is not None)
        focus = {f["properties"]["kind"]: f["properties"] for f in feats
                 if f["properties"]["hospital"] == "wenlock"
                 and f["properties"]["incident"] == "kulur"}
        scenario_summary[sid] = {
            "trigger_T": T, "blocked_edges": removed,
            "reachable_pairs": got,
            "total_pairs": len(HOSPITALS) * len(INCIDENTS),
            "focus_pair": focus,
        }
        print(f"   {sid}: {len(feats)} routes, {removed} blocked edges, {got}/{len(HOSPITALS)*len(INCIDENTS)} aware pairs OK")

    svals = [float(d.get("susceptibility", 0.0)) for _, _, _, d in G.edges(keys=True, data=True)]
    flood_prone = sum(v > 0.5 for v in svals)
    coverage = {
        "region": "Dakshina Kannada district, Karnataka, India",
        "boundary": "OpenStreetMap Nominatim administrative polygon",
        "graph": {"nodes": G.number_of_nodes(), "edges": G.number_of_edges(),
                  "flood_prone_edges": flood_prone,
                  "flood_prone_pct": round(100 * flood_prone / len(svals), 2)},
        "hospitals": {"count": len(HOSPITALS),
                      "taluks": sorted({h["taluk"] for h in HOSPITALS}),
                      "caveat": ("Curated routing origins; inclusion does not verify current "
                                 "ambulance or emergency-department availability.")},
        "scenario_points": len(INCIDENTS),
        "scenarios": scenario_summary,
    }
    json.dump(coverage, open(f"{OUT}/coverage.json", "w"), indent=2)
    print(">> Done.")


if __name__ == "__main__":
    main()
