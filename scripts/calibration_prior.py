"""Prior correction: what the susceptibility score actually means.

The classifier is trained on a stratified 1500/1500 sample, so its implied base
rate is 50%. Isotonic calibration fitted on that split therefore calibrates to a
50% prior. The deployment prevalence is measured at run time as the SAR-observed
flooded fraction of the coastal validation window. A score of 0.5 from the balanced model
does NOT mean "even odds of flooding here"; it means "typical of the flooded
class relative to an artificially balanced reference".

This script quantifies the gap and applies the standard correction. For a model
trained at prior $\\pi_{tr}$ and deployed at prior $\\pi_{dep}$, the corrected
posterior is (Elkan 2001; Saerens et al. 2002):

    p' = (p * w) / (p * w + (1 - p))      with   w = [pi_dep/(1-pi_dep)] / [pi_tr/(1-pi_tr)]

Because the correction is a strictly increasing function of p, it cannot change
the ranking, so ROC-AUC is invariant. What it changes is what a number means,
and how much of the landscape a 0.5 cut flags.

Outputs data/processed/calibration_prior.json.
"""
import json
import os
import sys

import numpy as np
import pandas as pd
import rasterio
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from floodrisk import predictors  # noqa: E402

TABLE = "data/processed/training.parquet"
SARVAL = "data/processed/sar_validation.json"
OUT = "data/processed/calibration_prior.json"


def prior_shift(p, pi_train, pi_deploy):
    """Map probabilities from a pi_train prior to a pi_deploy prior."""
    p = np.clip(np.asarray(p, dtype=float), 1e-9, 1 - 1e-9)
    w = (pi_deploy / (1 - pi_deploy)) / (pi_train / (1 - pi_train))
    return (p * w) / (p * w + (1 - p))


def main():
    df = pd.read_parquet(TABLE)
    feats = [f for f in predictors.PRIMARY_NUMERIC if f in df.columns]
    X, y = df[feats].astype(float), df["label"].astype(int)

    pi_train = float(y.mean())
    pi_deploy = json.load(open(SARVAL))["observed_flood_fraction"]
    print(f">> Prior correction: training prior {pi_train:.4f}, "
          f"deployment prevalence {pi_deploy:.5f}")

    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.30, stratify=y, random_state=42)

    base = XGBClassifier(n_estimators=400, max_depth=5, learning_rate=0.05,
                         subsample=0.8, colsample_bytree=0.8,
                         eval_metric="logloss", random_state=42, n_jobs=-1)
    base.fit(X_tr, y_tr)
    cal = CalibratedClassifierCV(base, method="isotonic", cv=5).fit(X_tr, y_tr)

    p_raw = base.predict_proba(X_te)[:, 1]
    p_cal = cal.predict_proba(X_te)[:, 1]
    p_shift = prior_shift(p_cal, pi_train, pi_deploy)

    # On the balanced test split the balanced-prior model is the right reference;
    # the prior-shifted score is deliberately mis-calibrated there, which is the
    # point: the two calibrations target different deployment populations.
    res = {
        "pi_train": round(pi_train, 4),
        "pi_deploy": round(pi_deploy, 5),
        "odds_ratio_w": round(float((pi_deploy / (1 - pi_deploy)) /
                                    (pi_train / (1 - pi_train))), 6),
        "balanced_split": {
            "brier_raw": round(float(brier_score_loss(y_te, p_raw)), 4),
            "brier_isotonic": round(float(brier_score_loss(y_te, p_cal)), 4),
            "auc_raw": round(float(roc_auc_score(y_te, p_raw)), 4),
            "auc_isotonic": round(float(roc_auc_score(y_te, p_cal)), 4),
            "auc_prior_shifted": round(float(roc_auc_score(y_te, p_shift)), 4),
        },
    }

    # ---- what the prior actually costs, measured on the real landscape -------
    heldout = "data/processed/susceptibility_heldout.tif"
    if os.path.exists(heldout):
        with rasterio.open(heldout) as s:
            a = s.read(1).astype("float64")
            a = np.where(a == s.nodata, np.nan, a)
        v = a[np.isfinite(a)]
        shifted = prior_shift(v, pi_train, pi_deploy)
        res["landscape"] = {
            "n_pixels": int(v.size),
            "frac_above_0.5_balanced": round(float((v >= 0.5).mean()), 4),
            "frac_above_0.5_prior_shifted": round(float((shifted >= 0.5).mean()), 6),
            "mean_score_balanced": round(float(v.mean()), 4),
            "mean_score_prior_shifted": round(float(shifted.mean()), 5),
            "note": ("A 0.5 cut on the balanced-prior score flags a large share of the "
                     "landscape; the same cut on the prior-corrected posterior "
                     "flags far less when the SAR-observed deployment prior is low. "
                     "Neither is 'the' answer: the balanced score is a "
                     "relative exposure ranking, the corrected one is an absolute "
                     "posterior under that SAR-observed prevalence, which is itself "
                     "a lower bound."),
        }
        print(f"   landscape flagged at 0.5: balanced "
              f"{100*res['landscape']['frac_above_0.5_balanced']:.1f}% -> "
              f"prior-corrected "
              f"{100*res['landscape']['frac_above_0.5_prior_shifted']:.3f}%")

        # Where does the corrected posterior put its own operating point?
        for q in (0.90, 0.95, 0.99):
            res.setdefault("corrected_quantiles", {})[f"q{int(q*100)}"] = round(
                float(np.quantile(shifted, q)), 5)

    os.makedirs("data/processed", exist_ok=True)
    json.dump(res, open(OUT, "w"), indent=2)
    print(f"   Brier (balanced split): raw {res['balanced_split']['brier_raw']} "
          f"-> isotonic {res['balanced_split']['brier_isotonic']}")
    print(f"   AUC invariant under prior shift: "
          f"{res['balanced_split']['auc_isotonic']} vs "
          f"{res['balanced_split']['auc_prior_shifted']}")
    print(f">> Saved -> {OUT}")


if __name__ == "__main__":
    main()
