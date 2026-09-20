"""Sensitivity of the trigger to its four author-chosen constants.

Equation (11) has three weights (0.5, 0.3, 0.2) and a saturation reference
(theta_sat = 200 mm). The IMD thresholds are published; these four are not. The
routing constants were swept and these were not, which is an asymmetry worth
removing, especially because the trigger carries the paper's weakest result: the
margin between a documented flood and a heavy-rain non-flood day.

This script sweeps the weight simplex and theta_sat and reports, for each
setting, two quantities computed on the SAME five scenarios already published in
Table 8 (no refetch, no new events, so this is a sensitivity analysis and not a
fit):

  margin_adv  = min(T over documented floods) - T(heavy-rain non-flood day)
                -> the hard discrimination the operating point nearly fails
  margin_ord  = min(T over documented floods) - T(ordinary wet day)
                -> the easy discrimination the operating point passes

Reporting the margin as a surface shows whether the operating point was a lucky
choice, a poor one, or immaterial. It does NOT license moving to the maximum:
selecting weights by these events would convert a validated trigger into a
fitted one, which is exactly the property the paper claims. The optimum is
reported for information and explicitly not adopted.

Outputs data/processed/trigger_sweep.json.
"""
import itertools
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from floodrisk import live  # noqa: E402

IN = "data/processed/trigger_table.json"
OUT = "data/processed/trigger_sweep.json"

STEP = 0.05                                   # weight-simplex resolution
THETA_SAT = [100, 150, 200, 250, 300]         # mm
BASE_W = (0.5, 0.3, 0.2)
BASE_SAT = 200.0


def trigger(r6, r24, r72, w, theta_sat):
    wd, ws, wb = w
    daily = min(r24 / live.IMD_VERY_HEAVY, 1.0)
    sat = min(r72 / theta_sat, 1.0)
    burst = min(r6 / live.IMD_HEAVY, 1.0)
    return min(wd * daily + ws * sat + wb * burst, 1.0)


def simplex(step=STEP):
    """All (w_daily, w_sat, w_burst) on the unit simplex at the given step."""
    n = int(round(1 / step))
    for i, j in itertools.product(range(n + 1), repeat=2):
        k = n - i - j
        if k < 0:
            continue
        yield (round(i * step, 3), round(j * step, 3), round(k * step, 3))


def main():
    rows = json.load(open(IN))["scenarios"]
    by_kind = {}
    for r in rows:
        by_kind.setdefault(r["kind"], []).append(
            (r["scenario"], r["rain_6h_mm"], r["rain_24h_mm"], r["rain_72h_mm"]))

    floods = by_kind["documented flood"]
    heavy = by_kind["heavy non-flood"][0]
    ordinary = by_kind["ordinary wet"][0]
    dry = by_kind["dry"][0]
    print(f">> Trigger sweep over {len(list(simplex()))} weight triples "
          f"x {len(THETA_SAT)} theta_sat values")

    def margins(w, ts):
        tf = [trigger(f[1], f[2], f[3], w, ts) for f in floods]
        th = trigger(heavy[1], heavy[2], heavy[3], w, ts)
        to = trigger(ordinary[1], ordinary[2], ordinary[3], w, ts)
        td = trigger(dry[1], dry[2], dry[3], w, ts)
        return min(tf) - th, min(tf) - to, min(tf), th, to, td

    cells = []
    for ts in THETA_SAT:
        for w in simplex():
            m_adv, m_ord, tmin, th, to, td = margins(w, ts)
            cells.append({
                "w_daily": w[0], "w_sat": w[1], "w_burst": w[2],
                "theta_sat": ts,
                "margin_adversarial": round(m_adv, 4),
                "margin_ordinary": round(m_ord, 4),
                "min_flood_T": round(tmin, 4),
                "heavy_nonflood_T": round(th, 4),
                "ordinary_T": round(to, 4),
                "dry_T": round(td, 4),
                "ordering_ok": bool(tmin > to > td),
            })

    op = next(c for c in cells
              if (c["w_daily"], c["w_sat"], c["w_burst"]) == BASE_W
              and c["theta_sat"] == BASE_SAT)

    valid = [c for c in cells if c["ordering_ok"]]
    best = max(valid, key=lambda c: c["margin_adversarial"])
    worst = min(valid, key=lambda c: c["margin_adversarial"])

    # How often does the operating point's qualitative conclusion survive?
    n_ord_ok = sum(1 for c in cells if c["ordering_ok"])
    n_adv_ok = sum(1 for c in cells if c["margin_adversarial"] > 0)
    n_adv_strong = sum(1 for c in cells if c["margin_adversarial"] > 0.05)

    # Marginal effect of each weight on the adversarial margin, at theta_sat=200
    at200 = [c for c in cells if c["theta_sat"] == 200]
    by_wsat = {}
    for c in at200:
        by_wsat.setdefault(c["w_sat"], []).append(c["margin_adversarial"])
    sat_trend = {k: round(sum(v) / len(v), 4) for k, v in sorted(by_wsat.items())}

    out = {
        "step": STEP,
        "theta_sat_values": THETA_SAT,
        "n_cells": len(cells),
        "operating_point": op,
        "best_adversarial_margin": best,
        "worst_adversarial_margin": worst,
        "n_cells_ordering_ok": n_ord_ok,
        "n_cells_adversarial_positive": n_adv_ok,
        "n_cells_adversarial_above_0.05": n_adv_strong,
        "mean_adversarial_margin_by_w_sat_at_theta200": sat_trend,
        "adopted": "operating point retained; optimum reported but NOT adopted",
        "cells": cells,
    }
    os.makedirs("data/processed", exist_ok=True)
    json.dump(out, open(OUT, "w"), indent=2)

    print(f"   operating point (0.5/0.3/0.2, theta_sat=200): "
          f"adversarial margin {op['margin_adversarial']:+.4f}, "
          f"ordinary margin {op['margin_ordinary']:+.4f}")
    print(f"   ordering correct in {n_ord_ok}/{len(cells)} cells")
    print(f"   adversarial margin positive in {n_adv_ok}/{len(cells)} cells; "
          f"> 0.05 in {n_adv_strong}")
    print(f"   best  : w={best['w_daily']}/{best['w_sat']}/{best['w_burst']} "
          f"theta={best['theta_sat']} -> {best['margin_adversarial']:+.4f}")
    print(f"   worst : w={worst['w_daily']}/{worst['w_sat']}/{worst['w_burst']} "
          f"theta={worst['theta_sat']} -> {worst['margin_adversarial']:+.4f}")
    print(f"   mean adversarial margin by saturation weight (theta=200): {sat_trend}")
    print(f">> Saved -> {OUT}")


if __name__ == "__main__":
    main()
