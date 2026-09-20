"""Step 2: build predictor stack, sample training points, save training table + diagnostics."""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from floodrisk import config, ee_init, sar, predictors, sampling  # noqa: E402

OUT_PARQUET = "data/processed/training.parquet"
NUMERIC_BANDS = [b for b in predictors.PREDICTOR_BANDS if b != "lulc"]  # lulc is categorical


def vif_report(df, cols):
    """Variance Inflation Factor via numpy least-squares (VIF_i = 1/(1-R2_i))."""
    X = df[cols].astype(float)
    X = (X - X.mean()) / X.std(ddof=0)   # standardize
    X = X.dropna(axis=0)
    print("\n   VIF (multicollinearity; >10 = concerning):")
    for c in cols:
        others = [o for o in cols if o != c]
        A = np.column_stack([np.ones(len(X)), X[others].values])
        y = X[c].values
        beta, *_ = np.linalg.lstsq(A, y, rcond=None)
        resid = y - A @ beta
        ss_res = np.sum(resid ** 2)
        ss_tot = np.sum((y - y.mean()) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
        vif = 1.0 / (1.0 - r2) if r2 < 1 else float("inf")
        flag = "  <-- high" if vif > 10 else ""
        print(f"     {c:18s} VIF={vif:6.2f}{flag}")


def main():
    ee = ee_init.init()
    geom = ee_init.aoi_district()

    print(">> Step 2: predictor stack + training table")
    flood_freq, n_passes = sar.flood_frequency(geom, config.MONSOON_WINDOWS)
    print(f"   SAR inventory: {n_passes} monsoon passes")

    stack = predictors.build_stack(geom)
    print(f"   Predictor bands: {predictors.PREDICTOR_BANDS}")

    fc = sampling.build_training_points(geom, flood_freq, stack, n_per_class=1500)
    print("   Sampling points (server-side)... pulling to local")
    rows = sampling.to_records(fc)
    df = pd.DataFrame(rows)

    # --- diagnostics ---
    print(f"\n   Rows: {len(df)}")
    print(f"   Class balance:\n{df['label'].value_counts().to_string()}")
    n_missing = df[predictors.PREDICTOR_BANDS].isna().sum()
    print(f"\n   Missing values per band:\n{n_missing[n_missing > 0].to_string() if n_missing.any() else '     none'}")

    df = df.dropna(subset=predictors.PREDICTOR_BANDS).reset_index(drop=True)
    print(f"   Rows after dropping NA: {len(df)}")

    vif_report(df, NUMERIC_BANDS)

    os.makedirs(os.path.dirname(OUT_PARQUET), exist_ok=True)
    df.to_parquet(OUT_PARQUET, index=False)
    print(f"\n>> Saved training table: {OUT_PARQUET} ({len(df)} rows, {df.shape[1]} cols)")


if __name__ == "__main__":
    main()
