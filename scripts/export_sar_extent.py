"""Export the REAL Sentinel-1 SAR observed-flood extent as vectors for the web.

Vectorizes flood_freq (fraction of monsoon passes seen flooded) over the city bbox
so the dashboard's "SAR observed flood extent" layer shows genuine detected water,
not hand-drawn polygons.
"""
import json
import os
import sys

import ee

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from floodrisk import config, ee_init, sar  # noqa: E402

BBOX = [74.78, 12.80, 74.92, 13.00]
OUT = "web_assets/sar_extent.geojson"


def main():
    ee = ee_init.init()
    region = ee.Geometry.Rectangle(BBOX)
    print(">> Exporting real SAR flood extent")
    flood_freq, _ = sar.flood_frequency(ee_init.aoi_district(), config.MONSOON_WINDOWS)
    # pixels seen flooded in >=1 pass, within the city bbox
    mask = flood_freq.gt(0).selfMask().clip(region)
    vectors = mask.reduceToVectors(
        geometry=region, scale=90, geometryType="polygon",
        eightConnected=False, maxPixels=1e9, bestEffort=True,
    )
    fc = vectors.getInfo()
    # tag source, drop tiny specks
    feats = [f for f in fc["features"]
             if f["geometry"] and f["geometry"]["type"] in ("Polygon", "MultiPolygon")]
    for f in feats:
        f["properties"] = {"source": "Sentinel-1 SAR"}
    out = {"type": "FeatureCollection", "features": feats}
    os.makedirs("web_assets", exist_ok=True)
    json.dump(out, open(OUT, "w"))
    print(f"   {OUT}: {len(feats)} flood polygons")


if __name__ == "__main__":
    main()
