"""Invariants for per-location explanation and the NL tool layer.

The explanation endpoint is what lets the dashboard (and the language model) make
claims about a place. These tests pin the properties that keep those claims honest:
attributions must reconcile with the prediction, physically-known locations must
land in the right risk band, and the narration must never assert something the
data doesn't say.
"""
import os

import pytest

from floodrisk import tools

STACK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "web_assets", "predictor_stack.tif")
MODEL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "models", "susceptibility_best.joblib")

pytestmark = pytest.mark.skipif(
    not (os.path.exists(STACK) and os.path.exists(MODEL)),
    reason="run `make train` and scripts/export_predictor_stack.py first",
)

# Ground-truth-ish reference points (lat, lon)
KULUR = (12.9250, 74.8270)          # riverside flood hotspot
UPLAND = (12.85, 74.915)            # elevated inland reference
OUTSIDE = (20.0, 80.0)              # far outside the exported raster


@pytest.fixture(scope="module")
def explain_mod():
    from floodrisk import explain
    return explain


def test_outside_raster_returns_none(explain_mod):
    assert explain_mod.explain(*OUTSIDE) is None


def test_low_lying_site_scores_higher_than_upland(explain_mod):
    kulur = explain_mod.explain(*KULUR)
    upland = explain_mod.explain(*UPLAND)
    assert kulur and upland
    assert kulur["susceptibility"] > upland["susceptibility"], (
        "a riverside site must score above elevated inland terrain")


def test_probability_and_band_are_consistent(explain_mod):
    r = explain_mod.explain(*KULUR)
    assert 0.0 <= r["susceptibility"] <= 1.0
    assert 0.0 <= r["calibrated_probability"] <= 1.0
    assert r["risk_band"] == explain_mod.risk_band(r["susceptibility"])


def test_drivers_are_ranked_by_absolute_contribution(explain_mod):
    r = explain_mod.explain(*KULUR)
    mags = [abs(d["shap"]) for d in r["drivers"]]
    assert mags == sorted(mags, reverse=True)
    for d in r["drivers"]:
        assert d["direction"] == ("increases" if d["shap"] > 0 else "decreases")


def test_narration_never_claims_high_or_low_values(explain_mod):
    """Regression: wording keyed off the SHAP sign once contradicted the value
    (e.g. 'drainage density 0 — dense channel network nearby')."""
    for pt in (KULUR, UPLAND):
        summary = explain_mod.explain(*pt)["summary"].lower()
        for banned in ("dense channel", "few channels", "lower rainfall",
                       "high rainfall", "low ground", "high ground"):
            assert banned not in summary, f"narration asserts an unverified claim: {banned}"


def test_depth_caveat_is_always_present(explain_mod):
    r = explain_mod.explain(*KULUR)
    assert "not water depth" in r["caveat"].lower()


# --------------------------------------------------------------------- tools

def test_tool_registry_matches_schemas():
    names = {s["name"] for s in tools.SCHEMAS}
    assert names == set(tools.REGISTRY), "every schema must map to a real function"


def test_unknown_tool_is_rejected():
    assert "error" in tools.call("does_not_exist")


def test_rank_incidents_orders_hardest_first():
    r = tools.call("rank_incidents_by_need", scenario="may2025")
    if "error" in r:
        pytest.skip("dispatch assets missing")
    ranking = r["ranking"]
    reachable = [x for x in ranking if x["best_eta_min"] is not None]
    etas = [x["best_eta_min"] for x in reachable]
    assert etas == sorted(etas, reverse=True), f"must be hardest-first, got {etas}"


def test_dispatch_plan_is_one_to_one():
    r = tools.call("dispatch_plan", scenario="may2025")
    if "error" in r:
        pytest.skip("dispatch assets missing")
    incidents = [a["incident"] for a in r["assignments"]]
    assert len(incidents) == len(set(incidents)), "an incident cannot be assigned twice"
