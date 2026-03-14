import os
import pandas as pd

INPUT_PATH = "data/processed/fatih_pois_clean.csv"
OUTPUT_PATH = "data/processed/fatih_pois_filtered.csv"


def map_poi_group(category: str):
    if pd.isna(category):
        return None

    category = str(category).strip()

    # 1) viewpoint / attraction
    if category in {"tourism:viewpoint", "tourism:attraction"}:
        return "viewpoint_attraction"

    # 2) museum + historic
    if category == "tourism:museum" or category.startswith("historic:"):
        return "museum_historic"

    # 3) park + garden
    if category in {"leisure:park", "leisure:garden"}:
        return "park_garden"

    # 4) yemek
    if category in {"amenity:cafe", "amenity:restaurant"}:
        return "food"

    return None


def keep_row(row):
    category = row["poi_category"]
    name = str(row["name"]).strip()

    poi_group = map_poi_group(category)
    if poi_group is None:
        return False

    # Unnamed POI ise sadece historic olanları tut
    if name == "Unnamed POI":
        if str(category).startswith("historic:"):
            return True
        return False

    return True


def main():
    print(f"Loading POIs from: {INPUT_PATH}")
    df = pd.read_csv(INPUT_PATH)

    # satır filtresi
    filtered = df[df.apply(keep_row, axis=1)].copy()

    # grup kolonu ekle
    filtered["poi_group"] = filtered["poi_category"].apply(map_poi_group)

    # kolon sırası düzenle
    preferred_cols = [
        "poi_id",
        "name",
        "lat",
        "lon",
        "poi_group",
        "poi_category",
        "amenity",
        "tourism",
        "historic",
        "leisure",
        "geometry",
    ]
    existing_cols = [col for col in preferred_cols if col in filtered.columns]
    filtered = filtered[existing_cols]

    # sıralama
    filtered = filtered.sort_values(by=["poi_group", "poi_category", "name"]).reset_index(drop=True)

    os.makedirs("data/processed", exist_ok=True)
    filtered.to_csv(OUTPUT_PATH, index=False)

    print("POI filtering completed.")
    print(f"Saved to: {OUTPUT_PATH}")
    print(f"Shape: {filtered.shape}")

    print("\nPOI group counts:")
    print(filtered["poi_group"].value_counts())

    print("\nPOI category counts:")
    print(filtered["poi_category"].value_counts())

    print("\nSample rows:")
    print(filtered.head(15))


if __name__ == "__main__":
    main()