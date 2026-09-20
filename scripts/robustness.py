"""Two robustness checks a reviewer would reasonably demand.

A. IS `rain_annual` A SECOND CONFOUND?
   CHIRPS is 0.05 deg (~5.5 km), so even district-wide coverage is spatially
   coarse relative to roads. A variable with relatively few distinct values
   cannot carry fine-scale hydrological signal, yet SHAP ranks it fourth. The
   suspicion is that it acts as a smooth coast-to-inland gradient, i.e. a proxy
   for distance from the sea and for the orographic ramp, which is structurally
   the same failure mode as the NDVI/land-cover confound already documented.
   Measured here: distinct-value count over the prediction window, correlation
   with elevation and distance-to-coast, and leave-one-out AUC.

B. ARE THE ROUTING RESULTS AN ARTEFACT OF CURATED INCIDENT SITES?
   The named benchmark is conditioned on thirteen scenario locations.
   Re-running over randomly sampled road-graph nodes converts the result from
   illustrative to broader. Reported: exposure reduction and detour over N random
   incidents, against the curated set.

Outputs data/processed/robustness.json.
"""
import json
import os
import sys

import numpy as np
import pandas as pd
import rasterio
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from floodrisk import predictors  # noqa: E402

TABLE = "data/processed/training.parquet"
STACK = "web_assets/predictor_stack.tif"
BANDS_JSON = "web_assets/predictor_stack.bands.json"
OUT = "data/processed/robustness.json"

N_RANDOM_INCIDENTS = 200
SEED = 11
TRIGGER = 0.70


def _model():
    return XGBClassifier(n_estimators=400, max_depth=5, learning_rate=0.05,
                         subsample=0.8, colsample_bytree=0.8,
                         eval_metric="logloss", random_state=42, n_jobs=-1)


# --------------------------------------------------------------- A. rainfall

def rainfall_proxy_check():
    df = pd.read_parquet(TABLE)
    feats = [f for f in predictors.PRIMARY_NUMERIC if f in df.columns]
    X, y = df[feats].astype(float), df["label"].astype(int)

    bands = json.load(open(BANDS_JSON))["bands"]
    with rasterio.open(STACK) as s:
        arr = s.read().astype("float64")
        H, W = s.height, s.width
        left, bottom, right, top = s.bounds
    land = np.isfinite(arr[bands.index("elevation")])
    rain = arr[bands.index("rain_annual")][land]
    elev = arr[bands.index("elevation")][land]

    # distance to coast, proxied by distance to the nearest no-data (sea) pixel
    from scipy.ndimage import distance_transform_edt
    px_deg_x = (right - left) / W
    d_coast = distance_transform_edt(land) * px_deg_x * 111.32 * np.cos(np.radians(12.9))
    d_coast = d_coast[land]

    # CHIRPS and SRTM have slightly different valid footprints, so restrict to
    # pixels where all three are finite before correlating.
    ok = np.isfinite(rain) & np.isfinite(elev) & np.isfinite(d_coast)
    rain_o, elev_o, dc_o = rain[ok], elev[ok], d_coast[ok]

    distinct = int(np.unique(np.round(rain_o, 3)).size)
    out = {
        "chirps_distinct_values_in_window": distinct,
        "window_pixels": int(land.sum()),
        "pixels_used_for_correlation": int(ok.sum()),
        "corr_rain_vs_dist_coast": round(float(np.corrcoef(rain_o, dc_o)[0, 1]), 4),
        "corr_rain_vs_elevation": round(float(np.corrcoef(rain_o, elev_o)[0, 1]), 4),
    }

    # leave-one-out AUC: what does dropping each feature actually cost?
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.30, stratify=y, random_state=42)
    full = _model().fit(X_tr, y_tr)
    auc_full = float(roc_auc_score(y_te, full.predict_proba(X_te)[:, 1]))
    loo = {}
    for f in feats:
        keep = [c for c in feats if c != f]
        m = _model().fit(X_tr[keep], y_tr)
        a = float(roc_auc_score(y_te, m.predict_proba(X_te[keep])[:, 1]))
        loo[f] = round(auc_full - a, 5)
    out["auc_full"] = round(auc_full, 4)
    out["leave_one_out_auc_drop"] = dict(sorted(loo.items(), key=lambda kv: -kv[1]))

    print("A. rain_annual proxy check")
    print(f"   distinct CHIRPS values across the window: {distinct} "
          f"over {int(land.sum())} pixels")
    print(f"   corr(rain, distance-to-coast) = {out['corr_rain_vs_dist_coast']}")
    print(f"   corr(rain, elevation)         = {out['corr_rain_vs_elevation']}")
    print(f"   leave-one-out AUC drop (top 4): "
          f"{list(out['leave_one_out_auc_drop'].items())[:4]}")
    return out


# ------------------------------------------------------------- B. incidents

def incident_robustness():
    import networkx as nx
    from floodrisk import routing

    G = routing.load_graph()
    hospitals = json.load(open("web_assets/hospitals.json"))
    curated = json.load(open("web_assets/incidents.json"))

    def tt(u, v, data):
        return min(d.get("travel_time", 1e9) for d in data.values())

    def aware(u, v, data):
        best = None
        for d in data.values():
            r = d.get("susceptibility", 0.0) * TRIGGER
            if r >= routing.BLOCK:
                continue
            c = d.get("travel_time", 0.0) * (1 + routing.PENALTY * r)
            best = c if best is None or c < best else best
        return best

    def profile(path):
        secs, risks = 0.0, []
        for u, v in zip(path[:-1], path[1:]):
            d = min(G[u][v].values(), key=lambda e: e.get("travel_time", 1e9))
            secs += d.get("travel_time", 0.0)
            risks.append(d.get("susceptibility", 0.0) * TRIGGER)
        return secs / 60.0, float(np.mean(risks))

    h_nodes = [routing.nearest_node(h["lat"], h["lon"], G) for h in hospitals]

    def run(targets, label):
        blind_e, aware_e, detours, severed = [], [], [], 0
        for t in targets:
            for s in h_nodes:
                try:
                    pb = nx.shortest_path(G, s, t, weight=tt)
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    continue
                mb, eb = profile(pb)
                try:
                    pa = nx.shortest_path(G, s, t, weight=aware)
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    severed += 1
                    continue
                ma, ea = profile(pa)
                blind_e.append(eb); aware_e.append(ea); detours.append(ma - mb)
        n = len(aware_e)
        res = {
            "label": label, "n_pairs_routed": n, "n_severed": severed,
            "mean_exposure_risk_blind": round(float(np.mean(blind_e)), 4),
            "mean_exposure_flood_aware": round(float(np.mean(aware_e)), 4),
            "exposure_reduction_pct": round(
                100 * (1 - float(np.mean(aware_e)) / float(np.mean(blind_e))), 1),
            "mean_detour_min": round(float(np.mean(detours)), 3),
        }
        print(f"   {label}: {n} pairs, exposure "
              f"{res['mean_exposure_risk_blind']} -> {res['mean_exposure_flood_aware']} "
              f"({res['exposure_reduction_pct']}% lower), "
              f"detour {res['mean_detour_min']} min, {severed} severed")
        return res

    print("\nB. incident-site robustness")
    curated_nodes = [routing.nearest_node(i["lat"], i["lon"], G) for i in curated]
    a = run(curated_nodes, f"curated ({len(curated)} sites)")

    rng = np.random.default_rng(SEED)
    all_nodes = list(G.nodes())
    rand_nodes = [all_nodes[i] for i in
                  rng.choice(len(all_nodes), size=N_RANDOM_INCIDENTS, replace=False)]
    b = run(rand_nodes, f"random ({N_RANDOM_INCIDENTS} nodes, seed {SEED})")

    return {"curated": a, "random": b,
            "n_random_incidents": N_RANDOM_INCIDENTS, "seed": SEED,
            "trigger": TRIGGER}


def main():
    print(">> Robustness checks")
    out = {"rainfall_proxy": rainfall_proxy_check(),
           "incident_robustness": incident_robustness()}
    os.makedirs("data/processed", exist_ok=True)
    json.dump(out, open(OUT, "w"), indent=2)
    print(f"\n>> Saved -> {OUT}")


if __name__ == "__main__":
    main()
