"""Measure true Sentinel-1 revisit cadence over Dakshina Kannada across a monsoon season."""
import ee
from datetime import datetime, timezone, timedelta

KEY_PATH = ".secrets/ee-service-account.json"
SERVICE_ACCOUNT = "flood-pipeline@gen-lang-client-0909626996.iam.gserviceaccount.com"
DK_BBOX_COORDS = [74.65, 12.65, 75.40, 13.15]
IST = timezone(timedelta(hours=5, minutes=30))

# Full monsoon windows
WINDOWS = [
    ("Monsoon 2024", "2024-06-01", "2024-09-30"),
    ("Monsoon 2025", "2025-05-15", "2025-07-20"),
]


def main():
    creds = ee.ServiceAccountCredentials(SERVICE_ACCOUNT, KEY_PATH)
    ee.Initialize(creds, project="gen-lang-client-0909626996")
    dk = ee.Geometry.Rectangle(DK_BBOX_COORDS)

    for name, start, end in WINDOWS:
        col = (
            ee.ImageCollection("COPERNICUS/S1_GRD")
            .filterBounds(dk)
            .filterDate(start, end)
            .filter(ee.Filter.eq("instrumentMode", "IW"))
        )
        feats = col.toList(200).getInfo()
        rows = []
        for f in feats:
            p = f["properties"]
            dt = datetime.fromtimestamp(p["system:time_start"] / 1000, tz=timezone.utc).astimezone(IST)
            rows.append((dt, p.get("orbitProperties_pass"), p.get("relativeOrbitNumber_start"), p.get("platform_number")))
        rows.sort()
        print(f"\n=== {name} ({start} to {end}): {len(rows)} passes ===")
        prev = None
        for dt, opass, rel, plat in rows:
            gap = f"  (+{(dt - prev).days}d)" if prev else ""
            print(f"  {dt.strftime('%Y-%m-%d %H:%M IST')} | {opass:10s} | relOrbit={rel:>3} | S1{plat}{gap}")
            prev = dt


if __name__ == "__main__":
    main()
