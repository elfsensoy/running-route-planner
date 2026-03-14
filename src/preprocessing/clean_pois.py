import os
import pandas as pd
from shapely import wkt

INPUT_PATH = "data/raw/fatih_pois.csv"
OUTPUT_PATH = "data/processed/fatih_pois_clean.csv"


def extract_lat_lon(geometry_str):
    try:
        geom = wkt.loads(geometry_str)
        return geom.y, geom.x
    except Exception:
        return None, None


def determine_poi_category(row):
    if pd.notna(row.get("historic")):
        return f"historic:{row['historic']}"
    if pd.notna(row.get("tourism")):
        return f"tourism:{row['tourism']}"
    if pd.notna(row.get("leisure")):
        return f"leisure:{row['leisure']}"
    if pd.notna(row.get("amenity")):
        return f"amenity:{row['amenity']}"
    return "unknown"


def main():
    print(f"Loading raw POIs from: {INPUT_PATH}")
    df = pd.read_csv(INPUT_PATH)

    keep_cols = [
        "element",
        "id",
        "name",
        "geometry",
        "amenity",
        "tourism",
        "historic",
        "leisure",
    ]

    existing_cols = [col for col in keep_cols if col in df.columns]
    pois = df[existing_cols].copy()

    # lat/lon çıkar
    pois[["lat", "lon"]] = pois["geometry"].apply(
        lambda g: pd.Series(extract_lat_lon(g))
    )

    # kategori oluştur
    pois["poi_category"] = pois.apply(determine_poi_category, axis=1)

    # id adını netleştir
    pois.rename(columns={"id": "poi_id"}, inplace=True)

    # çok boş olanları temizle
    pois = pois.dropna(subset=["lat", "lon"])

    # name boşsa doldur
    if "name" in pois.columns:
        pois["name"] = pois["name"].fillna("Unnamed POI")
    else:
        pois["name"] = "Unnamed POI"

    # kolon sırası
    final_cols = [
        "poi_id",
        "name",
        "lat",
        "lon",
        "poi_category",
        "amenity",
        "tourism",
        "historic",
        "leisure",
        "geometry",
    ]

    final_cols = [col for col in final_cols if col in pois.columns]
    pois = pois[final_cols]

    os.makedirs("data/processed", exist_ok=True)
    pois.to_csv(OUTPUT_PATH, index=False)

    print("POI cleaning completed.")
    print(f"Saved to: {OUTPUT_PATH}")
    print(f"Shape: {pois.shape}")
    print("Columns:")
    print(list(pois.columns))
    print("\nSample categories:")
    print(pois["poi_category"].value_counts().head(20))


if __name__ == "__main__":
    main()