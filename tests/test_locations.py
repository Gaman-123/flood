"""Coverage and provenance invariants for operational locations."""

from floodrisk import config, locations


def test_hospital_ids_and_osm_elements_are_unique():
    ids = [h["id"] for h in locations.HOSPITALS]
    osm = [(h["osm_type"], h["osm_id"]) for h in locations.HOSPITALS]
    assert len(ids) == len(set(ids))
    assert len(osm) == len(set(osm))


def test_hospitals_cover_all_nine_district_taluks():
    expected = {"Mangaluru", "Ullal", "Mulki", "Moodbidri", "Bantwal",
                "Belthangady", "Puttur", "Kadaba", "Sullia"}
    assert {h["taluk"] for h in locations.HOSPITALS} == expected


def test_every_location_is_inside_the_district_filter_extent():
    west, south, east, north = config.DK_BBOX
    for row in locations.HOSPITALS + locations.INCIDENTS + locations.TRIGGER_SITES:
        assert west <= row["lon"] <= east, row["id"]
        assert south <= row["lat"] <= north, row["id"]


def test_quantum_subproblem_is_a_strict_audited_subset():
    hospitals = {h["id"] for h in locations.HOSPITALS}
    incidents = {i["id"] for i in locations.INCIDENTS}
    assert len(locations.QUANTUM_HOSPITAL_IDS) == 3
    assert len(locations.QUANTUM_INCIDENT_IDS) == 3
    assert set(locations.QUANTUM_HOSPITAL_IDS) <= hospitals
    assert set(locations.QUANTUM_INCIDENT_IDS) <= incidents
