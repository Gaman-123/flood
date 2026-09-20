"""Reusable server-side susceptibility surface S(x).

Trains a GEE smileRandomForest (PROBABILITY output) on the same seed-stable sampled
points used in Step 2/3 and classifies the predictor stack. Shared by the map script
and the road-graph/routing stage so both use an identical surface.
"""
import ee

from . import config, sar, predictors, sampling

FEATURES = predictors.PRIMARY_NUMERIC


def build(geom, n_per_class=1500, n_trees=400):
    """Return (susceptibility ee.Image in 0-1, trained classifier)."""
    flood_freq, _ = sar.flood_frequency(geom, config.MONSOON_WINDOWS)
    stack = predictors.build_stack(geom).select(FEATURES)
    fc = sampling.build_training_points(geom, flood_freq, stack, n_per_class=n_per_class)

    clf = (ee.Classifier.smileRandomForest(numberOfTrees=n_trees)
           .setOutputMode("PROBABILITY")
           .train(fc, "label", FEATURES))
    susc = stack.classify(clf).rename("susceptibility").clip(geom)
    return susc, clf
