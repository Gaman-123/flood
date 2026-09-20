import ee

KEY_PATH = ".secrets/ee-service-account.json"
SERVICE_ACCOUNT = "flood-pipeline@gen-lang-client-0909626996.iam.gserviceaccount.com"


def main():
    credentials = ee.ServiceAccountCredentials(SERVICE_ACCOUNT, KEY_PATH)
    ee.Initialize(credentials, project="gen-lang-client-0909626996")

    aoi = ee.Geometry.Point([74.856, 12.914])  # Mangaluru
    collection = (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterBounds(aoi)
        .filterDate("2025-07-01", "2025-07-31")
        .filter(ee.Filter.eq("instrumentMode", "IW"))
    )
    count = collection.size().getInfo()
    print(f"Sentinel-1 IW scenes over Mangaluru in July 2025: {count}")

    first = collection.first()
    info = first.getInfo()
    print("Sample scene ID:", info["id"])
    print("Sample scene date:", info["properties"]["system:time_start"])


if __name__ == "__main__":
    main()
