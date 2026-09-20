"""Step 3: train & evaluate the static flood-susceptibility model (RF + XGBoost) with SHAP."""
import json
import os
import sys
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.metrics import (accuracy_score, precision_score, recall_score,
                             f1_score, roc_auc_score, confusion_matrix, brier_score_loss)
from xgboost import XGBClassifier

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from floodrisk import predictors  # noqa: E402

TABLE = "data/processed/training.parquet"
MODEL_OUT = "models/susceptibility_best.joblib"
METRICS_OUT = "data/processed/model_metrics.json"
IMPORTANCE_OUT = "data/processed/feature_importance.csv"
EXPERIMENTS_OUT = "data/processed/experiments.jsonl"


def _git_commit():
    """Record the code version each run was produced with (for reproducibility)."""
    import subprocess
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return None


def build_xy(df):
    # PRIMARY model: terrain + rainfall only (no NDVI/LULC — avoids SAR-canopy confound)
    X = df[predictors.PRIMARY_NUMERIC].astype(float)
    y = df["label"].astype(int)
    return X, y


def evaluate(model, X_te, y_te):
    pred = model.predict(X_te)
    proba = model.predict_proba(X_te)[:, 1]
    return {
        "accuracy": round(accuracy_score(y_te, pred), 4),
        "precision": round(precision_score(y_te, pred), 4),
        "recall": round(recall_score(y_te, pred), 4),
        "f1": round(f1_score(y_te, pred), 4),
        "roc_auc": round(roc_auc_score(y_te, proba), 4),
        "confusion_matrix": confusion_matrix(y_te, pred).tolist(),
    }


def main():
    df = pd.read_parquet(TABLE)
    X, y = build_xy(df)
    print(f">> Step 3: training on {len(df)} rows, {X.shape[1]} features")
    print(f"   features: {list(X.columns)}")

    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.30, stratify=y, random_state=42
    )
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    models = {
        "RandomForest": RandomForestClassifier(
            n_estimators=400, max_depth=None, min_samples_leaf=2,
            n_jobs=-1, random_state=42, class_weight="balanced"),
        "XGBoost": XGBClassifier(
            n_estimators=400, max_depth=5, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8, eval_metric="logloss",
            random_state=42, n_jobs=-1),
    }

    results = {}
    fitted = {}
    for name, model in models.items():
        cv_auc = cross_val_score(model, X_tr, y_tr, cv=cv, scoring="roc_auc", n_jobs=-1)
        model.fit(X_tr, y_tr)
        test_metrics = evaluate(model, X_te, y_te)
        results[name] = {
            "cv_roc_auc_mean": round(cv_auc.mean(), 4),
            "cv_roc_auc_std": round(cv_auc.std(), 4),
            "test": test_metrics,
        }
        fitted[name] = model
        print(f"\n   {name}: CV ROC-AUC = {cv_auc.mean():.4f} +/- {cv_auc.std():.4f}")
        for k, v in test_metrics.items():
            print(f"      {k}: {v}")

    best_name = max(results, key=lambda n: results[n]["test"]["roc_auc"])
    best = fitted[best_name]
    print(f"\n   Best model (test ROC-AUC): {best_name}")

    # --- Probability calibration -------------------------------------------------
    # The dashboard surfaces susceptibility as a "confidence"; raw tree-ensemble
    # scores are not calibrated probabilities. Isotonic calibration (fitted with CV
    # on the training split only) makes the number mean what it claims, and the
    # Brier score / reliability curve are reportable alongside AUC.
    calibrated = CalibratedClassifierCV(best, method="isotonic", cv=5)
    calibrated.fit(X_tr, y_tr)

    proba_raw = best.predict_proba(X_te)[:, 1]
    proba_cal = calibrated.predict_proba(X_te)[:, 1]
    brier_raw = brier_score_loss(y_te, proba_raw)
    brier_cal = brier_score_loss(y_te, proba_cal)
    frac_pos, mean_pred = calibration_curve(y_te, proba_cal, n_bins=10, strategy="quantile")

    calibration = {
        "method": "isotonic",
        "brier_raw": round(float(brier_raw), 4),
        "brier_calibrated": round(float(brier_cal), 4),
        "roc_auc_calibrated": round(float(roc_auc_score(y_te, proba_cal)), 4),
        "reliability_curve": {
            "mean_predicted": [round(float(v), 4) for v in mean_pred],
            "fraction_positive": [round(float(v), 4) for v in frac_pos],
        },
    }
    print(f"\n   Calibration (isotonic): Brier {brier_raw:.4f} -> {brier_cal:.4f} "
          f"({'improved' if brier_cal < brier_raw else 'no gain'})")
    print(f"      AUC after calibration: {calibration['roc_auc_calibrated']}")

    # --- SHAP feature importance (mean |SHAP|) ---
    import shap
    expl = shap.TreeExplainer(best)
    sv = expl.shap_values(X_te)
    if isinstance(sv, list):          # older API: list per class
        sv = sv[1]
    sv = np.asarray(sv)
    if sv.ndim == 3:                  # newer API: (n_samples, n_features, n_classes)
        sv = sv[:, :, -1]             # positive (flood) class
    mean_abs = np.abs(sv).mean(axis=0)
    imp = (pd.DataFrame({"feature": X.columns, "mean_abs_shap": mean_abs})
           .sort_values("mean_abs_shap", ascending=False).reset_index(drop=True))
    print("\n   Top predictors (SHAP):")
    for _, r in imp.head(8).iterrows():
        print(f"      {r['feature']:22s} {r['mean_abs_shap']:.4f}")

    os.makedirs("models", exist_ok=True)
    joblib.dump({
        "model": best,
        "calibrated": calibrated,
        "columns": list(X.columns),
        "name": best_name,
    }, MODEL_OUT)
    with open(METRICS_OUT, "w") as f:
        json.dump({"best": best_name, "results": results, "calibration": calibration}, f, indent=2)
    imp.to_csv(IMPORTANCE_OUT, index=False)

    # --- Experiment tracking -----------------------------------------------------
    # Metrics used to be overwritten every run, so the ablation history that drove
    # the methodology (SPI drop, NDVI/LULC exclusion, matched negatives) was
    # invisible. This append-only JSONL gives run history and comparison in a few
    # lines. MLflow was evaluated and rejected: it requires pandas<3 / pyarrow<25
    # and would downgrade the pinned research stack — a real reproducibility cost
    # for a convenience UI. Read the log with scripts/show_experiments.py.
    run = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": best_name,
        "features": list(X.columns),
        "n_features": int(X.shape[1]),
        "n_rows": int(len(df)),
        "test_size": 0.30,
        "test_roc_auc": results[best_name]["test"]["roc_auc"],
        "test_f1": results[best_name]["test"]["f1"],
        "cv_roc_auc_mean": results[best_name]["cv_roc_auc_mean"],
        "cv_roc_auc_std": results[best_name]["cv_roc_auc_std"],
        "brier_raw": calibration["brier_raw"],
        "brier_calibrated": calibration["brier_calibrated"],
        "top_features": imp.head(5)["feature"].tolist(),
        "git_commit": _git_commit(),
    }
    with open(EXPERIMENTS_OUT, "a") as f:
        f.write(json.dumps(run) + "\n")
    print(f"   Run appended -> {EXPERIMENTS_OUT} (compare: python scripts/show_experiments.py)")
    print(f"\n>> Saved model -> {MODEL_OUT}\n   metrics -> {METRICS_OUT}\n   importance -> {IMPORTANCE_OUT}")


if __name__ == "__main__":
    main()
