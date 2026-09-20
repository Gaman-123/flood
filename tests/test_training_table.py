"""Invariants for the training table and feature set.

These guard the methodological decisions that make the reported AUC trustworthy:
balanced classes, terrain-matched negatives (so the model can't shortcut on
"forest vs floodplain"), and no multicollinear predictors.
"""
import os

import numpy as np
import pytest

from floodrisk import config, predictors

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TABLE = os.path.join(REPO, "data", "processed", "training.parquet")

pytestmark = pytest.mark.skipif(
    not os.path.exists(TABLE), reason="run `make $(PROC)/training.parquet` first"
)


@pytest.fixture(scope="module")
def df():
    import pandas as pd
    return pd.read_parquet(TABLE)


def test_classes_are_balanced(df):
    counts = df["label"].value_counts()
    assert set(counts.index) == {0, 1}
    assert abs(counts[0] - counts[1]) / max(counts) < 0.05, f"imbalanced: {dict(counts)}"


def test_no_missing_predictor_values(df):
    cols = [c for c in predictors.PREDICTOR_BANDS if c in df.columns]
    assert df[cols].isna().sum().sum() == 0


def test_negatives_are_terrain_matched(df):
    """Both classes must sit inside the floodable-lowland domain.

    This is the fix for the forest-vs-plain sampling bias: if negatives were drawn
    from high uplands the classifier could separate them on elevation alone.
    """
    assert df["elevation"].max() <= config.DOMAIN_ELEV_MAX + 1e-6
    assert df["hand"].max() <= config.DOMAIN_HAND_MAX + 1e-6

    flood, nonflood = df[df.label == 1], df[df.label == 0]
    # class elevation distributions should overlap substantially, not be disjoint
    assert nonflood["elevation"].quantile(0.05) < flood["elevation"].quantile(0.95)


def test_primary_features_have_no_multicollinearity(df):
    """VIF < 10 for every modelled predictor (SPI was dropped for this reason)."""
    cols = [c for c in predictors.PRIMARY_NUMERIC if c in df.columns]
    X = df[cols].astype(float).to_numpy()
    X = (X - X.mean(0)) / (X.std(0) + 1e-12)
    for i, name in enumerate(cols):
        y = X[:, i]
        A = np.delete(X, i, axis=1)
        beta, *_ = np.linalg.lstsq(A, y, rcond=None)
        r2 = 1.0 - ((y - A @ beta) ** 2).sum() / ((y - y.mean()) ** 2).sum()
        vif = 1.0 / (1.0 - r2) if r2 < 1 else float("inf")
        assert vif < 10, f"{name} is collinear (VIF={vif:.2f})"


def test_spi_excluded_from_primary_model():
    """SPI was dropped after VIF screening; NDVI/LULC dropped for SAR-canopy circularity."""
    assert "spi" not in predictors.PRIMARY_NUMERIC
    assert "ndvi" not in predictors.PRIMARY_NUMERIC
    assert "lulc" not in predictors.PRIMARY_NUMERIC
