"""Step 1: build & visually verify the multi-temporal Sentinel-1 flood-frequency inventory."""
import os
import sys
import urllib.request

import ee

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from floodrisk import config, ee_init, sar  # noqa: E402

OUT_PNG = "data/processed/flood_freq_dk.png"
OUT_REF_PNG = "data/processed/flood_freq_nethravathi.png"


def download(url, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    urllib.request.urlretrieve(url, path)
    return os.path.getsize(path)


def main():
    ee = ee_init.init()
    geom = ee_init.aoi_district()  # real district polygon (removes sea corner)

    print(">> Building multi-temporal SAR flood-frequency inventory over Dakshina Kannada")
    print(f"   Monsoon windows: {config.MONSOON_WINDOWS}")
    print(f"   Dry-season baseline: {config.DRY_WINDOWS}")

    freq, n_passes = sar.flood_frequency(geom, config.MONSOON_WINDOWS)
    print(f"   Total monsoon SAR passes stacked: {n_passes}")

    # --- Diagnostics: how much area is flagged flood-prone at various frequencies ---
    stats_img = freq.gt(0).rename("any").addBands(freq.gte(0.25).rename("f25")) \
        .addBands(freq.gte(0.5).rename("f50"))
    stats = stats_img.multiply(ee.Image.pixelArea()).reduceRegion(
        reducer=ee.Reducer.sum(), geometry=geom, scale=30, maxPixels=1e10, bestEffort=True
    ).getInfo()
    for k, v in stats.items():
        print(f"   area {k}: {v/1e6:.1f} km^2")

    # --- Visualization thumbnails (blue=low freq -> red=high freq) ---
    vis = {"min": 0.0, "max": 1.0, "palette": ["cccccc", "00b7ff", "0033ff", "ff9900", "ff0000"]}

    url_dk = freq.getThumbURL({**vis, "region": geom, "dimensions": 1024})
    size = download(url_dk, OUT_PNG)
    print(f"   Saved DK inventory thumbnail: {OUT_PNG} ({size/1024:.0f} KB)")

    # Zoom on Nethravathi/Bantwal corridor for a targeted sanity check
    neth = ee.Geometry.Rectangle([74.90, 12.85, 75.15, 13.05])
    url_neth = freq.getThumbURL({**vis, "region": neth, "dimensions": 1024})
    size = download(url_neth, OUT_REF_PNG)
    print(f"   Saved Nethravathi zoom thumbnail: {OUT_REF_PNG} ({size/1024:.0f} KB)")

    print(">> Done. Inspect the PNGs to confirm floodplains/low-lying areas light up.")


if __name__ == "__main__":
    main()
