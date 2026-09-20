"""Publication-quality cartography for the journal manuscript.

Every map is drawn from committed pipeline artifacts. Nothing here is a mock-up:
the coastline is the valid-data boundary of the SRTM stack, the river network is
derived from the MERIT Hydro distance-to-river band, the flood polygons are the
SAR inventory, the roads carry their per-edge susceptibility, and the routes are
recomputed live from the graph.

Administrative outlines come from Natural Earth (public domain), cached under
data/external/. Download once with:

    make maps-data

Colour: sequential ramps are perceptually uniform and colour-vision-deficiency
safe (viridis / cividis / magma / single-hue Reds). No red-green pairs carry
meaning anywhere in these figures.
"""
import json
import math
import os
import sys
import zipfile

import geopandas as gpd
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.colors import LightSource, Normalize
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from shapely.geometry import box

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from floodrisk import config, locations  # noqa: E402

FIG = "paper/figures"
EXT = "data/external"

STACK = "web_assets/predictor_stack.tif"
BANDS_JSON = "web_assets/predictor_stack.bands.json"
SUSC = "data/processed/susceptibility_dk.tif"
HELDOUT = "data/processed/susceptibility_heldout.tif"
SAR = "web_assets/sar_extent.geojson"
ROADS = "web_assets/roads_light.geojson"

mpl.rcParams.update({
    "font.size": 8,
    "axes.titlesize": 9,
    "axes.labelsize": 8,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "axes.linewidth": 0.6,
    "pdf.fonttype": 42,        # embed TrueType, not Type-3 (journal requirement)
    "ps.fonttype": 42,
})

DK = config.DK_BBOX          # [lon_min, lat_min, lon_max, lat_max]


# --------------------------------------------------------------------- helpers

def _ne(name):
    """Load a cached Natural Earth layer, unzipping on first use."""
    zp = os.path.join(EXT, name + ".zip")
    dd = os.path.join(EXT, name)
    if not os.path.exists(dd):
        if not os.path.exists(zp):
            raise SystemExit(f"Missing {zp}. Run: make maps-data")
        os.makedirs(dd, exist_ok=True)
        with zipfile.ZipFile(zp) as z:
            z.extractall(dd)
    shp = [f for f in os.listdir(dd) if f.endswith(".shp")][0]
    return gpd.read_file(os.path.join(dd, shp))


def scalebar(ax, lon0, lat0, km, label=None, lw=2.2):
    """Draw a scale bar in degrees, correcting longitude for latitude."""
    deg = km / (111.32 * math.cos(math.radians(lat0)))
    ax.plot([lon0, lon0 + deg], [lat0, lat0], color="k", lw=lw,
            solid_capstyle="butt", zorder=20)
    for x in (lon0, lon0 + deg):
        ax.plot([x, x], [lat0, lat0 + deg * 0.12], color="k", lw=lw * 0.5, zorder=20)
    ax.text(lon0 + deg / 2, lat0 + deg * 0.18, label or f"{km:g} km",
            ha="center", va="bottom", fontsize=6.5, zorder=20)


def north_arrow(ax, x, y, size=0.045):
    """North arrow in axes fraction coordinates."""
    ax.annotate("N", xy=(x, y), xytext=(x, y - size),
                xycoords="axes fraction", textcoords="axes fraction",
                ha="center", va="center", fontsize=7.5, fontweight="bold",
                arrowprops=dict(arrowstyle="-|>", color="k", lw=1.0), zorder=20)


def latlon_axes(ax, nx=4, ny=4):
    ax.set_xlabel("Longitude ($^\\circ$E)")
    ax.set_ylabel("Latitude ($^\\circ$N)")
    ax.locator_params(axis="x", nbins=nx)
    ax.locator_params(axis="y", nbins=ny)
    ax.tick_params(labelsize=6.5)
    ax.set_aspect("equal", adjustable="box")


_roads_gdf = None


def road_edges():
    """Edge GeoDataFrame straight from the routing graph.

    NOTE: web_assets/roads_light.geojson is a deterministic display subset and
    must not be used for network statistics. Every road statistic and map here
    therefore comes from dakshina_kannada_roads.graphml, the router's graph.
    """
    global _roads_gdf
    if _roads_gdf is None:
        import osmnx as ox
        G = ox.io.load_graphml(
            "data/processed/dakshina_kannada_roads.graphml",
            edge_dtypes={"susceptibility": float, "travel_time": float, "length": float})
        gdf = ox.convert.graph_to_gdfs(G, nodes=False, edges=True)
        gdf["susceptibility"] = gdf["susceptibility"].astype(float)
        _roads_gdf = gdf
    return _roads_gdf


def read_stack():
    bands = json.load(open(BANDS_JSON))["bands"]
    with rasterio.open(STACK) as s:
        arr = s.read().astype("float64")
        ext = (s.bounds.left, s.bounds.right, s.bounds.bottom, s.bounds.top)
    return bands, arr, ext


def land_mask(arr, bands):
    """SRTM is masked over open water, so finite elevation IS the land mask."""
    return np.isfinite(arr[bands.index("elevation")])


def river_mask(arr, bands, within_m=90):
    """MERIT distance-to-river near zero marks the channel network."""
    return arr[bands.index("dist_river")] <= within_m


# --------------------------------------------------------------------- figures

def fig_study_area():
    """Three-panel locator: India -> Karnataka -> Dakshina Kannada district."""
    countries = _ne("ne_110m_admin_0_countries")
    states = _ne("ne_10m_admin_1_states_provinces")
    india = countries[countries["ADMIN"] == "India"]
    ka = states[(states["admin"] == "India") & (states["name"] == "Karnataka")]

    bands, arr, ext = read_stack()
    elev = arr[bands.index("elevation")]
    land = land_mask(arr, bands)

    fig = plt.figure(figsize=(7.2, 2.75))
    gs = fig.add_gridspec(1, 3, width_ratios=[1, 1, 1.35], wspace=0.32)

    # (a) India
    ax = fig.add_subplot(gs[0])
    countries.plot(ax=ax, color="#eceff4", edgecolor="#b0b7c3", linewidth=0.3)
    india.plot(ax=ax, color="#d8dee9", edgecolor="#4c566a", linewidth=0.5)
    ka.plot(ax=ax, color="#5e81ac", edgecolor="#2e3440", linewidth=0.5)
    ax.plot(74.84, 12.87, marker="v", color="#bf360c", ms=5, mec="k", mew=0.4, zorder=10)
    ax.set_xlim(66, 99); ax.set_ylim(5, 37)
    ax.set_title("(a) India", loc="left")
    latlon_axes(ax, 3, 3)
    north_arrow(ax, 0.90, 0.95)

    # (b) Karnataka + the district bbox
    ax = fig.add_subplot(gs[1])
    states[states["admin"] == "India"].plot(ax=ax, color="#eceff4",
                                            edgecolor="#b0b7c3", linewidth=0.3)
    ka.plot(ax=ax, color="#d8dee9", edgecolor="#2e3440", linewidth=0.7)
    boundary = (gpd.read_file(config.DISTRICT_BOUNDARY_PATH)
                if os.path.exists(config.DISTRICT_BOUNDARY_PATH)
                else gpd.GeoDataFrame(geometry=[box(*DK)], crs="EPSG:4326"))
    boundary.plot(
        ax=ax, facecolor="#bf360c", edgecolor="#bf360c", alpha=0.55, linewidth=0.8)
    ax.set_xlim(73.5, 79.0); ax.set_ylim(11.3, 18.8)
    ax.set_title("(b) Karnataka", loc="left")
    ax.annotate("Dakshina\nKannada", xy=(DK[0], (DK[1] + DK[3]) / 2),
                xytext=(-4, 0), textcoords="offset points", ha="right", va="center",
                fontsize=6, color="#bf360c", fontweight="bold")
    latlon_axes(ax, 3, 4)
    scalebar(ax, 73.9, 11.7, 100)
    north_arrow(ax, 0.90, 0.95)

    # (c) District: hillshaded terrain + rivers + operational locations
    ax = fig.add_subplot(gs[2])
    e = np.where(land, elev, np.nan)
    ls = LightSource(azdeg=315, altdeg=45)
    filled = np.nan_to_num(e, nan=0.0)
    shade = ls.hillshade(filled, vert_exag=90,
                         dx=30, dy=30)
    ax.imshow(e, extent=ext, origin="upper", cmap="cividis", zorder=1)
    ax.imshow(np.where(land, shade, np.nan), extent=ext, origin="upper",
              cmap="Greys_r", vmin=0.0, vmax=1.4, alpha=0.35, zorder=2)
    ax.imshow(np.where(land, np.nan, 1.0), extent=ext, origin="upper",
              cmap=mpl.colors.ListedColormap(["#9dc3e6"]), zorder=3)
    riv = river_mask(arr, bands)
    ax.imshow(np.where(riv & land, 1.0, np.nan), extent=ext, origin="upper",
              cmap=mpl.colors.ListedColormap(["#1f6fb4"]), zorder=4)

    hosp = json.load(open("web_assets/hospitals.json"))
    inc = json.load(open("web_assets/incidents.json"))
    ax.scatter([h["lon"] for h in hosp], [h["lat"] for h in hosp],
               marker="P", s=26, c="#ffffff", edgecolor="#111111",
               linewidth=0.5, zorder=10, label=f"Hospital origin ({len(hosp)})")
    ax.scatter([i["lon"] for i in inc], [i["lat"] for i in inc],
               marker="o", s=20, c="#bf360c", edgecolor="#111111",
               linewidth=0.4, zorder=10, label=f"Scenario point ({len(inc)})")
    ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3])
    ax.set_title("(c) Dakshina Kannada district", loc="left")
    latlon_axes(ax, 3, 4)
    scalebar(ax, ext[0] + 0.03, ext[2] + 0.03, 20)
    north_arrow(ax, 0.92, 0.95)
    ax.legend(loc="upper left", fontsize=5.8, frameon=True, framealpha=0.9,
              handletextpad=0.4, borderpad=0.3)

    fig.savefig(f"{FIG}/study_area.pdf")
    plt.close(fig)
    print("   study_area.pdf")


def fig_conditioning_factors():
    """9-panel grid of the primary model's input rasters."""
    bands, arr, ext = read_stack()
    land = land_mask(arr, bands)
    titles = {
        "elevation": ("Elevation", "m", "cividis"),
        "slope": ("Slope", "$^\\circ$", "magma"),
        "aspect": ("Aspect", "$^\\circ$", "twilight"),
        "curvature": ("Curvature", "-", "PuOr"),
        "hand": ("HAND", "m", "viridis"),
        "twi": ("TWI", "-", "YlGnBu"),
        "dist_river": ("Distance to river", "m", "Blues_r"),
        "drainage_density": ("Drainage density", "-", "BuPu"),
        "rain_annual": ("Mean annual rainfall", "mm", "GnBu"),
    }
    fig, axes = plt.subplots(3, 3, figsize=(7.2, 6.9))
    for ax, name in zip(axes.ravel(), bands):
        label, unit, cmap = titles[name]
        a = np.where(land, arr[bands.index(name)], np.nan)
        lo, hi = np.nanpercentile(a, [2, 98])
        im = ax.imshow(a, extent=ext, origin="upper", cmap=cmap,
                       norm=Normalize(lo, hi))
        ax.set_title(f"{label} ({unit})", loc="left", fontsize=7.5)
        ax.set_xticks([]); ax.set_yticks([])
        ax.set_aspect("equal")
        cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.02)
        cb.ax.tick_params(labelsize=5.5)
        cb.outline.set_linewidth(0.4)
    scalebar(axes[2, 0], ext[0] + 0.012, ext[2] + 0.010, 5)
    north_arrow(axes[0, 2], 0.90, 0.93)
    fig.tight_layout()
    fig.savefig(f"{FIG}/conditioning_factors.pdf")
    plt.close(fig)
    print("   conditioning_factors.pdf")


def _susc_panel(ax, path, title, sar=None, cbar_label="Susceptibility $S(x)$"):
    with rasterio.open(path) as s:
        a = s.read(1).astype("float64")
        nod = s.nodata
        ext = (s.bounds.left, s.bounds.right, s.bounds.bottom, s.bounds.top)
    if nod is not None:
        a = np.where(a == nod, np.nan, a)
    if np.nanmax(a) > 1.5:                     # stored 0-255
        a = a / 255.0
    im = ax.imshow(a, extent=ext, origin="upper", cmap="viridis",
                   norm=Normalize(0, 1))
    if sar is not None and len(sar):
        sar.boundary.plot(ax=ax, color="#ff2d00", linewidth=0.35, zorder=5)
    ax.set_title(title, loc="left")
    latlon_axes(ax)
    ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3])
    return im, ext


def fig_susceptibility_surface():
    """The trained susceptibility surface, with SAR-observed flooding overlaid."""
    sar = gpd.read_file(SAR)
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.5))

    im, ext = _susc_panel(axes[0], SUSC, "(a) Susceptibility $S(x)$, full model", sar)
    scalebar(axes[0], ext[0] + 0.012, ext[2] + 0.012, 5)
    north_arrow(axes[0], 0.92, 0.95)

    if os.path.exists(HELDOUT):
        im2, ext2 = _susc_panel(
            axes[1], HELDOUT, "(b) Geographic-transfer prediction", sar)
        scalebar(axes[1], ext2[0] + 0.012, ext2[2] + 0.012, 5)
        north_arrow(axes[1], 0.92, 0.95)
    axes[1].legend(handles=[Line2D([0], [0], color="#ff2d00", lw=1.0,
                                   label="SAR-observed flooding")],
                   loc="lower left", fontsize=6, frameon=True, framealpha=0.9)

    cb = fig.colorbar(im, ax=axes, fraction=0.030, pad=0.02)
    cb.set_label("Susceptibility $S(x)$", fontsize=7.5)
    cb.ax.tick_params(labelsize=6)
    fig.savefig(f"{FIG}/susceptibility_surface.pdf")
    plt.close(fig)
    print("   susceptibility_surface.pdf")


def fig_sar_inventory():
    """The multi-temporal SAR flood inventory in its terrain context."""
    sar = gpd.read_file(SAR)
    bands, arr, ext = read_stack()
    land = land_mask(arr, bands)
    hand = np.where(land, arr[bands.index("hand")], np.nan)

    fig, ax = plt.subplots(figsize=(4.2, 4.6))
    ax.imshow(hand, extent=ext, origin="upper", cmap="Greys",
              norm=Normalize(0, 60), alpha=0.85, zorder=1)
    ax.imshow(np.where(land, np.nan, 1.0), extent=ext, origin="upper",
              cmap=mpl.colors.ListedColormap(["#9dc3e6"]), zorder=2)
    riv = river_mask(arr, bands)
    ax.imshow(np.where(riv & land, 1.0, np.nan), extent=ext, origin="upper",
              cmap=mpl.colors.ListedColormap(["#1f6fb4"]), zorder=3)
    sar.plot(ax=ax, facecolor="#ff2d00", edgecolor="#7f1600",
             linewidth=0.25, alpha=0.85, zorder=6)

    # Area MUST be computed in an equal-area (or local UTM) projection. Web
    # Mercator inflates area by sec^2(lat) = 1.05x at 12.9 deg N, which silently
    # turned 2.86 km^2 into 3.03 km^2 in an earlier revision of this figure.
    area_km2 = sar.to_crs(32643).area.sum() / 1e6      # UTM 43N
    ax.set_title(f"SAR flood inventory: {len(sar)} polygons, "
                 f"{area_km2:.1f} km$^2$", loc="left")
    latlon_axes(ax)
    ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3])
    scalebar(ax, ext[0] + 0.012, ext[2] + 0.012, 5)
    north_arrow(ax, 0.92, 0.95)
    ax.legend(handles=[
        Line2D([0], [0], marker="s", color="none", markerfacecolor="#ff2d00",
               markeredgecolor="#7f1600", markersize=6, label="Observed flooding"),
        Line2D([0], [0], color="#1f6fb4", lw=1.4, label="River network"),
        Line2D([0], [0], marker="s", color="none", markerfacecolor="#9dc3e6",
               markersize=6, label="Sea / estuary"),
    ], loc="upper left", fontsize=6, frameon=True, framealpha=0.92)
    fig.savefig(f"{FIG}/sar_inventory.pdf")
    plt.close(fig)
    print("   sar_inventory.pdf")


def fig_road_graph_risk():
    """The routing graph coloured by per-edge susceptibility."""
    roads = road_edges()
    s = roads["susceptibility"]
    prone = s > 0.5

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.8),
                             gridspec_kw={"width_ratios": [1, 1]})

    ax = axes[0]
    roads.plot(ax=ax, column="susceptibility", cmap="viridis", linewidth=0.28,
               norm=Normalize(0, 1))
    ax.set_title("(a) Edge susceptibility $S(e)$", loc="left")
    latlon_axes(ax)
    b = roads.total_bounds
    scalebar(ax, b[0] + 0.010, b[1] + 0.008, 5)
    north_arrow(ax, 0.92, 0.95)

    ax = axes[1]
    roads[~prone].plot(ax=ax, color="#c9ced6", linewidth=0.22)
    roads[prone].plot(ax=ax, color="#c1121f", linewidth=0.45)
    ax.set_title(f"(b) Flood-prone edges ($S>0.5$): {prone.sum():,} of "
                 f"{len(roads):,} ({100 * prone.mean():.1f}%)", loc="left", fontsize=7.5)
    latlon_axes(ax)
    scalebar(ax, b[0] + 0.010, b[1] + 0.008, 5)
    ax.legend(handles=[
        Line2D([0], [0], color="#c1121f", lw=1.4, label="Flood-prone"),
        Line2D([0], [0], color="#c9ced6", lw=1.4, label="Not flood-prone"),
    ], loc="upper left", fontsize=6, frameon=True, framealpha=0.92)

    sm = mpl.cm.ScalarMappable(cmap="viridis", norm=Normalize(0, 1))
    cb = fig.colorbar(sm, ax=axes, fraction=0.030, pad=0.02)
    cb.set_label("Edge susceptibility", fontsize=7.5)
    cb.ax.tick_params(labelsize=6)
    fig.savefig(f"{FIG}/road_graph_risk.pdf")
    plt.close(fig)
    print("   road_graph_risk.pdf")


def fig_route_overlay():
    """Risk-blind vs flood-aware route for the representative pair, on the network."""
    import networkx as nx
    from floodrisk import routing

    G = routing.load_graph()
    T = 0.70
    hospitals = locations.by_id(locations.HOSPITALS)
    incidents = locations.by_id(locations.INCIDENTS)
    h = hospitals["wenlock"]
    incident = incidents["kulur"]
    src = routing.nearest_node(h["lat"], h["lon"], G)
    dst = routing.nearest_node(incident["lat"], incident["lon"], G)

    def tt(u, v, data):
        return min(d.get("travel_time", 1e9) for d in data.values())

    def aware(u, v, data):
        best = None
        for d in data.values():
            r = d.get("susceptibility", 0.0) * T
            if r >= routing.BLOCK:
                continue
            c = d.get("travel_time", 0.0) * (1 + routing.PENALTY * r)
            best = c if best is None or c < best else best
        return best

    blind = nx.shortest_path(G, src, dst, weight=tt)
    safe = nx.shortest_path(G, src, dst, weight=aware)

    def profile(path):
        secs, risks = 0.0, []
        for u, v in zip(path[:-1], path[1:]):
            d = min(G[u][v].values(), key=lambda e: e.get("travel_time", 1e9))
            secs += d.get("travel_time", 0.0)
            risks.append(d.get("susceptibility", 0.0) * T)
        return secs / 60.0, float(np.mean(risks)), float(np.max(risks))

    def coords(path):
        xy = routing.path_coords(G, path)
        return np.array(xy) if xy else np.empty((0, 2))

    bm, bmean, bmax = profile(blind)
    sm_, smean, smax = profile(safe)
    cb_, cs = coords(blind), coords(safe)

    roads = road_edges()
    fig, ax = plt.subplots(figsize=(4.6, 5.0))
    roads.plot(ax=ax, column="susceptibility", cmap="viridis", linewidth=0.30,
               norm=Normalize(0, 1), alpha=0.95, zorder=1)
    ax.plot(cb_[:, 0], cb_[:, 1], color="#ff9500", lw=2.0, zorder=6,
            label=f"Risk-blind: {bm:.1f} min, mean $R$={bmean:.3f}")
    ax.plot(cs[:, 0], cs[:, 1], color="#ffffff", lw=3.0, zorder=6, alpha=0.85)
    ax.plot(cs[:, 0], cs[:, 1], color="#0b6e4f", lw=2.0, zorder=7,
            label=f"Flood-aware: {sm_:.1f} min, mean $R$={smean:.3f}")
    ax.scatter([G.nodes[src]["x"]], [G.nodes[src]["y"]], marker="P", s=55,
               c="#ffffff", edgecolor="k", linewidth=0.6, zorder=10)
    ax.scatter([G.nodes[dst]["x"]], [G.nodes[dst]["y"]], marker="o", s=40,
               c="#bf360c", edgecolor="k", linewidth=0.5, zorder=10)
    ax.annotate(h["short"], (G.nodes[src]["x"], G.nodes[src]["y"]),
                textcoords="offset points", xytext=(7, -3), fontsize=6.2, zorder=11,
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.75))
    ax.annotate(incident["name"], (G.nodes[dst]["x"], G.nodes[dst]["y"]),
                textcoords="offset points", xytext=(7, 4), fontsize=6.2, zorder=11,
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.75))

    pad = 0.006
    xs = np.concatenate([cb_[:, 0], cs[:, 0]]); ys = np.concatenate([cb_[:, 1], cs[:, 1]])
    x0, x1 = xs.min() - pad, xs.max() + pad
    y0, y1 = ys.min() - pad, ys.max() + pad
    # headroom at the bottom so the legend and scale bar never overlap the routes
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0 - 0.22 * (y1 - y0), y1)
    ax.set_title(f"Flood-aware detour at $T={T}$: "
                 f"{sm_ - bm:+.1f} min for {100 * (1 - smean / bmean):.0f}% "
                 f"less mean exposure", loc="left", fontsize=8)
    latlon_axes(ax)
    scalebar(ax, x1 - 0.015, y0 - 0.13 * (y1 - y0), 2)
    north_arrow(ax, 0.93, 0.93)
    ax.legend(loc="lower left", fontsize=6, frameon=True, framealpha=0.94)

    sm2 = mpl.cm.ScalarMappable(cmap="viridis", norm=Normalize(0, 1))
    cb2 = fig.colorbar(sm2, ax=ax, fraction=0.036, pad=0.02)
    cb2.set_label("Edge susceptibility", fontsize=7)
    cb2.ax.tick_params(labelsize=6)
    fig.savefig(f"{FIG}/route_overlay.pdf")
    plt.close(fig)
    print(f"   route_overlay.pdf  (blind {bm:.1f}min/{bmean:.3f}, "
          f"aware {sm_:.1f}min/{smean:.3f})")
    return {"blind_min": bm, "blind_mean": bmean, "blind_max": bmax,
            "aware_min": sm_, "aware_mean": smean, "aware_max": smax}


def main():
    os.makedirs(FIG, exist_ok=True)
    print(">> Building maps")
    fig_study_area()
    fig_conditioning_factors()
    fig_susceptibility_surface()
    fig_sar_inventory()
    fig_road_graph_risk()
    stats = fig_route_overlay()
    json.dump(stats, open("data/processed/route_overlay_stats.json", "w"), indent=2)
    print(">> Maps written to", FIG)


if __name__ == "__main__":
    main()
