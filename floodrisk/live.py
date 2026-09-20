"""Live data ingestion for the dynamic flood-risk trigger.

Sources:
  - Open-Meteo (keyless): hourly precipitation, past + forecast -> antecedent rainfall.
  - WorldTides (key in .secrets/live_api.env): tide height for the coastal estuary.

The two-stage risk model uses these to build a temporal trigger T(t) that modulates
the static SAR-derived susceptibility S(x): dynamic risk R(x,t) = S(x) * T(t).
"""
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone

# IMD daily-rainfall categories (mm/24h) — used to normalize the rainfall trigger
IMD_HEAVY = 64.5
IMD_VERY_HEAVY = 115.6
IMD_EXTREME = 204.5


def _get_json(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "floodrisk/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


# Repo root = parent of the floodrisk package, so secrets resolve no matter the CWD
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_KEY_PATH = os.path.join(_REPO_ROOT, ".secrets", "live_api.env")


def _load_keys(path=None):
    """Load API keys from .secrets/live_api.env (repo-root relative) or the environment.

    Resolving against the package location rather than the CWD means the backend
    (run from flood-risk-app/backend) picks up the same keys as the pipeline scripts.
    Environment variables take precedence, for CI/deployment.
    """
    keys = {}
    for path_ in ([path] if path else [_DEFAULT_KEY_PATH, ".secrets/live_api.env"]):
        if path_ and os.path.exists(path_):
            with open(path_) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        keys.setdefault(k.strip(), v.strip())
            break
    for env_key in ("WORLDTIDES_API_KEY", "OPENWEATHER_API_KEY"):
        if os.environ.get(env_key):
            keys[env_key] = os.environ[env_key]
    return keys


def fetch_openmeteo_rainfall(lat, lon, past_days=7, forecast_days=2):
    """Hourly precipitation (mm) for a point: trailing `past_days` + `forecast_days`."""
    params = {
        "latitude": lat, "longitude": lon,
        "hourly": "precipitation",
        "past_days": past_days, "forecast_days": forecast_days,
        "timezone": "UTC",
    }
    url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(params)
    data = _get_json(url)
    h = data["hourly"]
    times = [datetime.fromisoformat(t).replace(tzinfo=timezone.utc) for t in h["time"]]
    precip = [p if p is not None else 0.0 for p in h["precipitation"]]
    return times, precip


def fetch_openmeteo_archive(lat, lon, start_date, end_date):
    """Historical hourly precipitation (mm) from the ERA5 archive (for event replays)."""
    params = {
        "latitude": lat, "longitude": lon,
        "hourly": "precipitation",
        "start_date": start_date, "end_date": end_date,
        "timezone": "UTC",
    }
    url = "https://archive-api.open-meteo.com/v1/archive?" + urllib.parse.urlencode(params)
    data = _get_json(url)
    h = data["hourly"]
    times = [datetime.fromisoformat(t).replace(tzinfo=timezone.utc) for t in h["time"]]
    precip = [p if p is not None else 0.0 for p in h["precipitation"]]
    return times, precip


def antecedent_rainfall(times, precip, now=None):
    """Trailing rainfall totals (mm) over 1/6/24/72 h up to `now` (UTC)."""
    if now is None:
        now = datetime.now(timezone.utc)
    windows = {"1h": 1, "6h": 6, "24h": 24, "72h": 72}
    out = {}
    for name, hrs in windows.items():
        total = sum(p for t, p in zip(times, precip)
                    if 0 <= (now - t).total_seconds() <= hrs * 3600)
        out[name] = round(total, 1)
    return out


def rainfall_trigger(antecedent):
    """Map antecedent rainfall to a 0-1 trigger intensity reflecting flood physics.

    Blends three drivers:
      - daily intensity  (24h total vs IMD very-heavy 115.6mm)
      - antecedent soil saturation (72h total vs ~200mm)
      - short burst      (6h total vs IMD heavy 64.5mm)
    A saturated catchment floods on less additional rain, so saturation is weighted
    alongside intensity rather than ignored.
    """
    r6 = antecedent.get("6h", 0.0)
    r24 = antecedent.get("24h", 0.0)
    r72 = antecedent.get("72h", 0.0)
    daily = min(r24 / IMD_VERY_HEAVY, 1.0)
    sat = min(r72 / 200.0, 1.0)
    burst = min(r6 / IMD_HEAVY, 1.0)
    trigger = 0.5 * daily + 0.3 * sat + 0.2 * burst
    return round(min(trigger, 1.0), 3)


def fetch_worldtides(lat, lon, keys=None):
    """Current tide height (m) and trend from WorldTides. Returns None if no key."""
    keys = keys or _load_keys()
    api = keys.get("WORLDTIDES_API_KEY")
    if not api:
        return None
    url = ("https://www.worldtides.info/api/v3?heights"
           f"&lat={lat}&lon={lon}&key={api}&duration=3600")
    try:
        data = _get_json(url)
        heights = data.get("heights", [])
        if heights:
            return {"height_m": round(heights[0]["height"], 2),
                    "datetime": heights[0]["date"]}
    except Exception as e:
        return {"error": str(e)}
    return None
