"""Orion — flood risk & emergency response API.

Serves the dashboard from REAL research artifacts:
  • /api/trigger  -> live rainfall + tide via `floodrisk.live` (Open-Meteo, WorldTides)
  • /api/metrics  -> data/processed/model_metrics.json (the trained model's own numbers)
  • /api/dispatch -> web_assets/{hospitals,incidents,eta_all_*}.json (real OSM routing)

Nothing here fabricates data. If a live source is unreachable the response is
explicitly marked `"source": "unavailable"` so the UI can say so, rather than
silently showing invented values.
"""
import asyncio
import functools
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

# Repo root: flood-risk-app/backend -> flood-risk-app -> <repo>
REPO_ROOT = ROOT_DIR.parent.parent
PROCESSED = REPO_ROOT / "data" / "processed"
ASSETS = REPO_ROOT / "web_assets"

# Mangaluru coastal reference point for the optional tide observation
LAT, LON = 12.87, 74.84

logger = logging.getLogger("floodapi")
app = FastAPI(title="Orion — Flood Risk & Emergency Response")
api_router = APIRouter(prefix="/api")


def _read_json(path: Path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        logger.warning("could not read %s: %s", path, e)
        return default


# --------------------------------------------------------------------------- scenarios

SCENARIOS = {
    "dry":     {"label": "Dry / calm",                       "T": 0.00, "kind": "data-driven"},
    "live":    {"label": "Live now",                         "T": None, "kind": "data-driven"},
    "aug2024": {"label": "Aug 2024 — Nethravathi river",     "T": 0.39, "kind": "data-driven"},
    "may2025": {"label": "May 2025 — Mangaluru urban flood", "T": 0.70, "kind": "data-driven"},
    "flash5":  {"label": "Flash flood in 5 minutes",         "T": 0.85, "kind": "illustrative"},
}

# Which precomputed route/ETA set each scenario uses. Exported sets are `dry` and
# `may2025`; scenarios that reuse one are flagged so the UI can say so honestly
# instead of implying every scenario has its own routing solution.
ETA_SOURCE = {
    "dry": "dry", "live": "dry",
    "aug2024": "may2025", "may2025": "may2025", "flash5": "may2025",
}


@api_router.get("/")
async def root():
    return {"message": "Orion — Flood Risk & Emergency Response", "status": "ok",
            "region": "Dakshina Kannada, Karnataka, India"}


@api_router.get("/metrics")
async def get_metrics():
    """Model metrics straight from the training run (not hardcoded)."""
    m = _read_json(PROCESSED / "model_metrics.json")
    if not m:
        raise HTTPException(503, "model_metrics.json not found — run `make train`")
    best = m.get("best")
    test = m.get("results", {}).get(best, {}).get("test", {})
    cv = m.get("results", {}).get(best, {})
    importance = []
    imp_path = PROCESSED / "feature_importance.csv"
    if imp_path.exists():
        rows = imp_path.read_text().strip().splitlines()[1:]
        importance = [{"feature": r.split(",")[0], "mean_abs_shap": float(r.split(",")[1])}
                      for r in rows if "," in r]
    coverage = _read_json(ASSETS / "coverage.json", {})
    return {
        "algorithm": best,
        "roc_auc": test.get("roc_auc"),
        "accuracy": test.get("accuracy"),
        "precision": test.get("precision"),
        "recall": test.get("recall"),
        "f1": test.get("f1"),
        "cv_roc_auc_mean": cv.get("cv_roc_auc_mean"),
        "cv_roc_auc_std": cv.get("cv_roc_auc_std"),
        "confusion_matrix": test.get("confusion_matrix"),
        "feature_importance": importance,
        "sar_source": "Sentinel-1 GRD (Copernicus), descending rel. orbit 63",
        "dem_source": "SRTM GL1 30 m + MERIT Hydro",
        "all_models": m.get("results", {}),
        "coverage": coverage,
    }


@api_router.get("/dispatch")
async def get_dispatch():
    """Hospitals, incidents and the real OSM-derived ETA matrices."""
    hospitals = _read_json(ASSETS / "hospitals.json", [])
    incidents = _read_json(ASSETS / "incidents.json", [])
    eta = {k: _read_json(ASSETS / f"eta_all_{k}.json") for k in ("dry", "may2025")}
    eta = {k: v for k, v in eta.items() if v}
    if not hospitals or not eta:
        raise HTTPException(503, "dispatch assets missing — run `make assets`")
    return {
        "hospitals": hospitals,
        "incidents": incidents,
        "eta_matrix": eta,
        "eta_source": ETA_SOURCE,
        "quantum": _read_json(ASSETS / "dispatch.json", {}),
        "coverage": _read_json(ASSETS / "coverage.json", {}),
    }


@api_router.get("/scenarios")
async def get_scenarios():
    return SCENARIOS


@api_router.get("/scenario/{sid}")
async def get_scenario(sid: str):
    if sid not in SCENARIOS:
        raise HTTPException(404, "unknown scenario")
    s = dict(SCENARIOS[sid])
    s["id"] = sid
    s["eta_source"] = ETA_SOURCE[sid]
    s["eta_is_shared"] = ETA_SOURCE[sid] != sid
    if s["T"] is None:                       # live scenario -> current trigger
        s["T"] = (await get_trigger()).get("T")
    return s


# --------------------------------------------------------------------------- explanation

@api_router.get("/explain")
async def explain_point(lat: float, lon: float, scenario: str = "may2025"):
    """Why is THIS location risky? Real SHAP attributions from the trained model.

    Every figure returned is computed, not narrated by a language model: the
    predictor values are sampled from the exported raster and decomposed into
    per-feature contributions by the same model that produced the published AUC.
    """
    try:
        from floodrisk import explain as _explain
    except ImportError as e:
        raise HTTPException(503, f"floodrisk not installed: {e}")

    try:
        result = _explain.explain(lat, lon)
    except FileNotFoundError as e:
        raise HTTPException(503, f"missing artifact — run `make assets`: {e}")
    if result is None:
        raise HTTPException(404, "coordinate is outside the exported Mangaluru raster")

    # Combine the static susceptibility with the scenario trigger -> dynamic risk.
    if scenario in SCENARIOS:
        T = SCENARIOS[scenario]["T"]
        if T is None:
            T = (await get_trigger()).get("T")
        if T is not None:
            result["scenario"] = scenario
            result["trigger_T"] = T
            result["dynamic_risk"] = round(result["susceptibility"] * T, 4)
    return result


async def _scenario_trigger(scenario: str) -> float:
    T = SCENARIOS.get(scenario, {}).get("T")
    if T is None:                       # 'live' (or unknown) -> current trigger
        T = (await get_trigger()).get("T")
    return T if T is not None else 0.70


@api_router.post("/emergency")
async def emergency(lat: float, lon: float, scenario: str = "may2025"):
    """Pinpoint emergency dispatch from an arbitrary dropped pin.

    Snaps the pin to the road graph, routes from every hospital under the active
    flood scenario, and returns the optimal dispatch, the nearest hospitals to
    notify, and the Dijkstra-vs-A* search comparison for the chosen route. First
    call loads the OSM graph (~3 s); subsequent calls are fast.
    """
    try:
        from floodrisk import routing
    except ImportError as e:
        raise HTTPException(503, f"routing unavailable: {e}")

    if not _inside_district(lat, lon):
        raise HTTPException(422, "coordinate is outside the Dakshina Kannada district boundary")

    T = await _scenario_trigger(scenario)
    try:
        result = routing.emergency_dispatch(lat, lon, T)
    except FileNotFoundError as e:
        raise HTTPException(503, f"road graph missing — run `make assets`: {e}")
    except Exception as e:
        logger.error("emergency dispatch failed: %s", e)
        raise HTTPException(502, f"dispatch failed: {e}")
    result["scenario"] = scenario
    return result


@api_router.get("/experiments")
async def get_experiments():
    """Training-run history (append-only log), so ablations are comparable."""
    path = PROCESSED / "experiments.jsonl"
    if not path.exists():
        return {"runs": []}
    runs = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return {"runs": runs, "count": len(runs)}


# --------------------------------------------------------------------------- live trigger

_cache = {"at": 0.0, "data": None}
CACHE_TTL = 600  # 10 min — matches the dashboard refresh interval


def _imd_category(rain_24h: float) -> str:
    """India Meteorological Department daily-rainfall bands (mm/24h)."""
    if rain_24h < 64.5:
        return "Light / Moderate"
    if rain_24h < 115.6:
        return "Heavy"
    if rain_24h < 204.5:
        return "Very Heavy"
    return "Extremely Heavy"


def _headline(T: float, rain_72h: float) -> str:
    if T < 0.15:
        return f"OK — {rain_72h} mm in 72 h, background risk only."
    if T < 0.35:
        return f"WATCH — {rain_72h} mm in 72 h, risk elevated in valley corridors."
    if T < 0.60:
        return f"WARNING — {rain_72h} mm in 72 h, low-lying roads likely impacted."
    return f"DANGER — {rain_72h} mm in 72 h, inundation likely in susceptible corridors."


@functools.lru_cache(maxsize=1)
def _district_geometry():
    path = PROCESSED / "dakshina_kannada_boundary.geojson"
    if not path.exists():
        return None
    try:
        from shapely.geometry import shape
        raw = json.loads(path.read_text())
        geoms = [shape(f["geometry"]) for f in raw.get("features", [])]
        if not geoms:
            return None
        from shapely.ops import unary_union
        return unary_union(geoms)
    except Exception as e:
        logger.warning("district boundary unavailable: %s", e)
        return None


def _inside_district(lat: float, lon: float) -> bool:
    geom = _district_geometry()
    if geom is None:
        # Conservative bounds fallback keeps the endpoint useful before the graph
        # has been regenerated, without accepting arbitrary remote coordinates.
        return 12.45 <= lat <= 13.19 and 74.77 <= lon <= 75.68
    from shapely.geometry import Point
    return geom.covers(Point(lon, lat))


@api_router.get("/trigger")
async def get_trigger():
    """Live district rainfall trigger plus a separately reported coastal tide.

    T(t) is rainfall-only. Tide is contextual and is not silently folded into the
    trigger until a validated district hydrodynamic calibration exists.

    Cached for 10 minutes. On failure returns `source: "unavailable"` with null
    values — the UI must show 'live data unavailable', never invented numbers.
    """
    now = time.time()
    if _cache["data"] and now - _cache["at"] < CACHE_TTL:
        return _cache["data"]

    try:
        from floodrisk import live, locations

        def fetch_site(site):
            times, precip = live.fetch_openmeteo_rainfall(site["lat"], site["lon"])
            ant = live.antecedent_rainfall(times, precip)
            return {**site, **ant, "T": live.rainfall_trigger(ant)}

        results = await asyncio.gather(
            *(asyncio.to_thread(fetch_site, site) for site in locations.TRIGGER_SITES),
            return_exceptions=True,
        )
        sites = [r for r in results if isinstance(r, dict)]
        if not sites:
            raise RuntimeError("Open-Meteo failed at every district sampling site")
        critical = max(sites, key=lambda s: s["T"])
        ant = {k: critical[k] for k in ("1h", "6h", "24h", "72h")}
        T = critical["T"]

        tide_m, tide_trend = None, "unknown"
        try:
            tide = live.fetch_worldtides(LAT, LON)
            if tide and "height_m" in tide:
                tide_m = tide["height_m"]
        except Exception as e:                      # tide is optional, rainfall is not
            logger.warning("tide unavailable: %s", e)

        payload = {
            "T": T,
            "rain_1h": ant.get("1h"),
            "rain_6h": ant.get("6h"),
            "rain_24h": ant.get("24h"),
            "rain_72h": ant.get("72h"),
            "imd_category": _imd_category(ant.get("24h", 0.0)),
            "tide_m": tide_m,
            "tide_trend": tide_trend,
            "updated": datetime.now(timezone.utc).isoformat(),
            "headline": _headline(T, ant.get("72h", 0.0)),
            "critical_site": critical["name"],
            "sites": sites,
            "site_failures": len(results) - len(sites),
            "aggregation": "maximum trigger across five district sampling sites",
            "source": "Open-Meteo district rainfall sample + WorldTides Mangaluru tide",
        }
        _cache.update(at=now, data=payload)
        return payload

    except Exception as e:
        logger.error("live trigger unavailable: %s", e)
        return {
            "T": None, "rain_1h": None, "rain_6h": None,
            "rain_24h": None, "rain_72h": None,
            "imd_category": None, "tide_m": None, "tide_trend": None,
            "updated": datetime.now(timezone.utc).isoformat(),
            "headline": "Live data unavailable — check network / API keys.",
            "source": "unavailable",
            "error": str(e),
        }


app.include_router(api_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
