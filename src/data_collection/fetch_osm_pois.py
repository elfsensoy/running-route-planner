import os
import osmnx as ox
import pandas as pd

PLACE_NAME = "Fatih, Istanbul, Turkey"
OUTPUT_PATH = "data/raw/fatih_pois.csv"

# Çekmek istediğimiz OSM tag'leri
TAGS = {
    "tourism": True,
    "historic": True,
    "leisure": True,
    "amenity": True,
}


def main():
    print(f"Downloading POIs for: {PLACE_NAME}")
    print(f"Using tags: {TAGS}")

    # Fatih için ilgili POI'leri çek
    pois_gdf = ox.features_from_place(PLACE_NAME, TAGS)

    # Klasör garanti olsun
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    # GeoDataFrame'i normal DataFrame gibi kaydetmeden önce kopyala
    pois_df = pois_gdf.copy()

    # geometry kolonunu stringe çevir ki csv'de saklansın
    if "geometry" in pois_df.columns:
        pois_df["geometry"] = pois_df["geometry"].astype(str)

    pois_df.to_csv(OUTPUT_PATH, index=True)

    print("POI download completed.")
    print(f"Saved to: {OUTPUT_PATH}")
    print(f"Shape: {pois_df.shape}")
    print("Columns:")
    print(list(pois_df.columns))


if __name__ == "__main__":
    main()