"""Deterministic tools backing the natural-language interface.

Design note: this is a plain tool registry, NOT an agent framework. Every question
the dashboard supports ("why is this risky?", "which areas need ambulances?",
"compare this year's rainfall") maps to exactly one deterministic computation, so
LangGraph/CrewAI-style multi-agent orchestration would add latency, nondeterminism
and failure modes for no benefit. The language model's only job is to pick a tool
and read its output back in prose — it never invents a number.
"""
import json
import os
from datetime import datetime, timezone

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(_REPO, "web_assets")


def _load(name, default=None):
    path = os.path.join(ASSETS, name)
    if not os.path.exists(path):
        return default
    with open(path) as f:
        return json.load(f)


# --------------------------------------------------------------------------- tools

def _gazetteer():
    """Canonical coordinates for known hospitals and incident sites."""
    places = []
    for p in _load("incidents.json", []) or []:
        places.append({"name": p["name"], "id": p["id"], "kind": "incident",
                       "lat": p["lat"], "lon": p["lon"]})
    for p in _load("hospitals.json", []) or []:
        places.append({"name": p["name"], "id": p["id"], "kind": "hospital",
                       "lat": p["lat"], "lon": p["lon"]})
    return places


def locate_place(name: str):
    """Resolve a place name to its CANONICAL coordinates.

    Exists so the language model never guesses coordinates for a named location —
    guessed lat/lon silently samples the wrong pixel and produces wrong terrain
    values. Always call this before explain_risk for a named place.
    """
    import difflib
    places = _gazetteer()
    if not places:
        return {"error": "gazetteer missing — run `make assets`"}
    q = (name or "").strip().lower()
    for p in places:
        if q == p["name"].lower() or q == p["id"].lower():
            return p
    for p in places:
        if q and (q in p["name"].lower() or p["name"].lower().startswith(q)):
            return p
    hit = difflib.get_close_matches(q, [p["name"].lower() for p in places], n=1, cutoff=0.6)
    if hit:
        return next(p for p in places if p["name"].lower() == hit[0])
    return {"error": f"unknown place '{name}'",
            "known_places": [p["name"] for p in places]}


def explain_risk(lat: float, lon: float):
    """Why is a specific COORDINATE risky? Real SHAP attributions.

    For a named place, call locate_place first — do not guess coordinates.
    """
    from . import explain as _explain
    r = _explain.explain(lat, lon)
    if r is None:
        return {"error": "coordinate outside the exported Dakshina Kannada raster"}
    return r


def explain_place(name: str):
    """Why is a NAMED place risky? Resolves canonical coordinates, then explains."""
    loc = locate_place(name)
    if "error" in loc:
        return loc
    r = explain_risk(loc["lat"], loc["lon"])
    if isinstance(r, dict) and "error" not in r:
        r["place"] = loc["name"]
        r["place_kind"] = loc["kind"]
    return r


def susceptibility_at(lat: float, lon: float):
    """Flood susceptibility (0-1) and risk band at a point."""
    from . import explain as _explain
    r = _explain.explain(lat, lon)
    if r is None:
        return {"error": "coordinate outside the exported Dakshina Kannada raster"}
    return {"lat": lat, "lon": lon, "susceptibility": r["susceptibility"],
            "calibrated_probability": r["calibrated_probability"],
            "risk_band": r["risk_band"],
            "caveat": r["caveat"]}


def current_conditions():
    """Live rainfall, tide and the resulting trigger T(t)."""
    from . import live
    times, precip = live.fetch_openmeteo_rainfall(12.87, 74.84)
    ant = live.antecedent_rainfall(times, precip)
    T = live.rainfall_trigger(ant)
    tide = None
    try:
        t = live.fetch_worldtides(12.87, 74.84)
        tide = t.get("height_m") if t else None
    except Exception:
        pass
    return {"trigger_T": T, "antecedent_rainfall_mm": ant, "tide_m": tide,
            "updated": datetime.now(timezone.utc).isoformat(),
            "source": "Open-Meteo + WorldTides"}


def compare_rainfall(year_a: int, year_b: int, month_start: int = 5, month_end: int = 9):
    """Compare monsoon-season rainfall totals between two years (ERA5 archive)."""
    from . import live
    out = {}
    for y in (year_a, year_b):
        start = f"{y}-{month_start:02d}-01"
        end = f"{y}-{month_end:02d}-30"
        try:
            _, precip = live.fetch_openmeteo_archive(12.87, 74.84, start, end)
            out[str(y)] = round(sum(precip), 1)
        except Exception as e:
            out[str(y)] = {"error": str(e)}
    a, b = out.get(str(year_a)), out.get(str(year_b))
    diff = None
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        diff = round(b - a, 1)
    return {"season": f"{month_start:02d}-01 to {month_end:02d}-30",
            "totals_mm": out, "difference_mm": diff,
            "note": "Open-Meteo ERA5 reanalysis at Mangaluru (12.87N, 74.84E)"}


def rank_incidents_by_need(scenario: str = "may2025"):
    """Rank incident sites by how hard they are to reach under a scenario.

    Uses the real flood-aware ETA matrix: sites with fewer reachable hospitals and
    longer best-ETA need more ambulance capacity.
    """
    key = "dry" if scenario == "dry" else "may2025"
    eta = _load(f"eta_all_{key}.json")
    incidents = _load("incidents.json", [])
    hospitals = _load("hospitals.json", [])
    if not eta or not incidents:
        return {"error": "dispatch assets missing — run `make assets`"}

    aware = eta.get("aware", {})
    rows = []
    for inc in incidents:
        etas = [aware.get(h["id"], {}).get(inc["id"]) for h in hospitals]
        reachable = [e for e in etas if e is not None]
        rows.append({
            "incident": inc["name"], "id": inc["id"],
            "reachable_hospitals": len(reachable),
            "severed_routes": len(etas) - len(reachable),
            "best_eta_min": round(min(reachable), 1) if reachable else None,
            "mean_eta_min": round(sum(reachable) / len(reachable), 1) if reachable else None,
        })
    # Hardest to reach first: fully unreachable, then most severed routes, then
    # slowest best-ETA. (Keys are NOT negated — reverse=True already descends.)
    rows.sort(key=lambda r: (r["best_eta_min"] is None,
                             r["severed_routes"],
                             r["best_eta_min"] or 0), reverse=True)
    return {"scenario": scenario, "ranking": rows,
            "note": "Ranked by access difficulty under flood-aware routing."}


def dispatch_plan(scenario: str = "may2025", fleet_per_hospital: int = 1):
    """Optimal hospital->incident assignment (the paper's dispatch result)."""
    key = "dry" if scenario == "dry" else "may2025"
    eta = _load(f"eta_all_{key}.json")
    incidents = _load("incidents.json", [])
    hospitals = _load("hospitals.json", [])
    if not eta:
        return {"error": "dispatch assets missing — run `make assets`"}

    import numpy as np
    from scipy.optimize import linear_sum_assignment

    aware = eta.get("aware", {})
    units = [h for h in hospitals for _ in range(max(1, fleet_per_hospital))]
    BIG = 1e6
    C = np.array([[aware.get(u["id"], {}).get(i["id"]) or BIG for i in incidents]
                  for u in units], dtype=float)
    r, c = linear_sum_assignment(C)

    assigns, total = [], 0.0
    for ri, ci in zip(r, c):
        val = C[ri, ci]
        if val >= BIG:
            assigns.append({"hospital": units[ri]["name"], "incident": incidents[ci]["name"],
                            "eta_min": None, "status": "unreachable"})
        else:
            total += val
            assigns.append({"hospital": units[ri]["name"], "incident": incidents[ci]["name"],
                            "eta_min": round(val, 1), "status": "assigned"})
    return {"scenario": scenario, "fleet_per_hospital": fleet_per_hospital,
            "assignments": assigns, "total_response_min": round(total, 1),
            "method": "Hungarian (identical optimum to the QAOA/QUBO formulation)"}


def fly_to_place(name: str):
    """Move the map camera to a named place with a cinematic aerial approach.

    Returns a `map_action` directive the dashboard executes; the camera work itself
    happens client-side.
    """
    loc = locate_place(name)
    if "error" in loc:
        return loc
    detail = susceptibility_at(loc["lat"], loc["lon"])
    return {
        "map_action": {"action": "fly_to", "lat": loc["lat"], "lon": loc["lon"],
                       "label": loc["name"], "zoom": 15.6},
        "place": loc["name"], "kind": loc["kind"],
        "susceptibility": detail.get("susceptibility"),
        "risk_band": detail.get("risk_band"),
        "spoken": f"Flying to {loc['name']}.",
    }


def follow_ambulance(incident: str, hospital: str = None, scenario: str = "may2025"):
    """Follow an ambulance along its flood-aware route to an incident.

    If no hospital is given, uses the one with the fastest flood-aware route.
    Returns a `map_action` the dashboard animates as a chase-camera shot.
    """
    key = "dry" if scenario == "dry" else "may2025"
    eta = _load(f"eta_all_{key}.json")
    hospitals = _load("hospitals.json", [])
    if not eta or not hospitals:
        return {"error": "dispatch assets missing — run `make assets`"}

    inc = locate_place(incident)
    if "error" in inc:
        return inc
    if inc["kind"] != "incident":
        return {"error": f"'{inc['name']}' is a hospital, not an incident site"}

    aware = eta.get("aware", {})
    if hospital:
        h = locate_place(hospital)
        if "error" in h:
            return h
        hid = h["id"]
        if aware.get(hid, {}).get(inc["id"]) is None:
            return {"error": f"no flood-aware route from {h['name']} to {inc['name']} "
                             f"under {scenario} — the route is severed"}
    else:
        options = [(hid, v.get(inc["id"])) for hid, v in aware.items()
                   if v.get(inc["id"]) is not None]
        if not options:
            return {"error": f"{inc['name']} is unreachable under {scenario}"}
        hid = min(options, key=lambda x: x[1])[0]

    hname = next((x["name"] for x in hospitals if x["id"] == hid), hid)
    minutes = aware[hid][inc["id"]]
    return {
        "map_action": {"action": "follow_route", "hospital": hid, "incident": inc["id"],
                       "scenario": scenario, "label": f"{hname} → {inc['name']}"},
        "hospital": hname, "incident": inc["name"], "scenario": scenario,
        "eta_min": minutes,
        "spoken": f"Following the ambulance from {hname} to {inc['name']}, "
                  f"estimated {minutes:.0f} minutes.",
    }


def model_info():
    """Model performance and top predictors, straight from the training run."""
    p = os.path.join(_REPO, "data", "processed", "model_metrics.json")
    if not os.path.exists(p):
        return {"error": "model_metrics.json missing — run `make train`"}
    m = json.load(open(p))
    best = m.get("best")
    t = m.get("results", {}).get(best, {})
    return {"algorithm": best, "test": t.get("test"),
            "cv_roc_auc_mean": t.get("cv_roc_auc_mean"),
            "calibration": m.get("calibration", {}).get("brier_calibrated"),
            "caveat": "Susceptibility is a relative exposure index, not water depth."}


# --------------------------------------------------------------------------- registry

REGISTRY = {
    "fly_to_place": fly_to_place,
    "follow_ambulance": follow_ambulance,
    "locate_place": locate_place,
    "explain_place": explain_place,
    "explain_risk": explain_risk,
    "susceptibility_at": susceptibility_at,
    "current_conditions": current_conditions,
    "compare_rainfall": compare_rainfall,
    "rank_incidents_by_need": rank_incidents_by_need,
    "dispatch_plan": dispatch_plan,
    "model_info": model_info,
}

# Anthropic tool-use schemas.
SCHEMAS = [
    {"name": "fly_to_place",
     "description": ("Move the map camera to a named place with a cinematic aerial "
                     "approach. Use for 'take me to X', 'show me X', 'zoom into X'."),
     "input_schema": {"type": "object", "properties": {
         "name": {"type": "string"}}, "required": ["name"]}},
    {"name": "follow_ambulance",
     "description": ("Follow an ambulance along its flood-aware route to an incident "
                     "with a chase camera. Use for 'show me the ambulance routing to X', "
                     "'follow the ambulance to X'. Hospital is optional - omit it to use "
                     "the fastest available."),
     "input_schema": {"type": "object", "properties": {
         "incident": {"type": "string"},
         "hospital": {"type": "string"},
         "scenario": {"type": "string", "enum": ["dry", "may2025"]}},
         "required": ["incident"]}},
    {"name": "explain_place",
     "description": ("Explain why a NAMED place (e.g. 'Kulur', 'Pumpwell', 'Wenlock') is "
                     "flood-risky, using its canonical coordinates. PREFER THIS over "
                     "explain_risk whenever the user names a location."),
     "input_schema": {"type": "object", "properties": {
         "name": {"type": "string"}}, "required": ["name"]}},
    {"name": "locate_place",
     "description": ("Resolve a place name to its canonical latitude/longitude. Use this "
                     "instead of guessing coordinates for a named location."),
     "input_schema": {"type": "object", "properties": {
         "name": {"type": "string"}}, "required": ["name"]}},
    {"name": "explain_risk",
     "description": ("Explain why a specific COORDINATE is flood-risky, with SHAP feature "
                     "attributions. Only use when given explicit lat/lon; for named places "
                     "use explain_place."),
     "input_schema": {"type": "object", "properties": {
         "lat": {"type": "number"}, "lon": {"type": "number"}}, "required": ["lat", "lon"]}},
    {"name": "susceptibility_at",
     "description": "Flood susceptibility score and risk band at a coordinate.",
     "input_schema": {"type": "object", "properties": {
         "lat": {"type": "number"}, "lon": {"type": "number"}}, "required": ["lat", "lon"]}},
    {"name": "current_conditions",
     "description": "Live rainfall, tide and the current dynamic trigger T(t).",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "compare_rainfall",
     "description": "Compare monsoon rainfall totals between two years.",
     "input_schema": {"type": "object", "properties": {
         "year_a": {"type": "integer"}, "year_b": {"type": "integer"}},
         "required": ["year_a", "year_b"]}},
    {"name": "rank_incidents_by_need",
     "description": "Rank incident sites by access difficulty / ambulance need under a scenario.",
     "input_schema": {"type": "object", "properties": {
         "scenario": {"type": "string", "enum": ["dry", "may2025"]}}}},
    {"name": "dispatch_plan",
     "description": "Optimal ambulance dispatch assignment for a scenario.",
     "input_schema": {"type": "object", "properties": {
         "scenario": {"type": "string", "enum": ["dry", "may2025"]},
         "fleet_per_hospital": {"type": "integer"}}}},
    {"name": "model_info",
     "description": "Susceptibility model performance metrics and caveats.",
     "input_schema": {"type": "object", "properties": {}}},
]


def call(tool_name, /, **kwargs):
    """Invoke a registered tool by name.

    `tool_name` is positional-only: several tools take their own `name` argument
    (locate_place, explain_place), which would otherwise collide.
    """
    fn = REGISTRY.get(tool_name)
    if fn is None:
        return {"error": f"unknown tool '{tool_name}'"}
    try:
        return fn(**kwargs)
    except TypeError as e:
        return {"error": f"bad arguments for {tool_name}: {e}"}
