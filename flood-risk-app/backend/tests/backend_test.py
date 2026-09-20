"""
Backend API tests for Dakshina Kannada Flood Response dashboard.
Covers /api/trigger, /api/metrics, /api/dispatch, /api/scenarios, /api/scenario/{id}.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    # Fallback: read from frontend .env (public URL used by frontend)
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip()
                    break
    except Exception:
        pass

assert BASE_URL, "REACT_APP_BACKEND_URL must be set"
BASE_URL = BASE_URL.rstrip("/")


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------- /api root ----------
class TestRoot:
    def test_root(self, api):
        r = api.get(f"{BASE_URL}/api/", timeout=15)
        assert r.status_code == 200
        assert "message" in r.json()


# ---------- /api/trigger ----------
class TestTrigger:
    def test_trigger_shape_and_values(self, api):
        r = api.get(f"{BASE_URL}/api/trigger", timeout=15)
        assert r.status_code == 200
        d = r.json()
        for k in ["T", "rain_24h", "rain_72h", "imd_category", "tide_m", "tide_trend", "updated", "headline"]:
            assert k in d, f"missing key {k}"
        # T in [0,1]
        assert isinstance(d["T"], (int, float))
        assert 0.0 <= d["T"] <= 1.0
        assert d["imd_category"] in ["Light", "Heavy", "Very Heavy", "Extreme"]
        assert d["tide_trend"] in ["rising", "falling"]
        assert isinstance(d["headline"], str) and len(d["headline"]) > 0


# ---------- /api/metrics ----------
class TestMetrics:
    def test_metrics_values(self, api):
        r = api.get(f"{BASE_URL}/api/metrics", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["roc_auc"] == 0.962
        assert d["road_edges"] == 28529
        assert d["flood_prone_pct"] == 17.1
        assert d["flood_prone_edges"] == 4873
        assert d["algorithm"] == "XGBoost"


# ---------- /api/dispatch ----------
class TestDispatch:
    def test_dispatch_structure(self, api):
        r = api.get(f"{BASE_URL}/api/dispatch", timeout=15)
        assert r.status_code == 200
        d = r.json()
        # 3 hospitals: Wenlock, AJ Kuntikana, KMC Attavar
        hospital_ids = {h["id"] for h in d["hospitals"]}
        assert hospital_ids == {"wenlock", "aj", "kmc"}
        hospital_names = {h["name"] for h in d["hospitals"]}
        assert "Wenlock District Hospital" in hospital_names
        assert "AJ Hospital Kuntikana" in hospital_names
        assert "KMC Attavar" in hospital_names

        # 3 incidents
        incident_ids = {i["id"] for i in d["incidents"]}
        assert incident_ids == {"kottara", "kulur", "pumpwell"}

        # Coord sanity check (near Mangaluru ~12.87N 74.85E)
        for h in d["hospitals"]:
            assert 12.5 < h["lat"] < 13.5
            assert 74.5 < h["lon"] < 75.0

        # ETA matrix
        assert "eta_matrix" in d
        assert "dry" in d["eta_matrix"] and "may2025" in d["eta_matrix"]
        assert d["eta_matrix"]["dry"]["wenlock"] == [5.3, 7.0, 13.6]
        assert d["eta_matrix"]["may2025"]["wenlock"] == [5.3, 7.3, 17.4]
        # optimal_assignment
        opt = d["optimal_assignment"]
        assert {(a["hospital"], a["incident"]) for a in opt} == {
            ("wenlock", "kottara"), ("aj", "kulur"), ("kmc", "pumpwell")
        }


# ---------- /api/scenarios and /api/scenario/{id} ----------
class TestScenarios:
    def test_scenarios_list(self, api):
        r = api.get(f"{BASE_URL}/api/scenarios", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert set(d.keys()) == {"dry", "live", "aug2024", "may2025", "flash5"}

    def test_scenario_may2025(self, api):
        r = api.get(f"{BASE_URL}/api/scenario/may2025", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["id"] == "may2025"
        assert d["T"] == 0.70
        assert d["kind"] == "data-driven"
        assert "dispatch" in d

    def test_scenario_flash5(self, api):
        r = api.get(f"{BASE_URL}/api/scenario/flash5", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["id"] == "flash5"
        assert d["T"] == 0.85
        assert d["kind"] == "illustrative"

    def test_scenario_dry(self, api):
        r = api.get(f"{BASE_URL}/api/scenario/dry", timeout=15)
        assert r.status_code == 200
        assert r.json()["T"] == 0.0

    def test_scenario_unknown_404(self, api):
        r = api.get(f"{BASE_URL}/api/scenario/unknown", timeout=15)
        assert r.status_code == 404
