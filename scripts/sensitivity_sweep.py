"""Sensitivity of the flood-aware routing outcome to its two free constants.

The edge-cost model has exactly two hand-set parameters:

    cost(e) = travel_time(e) * (1 + kappa * R(e))     if R(e) <  block
              impassable                              if R(e) >= block

The conference version fixed kappa=8, block=0.60 and declared the absence of a
sweep as a limitation. This script removes that limitation: it recomputes the
FULL hospital x incident routing outcome for every (kappa, block) cell and
reports how the operating point behaves relative to its neighbourhood.

Reported per cell, averaged over all reachable hospital->incident pairs under the
May-2025 trigger:
  * mean route exposure   -- mean over route edges of R(e) = S(e)*T
  * mean detour           -- extra minutes vs the risk-blind shortest-time route
  * unreachable pairs     -- pairs severed by the impassability threshold

No graph copies: networkx accepts a callable edge weight, so one graph serves all
49 cells (a copy per cell would be ~17 MB x 49 and dominate the runtime).
"""
import itertools
import json
import os
import sys
import time

import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from floodrisk import routing  # noqa: E402

OUT = "data/processed/sensitivity_sweep.json"

TRIGGER = 0.70                                    # May-2025 documented event
KAPPAS = [2, 4, 6, 8, 10, 12, 16]
BLOCKS = [0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75]

BASE_KAPPA, BASE_BLOCK = 8.0, 0.60                # the operating point under test


def _risk(d, T=TRIGGER):
    return d.get("susceptibility", 0.0) * T


def make_weight(kappa, block):
    """Callable edge weight: None makes networkx treat the edge as absent."""
    def w(u, v, data):
        best = None
        for d in data.values():
            r = _risk(d)
            if r >= block:
                continue
            c = d.get("travel_time", 0.0) * (1.0 + kappa * r)
            if best is None or c < best:
                best = c
        return best
    return w


def _tt_weight(u, v, data):
    return min(d.get("travel_time", 1e9) for d in data.values())


def route_profile(G, path):
    """(minutes, mean exposure, max exposure) along a node path, on the FULL graph."""
    if not path or len(path) < 2:
        return 0.0, 0.0, 0.0
    secs, risks = 0.0, []
    for u, v in zip(path[:-1], path[1:]):
        d = min(G[u][v].values(), key=lambda e: e.get("travel_time", 1e9))
        secs += d.get("travel_time", 0.0)
        risks.append(_risk(d))
    return secs / 60.0, sum(risks) / len(risks), max(risks)


def main():
    print(">> Sensitivity sweep over (kappa, impassability threshold)")
    G = routing.load_graph()
    print(f"   graph: {G.number_of_nodes()} nodes / {G.number_of_edges()} edges")

    hospitals = json.load(open("web_assets/hospitals.json"))
    incidents = json.load(open("web_assets/incidents.json"))

    h_nodes = [(h["id"], routing.nearest_node(h["lat"], h["lon"], G)) for h in hospitals]
    i_nodes = [(i["id"], routing.nearest_node(i["lat"], i["lon"], G)) for i in incidents]
    n_pairs = len(h_nodes) * len(i_nodes)
    print(f"   {n_pairs} hospital-incident pairs, trigger T={TRIGGER}")

    # ---- risk-blind baseline: same for every cell, so compute once -------------
    baseline = {}
    for hid, s in h_nodes:
        for iid, t in i_nodes:
            try:
                p = nx.shortest_path(G, s, t, weight=_tt_weight)
                mins, mean_r, max_r = route_profile(G, p)
                baseline[(hid, iid)] = {"minutes": mins, "mean": mean_r, "max": max_r}
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                baseline[(hid, iid)] = None
    n_base = sum(1 for v in baseline.values() if v)
    print(f"   risk-blind baseline routable on {n_base}/{n_pairs} pairs")

    cells, t0 = [], time.time()
    per_pair = {}          # (kappa, block) -> {pair: (mean_exposure, detour, max)}
    for kappa, block in itertools.product(KAPPAS, BLOCKS):
        w = make_weight(kappa, block)
        exposures, detours, maxes, unreachable = [], [], [], 0
        rec = {}
        for hid, s in h_nodes:
            for iid, t in i_nodes:
                b = baseline[(hid, iid)]
                try:
                    p = nx.shortest_path(G, s, t, weight=w)
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    unreachable += 1
                    continue
                mins, mean_r, max_r = route_profile(G, p)
                exposures.append(mean_r)
                maxes.append(max_r)
                rec[(hid, iid)] = (mean_r, (mins - b["minutes"]) if b else None, max_r)
                if b:
                    detours.append(mins - b["minutes"])
        per_pair[(kappa, block)] = rec
        cells.append({
            "kappa": kappa,
            "block": block,
            "n_routed": len(exposures),
            "unreachable": unreachable,
            "mean_exposure": round(sum(exposures) / len(exposures), 4) if exposures else None,
            "mean_max_exposure": round(sum(maxes) / len(maxes), 4) if maxes else None,
            "mean_detour_min": round(sum(detours) / len(detours), 3) if detours else None,
        })
        c = cells[-1]
        print(f"   kappa={kappa:<3} block={block:.2f}  exposure={c['mean_exposure']}  "
              f"detour={c['mean_detour_min']}min  unreachable={unreachable}")

    # ---- survivorship correction --------------------------------------------
    # Cell means above are taken over whichever pairs each cell could route. At a
    # low threshold most pairs are severed, and the survivors are systematically
    # the short inland ones, so a naive comparison makes an aggressive threshold
    # look like it lowers exposure when it has really just dropped hard cases.
    # Re-aggregate over the pairs routable in EVERY cell so the columns compare
    # like with like.
    common = set.intersection(*(set(r.keys()) for r in per_pair.values()))
    print(f"\n   pairs routable in all {len(per_pair)} cells: {len(common)} of {n_pairs}")
    for c in cells:
        rec = per_pair[(c["kappa"], c["block"])]
        ex = [rec[p][0] for p in common]
        de = [rec[p][1] for p in common if rec[p][1] is not None]
        mx = [rec[p][2] for p in common]
        c["n_common"] = len(common)
        c["mean_exposure_common"] = round(sum(ex) / len(ex), 4) if ex else None
        c["mean_detour_min_common"] = round(sum(de) / len(de), 3) if de else None
        c["mean_max_exposure_common"] = round(sum(mx) / len(mx), 4) if mx else None

    base_common = [baseline[p] for p in common if baseline[p]]
    common_baseline = {
        "mean_exposure": round(sum(v["mean"] for v in base_common) / len(base_common), 4),
        "mean_minutes": round(sum(v["minutes"] for v in base_common) / len(base_common), 3),
        "n_pairs": len(base_common),
    }
    print(f"   risk-blind baseline over the common subset: {common_baseline}")

    # ---- baseline (risk-blind) aggregate, for the exposure-reduction figure ----
    bl = [v for v in baseline.values() if v]
    base_exposure = round(sum(v["mean"] for v in bl) / len(bl), 4)
    base_minutes = round(sum(v["minutes"] for v in bl) / len(bl), 3)

    # ---- stability of the operating point vs its immediate neighbourhood ------
    def cell(k, b):
        return next(c for c in cells if c["kappa"] == k and c["block"] == b)

    op = cell(BASE_KAPPA, BASE_BLOCK)
    neigh = [c for c in cells
             if abs(KAPPAS.index(c["kappa"]) - KAPPAS.index(BASE_KAPPA)) <= 1
             and abs(BLOCKS.index(c["block"]) - BLOCKS.index(BASE_BLOCK)) <= 1
             and not (c["kappa"] == BASE_KAPPA and c["block"] == BASE_BLOCK)]
    # Spread is measured on the survivorship-corrected statistic.
    spread = max(abs(c["mean_exposure_common"] - op["mean_exposure_common"])
                 for c in neigh)
    rel = 100 * spread / op["mean_exposure_common"]

    summary = {
        "trigger": TRIGGER,
        "kappas": KAPPAS,
        "blocks": BLOCKS,
        "n_pairs": n_pairs,
        "baseline_risk_blind": {"mean_exposure": base_exposure, "mean_minutes": base_minutes},
        "baseline_risk_blind_common": common_baseline,
        "n_common_pairs": len(common),
        "operating_point": {"kappa": BASE_KAPPA, "block": BASE_BLOCK, **op},
        "neighbourhood_max_exposure_spread": round(spread, 4),
        "neighbourhood_max_exposure_spread_pct": round(rel, 2),
        "sweep_seconds": round(time.time() - t0, 1),
        "cells": cells,
    }
    os.makedirs("data/processed", exist_ok=True)
    json.dump(summary, open(OUT, "w"), indent=2)

    print(f"\n   risk-blind baseline: exposure {base_exposure}, {base_minutes} min")
    print(f"   operating point kappa={BASE_KAPPA} block={BASE_BLOCK}: "
          f"exposure {op['mean_exposure']}, detour {op['mean_detour_min']} min, "
          f"{op['unreachable']} unreachable")
    print(f"   max exposure spread across the 8 neighbouring cells: "
          f"{spread:.4f} ({rel:.1f}% of the operating value)")
    print(f">> Saved -> {OUT}  ({summary['sweep_seconds']}s)")


if __name__ == "__main__":
    main()
