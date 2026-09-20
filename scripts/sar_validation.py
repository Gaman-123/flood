"""Spatially held-out validation of the susceptibility surface against SAR observation.

The strongest objection to any flood-susceptibility map is that its accuracy is
measured on points drawn from the same neighbourhoods as its training data, so the
score reflects spatial autocorrelation rather than transferable skill.

This script removes that objection by construction:

  * Define a coastal holdout zone from the actual SAR-observation footprint.
  * TRAIN on labelled points outside that zone.
  * PREDICT wall-to-wall only inside the zone, from the district predictor stack.
  * SCORE against the SAR flood-frequency polygons observed inside that zone.

The model therefore never sees a single label from the area it is evaluated on.
This is a geographic transfer test, which is what an operational deployment to a
neighbouring taluk would actually require.

Metrics follow the flood-susceptibility literature: ROC-AUC, plus the hit rate
(probability of detection), false-alarm ratio, and a success-rate curve reporting
what fraction of observed flooding is captured by the highest-susceptibility
fraction of the landscape.

IMPORTANT INTERPRETATION LIMIT: SAR observes flooding only on its ~12-day revisit,
so the polygons are a LOWER BOUND on true flooding. Pixels outside them are "not
observed flooded", NOT "observed dry". False positives are therefore not
necessarily errors, and the false-alarm ratio is an upper bound on the true rate.
"""
import json
import os
import sys

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from rasterio.windows import bounds as window_bounds
from rasterio.windows import from_bounds
from sklearn.metrics import roc_auc_score, roc_curve, confusion_matrix
from xgboost import XGBClassifier

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from floodrisk import predictors  # noqa: E402

TABLE = "data/processed/training.parquet"
STACK = "web_assets/predictor_stack.tif"
BANDS_JSON = "web_assets/predictor_stack.bands.json"
SAR = "web_assets/sar_extent.geojson"
OUT = "data/processed/sar_validation.json"

THRESHOLD = 0.50          # susceptibility above this = predicted flood-prone
HOLDOUT_PAD_DEG = 0.01    # keep training labels clear of the SAR footprint edge


def main():
    bands = json.load(open(BANDS_JSON))["bands"]
    df = pd.read_parquet(TABLE)

    sar = gpd.read_file(SAR).to_crs("EPSG:4326")
    sar_left, sar_bottom, sar_right, sar_top = sar.total_bounds

    with rasterio.open(STACK) as src:
        raw_window = from_bounds(
            sar_left - HOLDOUT_PAD_DEG, sar_bottom - HOLDOUT_PAD_DEG,
            sar_right + HOLDOUT_PAD_DEG, sar_top + HOLDOUT_PAD_DEG,
            transform=src.transform,
        )
        window = raw_window.round_offsets().round_lengths()
        stack = src.read(window=window).astype("float64")
        transform = src.window_transform(window)
        H, W = stack.shape[1:]
        left, bottom, right, top = window_bounds(window, src.transform)
        crs = src.crs

    print(f">> Spatially held-out validation over the coastal SAR window "
          f"({left:.3f},{bottom:.3f})-({right:.3f},{top:.3f})")

    # ---- split training points by geography, not at random --------------------
    inside = ((df["lon"] >= left) & (df["lon"] <= right) &
              (df["lat"] >= bottom) & (df["lat"] <= top))
    train = df[~inside]
    print(f"   training points outside window: {len(train)} "
          f"({int(train['label'].sum())} flood / {int((1 - train['label']).sum())} non-flood)")
    print(f"   points inside window withheld : {int(inside.sum())}")
    if train["label"].nunique() < 2:
        sys.exit("   Held-out split leaves a single class -- cannot train.")

    feats = [f for f in predictors.PRIMARY_NUMERIC if f in df.columns]
    model = XGBClassifier(
        n_estimators=400, max_depth=5, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8, eval_metric="logloss",
        random_state=42, n_jobs=-1)
    model.fit(train[feats].astype(float), train["label"].astype(int))

    # ---- predict wall-to-wall inside the window -------------------------------
    order = [bands.index(f) for f in feats]
    X = stack[order].reshape(len(feats), -1).T
    finite = np.isfinite(X).all(axis=1)
    surface = np.full(X.shape[0], np.nan)
    surface[finite] = model.predict_proba(X[finite])[:, 1]
    surface = surface.reshape(H, W)
    print(f"   predicted {int(finite.sum())}/{X.shape[0]} valid pixels")

    # ---- observed SAR flooding, rasterized to the same grid -------------------
    observed = rasterize(
        ((geom, 1) for geom in sar.geometry),
        out_shape=(H, W), transform=transform, fill=0, dtype="uint8").astype(bool)
    print(f"   SAR polygons: {len(sar)}; observed-flood pixels: {int(observed.sum())}")

    valid = np.isfinite(surface)
    y_true = observed[valid].astype(int)
    y_score = surface[valid]
    if y_true.sum() == 0:
        sys.exit("   No observed-flood pixels intersect the valid prediction area.")

    auc = float(roc_auc_score(y_true, y_score))
    y_pred = (y_score >= THRESHOLD).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    pod = tp / (tp + fn)                       # hit rate / probability of detection
    far = fp / (tp + fp) if (tp + fp) else 0.0  # false-alarm ratio (upper bound, see docstring)
    csi = tp / (tp + fp + fn)                  # critical success index

    fpr, tpr, _ = roc_curve(y_true, y_score)
    step = max(1, len(fpr) // 200)

    # ---- success-rate curve: observed flooding captured vs landscape ranked ---
    order_desc = np.argsort(y_score)[::-1]
    cum_hits = np.cumsum(y_true[order_desc]) / y_true.sum()
    frac_area = np.arange(1, len(order_desc) + 1) / len(order_desc)
    srate = {
        f"top_{int(p * 100)}pct_area": round(float(cum_hits[int(p * len(cum_hits)) - 1]), 4)
        for p in (0.05, 0.10, 0.20, 0.30, 0.50)
    }

    out = {
        "window": {"left": left, "bottom": bottom, "right": right, "top": top,
                   "definition": "SAR footprint plus 0.01-degree buffer"},
        "n_train_points_outside": int(len(train)),
        "n_points_withheld_inside": int(inside.sum()),
        "features": feats,
        "n_valid_pixels": int(valid.sum()),
        "n_observed_flood_pixels": int(y_true.sum()),
        "observed_flood_fraction": round(float(y_true.mean()), 5),
        "threshold": THRESHOLD,
        "roc_auc": round(auc, 4),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "hit_rate_pod": round(float(pod), 4),
        "false_alarm_ratio": round(float(far), 4),
        "critical_success_index": round(float(csi), 4),
        "success_rate_curve": srate,
        "roc_curve": {"fpr": [round(float(v), 4) for v in fpr[::step]],
                      "tpr": [round(float(v), 4) for v in tpr[::step]]},
        "caveat": ("SAR observes flooding only on its ~12-day revisit; polygons are a "
                   "lower bound on true flooding, so the false-alarm ratio is an upper "
                   "bound and non-flood pixels mean 'not observed flooded', not 'dry'."),
    }
    os.makedirs("data/processed", exist_ok=True)
    json.dump(out, open(OUT, "w"), indent=2)

    # also persist the held-out predicted surface for the validation map
    prof = {"driver": "GTiff", "height": H, "width": W, "count": 1,
            "dtype": "float32", "crs": crs, "transform": transform,
            "nodata": -9999.0}
    with rasterio.open("data/processed/susceptibility_heldout.tif", "w", **prof) as dst:
        dst.write(np.where(np.isfinite(surface), surface, -9999.0).astype("float32"), 1)

    print(f"\n   ROC-AUC (geographic transfer): {auc:.4f}")
    print(f"   hit rate {pod:.3f} | false-alarm ratio {far:.3f} | CSI {csi:.3f}")
    print(f"   top 10% of landscape by susceptibility captures "
          f"{100 * srate['top_10pct_area']:.1f}% of observed flooding")
    print(f"   top 20%: {100 * srate['top_20pct_area']:.1f}%")
    print(f">> Saved -> {OUT} and data/processed/susceptibility_heldout.tif")


if __name__ == "__main__":
    main()
