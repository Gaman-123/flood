"""Step 3b: district flood-susceptibility map via server-side classification + thumbnail.

The quantitative model (AUC/SHAP) is the local sklearn XGBoost from Step 3. For the
wall-to-wall MAP we train an equivalent GEE smileRandomForest (probability output) on
the same sampled points and classify the predictor stack — reliable and stays
server-side (large raster downloads hit GEE's 50 MB / 400 limits). RF vs XGBoost
differed by <0.001 AUC, so the map is materially the same model.
"""
import os
import sys
import urllib.request

import ee

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from floodrisk import config, ee_init, sar, predictors, sampling  # noqa: E402

SUSC_PNG = "data/processed/susceptibility_map.png"
FEATURES = predictors.PRIMARY_NUMERIC

VALIDATION = {
    "Mangaluru city (May 2025 flood)": (74.842, 12.870),
    "Bantwal / Nethravathi (Aug 2024)": (75.035, 12.890),
    "Ullal coast": (74.842, 12.805),
    "Upland reference (expect LOW)": (75.35, 12.80),
}


def download(url, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    for attempt in range(5):
        try:
            data = urllib.request.urlopen(url, timeout=180).read()
            with open(path, "wb") as f:
                f.write(data)
            return os.path.getsize(path)
        except Exception as e:
            import time
            print(f"      thumb attempt {attempt+1} failed ({e}); retry"); time.sleep(5 * (attempt + 1))
    raise RuntimeError("thumbnail download failed")


def main():
    ee = ee_init.init()
    geom = ee_init.aoi_district()

    print(">> Step 3b: susceptibility map (server-side smileRandomForest)")
    flood_freq, _ = sar.flood_frequency(geom, config.MONSOON_WINDOWS)
    stack = predictors.build_stack(geom).select(FEATURES)

    # Same sampled points as Step 2 (seed-stable); stack has elevation+hand for the domain mask
    fc = sampling.build_training_points(geom, flood_freq, stack, n_per_class=1500)

    clf = (ee.Classifier.smileRandomForest(numberOfTrees=400)
           .setOutputMode("PROBABILITY")
           .train(fc, "label", FEATURES))
    susc = stack.classify(clf).rename("susceptibility").clip(geom)

    vis = {"min": 0, "max": 1, "palette": ["2c7bb6", "abd9e9", "ffffbf", "fdae61", "d7191c"],
           "region": geom.bounds(), "dimensions": 1024}
    size = download(susc.getThumbURL(vis), SUSC_PNG)
    print(f"   Saved map: {SUSC_PNG} ({size/1024:.0f} KB)")

    # server-side validation at known points
    pts = ee.FeatureCollection([
        ee.Feature(ee.Geometry.Point([lon, lat]), {"name": name})
        for name, (lon, lat) in VALIDATION.items()
    ])
    sampled = susc.reduceRegions(pts, ee.Reducer.first(), scale=90).getInfo()
    print("\n   Susceptibility at validation points (0-1):")
    for f in sampled["features"]:
        p = f["properties"]
        val = p.get("first")
        val = f"{val:.3f}" if val is not None else "n/a"
        print(f"      {p['name']:36s} {val}")


if __name__ == "__main__":
    main()
