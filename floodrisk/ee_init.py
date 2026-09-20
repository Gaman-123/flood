"""Earth Engine initialization via service account."""
import ee

from . import config


def init():
    """Authenticate and initialize Earth Engine with the project service account."""
    creds = ee.ServiceAccountCredentials(config.EE_SERVICE_ACCOUNT, config.EE_KEY_PATH)
    ee.Initialize(creds, project=config.EE_PROJECT)
    return ee


def aoi():
    """Return the Dakshina Kannada AOI rectangle geometry (bbox, for filtering)."""
    return ee.Geometry.Rectangle(config.DK_BBOX)


def aoi_district():
    """Return the Dakshina Kannada district polygon (FAO GAUL 2015 level 2).

    Falls back to the bbox if the admin feature is not found.
    """
    fc = (
        ee.FeatureCollection("FAO/GAUL/2015/level2")
        .filter(ee.Filter.eq("ADM1_NAME", "Karnataka"))
        .filter(ee.Filter.eq("ADM2_NAME", "Dakshin Kannad"))  # GAUL spelling
    )
    return fc.geometry()
