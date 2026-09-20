"""Invariants for the analyses added for the journal manuscript.

These tests guard the specific claims the manuscript makes. If an upstream change
breaks one, the corresponding sentence in paper_journal.tex has become false and
must be rewritten, not the test relaxed.
"""
import json
import os

import pytest

P = "data/processed"


def _load(name):
    path = os.path.join(P, name)
    if not os.path.exists(path):
        pytest.skip(f"{name} not built; run `make journal-analyses`")
    with open(path) as f:
        return json.load(f)


# --------------------------------------------------------------- sensitivity

def test_sensitivity_covers_the_full_grid():
    d = _load("sensitivity_sweep.json")
    assert len(d["cells"]) == len(d["kappas"]) * len(d["blocks"])


def test_flood_aware_routing_beats_risk_blind_on_exposure():
    """The core routing claim: the operating point lowers mean exposure."""
    d = _load("sensitivity_sweep.json")
    assert d["operating_point"]["mean_exposure"] < d["baseline_risk_blind"]["mean_exposure"]


def test_kappa_sensitivity_is_reported_honestly():
    """District expansion made the high-kappa effect material; preserve that result."""
    d = _load("sensitivity_sweep.json")
    tau = d["operating_point"]["block"]
    row = {c["kappa"]: c["mean_exposure"] for c in d["cells"] if c["block"] == tau}
    hi = max(row)
    assert abs(row[8] - row[hi]) / row[8] > 0.01


def test_threshold_controls_connectivity_monotonically():
    """Raising the impassability threshold can never sever more pairs."""
    d = _load("sensitivity_sweep.json")
    for k in d["kappas"]:
        col = sorted((c["block"], c["unreachable"]) for c in d["cells"] if c["kappa"] == k)
        counts = [u for _, u in col]
        assert counts == sorted(counts, reverse=True), f"non-monotone at kappa={k}"


# ---------------------------------------------------------- spatial validation

def test_spatial_block_cv_never_exceeds_random_cv():
    """Block CV removes leakage, so it cannot score higher than random CV."""
    d = _load("spatial_validation.json")
    for name, s in d["spatial_cv"].items():
        assert s["spatial_block_auc_mean"] <= s["random_kfold_auc_mean"], name


def test_primary_model_is_weaker_than_the_confounded_one():
    """The manuscript's central honesty claim: removing NDVI/LULC costs accuracy.

    If this ever reverses, the confound narrative in Section 4.6 is wrong.
    """
    d = _load("spatial_validation.json")
    assert (d["ablation"]["primary_9"]["test"]["roc_auc"]
            < d["ablation"]["full_12"]["test"]["roc_auc"])


def test_confounded_model_ranks_landcover_or_ndvi_first():
    """The diagnostic that identified the confound must still hold."""
    d = _load("spatial_validation.json")
    assert d["ablation"]["full_12"]["top5"][0] in ("lulc", "ndvi")


def test_primary_model_ranks_terrain_first():
    """With the confound removed, physical drivers must lead."""
    d = _load("spatial_validation.json")
    top3 = d["ablation"]["primary_9"]["top5"][:3]
    assert "elevation" in top3 and "hand" in top3
    assert "lulc" not in top3 and "ndvi" not in top3


def test_no_retained_predictor_is_collinear():
    """VIF < 10 for every factor in the primary set."""
    path = os.path.join(P, "vif.json")
    if not os.path.exists(path):
        pytest.skip("vif.json not built")
    vif = json.load(open(path))["primary_9"]
    assert all(v < 10 for v in vif.values()), vif


# -------------------------------------------------------------- SAR transfer

def test_geographic_transfer_is_honestly_weaker():
    """Transfer AUC must be below the in-sample test AUC.

    A transfer score at or above the random-split score would indicate the split
    is not actually geographic.
    """
    sar = _load("sar_validation.json")
    sv = _load("spatial_validation.json")
    assert sar["roc_auc"] < sv["ablation"]["primary_9"]["test"]["roc_auc"]


def test_transfer_training_set_excludes_the_evaluation_window():
    sar = _load("sar_validation.json")
    assert sar["n_points_withheld_inside"] > 0
    assert sar["n_train_points_outside"] > 0


def test_susceptibility_ranking_beats_random():
    """Success-rate curve must lie above the 1:1 random-ranking line."""
    sar = _load("sar_validation.json")
    src = sar["success_rate_curve"]
    for key, frac_area in (("top_10pct_area", 0.10), ("top_20pct_area", 0.20)):
        assert src[key] > frac_area, key


# ------------------------------------------------------------------- trigger

def test_trigger_is_monotone_in_rainfall():
    d = _load("trigger_table.json")
    assert d["monotonicity_check"]["passed"]


def test_documented_floods_outrank_ordinary_and_dry():
    d = _load("trigger_table.json")
    assert d["event_ordering_correct"]


def test_trigger_stays_in_unit_interval():
    d = _load("trigger_table.json")
    assert all(0.0 <= r["trigger_T"] <= 1.0 for r in d["scenarios"])


def test_trigger_weights_sum_to_one():
    d = _load("trigger_table.json")
    assert abs(sum(d["weights"].values()) - 1.0) < 1e-9


# ---------------------------------------------------------------------- QAOA

def test_qubo_ground_state_equals_hungarian_optimum():
    """The verification that licenses calling the QAOA result 'correct'."""
    d = _load("qaoa_depth_study.json")
    for name, s in d["scenarios"].items():
        assert s["qubo_matches_hungarian"], name
        assert abs(s["qubo_ground_energy"] - s["hungarian_cost_min"]) < 1e-6, name


def test_approximation_ratio_is_bounded():
    d = _load("qaoa_depth_study.json")
    for s in d["scenarios"].values():
        for r in s["depths"]:
            assert 0.0 <= r["approx_ratio_mean"] <= 1.0


def test_qaoa_depth_nonmonotonicity_is_recorded():
    """The district-spread instances do not support a monotone-depth claim."""
    d = _load("qaoa_depth_study.json")
    for name, s in d["scenarios"].items():
        means = [r["approx_ratio_mean"] for r in s["depths"]]
        assert s["approx_ratio_monotone_in_p"] == (means == sorted(means)), name
        assert len(set(means)) > 1, f"{name}: {means}"


def test_qaoa_beats_uniform_random_sampling():
    d = _load("qaoa_depth_study.json")
    for s in d["scenarios"].values():
        base = s["random_sampling_baseline"]
        for r in s["depths"]:
            assert r["prob_optimal_mean"] > base


def test_depth_study_averages_over_multiple_seeds():
    """Single-seed results would not support the monotonicity claim."""
    d = _load("qaoa_depth_study.json")
    assert len(d["seeds"]) >= 3
    for s in d["scenarios"].values():
        assert all(r["n_seeds"] >= 3 for r in s["depths"])


# --------------------------------------------- survivorship / prior / robustness
# Added in response to peer review. Each guards a claim that a reviewer showed was
# either wrong or unsupported in an earlier revision.

def test_sensitivity_cells_report_a_common_subset():
    """Cell means must be comparable across cells, not taken over survivors.

    At a low impassability threshold most pairs are severed and the survivors are
    the easy ones, which made an aggressive threshold look beneficial.
    """
    d = _load("sensitivity_sweep.json")
    assert d["n_common_pairs"] > 0
    for c in d["cells"]:
        assert c["n_common"] == d["n_common_pairs"]
        assert c["mean_exposure_common"] is not None


def test_operating_point_reports_connectivity_and_common_subset():
    """Exposure comparisons must retain both connectivity loss and common-pair data."""
    d = _load("sensitivity_sweep.json")
    op = d["operating_point"]
    assert op["n_routed"] + op["unreachable"] == d["n_pairs"]
    assert op["n_common"] == d["n_common_pairs"]
    assert d["neighbourhood_max_exposure_spread_pct"] >= 0


def test_prior_correction_preserves_ranking():
    """Prior shift is strictly monotone, so AUC must be invariant."""
    d = _load("calibration_prior.json")
    b = d["balanced_split"]
    assert abs(b["auc_isotonic"] - b["auc_prior_shifted"]) < 1e-6


def test_balanced_prior_overflags_the_landscape():
    """Guards the corrected claim in Section 5.2: a 0.5 cut is not a posterior."""
    d = _load("calibration_prior.json")
    L = d["landscape"]
    assert L["frac_above_0.5_balanced"] > 5 * L["frac_above_0.5_prior_shifted"]
    assert d["pi_deploy"] < 0.05 < d["pi_train"]


def test_trigger_ordering_is_robust_to_all_weightings():
    """The easy discrimination must not depend on the author-chosen weights."""
    d = _load("trigger_sweep.json")
    assert d["n_cells_ordering_ok"] == d["n_cells"]


def test_adversarial_margin_rises_with_the_saturation_weight():
    """Quantifies the Section 5.4 diagnosis rather than asserting it."""
    d = _load("trigger_sweep.json")
    trend = d["mean_adversarial_margin_by_w_sat_at_theta200"]
    vals = [trend[k] for k in sorted(trend, key=float)]
    assert vals == sorted(vals)
    assert vals[0] < 0 < vals[-1]


def test_operating_point_was_not_tuned_to_the_optimum():
    """The paper claims it reports but does not adopt the optimum."""
    d = _load("trigger_sweep.json")
    assert d["operating_point"]["margin_adversarial"] < \
        d["best_adversarial_margin"]["margin_adversarial"]


def test_routing_gain_survives_random_incident_sites():
    """The benchmark must not be an artefact of seven hand-picked locations."""
    d = _load("robustness.json")["incident_robustness"]
    assert d["random"]["exposure_reduction_pct"] > 20
    assert abs(d["random"]["exposure_reduction_pct"]
               - d["curated"]["exposure_reduction_pct"]) < 10


def test_rain_annual_is_flagged_as_partly_positional():
    """CHIRPS remains coarse relative to the district raster and partly positional."""
    d = _load("robustness.json")["rainfall_proxy"]
    assert d["chirps_distinct_values_in_window"] / d["window_pixels"] < 0.001
    assert abs(d["corr_rain_vs_elevation"]) > 0.2
    assert d["leave_one_out_auc_drop"]["rain_annual"] > 0
