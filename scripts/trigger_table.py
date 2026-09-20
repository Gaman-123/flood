"""Emit the raw meteorological inputs behind every trigger value T(t).

The conference paper reported only the four resulting T values. A reviewer cannot
check a trigger they cannot see the inputs to, so this script publishes the full
audit trail: the 6 h / 24 h / 72 h antecedent rainfall totals pulled from the
ERA5 archive for each scenario instant, which India Meteorological Department
daily-rainfall category each 24 h total falls in, the three sub-terms of the
trigger, and the resulting T.

It also runs a monotonicity check: scaling a rainfall profile up must never lower
T. That is a falsifiable property of the functional form, not a fitted result.

All rainfall is fetched live from the Open-Meteo ERA5 archive; nothing is stored
or hand-entered, so re-running reproduces the table from source.
"""
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from floodrisk import live  # noqa: E402

OUT = "data/processed/trigger_table.json"
MANGALURU = (12.87, 74.84)

# (label, kind, instant, archive-window-start, archive-window-end)
#
# The fourth row is deliberately adversarial. 2025-07-15 was an IMD "Heavy"
# rainfall day with NO reported urban flooding in Mangaluru. Including it tests
# whether the trigger merely tracks rainfall magnitude or actually discriminates
# flood-producing conditions, and the answer is reported as measured.
SCENARIOS = [
    ("May 2025 Mangaluru urban flood", "documented flood",
     datetime(2025, 5, 30, 6, tzinfo=timezone.utc), "2025-05-25", "2025-06-02"),
    ("Aug 2024 Nethravathi river flood", "documented flood",
     datetime(2024, 8, 1, 6, tzinfo=timezone.utc), "2024-07-27", "2024-08-04"),
    ("Heavy rain, no reported flooding", "heavy non-flood",
     datetime(2025, 7, 15, 6, tzinfo=timezone.utc), "2025-07-10", "2025-07-18"),
    ("Ordinary monsoon wet day", "ordinary wet",
     datetime(2025, 9, 6, 6, tzinfo=timezone.utc), "2025-09-01", "2025-09-09"),
    ("Dry-season baseline", "dry",
     datetime(2025, 2, 16, 6, tzinfo=timezone.utc), "2025-02-10", "2025-02-18"),
]


def imd_category(r24):
    """IMD daily-rainfall category for a 24 h total (mm)."""
    if r24 >= live.IMD_EXTREME:
        return "Extremely Heavy"
    if r24 >= live.IMD_VERY_HEAVY:
        return "Very Heavy"
    if r24 >= live.IMD_HEAVY:
        return "Heavy"
    if r24 >= 15.6:
        return "Moderate"
    if r24 > 0:
        return "Light"
    return "No rain"


def decompose(ant):
    """The three weighted sub-terms of the trigger, so the total is auditable."""
    r6, r24, r72 = ant.get("6h", 0.0), ant.get("24h", 0.0), ant.get("72h", 0.0)
    daily = min(r24 / live.IMD_VERY_HEAVY, 1.0)
    sat = min(r72 / 200.0, 1.0)
    burst = min(r6 / live.IMD_HEAVY, 1.0)
    return {
        "daily_term": round(daily, 4), "daily_weighted": round(0.5 * daily, 4),
        "saturation_term": round(sat, 4), "saturation_weighted": round(0.3 * sat, 4),
        "burst_term": round(burst, 4), "burst_weighted": round(0.2 * burst, 4),
    }


def main():
    lat, lon = MANGALURU
    print(">> Trigger input audit trail (ERA5 archive via Open-Meteo)")
    rows = []
    for label, kind, when, start, end in SCENARIOS:
        times, precip = live.fetch_openmeteo_archive(lat, lon, start, end)
        ant = live.antecedent_rainfall(times, precip, now=when)
        T = live.rainfall_trigger(ant)
        parts = decompose(ant)
        rows.append({
            "scenario": label,
            "kind": kind,
            "instant_utc": when.isoformat(),
            "archive_window": [start, end],
            "rain_6h_mm": ant["6h"], "rain_24h_mm": ant["24h"],
            "rain_72h_mm": ant["72h"],
            "imd_category_24h": imd_category(ant["24h"]),
            **parts,
            "trigger_T": T,
        })
        print(f"   {label:36s} 6h={ant['6h']:6.1f} 24h={ant['24h']:6.1f} "
              f"72h={ant['72h']:6.1f}  [{imd_category(ant['24h']):16s}] T={T:.3f}")

    # ---- falsifiable property: T is monotone non-decreasing in rainfall -------
    base = {"6h": 10.0, "24h": 30.0, "72h": 60.0}
    scales = [0.0, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0]
    mono = [{"scale": s,
             "T": live.rainfall_trigger({k: v * s for k, v in base.items()})}
            for s in scales]
    is_monotone = all(b["T"] >= a["T"] for a, b in zip(mono, mono[1:]))
    print(f"\n   monotonicity under uniform rainfall scaling: "
          f"{[m['T'] for m in mono]} -> {'PASS' if is_monotone else 'FAIL'}")

    floods = [r["trigger_T"] for r in rows if r["kind"] == "documented flood"]
    ordinary = next(r["trigger_T"] for r in rows if r["kind"] == "ordinary wet")
    dry = next(r["trigger_T"] for r in rows if r["kind"] == "dry")
    heavy_nf = next(r["trigger_T"] for r in rows if r["kind"] == "heavy non-flood")

    ordering_correct = min(floods) > ordinary > dry
    # Separation against the adversarial case is reported, not asserted: this is
    # where the trigger's discriminative power is genuinely weakest.
    margin_vs_heavy = round(min(floods) - heavy_nf, 3)
    print(f"   documented events rank above ordinary and dry: "
          f"{'PASS' if ordering_correct else 'FAIL'}")
    print(f"   margin of the weaker documented flood over the heavy non-flood day: "
          f"{margin_vs_heavy:+.3f}")

    out = {
        "location": {"lat": lat, "lon": lon, "name": "Mangaluru"},
        "imd_thresholds_mm": {"heavy": live.IMD_HEAVY,
                              "very_heavy": live.IMD_VERY_HEAVY,
                              "extreme": live.IMD_EXTREME},
        "weights": {"daily": 0.5, "saturation": 0.3, "burst": 0.2},
        "saturation_reference_mm": 200.0,
        "scenarios": rows,
        "monotonicity_check": {"base_mm": base, "samples": mono, "passed": is_monotone},
        "event_ordering_correct": ordering_correct,
        "margin_over_heavy_non_flood_day": margin_vs_heavy,
    }
    os.makedirs("data/processed", exist_ok=True)
    json.dump(out, open(OUT, "w"), indent=2)
    print(f">> Saved -> {OUT}")


if __name__ == "__main__":
    main()
