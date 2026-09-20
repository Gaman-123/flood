"""Export the predictor stack as a district-wide multi-band GeoTIFF.

This is what makes per-location explanation possible: the dashboard needs the actual
FEATURE VALUES at a clicked point (elevation, HAND, TWI, ...) to run SHAP against the
trained model, not just the final probability. Sampling a local raster keeps
/api/explain fast and offline instead of round-tripping to Earth Engine per click.

Band order matches models/susceptibility_best.joblib's `columns`.
"""
import os
import sys
import urllib.request

import ee

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from floodrisk import config, ee_init, predictors  # noqa: E402

OUT = "web_assets/predictor_stack.tif"
BANDS = predictors.PRIMARY_NUMERIC          # the model's feature set, in order


def download(url, path, timeout=300):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    for attempt in range(4):
        try:
            data = urllib.request.urlopen(url, timeout=timeout).read()
            with open(path, "wb") as f:
                f.write(data)
            return os.path.getsize(path)
        except Exception as e:
            import time
            print(f"      attempt {attempt+1} failed ({e}); retry")
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("predictor stack download failed")


def main():
    ee = ee_init.init()
    print(">> Exporting district predictor stack for per-point explanation")
    print(f"   bands: {BANDS}")

    geom = ee_init.aoi_district()
    stack = predictors.build_stack(geom).select(BANDS).toFloat()
    region = geom

    url = stack.getDownloadURL({
        "scale": config.EXPLAIN_RASTER_SCALE_M,
        "region": region,
        "format": "GEO_TIFF",
        "crs": "EPSG:4326",
    })
    size = download(url, OUT)
    print(f"   {OUT}: {size/1024:.0f} KB")

    # Record band order so the API never mis-maps a column.
    import json
    json.dump({"bands": BANDS, "bbox": config.DK_BBOX,
               "scale_m": config.EXPLAIN_RASTER_SCALE_M,
               "coverage": "Dakshina Kannada administrative district"},
              open(OUT.replace(".tif", ".bands.json"), "w"))
    print(f"   band manifest -> {OUT.replace('.tif', '.bands.json')}")


if __name__ == "__main__":
    main()
