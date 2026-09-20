"""Spatial-block cross-validation and the feature-set ablation ladder.

Two things the conference paper asserted in prose and now measures:

1. SPATIAL AUTOCORRELATION.  Random k-fold CV on geospatial samples is optimistic:
   neighbouring training points share terrain, so a random split leaks information
   across the fold boundary. Spatial *block* CV holds out whole geographic blocks,
   which is the honest estimate of skill at an unvisited location. Reporting both
   quantifies how much of the headline AUC is autocorrelation rather than skill.

2. THE NDVI/LULC CONFOUND.  Non-flood pixels in this coastal lowland are ~93%
   forest, and SAR cannot see standing water under canopy, so a model given NDVI
   and LULC can learn "forest => flood undetectable" instead of flood physics.
   The ablation ladder measures the cost of removing that shortcut, with SHAP
   rankings side by side to show *why* the full model scores higher.

Outputs data/processed/spatial_validation.json.
"""
import json
import os
import sys

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold, StratifiedKFold, cross_val_score, train_test_split
from sklearn.metrics import (accuracy_score, precision_score, recall_score, f1_score,
                             roc_auc_score, confusion_matrix)
from xgboost import XGBClassifier

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from floodrisk import predictors  # noqa: E402

TABLE = "data/processed/training.parquet"
OUT = "data/processed/spatial_validation.json"

BLOCK_DEG = 0.05          # ~5.5 km blocks -- larger than the terrain autocorrelation range
N_SPATIAL_FOLDS = 5


def _model():
    return XGBClassifier(
        n_estimators=400, max_depth=5, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8, eval_metric="logloss",
        random_state=42, n_jobs=-1)


# Ablation ladder: each rung removes one class of predictor.
FEATURE_SETS = {
    "full_12": predictors.PREDICTOR_BANDS,                       # everything, incl. SPI/NDVI/LULC
    "vif_11": predictors.MODEL_FEATURES,                         # after SPI dropped (VIF>10)
    "primary_9": predictors.PRIMARY_NUMERIC,                     # terrain + rainfall only
}


def block_ids(df, deg=BLOCK_DEG):
    """Assign each sample to a square geographic block; folds hold out whole blocks."""
    bx = np.floor(df["lon"] / deg).astype(int)
    by = np.floor(df["lat"] / deg).astype(int)
    return (bx.astype(str) + "_" + by.astype(str)).values


def evaluate_split(model, X_te, y_te):
    pred = model.predict(X_te)
    proba = model.predict_proba(X_te)[:, 1]
    return {
        "accuracy": round(float(accuracy_score(y_te, pred)), 4),
        "precision": round(float(precision_score(y_te, pred)), 4),
        "recall": round(float(recall_score(y_te, pred)), 4),
        "f1": round(float(f1_score(y_te, pred)), 4),
        "roc_auc": round(float(roc_auc_score(y_te, proba)), 4),
        "confusion_matrix": confusion_matrix(y_te, pred).tolist(),
    }


def shap_ranking(model, X):
    import shap
    sv = shap.TreeExplainer(model).shap_values(X)
    if isinstance(sv, list):
        sv = sv[1]
    sv = np.asarray(sv)
    if sv.ndim == 3:
        sv = sv[:, :, -1]
    mean_abs = np.abs(sv).mean(axis=0)
    order = np.argsort(mean_abs)[::-1]
    return [{"feature": str(X.columns[i]), "mean_abs_shap": round(float(mean_abs[i]), 4)}
            for i in order]


def main():
    df = pd.read_parquet(TABLE)
    groups = block_ids(df)
    y = df["label"].astype(int)
    n_blocks = len(set(groups))
    print(f">> Spatial validation on {len(df)} samples across {n_blocks} "
          f"{BLOCK_DEG}-degree blocks")

    out = {"n_samples": int(len(df)), "block_deg": BLOCK_DEG, "n_blocks": int(n_blocks),
           "ablation": {}, "spatial_cv": {}}

    # ---------------------------------------------------------------- ablation
    for name, feats in FEATURE_SETS.items():
        feats = [f for f in feats if f in df.columns]
        X = df[feats].astype(float)
        X_tr, X_te, y_tr, y_te = train_test_split(
            X, y, test_size=0.30, stratify=y, random_state=42)

        m = _model()
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        random_auc = cross_val_score(m, X_tr, y_tr, cv=cv, scoring="roc_auc", n_jobs=-1)
        m.fit(X_tr, y_tr)
        test = evaluate_split(m, X_te, y_te)
        ranking = shap_ranking(m, X_te)

        out["ablation"][name] = {
            "n_features": len(feats),
            "features": feats,
            "cv_roc_auc_mean": round(float(random_auc.mean()), 4),
            "cv_roc_auc_std": round(float(random_auc.std()), 4),
            "test": test,
            "shap_ranking": ranking,
            "top5": [r["feature"] for r in ranking[:5]],
        }
        print(f"\n   [{name}] {len(feats)} features -> test AUC {test['roc_auc']}, "
              f"F1 {test['f1']}")
        print(f"      SHAP top-5: {', '.join(r['feature'] for r in ranking[:5])}")

    # ------------------------------------------------------------- spatial CV
    # Compare random k-fold against block k-fold on the SAME feature set, so the
    # difference is attributable to the split geometry and nothing else.
    for name, feats in FEATURE_SETS.items():
        feats = [f for f in feats if f in df.columns]
        X = df[feats].astype(float)

        rand_cv = StratifiedKFold(n_splits=N_SPATIAL_FOLDS, shuffle=True, random_state=42)
        rand_auc = cross_val_score(_model(), X, y, cv=rand_cv, scoring="roc_auc", n_jobs=-1)

        gkf = GroupKFold(n_splits=N_SPATIAL_FOLDS)
        fold_auc, fold_detail = [], []
        for fi, (tr, te) in enumerate(gkf.split(X, y, groups=groups), start=1):
            if len(set(y.iloc[te])) < 2:          # a block fold can be single-class
                continue
            m = _model()
            m.fit(X.iloc[tr], y.iloc[tr])
            a = roc_auc_score(y.iloc[te], m.predict_proba(X.iloc[te])[:, 1])
            fold_auc.append(float(a))
            fold_detail.append({
                "fold": fi, "n_test": int(len(te)),
                "n_blocks_held_out": int(len(set(groups[te]))),
                "roc_auc": round(float(a), 4),
                "positive_rate": round(float(y.iloc[te].mean()), 3),
            })

        drop = float(rand_auc.mean()) - float(np.mean(fold_auc))
        out["spatial_cv"][name] = {
            "n_features": len(feats),
            "random_kfold_auc_mean": round(float(rand_auc.mean()), 4),
            "random_kfold_auc_std": round(float(rand_auc.std()), 4),
            "spatial_block_auc_mean": round(float(np.mean(fold_auc)), 4),
            "spatial_block_auc_std": round(float(np.std(fold_auc)), 4),
            "auc_drop": round(drop, 4),
            "auc_drop_pct": round(100 * drop / float(rand_auc.mean()), 2),
            "folds": fold_detail,
        }
        s = out["spatial_cv"][name]
        print(f"\n   [{name}] random {s['random_kfold_auc_mean']:.4f} vs "
              f"spatial-block {s['spatial_block_auc_mean']:.4f} "
              f"(drop {s['auc_drop']:.4f} = {s['auc_drop_pct']}%)")

    os.makedirs("data/processed", exist_ok=True)
    json.dump(out, open(OUT, "w"), indent=2)
    print(f"\n>> Saved -> {OUT}")


if __name__ == "__main__":
    main()
