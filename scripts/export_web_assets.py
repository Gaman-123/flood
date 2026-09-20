"""Export REAL model outputs as web-ready assets for the dashboard front-end.

Replaces the synthetic front-end `geoData.js` with genuine data:
  susceptibility_overlay.png + .bounds.json   <- susceptibility_dk.tif
  roads.geojson (per-edge susceptibility)      <- dakshina_kannada_roads.graphml
  routes_<scenario>.geojson (blind + aware)    <- graphml + live trigger
  blocked_<scenario>.geojson                   <- graphml edges above block threshold
  dispatch.json                                <- quantum_dispatch.json (copy)

Writes into web_assets/ ; the front-end build copies these into public/data/.
"""
import json
import os
import shutil
import sys
from datetime import datetime, timezone

import numpy as np
import osmnx as ox
import rasterio
import matplotlib
from matplotlib.colors import Normalize
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from floodrisk import config, live, locations  # noqa: E402

PROC = "data/processed"
OUT = "web_assets"
GRAPH = config.ROAD_GRAPH_PATH
TIF = config.ROUTING_SUSCEPTIBILITY_PATH

_H = locations.by_id(locations.HOSPITALS)
_I = locations.by_id(locations.INCIDENTS)
HOSPITALS = {k: (_H[k]["lat"], _H[k]["lon"])
             for k in locations.QUANTUM_HOSPITAL_IDS}
INCIDENTS = {k: (_I[k]["lat"], _I[k]["lon"])
             for k in locations.QUANTUM_INCIDENT_IDS}
PAIRS = list(zip(locations.QUANTUM_HOSPITAL_IDS, locations.QUANTUM_INCIDENT_IDS))
PENALTY, BLOCK = 8.0, 0.60

SCENARIOS = {  # id -> (T, is illustrative)
    "dry": 0.00, "live": None, "aug2024": 0.39, "may2025": 0.70, "flash5": 0.85,
}


def export_overlay():
    """Colorized RGBA PNG of susceptibility + geographic bounds for a MapLibre image source."""
    with rasterio.open(TIF) as src:
        arr = src.read(1).astype("float32")
        nodata = src.nodata
        b = src.bounds
    mask = np.isfinite(arr) & (arr != nodata if nodata is not None else True)
    norm = Normalize(vmin=0.0, vmax=1.0)
    rgba = matplotlib.colormaps["turbo"](norm(np.clip(arr, 0, 1)))
    rgba[..., 3] = np.where(mask, 0.78, 0.0)          # transparent outside data
    img = Image.fromarray((rgba * 255).astype("uint8"), "RGBA")
    img.save(f"{OUT}/susceptibility_overlay.png")
    # MapLibre image source wants the 4 corners, clockwise from top-left
    bounds = {
        "coordinates": [[b.left, b.top], [b.right, b.top], [b.right, b.bottom], [b.left, b.bottom]],
        "bbox": [b.left, b.bottom, b.right, b.top],
    }
    json.dump(bounds, open(f"{OUT}/susceptibility_overlay.bounds.json", "w"))
    print(f"   overlay: {img.size[0]}x{img.size[1]} px, bbox {bounds['bbox']}")


def load_graph():
    G = ox.io.load_graphml(GRAPH, edge_dtypes={
        "susceptibility": float, "travel_time": float, "length": float,
    })
    return G


def edge_geom(G, u, v, k):
    d = G.edges[u, v, k]
    if "geometry" in d:
        return [[x, y] for x, y in d["geometry"].coords]
    return [[G.nodes[u]["x"], G.nodes[u]["y"]], [G.nodes[v]["x"], G.nodes[v]["y"]]]


def export_roads(G):
    feats = []
    for u, v, k in G.edges(keys=True):
        s = G.edges[u, v, k].get("susceptibility", 0.0)
        coords = [[round(x, 5), round(y, 5)] for x, y in edge_geom(G, u, v, k)]
        feats.append({"type": "Feature", "properties": {"s": round(float(s), 3)},
                      "geometry": {"type": "LineString", "coordinates": coords}})
    fc = {"type": "FeatureCollection", "features": feats}
    json.dump(fc, open(f"{OUT}/roads.geojson", "w"))
    print(f"   roads.geojson: {len(feats)} edges")

    # The browser receives a representative, district-spread subset. Preserve
    # every higher-class road and deterministically thin local/service streets.
    important = {"motorway", "trunk", "primary", "secondary", "tertiary",
                 "motorway_link", "trunk_link", "primary_link", "secondary_link"}
    major, minor = [], []
    for idx, ((u, v, k), feat) in enumerate(zip(G.edges(keys=True), feats)):
        hw = G.edges[u, v, k].get("highway", "")
        kinds = set(hw if isinstance(hw, list) else [hw])
        (major if kinds & important else minor).append(feat)
    budget = max(0, 30000 - len(major))
    if budget and len(minor) > budget:
        step = len(minor) / budget
        minor = [minor[int(i * step)] for i in range(budget)]
    light = {"type": "FeatureCollection", "features": major + minor}
    json.dump(light, open(f"{OUT}/roads_light.geojson", "w"), separators=(",", ":"))
    print(f"   roads_light.geojson: {len(light['features'])} representative edges")


def route_coords(G, route):
    pts, cum, exp = [], [0.0], []
    t = 0.0
    for a, b in zip(route[:-1], route[1:]):
        d = min(G[a][b].values(), key=lambda e: e.get("travel_time", 1e9))
        seg = edge_geom(G, a, b, list(G[a][b].keys())[0])
        for p in seg:
            pts.append([round(p[0], 5), round(p[1], 5)])
        t += d.get("travel_time", 0.0)
        cum.append(round(t / 60.0, 2))
        exp.append(round(d.get("susceptibility", 0.0), 3))
    return pts, t / 60.0, exp


def export_routes(G, scenario, T):
    import networkx as nx
    feats = []
    for hid, iid in PAIRS:
        o = ox.distance.nearest_nodes(G, HOSPITALS[hid][1], HOSPITALS[hid][0])
        d = ox.distance.nearest_nodes(G, INCIDENTS[iid][1], INCIDENTS[iid][0])
        blind = ox.routing.shortest_path(G, o, d, weight="travel_time")
        H = G.copy()
        for a, b, k, dd in list(H.edges(keys=True, data=True)):
            r = dd.get("susceptibility", 0.0) * T
            if r >= BLOCK:
                H.remove_edge(a, b, k)
            else:
                dd["cost"] = dd.get("travel_time", 0.0) * (1 + PENALTY * r)
        aware = ox.routing.shortest_path(H, o, d, weight="cost")
        for kind, rt in (("blind", blind), ("aware", aware)):
            if rt is None:
                continue
            pts, mins, exp = route_coords(G, rt)
            feats.append({"type": "Feature",
                          "properties": {"kind": kind, "hospital": hid, "incident": iid,
                                         "minutes": round(mins, 1), "mean_exposure": round(float(np.mean([e*T for e in exp])), 3),
                                         "max_exposure": round(float(max([e*T for e in exp], default=0)), 3)},
                          "geometry": {"type": "LineString", "coordinates": pts}})
    json.dump({"type": "FeatureCollection", "features": feats},
              open(f"{OUT}/routes_{scenario}.geojson", "w"))
    print(f"   routes_{scenario}.geojson: {len(feats)} routes (T={T:.2f})")


def export_blocked(G, scenario, T):
    feats = []
    if T > 0.2:
        for u, v, k in G.edges(keys=True):
            if G.edges[u, v, k].get("susceptibility", 0.0) * T >= BLOCK:
                coords = [[round(x, 5), round(y, 5)] for x, y in edge_geom(G, u, v, k)]
                feats.append({"type": "Feature", "properties": {},
                              "geometry": {"type": "LineString", "coordinates": coords}})
    json.dump({"type": "FeatureCollection", "features": feats},
              open(f"{OUT}/blocked_{scenario}.geojson", "w"))
    print(f"   blocked_{scenario}.geojson: {len(feats)} edges")


def live_trigger():
    times, precip = live.fetch_openmeteo_rainfall(12.87, 74.84)
    ant = live.antecedent_rainfall(times, precip)
    return live.rainfall_trigger(ant), ant


def main():
    os.makedirs(OUT, exist_ok=True)
    print(">> Exporting real web assets")
    export_overlay()
    shutil.copy(f"{PROC}/quantum_dispatch.json", f"{OUT}/dispatch.json")

    G = load_graph()
    print(f"   graph: {G.number_of_nodes()} nodes / {G.number_of_edges()} edges")
    export_roads(G)

    T_live, ant = live_trigger()
    print(f"   live trigger T={T_live:.3f} antecedent={ant}")
    svals = [float(d.get("susceptibility", 0.0))
             for _, _, _, d in G.edges(keys=True, data=True)]
    hi = sum(v > 0.5 for v in svals)
    manifest = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "region": "Dakshina Kannada administrative district",
        "graph": {"nodes": G.number_of_nodes(), "edges": G.number_of_edges(),
                  "flood_prone_edges": hi,
                  "flood_prone_pct": round(100 * hi / len(svals), 2)},
        "live": {"T": round(T_live, 3), "antecedent": ant},
    }
    for sid, T in SCENARIOS.items():
        t = T_live if T is None else T
        export_routes(G, sid, t)
        export_blocked(G, sid, t)
        manifest.setdefault("scenarios", {})[sid] = round(t, 3)
    json.dump(manifest, open(f"{OUT}/manifest.json", "w"), indent=2)
    print(">> Done. Assets in web_assets/")


if __name__ == "__main__":
    main()
