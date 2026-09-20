"""Write a reproducible audit of the curated district hospital routing origins.

This is a data-integrity audit, not a capability certification. It verifies that
the curated records are unique, have traceable OSM element IDs, fall inside the
cached district polygon, and cover all nine taluks. Ambulance availability and
emergency-service capability still require confirmation with district authorities.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from floodrisk import config, locations  # noqa: E402

OUT = "data/processed/hospital_audit.json"


def main():
    from shapely.geometry import Point, shape
    from shapely.ops import unary_union

    boundary = json.load(open(config.DISTRICT_BOUNDARY_PATH))
    geom = unary_union([shape(f["geometry"]) for f in boundary["features"]])
    rows = []
    for h in locations.HOSPITALS:
        inside = geom.covers(Point(h["lon"], h["lat"]))
        rows.append({**h, "inside_district": inside})

    ids = [h["id"] for h in rows]
    osm = [(h["osm_type"], h["osm_id"]) for h in rows]
    summary = {
        "as_of": "2026-09-11",
        "source": "OpenStreetMap amenity=hospital objects, manually deduplicated and screened",
        "official_context": [
            "https://dkhfw.in/govt-hospitals-list/",
            "https://hfwcom.karnataka.gov.in/storage/pdf-files/GroupDVacancyList.pdf",
        ],
        "caveat": ("Routing-origin inclusion does not verify present ambulance availability, "
                   "emergency-department status, bed capacity, or official empanelment."),
        "count": len(rows),
        "taluks": sorted({h["taluk"] for h in rows}),
        "all_inside_district": all(h["inside_district"] for h in rows),
        "unique_ids": len(ids) == len(set(ids)),
        "unique_osm_elements": len(osm) == len(set(osm)),
        "facilities": rows,
    }
    if not all((summary["all_inside_district"], summary["unique_ids"],
                summary["unique_osm_elements"], len(summary["taluks"]) == 9)):
        raise SystemExit("hospital audit failed")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(summary, open(OUT, "w"), indent=2)
    print(f">> {len(rows)} audited routing origins across {len(summary['taluks'])} taluks")
    print(f">> Saved: {OUT}")


if __name__ == "__main__":
    main()
