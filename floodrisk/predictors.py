"""Build the flood-conditioning-factor (predictor) stack over the AOI, server-side in GEE.

Factors (per refs [4][10][11][17]): elevation, slope, aspect, curvature, HAND, TWI, SPI,
distance-to-river, drainage density, NDVI, rainfall, LULC.
"""
import math

import ee


def _terrain(dem):
    slope = ee.Terrain.slope(dem)          # degrees
    aspect = ee.Terrain.aspect(dem)        # degrees
    slope_rad = slope.multiply(math.pi / 180.0)
    # General (Laplacian) curvature from a 3x3 second-derivative kernel
    lap = ee.Kernel.laplacian8()
    curvature = dem.convolve(lap).rename("curvature")
    return slope.rename("slope"), aspect.rename("aspect"), slope_rad, curvature


def _wetness(upa_m2, slope_rad):
    """TWI and SPI from specific catchment area (upa) and slope."""
    tan_slope = slope_rad.tan().max(0.001)          # avoid div-by-zero on flats
    twi = upa_m2.divide(tan_slope).max(1).log().rename("twi")
    spi = upa_m2.multiply(tan_slope).max(1).log().rename("spi")
    return twi, spi


def _river_metrics(upa_km2, river_thresh_km2=1.0):
    """River mask (upstream area threshold), distance-to-river, drainage density."""
    river = upa_km2.gte(river_thresh_km2).rename("river")
    # distance-to-river in metres (fastDistanceTransform gives squared pixel distance)
    proj = upa_km2.projection()
    px = ee.Number(proj.nominalScale())
    dist = (
        river.fastDistanceTransform(256).sqrt()
        .multiply(px)
        .rename("dist_river")
    )
    # drainage density: fraction of river pixels in a ~1 km neighborhood
    dd = river.reduceNeighborhood(
        reducer=ee.Reducer.mean(),
        kernel=ee.Kernel.circle(1000, "meters"),
    ).rename("drainage_density")
    return dist, dd


def _ndvi(geom, start="2024-01-01", end="2024-12-31"):
    s2 = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(geom)
        .filterDate(start, end)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30))
    )
    med = s2.median()
    return med.normalizedDifference(["B8", "B4"]).rename("ndvi")


def _rainfall(geom, start="2020-01-01", end="2024-12-31"):
    """Mean annual rainfall (mm) from CHIRPS climatology."""
    chirps = (
        ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY")
        .filterBounds(geom)
        .filterDate(start, end)
        .select("precipitation")
    )
    years = 5.0
    return chirps.sum().divide(years).rename("rain_annual")


def build_stack(geom):
    """Return a single multi-band ee.Image of all conditioning factors, clipped to geom."""
    dem = ee.Image("USGS/SRTMGL1_003").select("elevation").rename("elevation")
    slope, aspect, slope_rad, curvature = _terrain(dem)

    merit = ee.Image("MERIT/Hydro/v1_0_1")
    hand = merit.select("hnd").rename("hand")
    upa_km2 = merit.select("upa")                 # upstream drainage area, km^2
    upa_m2 = upa_km2.multiply(1e6)

    twi, spi = _wetness(upa_m2, slope_rad)
    dist_river, drainage_density = _river_metrics(upa_km2)

    ndvi = _ndvi(geom)
    rain = _rainfall(geom)
    lulc = ee.ImageCollection("ESA/WorldCover/v200").first().select("Map").rename("lulc")

    stack = (
        dem.addBands(slope).addBands(aspect).addBands(curvature)
        .addBands(hand).addBands(twi).addBands(spi)
        .addBands(dist_river).addBands(drainage_density)
        .addBands(ndvi).addBands(rain).addBands(lulc)
    )
    return stack.clip(geom)


PREDICTOR_BANDS = [
    "elevation", "slope", "aspect", "curvature", "hand", "twi", "spi",
    "dist_river", "drainage_density", "ndvi", "rain_annual", "lulc",
]

# Features used for modeling (SPI dropped: VIF>10, collinear with TWI/slope).
MODEL_NUMERIC = [
    "elevation", "slope", "aspect", "curvature", "hand", "twi",
    "dist_river", "drainage_density", "ndvi", "rain_annual",
]
MODEL_CATEGORICAL = ["lulc"]
MODEL_FEATURES = MODEL_NUMERIC + MODEL_CATEGORICAL

# PRIMARY model = terrain + rainfall only. NDVI/LULC dropped to avoid the
# SAR-under-canopy circularity (forest => flood undetectable); ablation showed
# terrain-only retains test-AUC ~0.96. Full model kept as a sensitivity analysis.
PRIMARY_NUMERIC = [
    "elevation", "slope", "aspect", "curvature", "hand", "twi",
    "dist_river", "drainage_density", "rain_annual",
]
