"""Invariants for the deterministic tool layer + place resolution.

The risky failure mode is silent misdirection: the model must never guess a
coordinate for a named place, and severed routes must surface as errors rather
than being quietly substituted. (The voice layer these tools once fed has been
removed; the tools remain as a library used by the explain endpoint.)
"""
import pytest

from floodrisk import tools


def test_known_places_resolve_to_canonical_coordinates():
    r = tools.call("locate_place", name="Kulur")
    if "error" in r:
        pytest.skip("gazetteer missing — run `make assets`")
    assert r["name"] == "Kulur"
    assert 12.8 < r["lat"] < 13.0 and 74.7 < r["lon"] < 75.0


def test_place_lookup_is_fuzzy_but_bounded():
    hit = tools.call("locate_place", name="kulur")          # case-insensitive
    if "error" in hit:
        pytest.skip("gazetteer missing")
    assert hit["name"] == "Kulur"
    miss = tools.call("locate_place", name="Zzzzzzz")
    assert "error" in miss and "known_places" in miss


def test_explain_place_matches_explain_at_its_coordinates():
    """A named place must give exactly the same answer as its canonical coords.

    This is the guard against the model guessing lat/lon: explain_place is the
    only path that can be trusted for a named location.
    """
    loc = tools.call("locate_place", name="Kulur")
    if "error" in loc:
        pytest.skip("gazetteer missing")
    by_name = tools.call("explain_place", name="Kulur")
    by_coord = tools.call("explain_risk", lat=loc["lat"], lon=loc["lon"])
    if "error" in by_name or "error" in by_coord:
        pytest.skip("predictor stack missing — run scripts/export_predictor_stack.py")
    assert by_name["susceptibility"] == by_coord["susceptibility"]
    assert by_name["place"] == "Kulur"


def test_tool_name_collision_is_handled():
    """Regression: call(name, **kwargs) collided with tools taking their own `name`."""
    r = tools.call("locate_place", name="Pumpwell")
    assert "error" not in r or "unknown place" in r.get("error", "")


def test_registry_and_schemas_stay_in_sync():
    assert {s["name"] for s in tools.SCHEMAS} == set(tools.REGISTRY)


def test_fly_to_place_returns_canonical_coordinates():
    r = tools.call("fly_to_place", name="Kulur")
    if "error" in r:
        pytest.skip("gazetteer missing")
    loc = tools.call("locate_place", name="Kulur")
    assert r["map_action"]["action"] == "fly_to"
    assert r["map_action"]["lat"] == loc["lat"]
    assert r["map_action"]["lon"] == loc["lon"]


def test_follow_ambulance_picks_a_reachable_hospital():
    r = tools.call("follow_ambulance", incident="Kulur", scenario="may2025")
    if "error" in r:
        pytest.skip("dispatch assets missing")
    assert r["map_action"]["action"] == "follow_route"
    assert r["eta_min"] is not None
    # the chosen hospital must actually have a flood-aware route
    eta = tools._load("eta_all_may2025.json")["aware"]
    assert eta[r["map_action"]["hospital"]][r["map_action"]["incident"]] is not None


def test_follow_ambulance_rejects_a_hospital_as_destination():
    r = tools.call("follow_ambulance", incident="Wenlock")
    if "error" in r and "assets missing" in r["error"]:
        pytest.skip("dispatch assets missing")
    assert "error" in r and "not an incident" in r["error"]


def test_follow_ambulance_reports_severed_routes_honestly():
    """Any currently severed matrix entry must surface as an error."""
    aware = tools._load("eta_all_may2025.json", {}).get("aware", {})
    pair = next(((hid, iid) for hid, row in aware.items()
                 for iid, eta in row.items() if eta is None), None)
    if pair is None:
        pytest.skip("current scenario has no severed hospital-incident pair")
    hid, iid = pair
    r = tools.call("follow_ambulance", incident=iid,
                   hospital=hid, scenario="may2025")
    if "error" in r and "assets missing" in r["error"]:
        pytest.skip("dispatch assets missing")
    assert "error" in r and "severed" in r["error"]
