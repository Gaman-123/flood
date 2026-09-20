"""Step 4: dynamic flood-risk = static susceptibility S(x) x temporal trigger T(t).

Demonstrates the two-stage model: the SAR/terrain susceptibility map (spatial prior)
modulated by a live/antecedent-rainfall trigger (+ tide), producing a time-varying
risk snapshot. Validated by replaying the May 2025 flood vs a calm day.
"""
import os
import sys
import urllib.request
from datetime import datetime, timezone

import ee

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from floodrisk import config, ee_init, sar, predictors, sampling, live  # noqa: E402

MANGALURU = (12.87, 74.84)
FEATURES = predictors.PRIMARY_NUMERIC


def susceptibility_image(ee, geom):
    """Rebuild the trained susceptibility surface (server-side RF, seed-stable)."""
    flood_freq, _ = sar.flood_frequency(geom, config.MONSOON_WINDOWS)
    stack = predictors.build_stack(geom).select(FEATURES)
    fc = sampling.build_training_points(geom, flood_freq, stack, n_per_class=1500)
    clf = (ee.Classifier.smileRandomForest(numberOfTrees=400)
           .setOutputMode("PROBABILITY").train(fc, "label", FEATURES))
    return stack.classify(clf).rename("susceptibility").clip(geom)


def trigger_for(when_utc, start, end):
    """Antecedent-rainfall trigger at Mangaluru for a given instant (archive replay)."""
    lat, lon = MANGALURU
    times, precip = live.fetch_openmeteo_archive(lat, lon, start, end)
    ant = live.antecedent_rainfall(times, precip, now=when_utc)
    return live.rainfall_trigger(ant), ant


def save_thumb(img, geom, path, vmax=1.0):
    vis = {"min": 0, "max": vmax,
           "palette": ["2c7bb6", "abd9e9", "ffffbf", "fdae61", "d7191c"],
           "region": geom.bounds(), "dimensions": 1024}
    for attempt in range(5):
        try:
            data = urllib.request.urlopen(img.getThumbURL(vis), timeout=180).read()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "wb").write(data)
            return os.path.getsize(path)
        except Exception as e:
            import time
            print(f"      thumb retry {attempt+1} ({e})"); time.sleep(5 * (attempt + 1))
    raise RuntimeError("thumb failed")


def main():
    ee = ee_init.init()
    geom = ee_init.aoi_district()
    print(">> Step 4: dynamic risk = susceptibility x rainfall trigger")

    susc = susceptibility_image(ee, geom)

    scenarios = {
        "may2025_flood": (datetime(2025, 5, 30, 6, tzinfo=timezone.utc), "2025-05-25", "2025-06-02"),
        "aug2024_flood": (datetime(2024, 8, 1, 6, tzinfo=timezone.utc), "2024-07-27", "2024-08-04"),
        "drycalm": (datetime(2025, 2, 16, 6, tzinfo=timezone.utc), "2025-02-10", "2025-02-18"),
    }

    # live "now" trigger too
    lat, lon = MANGALURU
    t_now, ant_now = None, None
    try:
        tn, pn = live.fetch_openmeteo_rainfall(lat, lon)
        ant_now = live.antecedent_rainfall(tn, pn)
        t_now = live.rainfall_trigger(ant_now)
        tide = live.fetch_worldtides(lat, lon)
    except Exception as e:
        tide = {"error": str(e)}

    print("\n   Trigger by scenario:")
    for name, (when, s, e) in scenarios.items():
        trig, ant = trigger_for(when, s, e)
        print(f"      {name:16s} T={trig:.3f}   antecedent={ant}")
        risk = susc.multiply(trig).rename("risk")
        size = save_thumb(risk, geom, f"data/processed/risk_{name}.png")
        print(f"        -> risk map data/processed/risk_{name}.png ({size/1024:.0f} KB)")

    print(f"\n   LIVE now: T={t_now}  antecedent={ant_now}")
    print(f"   LIVE tide: {tide}")


if __name__ == "__main__":
    main()
