"""Step 5b: flood-aware ambulance routing vs risk-blind shortest path.

Edge cost couples travel time to the dynamic risk R = S(x) * T(t):

    cost(e) = travel_time(e) * (1 + PENALTY * R(e))          if R(e) < BLOCK
              impassable                                      if R(e) >= BLOCK

so the router trades a modest detour for avoiding inundated segments. Comparing the
two routes under the same live trigger quantifies the safety gain per unit of delay.
"""
import os
import sys

import networkx as nx
import osmnx as ox

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from floodrisk import live  # noqa: E402

GRAPH = "data/processed/dakshina_kannada_roads.graphml"
PLOT = "data/processed/route_comparison.png"

PENALTY = 8.0    # travel-time multiplier weight on risk
BLOCK = 0.60     # edges at/above this dynamic risk are treated as impassable

# Wenlock District Hospital -> Kulur (crosses the Gurupura/Phalguni floodplain)
ORIGIN = (12.8703, 74.8430)
DEST = (12.9200, 74.8480)

SCENARIOS = {
    "may2025_flood": ("2025-05-25", "2025-06-02", "2025-05-30T06:00"),
    "aug2024_flood": ("2024-07-28", "2024-08-05", "2024-08-02T06:00"),
}


def route_stats(G, route, trigger):
    """Travel time (min) and risk profile along a node route."""
    t, risks = 0.0, []
    for u, v in zip(route[:-1], route[1:]):
        d = min(G[u][v].values(), key=lambda e: e.get("travel_time", 1e9))
        t += d.get("travel_time", 0.0)
        risks.append(d.get("susceptibility", 0.0) * trigger)
    return {
        "minutes": t / 60.0,
        "max_risk": max(risks) if risks else 0.0,
        "mean_risk": sum(risks) / len(risks) if risks else 0.0,
        "blocked_edges": sum(1 for r in risks if r >= BLOCK),
    }


def main():
    if not os.path.exists(GRAPH):
        sys.exit(f"Missing {GRAPH} -- run scripts/build_road_graph.py first")

    print(">> Step 5b: flood-aware routing")
    # GraphML stores custom attrs as strings -- cast susceptibility back to float
    G = ox.io.load_graphml(GRAPH, edge_dtypes={"susceptibility": float})
    print(f"   Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    orig = ox.distance.nearest_nodes(G, ORIGIN[1], ORIGIN[0])
    dest = ox.distance.nearest_nodes(G, DEST[1], DEST[0])

    # live trigger + documented-event replays
    times, precip = live.fetch_openmeteo_rainfall(*ORIGIN)
    triggers = {"live_now": live.rainfall_trigger(live.antecedent_rainfall(times, precip))}
    from datetime import datetime, timezone
    for name, (s, e, peak) in SCENARIOS.items():
        t2, p2 = live.fetch_openmeteo_archive(ORIGIN[0], ORIGIN[1], s, e)
        when = datetime.fromisoformat(peak).replace(tzinfo=timezone.utc)
        triggers[name] = live.rainfall_trigger(live.antecedent_rainfall(t2, p2, now=when))

    # risk-blind baseline (same under every trigger)
    base = ox.routing.shortest_path(G, orig, dest, weight="travel_time")
    if base is None:
        sys.exit("   No route found between origin and destination")

    for name, T in sorted(triggers.items(), key=lambda kv: kv[1]):
        print(f"\n   === {name}  (trigger T={T:.3f}) ===")

        H = G.copy()
        removed = 0
        for u, v, k, d in list(H.edges(keys=True, data=True)):
            r = d.get("susceptibility", 0.0) * T
            if r >= BLOCK:
                H.remove_edge(u, v, k); removed += 1
            else:
                d["cost"] = d.get("travel_time", 0.0) * (1 + PENALTY * r)

        safe = ox.routing.shortest_path(H, orig, dest, weight="cost") if removed < H.number_of_edges() else None
        b = route_stats(G, base, T)
        print(f"      impassable edges removed: {removed}")
        print(f"      risk-blind : {b['minutes']:.1f} min | max risk {b['max_risk']:.3f} "
              f"| mean {b['mean_risk']:.3f} | {b['blocked_edges']} unsafe edges")

        if safe is None:
            print("      flood-aware: NO SAFE ROUTE (network severed at this trigger)")
            continue
        s = route_stats(G, safe, T)
        print(f"      flood-aware: {s['minutes']:.1f} min | max risk {s['max_risk']:.3f} "
              f"| mean {s['mean_risk']:.3f} | {s['blocked_edges']} unsafe edges")
        dt = s["minutes"] - b["minutes"]
        print(f"      -> detour cost {dt:+.1f} min ({100*dt/max(b['minutes'],1e-9):+.1f}%), "
              f"max risk {b['max_risk']:.3f} -> {s['max_risk']:.3f}")

        if name == "may2025_flood" and safe != base:
            fig, ax = ox.plot.plot_graph_routes(
                G, [base, safe], route_colors=["red", "blue"], route_linewidth=3,
                node_size=0, bgcolor="white", edge_color="#cccccc", edge_linewidth=0.4,
                show=False, close=True,
            )
            fig.savefig(PLOT, dpi=150, bbox_inches="tight")
            print(f"      plot: {PLOT}  (red=risk-blind, blue=flood-aware)")


if __name__ == "__main__":
    main()
