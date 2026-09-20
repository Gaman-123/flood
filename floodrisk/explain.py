"""Per-location flood-risk explanation via local SHAP attributions.

Answers "why is THIS place risky?" with a real computation rather than prose:
sample the predictor raster at a coordinate, run the trained model, and decompose
the prediction into per-feature SHAP contributions. Every number the dashboard or
the NL layer states about a location comes from here.
"""
import functools
import json
import os

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STACK_TIF = os.path.join(_REPO, "web_assets", "predictor_stack.tif")
BANDS_JSON = os.path.join(_REPO, "web_assets", "predictor_stack.bands.json")
MODEL_PATH = os.path.join(_REPO, "models", "susceptibility_best.joblib")

# Plain-language label + unit per feature. Deliberately NO "high/low" wording keyed
# off the SHAP sign: a feature's contribution direction does not tell you whether its
# value is high or low (e.g. high rainfall can still contribute negatively relative to
# the district baseline), and asserting otherwise produced text that contradicted the
# displayed value. The narration states the measured value and its effect, nothing more.
FEATURE_TEXT = {
    "elevation": ("elevation", " m"),
    "hand": ("height above nearest drainage", " m"),
    "dist_river": ("distance to river", " m"),
    "twi": ("topographic wetness index", ""),
    "rain_annual": ("mean annual rainfall", " mm"),
    "drainage_density": ("drainage density", ""),
    "slope": ("slope", "°"),
    "curvature": ("curvature", ""),
    "aspect": ("aspect", "°"),
}


@functools.lru_cache(maxsize=1)
def _load():
    """Load model + raster handle once (cached across requests).

    joblib.load unpickles, which is unsafe for untrusted input. This file is a
    first-party build artifact produced locally by scripts/train_susceptibility.py
    and gitignored, never downloaded — so there is no untrusted-source exposure.
    """
    import joblib
    import rasterio

    bundle = joblib.load(MODEL_PATH)
    bands = json.load(open(BANDS_JSON))["bands"]
    # Read the district stack into memory and close the file: holding an open
    # GDAL handle in a process-lifetime cache leaks a descriptor in a long-running
    # API and produces noise at interpreter shutdown.
    with rasterio.open(STACK_TIF) as src:
        if src.count != len(bands):
            raise RuntimeError(f"raster has {src.count} bands, manifest lists {len(bands)}")
        arr = src.read()                       # (bands, rows, cols)
        meta = {"bounds": tuple(src.bounds), "transform": src.transform,
                "nodata": src.nodata, "height": src.height, "width": src.width}
    return bundle, bands, arr, meta


@functools.lru_cache(maxsize=1)
def _explainer():
    import shap
    bundle, _, _, _ = _load()
    return shap.TreeExplainer(bundle["model"])


def sample_predictors(lat, lon):
    """Predictor values at a coordinate. Returns None if outside the raster."""
    _, bands, arr, meta = _load()
    left, bottom, right, top = meta["bounds"]
    if not (left <= lon <= right and bottom <= lat <= top):
        return None

    # rasterio: ~transform * (x, y) -> (col, row) as floats
    col, row = ~meta["transform"] * (lon, lat)
    r, c = int(row), int(col)
    if not (0 <= r < meta["height"] and 0 <= c < meta["width"]):
        return None

    vals = arr[:, r, c]
    if any(v is None or not np.isfinite(v) for v in vals):
        return None
    if meta["nodata"] is not None and all(v == meta["nodata"] for v in vals):
        return None
    return dict(zip(bands, [float(v) for v in vals]))


def explain(lat, lon, top_k=4):
    """Susceptibility + calibrated probability + SHAP attributions at a point.

    Returns None when the coordinate falls outside the district raster or on a
    no-data pixel outside the administrative/land mask.
    """
    feats = sample_predictors(lat, lon)
    if feats is None:
        return None

    bundle, _, _, _ = _load()
    cols = bundle["columns"]
    x = np.array([[feats[c] for c in cols]], dtype=float)

    raw = float(bundle["model"].predict_proba(x)[0, 1])
    calibrated = raw
    if bundle.get("calibrated") is not None:
        try:
            calibrated = float(bundle["calibrated"].predict_proba(x)[0, 1])
        except Exception:
            pass

    sv = _explainer().shap_values(x)
    if isinstance(sv, list):
        sv = sv[1]
    sv = np.asarray(sv)
    if sv.ndim == 3:
        sv = sv[:, :, -1]
    contrib = sv[0]

    drivers = sorted(
        ({"feature": c, "value": round(feats[c], 2), "shap": round(float(s), 4),
          "direction": "increases" if s > 0 else "decreases"}
         for c, s in zip(cols, contrib)),
        key=lambda d: abs(d["shap"]), reverse=True,
    )

    return {
        "lat": lat, "lon": lon,
        "susceptibility": round(raw, 4),
        "calibrated_probability": round(calibrated, 4),
        "risk_band": risk_band(raw),
        "features": {k: round(v, 2) for k, v in feats.items()},
        "drivers": drivers[:top_k],
        "all_drivers": drivers,                      # every factor, ranked
        "sar_observed": observed_flooding(lat, lon),  # measured, not predicted
        **context(lat, lon),
        "summary": narrate(drivers[:top_k], raw),
        "caveat": "Relative flood-risk exposure index — not water depth.",
    }


def _haversine_km(lat1, lon1, lat2, lon2):
    from math import radians, sin, cos, asin, sqrt
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 6371.0 * 2 * asin(sqrt(a))


@functools.lru_cache(maxsize=1)
def _sar_polygons():
    """Observed Sentinel-1 flood polygons, for point-in-extent testing."""
    path = os.path.join(_REPO, "web_assets", "sar_extent.geojson")
    if not os.path.exists(path):
        return None
    try:
        from shapely.geometry import shape
        from shapely.strtree import STRtree
        feats = json.load(open(path))["features"]
        geoms = [shape(f["geometry"]) for f in feats]
        return STRtree(geoms), geoms
    except Exception:
        return None


def observed_flooding(lat, lon):
    """Has Sentinel-1 actually seen water here during the monsoon record?

    This is measured ground truth, independent of the model's prediction — the
    single most useful corroboration for a location.
    """
    idx = _sar_polygons()
    if idx is None:
        return None
    tree, geoms = idx
    try:
        from shapely.geometry import Point
        p = Point(lon, lat)
        for i in tree.query(p):
            if geoms[i].contains(p):
                return True
        return False
    except Exception:
        return None


def context(lat, lon):
    """Nearby named places and hospitals for a coordinate."""
    from . import tools
    places = tools._gazetteer()
    if not places:
        return {}
    ranked = sorted(
        ({**p, "km": round(_haversine_km(lat, lon, p["lat"], p["lon"]), 2)} for p in places),
        key=lambda p: p["km"])
    nearest = ranked[0]
    hospitals = [p for p in ranked if p["kind"] == "hospital"][:3]
    return {
        "nearest_place": {"name": nearest["name"], "kind": nearest["kind"], "km": nearest["km"]},
        # straight-line distance only — a routed ETA needs a road-graph origin/destination
        # pair, which an arbitrary clicked pixel does not have.
        "nearest_hospitals": [{"name": h["name"], "km": h["km"]} for h in hospitals],
    }


def risk_band(p):
    if p < 0.2:
        return "Low"
    if p < 0.4:
        return "Moderate"
    if p < 0.6:
        return "Elevated"
    if p < 0.8:
        return "High"
    return "Very High"


def narrate(drivers, prob):
    """One-sentence plain-language cause, built strictly from the SHAP output.

    Only states the measured value and the direction of its contribution — it never
    infers whether that value is "high" or "low", which the SHAP sign cannot tell us.
    """
    ups = [d for d in drivers if d["shap"] > 0]
    downs = [d for d in drivers if d["shap"] < 0]

    def phrase(d):
        name, unit = FEATURE_TEXT.get(d["feature"], (d["feature"], ""))
        return f"{name} {d['value']:g}{unit}"

    parts = [f"{risk_band(prob)} risk ({prob:.0%})."]
    if ups:
        parts.append("Raised by " + "; ".join(phrase(d) for d in ups[:2]) + ".")
    if downs:
        parts.append("Reduced by " + "; ".join(phrase(d) for d in downs[:2]) + ".")
    return " ".join(parts)
