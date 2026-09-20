"""Sample balanced flood / non-flood training points against the SAR inventory."""
import ee

from . import config
from . import predictors as _pred


def build_training_points(geom, flood_freq, stack, n_per_class=1200,
                          flood_min_freq=0.05, buffer_m=120, scale=30, seed=42):
    """Return a FeatureCollection of balanced labelled points with predictor values.

    Uses stratifiedSample so each class gets a guaranteed count despite the rare
    positive (flood) class. Both classes are confined to the floodable-lowland
    domain (elevation/HAND capped) so negatives are terrain-matched, not easy
    forested uplands:
    - label=1 where flood_freq >= flood_min_freq (flooded at least once), in-domain.
    - label=0 where flood_freq == 0 AND >= buffer_m from any flood pixel, in-domain.
    """
    # Floodable-lowland domain: elevation/HAND-matched to where floods occur
    domain = (
        stack.select("elevation").lte(config.DOMAIN_ELEV_MAX)
        .And(stack.select("hand").lte(config.DOMAIN_HAND_MAX))
    )

    flood = flood_freq.gte(flood_min_freq).And(domain)

    # Distance from flood pixels, to carve a clean non-flood zone (drop ambiguous halo)
    flood_dist = (
        flood.fastDistanceTransform(256).sqrt()
        .multiply(ee.Number(flood_freq.projection().nominalScale()))
    )
    nonflood = flood_freq.eq(0).And(flood_dist.gt(buffer_m)).And(domain)

    # class band: 1 on flood, 0 on non-flood, masked everywhere else
    candidate = flood.Or(nonflood)
    label = flood.rename("label").updateMask(candidate)

    sample_img = stack.addBands(label)
    return sample_img.stratifiedSample(
        numPoints=n_per_class,
        classBand="label",
        region=geom,
        scale=scale,
        classValues=[0, 1],
        classPoints=[n_per_class, n_per_class],
        seed=seed,
        dropNulls=True,
        geometries=True,
        tileScale=4,
    )


def to_records(fc, bands=None):
    """Pull a FeatureCollection to local list-of-dicts (bands + label + lon/lat)."""
    if bands is None:
        bands = _pred.PREDICTOR_BANDS
    props = bands + ["label"]
    info = fc.getInfo()
    rows = []
    for f in info["features"]:
        p = f["properties"]
        rec = {k: p.get(k) for k in props}
        coords = f.get("geometry", {}).get("coordinates")
        if coords:
            rec["lon"], rec["lat"] = coords[0], coords[1]
        rows.append(rec)
    return rows
