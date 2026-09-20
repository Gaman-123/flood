"""Build the district-wide OSM road graph and annotate edge flood susceptibility.

The model is trained over Dakshina Kannada, so the operational graph must cover
the same administrative district. The district boundary is resolved once from
OpenStreetMap Nominatim, cached locally, and used for an exact polygon query.
"""
import os
import sys

import geopandas as gpd
import joblib
import numpy as np
import osmnx as ox
import rasterio
from shapely.geometry import Point

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from floodrisk import config, locations  # noqa: E402

BOUNDARY_OUT = config.DISTRICT_BOUNDARY_PATH
SUSC_TIF = config.ROUTING_SUSCEPTIBILITY_PATH
GRAPH_OUT = config.ROAD_GRAPH_PATH
PREDICTOR_STACK = "web_assets/predictor_stack.tif"
BANDS_JSON = "web_assets/predictor_stack.bands.json"
MODEL_PATH = "models/susceptibility_best.joblib"


def build_susceptibility_raster():
    """Apply the published local XGBoost model to the district predictor stack."""
    import json

    if not os.path.exists(PREDICTOR_STACK):
        raise FileNotFoundError("district predictor stack missing; run export_predictor_stack.py")
    bundle = joblib.load(MODEL_PATH)
    bands = json.load(open(BANDS_JSON))["bands"]
    with rasterio.open(PREDICTOR_STACK) as src:
        arr = src.read().astype("float32")
        meta = src.meta.copy()
        nodata = src.nodata
    if bands != bundle["columns"]:
        raise RuntimeError(f"model/raster feature mismatch: {bundle['columns']} != {bands}")

    valid = np.all(np.isfinite(arr), axis=0)
    if nodata is not None:
        valid &= ~np.all(arr == nodata, axis=0)
    flat = arr[:, valid].T
    if not len(flat):
        raise RuntimeError("predictor stack contains no valid district pixels")
    pred = np.full(valid.shape, -9999.0, dtype="float32")
    # Chunking limits peak RAM and keeps XGBoost prediction responsive.
    values = np.concatenate([
        bundle["model"].predict_proba(flat[start:start + 250_000])[:, 1]
        for start in range(0, len(flat), 250_000)
    ]).astype("float32")
    pred[valid] = values
    meta.update(count=1, dtype="float32", nodata=-9999.0, compress="deflate")
    os.makedirs(os.path.dirname(SUSC_TIF), exist_ok=True)
    with rasterio.open(SUSC_TIF, "w", **meta) as dst:
        dst.write(pred, 1)
    return os.path.getsize(SUSC_TIF)


def district_boundary():
    """Return the cached EPSG:4326 district polygon, resolving it if needed."""
    if os.path.exists(BOUNDARY_OUT):
        gdf = gpd.read_file(BOUNDARY_OUT).to_crs("EPSG:4326")
    else:
        print(f"   Resolving boundary: {config.DK_PLACE_QUERY}")
        gdf = ox.geocoder.geocode_to_gdf(config.DK_PLACE_QUERY).to_crs("EPSG:4326")
        if gdf.empty:
            raise RuntimeError("Nominatim returned no Dakshina Kannada boundary")
        os.makedirs(os.path.dirname(BOUNDARY_OUT), exist_ok=True)
        gdf[["display_name", "geometry"]].to_file(BOUNDARY_OUT, driver="GeoJSON")

    geom = gdf.geometry.union_all()
    if geom.geom_type not in {"Polygon", "MultiPolygon"}:
        raise RuntimeError(f"expected district polygon, got {geom.geom_type}")
    minx, miny, maxx, maxy = geom.bounds
    expected = config.DK_BBOX
    if (minx < expected[0] - 0.03 or miny < expected[1] - 0.03
            or maxx > expected[2] + 0.03 or maxy > expected[3] + 0.03):
        raise RuntimeError(f"district boundary bounds look wrong: {geom.bounds}")

    outside = [h["id"] for h in locations.HOSPITALS
               if not geom.buffer(0.002).covers(Point(h["lon"], h["lat"]))]
    if outside:
        raise RuntimeError(f"audited hospitals outside district polygon: {outside}")
    return geom


def main():
    print(">> Step 5a: district OSM road graph + susceptibility per edge")
    polygon = district_boundary()
    print(f"   Boundary bounds: {[round(v, 5) for v in polygon.bounds]}")

    # Apply the exact serialized XGBoost to the district predictor stack. This
    # replaces the former city-only server-side Random Forest approximation.
    raster_stale = (
        not os.path.exists(SUSC_TIF)
        or os.path.getmtime(SUSC_TIF) < os.path.getmtime(MODEL_PATH)
        or os.path.getmtime(SUSC_TIF) < os.path.getmtime(PREDICTOR_STACK)
    )
    if raster_stale:
        size = build_susceptibility_raster()
        print(f"   District susceptibility: {SUSC_TIF} ({size / 1024 / 1024:.1f} MB)")
    else:
        print(f"   District susceptibility cached: {SUSC_TIF}")

    print("   Downloading district OSM drivable network (Overpass)...")
    G = ox.graph.graph_from_polygon(
        polygon, network_type="drive", simplify=True, retain_all=False,
        truncate_by_edge=True,
    )
    G = ox.routing.add_edge_speeds(G)
    G = ox.routing.add_edge_travel_times(G)
    print(f"   Road graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    edges = ox.convert.graph_to_gdfs(G, nodes=False)
    projected = edges.to_crs(edges.estimate_utm_crs())
    mids = projected.geometry.interpolate(0.5, normalized=True)
    mids = gpd.GeoSeries(mids, crs=projected.crs).to_crs("EPSG:4326")
    coords = [(p.x, p.y) for p in mids]

    with rasterio.open(SUSC_TIF) as src:
        from scipy.ndimage import distance_transform_edt

        arr = src.read(1).astype("float32")
        nodata = src.nodata
        valid = np.isfinite(arr) & (arr != nodata if nodata is not None else True)
        nearest = distance_transform_edt(~valid, return_distances=False, return_indices=True)
        filled = arr[tuple(nearest)]
        vals = []
        for x, y in coords:
            row, col = src.index(x, y)
            if 0 <= row < src.height and 0 <= col < src.width:
                vals.append(float(filled[row, col]))
            else:
                vals.append(float("nan"))

    n_bad = 0
    for (u, v, k), s in zip(edges.index, vals):
        if s is None or s != s:
            # This should only occur for an edge extending beyond the raster's
            # bounding box. Use a conservative uncertainty value, never zero.
            s, n_bad = 0.75, n_bad + 1
        G.edges[u, v, k]["susceptibility"] = float(max(0.0, min(1.0, s)))

    values = [G.edges[e]["susceptibility"] for e in G.edges]
    hi = sum(1 for s in values if s > 0.5)
    print(f"   Sampled {len(values)} edges ({n_bad} out-of-bounds midpoints -> 0.75)")
    print(f"      mean={sum(values) / len(values):.3f} max={max(values):.3f}")
    print(f"      edges with S>0.5: {hi} ({100 * hi / len(values):.1f}%)")

    G.graph["coverage"] = "Dakshina Kannada administrative district"
    G.graph["boundary_source"] = "OpenStreetMap Nominatim"
    G.graph["susceptibility_scale_m"] = str(config.ROUTING_RASTER_SCALE_M)
    G.graph["hospital_count"] = str(len(locations.HOSPITALS))
    os.makedirs(os.path.dirname(GRAPH_OUT), exist_ok=True)
    ox.io.save_graphml(G, GRAPH_OUT)
    print(f">> Saved graph: {GRAPH_OUT}")


if __name__ == "__main__":
    main()
