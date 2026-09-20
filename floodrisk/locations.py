"""Audited operational locations for district-scale dispatch.

The original dashboard used seven Mangaluru hospitals and seven city incidents.
This module is the single source of truth for a district-wide demonstration.
Facilities are deliberately curated rather than treating every OpenStreetMap
``amenity=hospital`` object as an ambulance base: the raw district query contains
duplicates, eye/dental/veterinary facilities, clinics, and unnamed records.

Coordinates and OSM element identifiers were checked against the Dakshina Kannada
administrative polygon on 2026-09-11. Inclusion means "routing origin in this
research prototype"; it does not assert current ambulance availability, emergency
department status, bed capacity, or official empanelment.
"""

HOSPITALS = [
    {"id": "wenlock", "name": "Government Wenlock District Hospital", "short": "Wenlock",
     "lat": 12.867142, "lon": 74.842770, "taluk": "Mangaluru", "ownership": "government",
     "osm_type": "way", "osm_id": 132058594},
    {"id": "aj", "name": "A. J. Hospital and Research Centre", "short": "A. J.",
     "lat": 12.899388, "lon": 74.845720, "taluk": "Mangaluru", "ownership": "private",
     "osm_type": "way", "osm_id": 319584642},
    {"id": "kmc", "name": "KMC Hospital Ambedkar Circle", "short": "KMC",
     "lat": 12.871760, "lon": 74.848976, "taluk": "Mangaluru", "ownership": "private",
     "osm_type": "way", "osm_id": 26564971},
    {"id": "father_muller", "name": "Father Muller Medical College Hospital", "short": "Father Muller",
     "lat": 12.866241, "lon": 74.859738, "taluk": "Mangaluru", "ownership": "private",
     "osm_type": "way", "osm_id": 160151297},
    {"id": "indiana", "name": "Indiana Hospital and Heart Institute", "short": "Indiana",
     "lat": 12.867680, "lon": 74.866423, "taluk": "Mangaluru", "ownership": "private",
     "osm_type": "node", "osm_id": 1699731456},
    {"id": "yenepoya", "name": "Yenepoya Medical College Hospital", "short": "Yenepoya",
     "lat": 12.812225, "lon": 74.880570, "taluk": "Ullal", "ownership": "private",
     "osm_type": "node", "osm_id": 6944343600},
    {"id": "srinivas_mukka", "name": "Srinivas Hospital Mukka", "short": "Srinivas Mukka",
     "lat": 13.021434, "lon": 74.791943, "taluk": "Mangaluru", "ownership": "private",
     "osm_type": "way", "osm_id": 228511262},
    {"id": "surathkal_gh", "name": "Surathkal Government Hospital", "short": "Surathkal GH",
     "lat": 12.987288, "lon": 74.803540, "taluk": "Mangaluru", "ownership": "government",
     "osm_type": "way", "osm_id": 239545312},
    {"id": "mulki_gh", "name": "Mulki Government Hospital", "short": "Mulki GH",
     "lat": 13.087491, "lon": 74.792202, "taluk": "Mulki", "ownership": "government",
     "osm_type": "way", "osm_id": 226734809},
    {"id": "shirthady_gh", "name": "Shirthady Government Hospital", "short": "Shirthady GH",
     "lat": 13.085766, "lon": 75.082503, "taluk": "Moodbidri", "ownership": "government",
     "osm_type": "node", "osm_id": 7202935830},
    {"id": "bantwal_th", "name": "Bantwal Taluk General Hospital", "short": "Bantwal TH",
     "lat": 12.894021, "lon": 75.041558, "taluk": "Bantwal", "ownership": "government",
     "osm_type": "node", "osm_id": 7213565706},
    {"id": "vitla_gh", "name": "Vitla Government Hospital", "short": "Vitla GH",
     "lat": 12.763476, "lon": 75.097878, "taluk": "Bantwal", "ownership": "government",
     "osm_type": "node", "osm_id": 922426889},
    {"id": "puttur_gh", "name": "Puttur General Hospital", "short": "Puttur GH",
     "lat": 12.758473, "lon": 75.200597, "taluk": "Puttur", "ownership": "government",
     "osm_type": "node", "osm_id": 7202723940},
    {"id": "belthangady_th", "name": "Belthangady Taluk Hospital", "short": "Belthangady TH",
     "lat": 12.988388, "lon": 75.275877, "taluk": "Belthangady", "ownership": "government",
     "osm_type": "node", "osm_id": 7202935866},
    {"id": "sdm_ujire", "name": "SDM Hospital Ujire", "short": "SDM Ujire",
     "lat": 12.994598, "lon": 75.332131, "taluk": "Belthangady", "ownership": "private",
     "osm_type": "way", "osm_id": 1029706100},
    {"id": "ashwini_nellyady", "name": "Ashwini Hospital Nellyady", "short": "Ashwini Nellyady",
     "lat": 12.830770, "lon": 75.413230, "taluk": "Kadaba", "ownership": "private",
     "osm_type": "node", "osm_id": 6938544863},
    {"id": "shastri_kadaba", "name": "Shastri Hospital Kadaba", "short": "Shastri Kadaba",
     "lat": 12.743540, "lon": 75.471006, "taluk": "Kadaba", "ownership": "private",
     "osm_type": "node", "osm_id": 7562741471},
    {"id": "sullia_th", "name": "Sullia Taluk Government Hospital", "short": "Sullia TH",
     "lat": 12.562293, "lon": 75.389772, "taluk": "Sullia", "ownership": "government",
     "osm_type": "node", "osm_id": 7202979523},
    {"id": "subrahmanya_gh", "name": "Subrahmanya Government Hospital", "short": "Subrahmanya GH",
     "lat": 12.677804, "lon": 75.599911, "taluk": "Sullia", "ownership": "government",
     "osm_type": "node", "osm_id": 7202723959},
]


# District-spread demand points used to test dispatch coverage. These are scenario
# locations, not claims that a real emergency occurred at the coordinate.
INCIDENTS = [
    {"id": "mangaluru", "name": "Mangaluru", "lat": 12.8698, "lon": 74.8431, "kind": "scenario_point"},
    {"id": "kulur", "name": "Kulur", "lat": 12.9250, "lon": 74.8270, "kind": "scenario_point"},
    {"id": "ullal", "name": "Ullal", "lat": 12.8050, "lon": 74.8600, "kind": "scenario_point"},
    {"id": "mulki", "name": "Mulki", "lat": 13.0910, "lon": 74.7930, "kind": "scenario_point"},
    {"id": "moodbidri", "name": "Moodbidri", "lat": 13.0660, "lon": 74.9950, "kind": "scenario_point"},
    {"id": "bantwal", "name": "Bantwal", "lat": 12.8900, "lon": 75.0350, "kind": "scenario_point"},
    {"id": "vitla", "name": "Vitla", "lat": 12.7600, "lon": 75.1200, "kind": "scenario_point"},
    {"id": "puttur", "name": "Puttur", "lat": 12.7690, "lon": 75.2070, "kind": "scenario_point"},
    {"id": "belthangady", "name": "Belthangady", "lat": 12.9900, "lon": 75.3000, "kind": "scenario_point"},
    {"id": "uppinangady", "name": "Uppinangady", "lat": 12.8370, "lon": 75.2470, "kind": "scenario_point"},
    {"id": "kadaba", "name": "Kadaba", "lat": 12.7130, "lon": 75.4700, "kind": "scenario_point"},
    {"id": "sullia", "name": "Sullia", "lat": 12.5580, "lon": 75.3900, "kind": "scenario_point"},
    {"id": "subrahmanya", "name": "Subrahmanya", "lat": 12.6680, "lon": 75.6150, "kind": "scenario_point"},
]


# The 9-qubit QAOA experiment remains a deliberately small, reproducible 3x3
# subproblem. District-wide dispatch is classical and uses every facility above.
QUANTUM_HOSPITAL_IDS = ["wenlock", "puttur_gh", "sullia_th"]
QUANTUM_INCIDENT_IDS = ["mulki", "belthangady", "subrahmanya"]

# Representative rainfall sampling sites spanning the coast, central valley and
# Western Ghats. The live district trigger uses the maximum site trigger as a
# conservative operational summary and returns every site value to the UI/API.
TRIGGER_SITES = [
    {"id": "mangaluru", "name": "Mangaluru coast", "lat": 12.8698, "lon": 74.8431},
    {"id": "moodbidri", "name": "Moodbidri north", "lat": 13.0660, "lon": 74.9950},
    {"id": "bantwal", "name": "Bantwal Nethravathi", "lat": 12.8900, "lon": 75.0350},
    {"id": "puttur", "name": "Puttur interior", "lat": 12.7690, "lon": 75.2070},
    {"id": "sullia", "name": "Sullia Ghats", "lat": 12.5580, "lon": 75.3900},
]


def by_id(rows):
    return {row["id"]: row for row in rows}
