"""On-demand flood-aware routing from an arbitrary point, with instrumented
Dijkstra and A* so the dashboard can *show how* a live route is computed.

The precomputed hospital<->incident matrices cover fixed pairs. A dropped emergency
pin is an arbitrary coordinate, so we snap it to the road graph and route live.

Both search algorithms are implemented explicitly (not via networkx) to expose the
set of nodes each one explores — the whole point of the comparison. On the same
graph they return the SAME optimal path; they differ in how much of the network they
touch to find it:
  * Dijkstra expands uniformly outward (a growing disc) — no sense of direction.
  * A* is guided by a straight-line-time heuristic toward the goal, so it explores a
    narrow corridor and settles far fewer nodes.
"""
import heapq
import math
import os
import time

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRAPH_PATH = os.path.join(_REPO, "data", "processed", "dakshina_kannada_roads.graphml")

PENALTY, BLOCK = 8.0, 0.60
_FALLBACK_MAX_SPEED_MPS = 50.0  # conservative fallback for malformed/missing edge attributes

_graph = None
_aware_cache = {}           # T -> graph with per-edge 'cost' and blocked edges pruned


# --------------------------------------------------------------------------- graph

def load_graph():
    global _graph
    if _graph is None:
        import osmnx as ox
        _graph = ox.io.load_graphml(GRAPH_PATH, edge_dtypes={
            "susceptibility": float, "travel_time": float, "length": float})
    return _graph


def aware_graph(T):
    """Graph pruned to passable edges at trigger T, with a flood-aware 'cost' weight."""
    key = round(float(T), 3)
    if key in _aware_cache:
        return _aware_cache[key]
    G = load_graph().copy()
    for u, v, k, d in list(G.edges(keys=True, data=True)):
        r = d.get("susceptibility", 0.0) * key
        if r >= BLOCK:
            G.remove_edge(u, v, k)
        else:
            d["cost"] = d.get("travel_time", 0.0) * (1 + PENALTY * r)
    _aware_cache[key] = G
    return G


def nearest_node(lat, lon, G=None):
    import osmnx as ox
    G = G or load_graph()
    return ox.distance.nearest_nodes(G, lon, lat)


def _haversine_s(G, a, b):
    """Lower bound on travel time (s) between two nodes: straight-line dist / max speed."""
    ax, ay = G.nodes[a]["x"], G.nodes[a]["y"]
    bx, by = G.nodes[b]["x"], G.nodes[b]["y"]
    r = 6371000.0
    p1, p2 = math.radians(ay), math.radians(by)
    dphi = math.radians(by - ay)
    dlam = math.radians(bx - ax)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlam / 2) ** 2
    # District highways can exceed the old city-only 80 km/h ceiling. Derive the
    # actual graph maximum so the heuristic remains admissible after expansion.
    max_speed = G.graph.get("_heuristic_max_speed_mps")
    if max_speed is None:
        observed = [d.get("length", 0.0) / d.get("travel_time", math.inf)
                    for _, _, _, d in G.edges(keys=True, data=True)
                    if d.get("travel_time", 0.0) > 0]
        max_speed = max(observed, default=_FALLBACK_MAX_SPEED_MPS) * 1.01
        G.graph["_heuristic_max_speed_mps"] = max_speed
    return (2 * r * math.asin(math.sqrt(h))) / max_speed


def _min_edge(G, u, v, weight):
    return min(d.get(weight, math.inf) for d in G[u][v].values())


def _reconstruct(prev, source, target):
    if target not in prev and target != source:
        return None
    path, n = [], target
    while n != source:
        path.append(n)
        n = prev[n]
    path.append(source)
    path.reverse()
    return path


def dijkstra(G, source, target, weight="cost"):
    """Uniform-cost search. Returns (path, explored_nodes, cost, seconds)."""
    t0 = time.perf_counter()
    dist = {source: 0.0}
    prev, visited, explored = {}, set(), []
    pq = [(0.0, source)]
    while pq:
        d, u = heapq.heappop(pq)
        if u in visited:
            continue
        visited.add(u)
        explored.append(u)
        if u == target:
            break
        for v in G.successors(u):
            nd = d + _min_edge(G, u, v, weight)
            if nd < dist.get(v, math.inf):
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd, v))
    return (_reconstruct(prev, source, target), explored,
            dist.get(target), time.perf_counter() - t0)


def astar(G, source, target, weight="cost"):
    """Heuristic-guided search toward `target`. Returns (path, explored, cost, seconds)."""
    t0 = time.perf_counter()
    g = {source: 0.0}
    prev, visited, explored = {}, set(), []
    pq = [(_haversine_s(G, source, target), 0.0, source)]
    while pq:
        _, gu, u = heapq.heappop(pq)
        if u in visited:
            continue
        visited.add(u)
        explored.append(u)
        if u == target:
            break
        for v in G.successors(u):
            ng = gu + _min_edge(G, u, v, weight)
            if ng < g.get(v, math.inf):
                g[v] = ng
                prev[v] = u
                heapq.heappush(pq, (ng + _haversine_s(G, v, target), ng, v))
    return (_reconstruct(prev, source, target), explored,
            g.get(target), time.perf_counter() - t0)


# --------------------------------------------------------------------------- geometry

def path_coords(G, path):
    """[[lon,lat], ...] following real edge geometry where available."""
    if not path or len(path) < 2:
        return []
    out = []
    for a, b in zip(path[:-1], path[1:]):
        d = min(G[a][b].values(), key=lambda e: e.get("travel_time", math.inf))
        if "geometry" in d:
            out += [[round(x, 5), round(y, 5)] for x, y in d["geometry"].coords]
        else:
            out += [[round(G.nodes[a]["x"], 5), round(G.nodes[a]["y"], 5)],
                    [round(G.nodes[b]["x"], 5), round(G.nodes[b]["y"], 5)]]
    return out


def node_points(G, nodes, cap=1500):
    """[[lon,lat], ...] for a set of explored nodes (downsampled for the wire)."""
    step = max(1, len(nodes) // cap)
    return [[round(G.nodes[n]["x"], 5), round(G.nodes[n]["y"], 5)] for n in nodes[::step]]


def path_minutes(G, path):
    if not path or len(path) < 2:
        return 0.0
    secs = sum(_min_edge(G, a, b, "travel_time") for a, b in zip(path[:-1], path[1:]))
    return round(secs / 60.0, 1)


# --------------------------------------------------------------------------- dispatch

_hospital_nodes = None


def _hospitals():
    import json
    return json.load(open(os.path.join(_REPO, "web_assets", "hospitals.json")))


def _hospital_node_map():
    """Snap each hospital to a graph node once (pruning removes edges, not nodes)."""
    global _hospital_nodes
    if _hospital_nodes is None:
        G = load_graph()
        _hospital_nodes = [{**h, "node": nearest_node(h["lat"], h["lon"], G)}
                           for h in _hospitals()]
    return _hospital_nodes


def emergency_dispatch(lat, lon, T, notify_k=3):
    """Route from every hospital to a dropped emergency pin; return the optimal
    dispatch, the hospitals to notify, and the Dijkstra-vs-A* comparison for the
    chosen route. Handles the case where flooding has severed all approaches.
    """
    import networkx as nx

    G = aware_graph(T)
    e = nearest_node(lat, lon, G)

    # One reverse Dijkstra search settles every hospital-to-incident cost. This
    # replaces one full shortest-path search per facility and keeps district-scale
    # pinpoint dispatch responsive. Returned reverse paths are flipped back into
    # hospital -> incident order before travel-time reporting.
    reverse = G.reverse(copy=False)
    try:
        _, reverse_paths = nx.single_source_dijkstra(reverse, e, weight="cost")
    except nx.NodeNotFound:
        reverse_paths = {}

    results = []
    for h in _hospital_node_map():
        rev_path = reverse_paths.get(h["node"])
        if rev_path:
            path = list(reversed(rev_path))
            results.append({"id": h["id"], "name": h["name"], "node": h["node"],
                            "eta_min": path_minutes(G, path), "reachable": True})
        else:
            results.append({"id": h["id"], "name": h["name"], "node": h["node"],
                            "eta_min": None, "reachable": False})

    reachable = sorted((r for r in results if r["reachable"]), key=lambda r: r["eta_min"])
    results.sort(key=lambda r: (r["eta_min"] is None, r["eta_min"] or 1e9))
    public = [{k: r[k] for k in ("id", "name", "eta_min", "reachable")} for r in results]

    if not reachable:
        return {"emergency": {"lat": lat, "lon": lon}, "trigger_T": T,
                "reachable": False, "hospitals": public,
                "message": "All road approaches to this point are flooded at the current trigger."}

    best = reachable[0]
    pd, ed, cd, sd = dijkstra(G, best["node"], e)
    pa, ea, ca, sa = astar(G, best["node"], e)

    return {
        "emergency": {"lat": lat, "lon": lon}, "trigger_T": T, "reachable": True,
        "optimal": {"id": best["id"], "name": best["name"],
                    "eta_min": best["eta_min"], "route": path_coords(G, pd)},
        "hospitals": public,
        "notified": [{"id": r["id"], "name": r["name"], "eta_min": r["eta_min"]}
                     for r in reachable[:notify_k]],
        "algorithms": {
            "dijkstra": {"explored": len(ed), "ms": round(sd * 1000, 1), "path_nodes": len(pd)},
            "astar": {"explored": len(ea), "ms": round(sa * 1000, 1), "path_nodes": len(pa)},
            "same_path": pd == pa,
            "speedup": round(len(ed) / max(1, len(ea)), 2),
            "explored_dijkstra": node_points(G, ed),
            "explored_astar": node_points(G, ea),
        },
    }
