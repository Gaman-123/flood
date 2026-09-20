"""Sentinel-1 SAR loading, speckle filtering, water masking, and flood-frequency inventory."""
import ee

from . import config


def s1_collection(start, end, geom):
    """Sentinel-1 GRD, IW, VV+VH, restricted to the single DK-covering orbit."""
    return (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterBounds(geom)
        .filterDate(start, end)
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
        .filter(ee.Filter.eq("orbitProperties_pass", config.S1_ORBIT_PASS))
        .filter(ee.Filter.eq("relativeOrbitNumber_start", config.S1_REL_ORBIT))
        .select(["VV", "VH"])
    )


def speckle_filter(img):
    """Focal-median speckle reduction in dB space, preserving image properties."""
    smoothed = img.focal_median(config.SPECKLE_RADIUS_M, "circle", "meters")
    return smoothed.copyProperties(img, ["system:time_start"])


def water_mask(img):
    """Binary open-water mask from VV (and VH) backscatter thresholds."""
    vv = img.select("VV")
    vh = img.select("VH")
    mask = vv.lt(config.VV_WATER_THRESH_DB).And(vh.lt(config.VH_WATER_THRESH_DB))
    return mask.rename("water").copyProperties(img, ["system:time_start"])


def permanent_water(geom):
    """JRC Global Surface Water permanent-water mask over the AOI."""
    occ = ee.Image("JRC/GSW1_4/GlobalSurfaceWater").select("occurrence")
    return occ.gte(config.JRC_PERMANENT_OCCURRENCE).unmask(0).clip(geom)


def water_freq_over(geom, windows):
    """Fraction of passes (across windows) that each pixel is classified as water."""
    masks = ee.List([])
    for start, end in windows:
        col = s1_collection(start, end, geom).map(speckle_filter).map(water_mask)
        masks = masks.cat(col.toList(col.size()))
    stack = ee.ImageCollection(masks)
    return stack.sum().divide(stack.size())


def flood_frequency(geom, windows, dry_windows=None, dry_water_max=0.2):
    """Multi-temporal SAR flood-frequency inventory via dry-season change detection.

    A pixel counts as *flooded* in a given monsoon pass only if it is water in that
    pass AND is "normally dry" (dry-season water frequency <= dry_water_max). This
    removes permanent rivers/estuary/sea and isolates transient inundation.

    Returns (flood_freq_image, n_passes).
    """
    if dry_windows is None:
        dry_windows = config.DRY_WINDOWS

    # Baseline: pixels that are water even in the dry season are NOT flood signal.
    dry_freq = water_freq_over(geom, dry_windows)
    normally_dry = dry_freq.lte(dry_water_max).unmask(1)

    # Monsoon passes: flooded = water this pass AND normally dry.
    masks = ee.List([])
    total = 0
    for start, end in windows:
        col = s1_collection(start, end, geom).map(speckle_filter).map(water_mask)
        total += col.size().getInfo()
        masks = masks.cat(col.toList(col.size()))

    stack = ee.ImageCollection(masks)
    n = stack.size()
    flooded = stack.map(lambda m: ee.Image(m).And(normally_dry))
    freq = flooded.sum().divide(n).rename("flood_freq")

    perm = permanent_water(geom)
    flood_freq = freq.updateMask(perm.Not()).clip(geom)
    return flood_freq, total


def passes_count(geom, windows):
    """Total number of SAR passes across the windows (for reporting)."""
    total = 0
    for start, end in windows:
        total += s1_collection(start, end, geom).size().getInfo()
    return total
