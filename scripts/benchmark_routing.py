"""Benchmark Dijkstra vs A* across every hospital->incident pair for the paper.

Produces a real, multi-query comparison (not a single anecdotal example): for
every reachable pair under the May-2025 trigger, run both algorithms, confirm
they agree on the optimal path, and record explored-node counts and wall time.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from floodrisk import routing  # noqa: E402

OUT = "data/processed/routing_benchmark.json"


def main():
    print(">> Benchmarking Dijkstra vs A* across all hospital->incident pairs (May 2025)")
    G = routing.aware_graph(0.70)
    hospitals = json.load(open("web_assets/hospitals.json"))
    incidents = json.load(open("web_assets/incidents.json"))
    print(f"   graph: {G.number_of_nodes()} nodes / {G.number_of_edges()} edges (post-prune)")

    rows = []
    t0 = time.time()
    for h in hospitals:
        s = routing.nearest_node(h["lat"], h["lon"], G)
        for inc in incidents:
            t = routing.nearest_node(inc["lat"], inc["lon"], G)
            pd_, ed, cd, sd = routing.dijkstra(G, s, t)
            pa_, ea, ca, sa = routing.astar(G, s, t)
            if pd_ is None:
                continue
            same = pd_ == pa_
            rows.append({
                "hospital": h["id"], "incident": inc["id"],
                "dijkstra_explored": len(ed), "astar_explored": len(ea),
                "dijkstra_ms": round(sd * 1000, 3), "astar_ms": round(sa * 1000, 3),
                "same_path": same, "cost_match": abs(cd - ca) < 1e-6,
                "path_len_nodes": len(pd_),
            })
    dt = time.time() - t0

    n = len(rows)
    mean_d = sum(r["dijkstra_explored"] for r in rows) / n
    mean_a = sum(r["astar_explored"] for r in rows) / n
    mean_dt = sum(r["dijkstra_ms"] for r in rows) / n
    mean_at = sum(r["astar_ms"] for r in rows) / n
    all_same = all(r["same_path"] for r in rows)
    all_cost_match = all(r["cost_match"] for r in rows)
    speedup = mean_d / mean_a

    summary = {
        "n_pairs": n, "total_bench_seconds": round(dt, 2),
        "mean_dijkstra_explored": round(mean_d, 1),
        "mean_astar_explored": round(mean_a, 1),
        "mean_dijkstra_ms": round(mean_dt, 3),
        "mean_astar_ms": round(mean_at, 3),
        "mean_node_reduction_pct": round(100 * (1 - mean_a / mean_d), 1),
        "mean_time_reduction_pct": round(100 * (1 - mean_at / mean_dt), 1),
        "speedup_nodes": round(speedup, 3),
        "all_pairs_same_optimal_path": all_same,
        "all_pairs_cost_match": all_cost_match,
        "pairs": rows,
    }
    os.makedirs("data/processed", exist_ok=True)
    json.dump(summary, open(OUT, "w"), indent=2)

    print(f"   {n} reachable pairs benchmarked in {dt:.1f}s")
    print(f"   mean explored: Dijkstra {mean_d:.0f}  vs  A* {mean_a:.0f}  "
          f"({summary['mean_node_reduction_pct']}% fewer)")
    print(f"   mean time    : Dijkstra {mean_dt:.2f}ms vs A* {mean_at:.2f}ms")
    print(f"   same optimal path on ALL pairs: {all_same}  |  cost match: {all_cost_match}")
    print(f">> Saved -> {OUT}")


if __name__ == "__main__":
    main()
