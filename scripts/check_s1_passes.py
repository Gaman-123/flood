"""Check Sentinel-1 pass availability around documented Dakshina Kannada flood events."""
import ee
from datetime import datetime, timezone, timedelta

KEY_PATH = ".secrets/ee-service-account.json"
SERVICE_ACCOUNT = "flood-pipeline@gen-lang-client-0909626996.iam.gserviceaccount.com"

# Dakshina Kannada district bounding box (approx): lon 74.65-75.4, lat 12.65-13.15
DK_BBOX_COORDS = [74.65, 12.65, 75.40, 13.15]

EVENTS = [
    ("May 2025 Mangaluru urban flood", "2025-05-24", "2025-06-05"),
    ("Aug 2024 Nethravathi river flood", "2024-07-26", "2024-08-08"),
    # extra context: broader 2024 & 2025 monsoon windows to see revisit cadence
]

IST = timezone(timedelta(hours=5, minutes=30))


def fmt(ms):
    dt_utc = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    dt_ist = dt_utc.astimezone(IST)
    return dt_utc.strftime("%Y-%m-%d %H:%M UTC") + " / " + dt_ist.strftime("%Y-%m-%d %H:%M IST")


def main():
    creds = ee.ServiceAccountCredentials(SERVICE_ACCOUNT, KEY_PATH)
    ee.Initialize(creds, project="gen-lang-client-0909626996")

    dk_bbox = ee.Geometry.Rectangle(DK_BBOX_COORDS)

    for name, start, end in EVENTS:
        col = (
            ee.ImageCollection("COPERNICUS/S1_GRD")
            .filterBounds(dk_bbox)
            .filterDate(start, end)
            .filter(ee.Filter.eq("instrumentMode", "IW"))
        )
        feats = col.toList(50).getInfo()
        print(f"\n=== {name}  (window {start} to {end}) ===")
        print(f"Scenes covering Dakshina Kannada: {len(feats)}")
        for f in feats:
            p = f["properties"]
            print(
                f"  {fmt(p['system:time_start'])} | "
                f"orbit={p.get('orbitProperties_pass'):9s} | "
                f"relOrbit={p.get('relativeOrbitNumber_start')} | "
                f"pol={p.get('transmitterReceiverPolarisation')} | "
                f"platform={p.get('platform_number')}"
            )


if __name__ == "__main__":
    main()
