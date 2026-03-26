from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[2]

EDGES_PATH = BASE_DIR / "data" / "processed" / "fatih_edges_clean.csv"
POIS_PATH = BASE_DIR / "data" / "processed" / "fatih_pois_edge_mapped.csv"
OUTPUT_PATH = BASE_DIR / "data" / "processed" / "fatih_edges_poi_enriched.csv"

EDGE_DISTANCE_THRESHOLD = 15  # meters


def main():
    edges_df = pd.read_csv(EDGES_PATH)
    pois_df = pd.read_csv(POIS_PATH)

    required_edge_cols = {"u", "v", "key"}
    required_poi_cols = {
        "nearest_edge_u",
        "nearest_edge_v",
        "nearest_edge_key",
        "poi_group",
        "distance_to_edge_m",
    }

    missing_edge = required_edge_cols - set(edges_df.columns)
    missing_poi = required_poi_cols - set(pois_df.columns)

    if missing_edge:
        raise ValueError(f"Edges dosyasında eksik kolon(lar): {missing_edge}")
    if missing_poi:
        raise ValueError(f"POI dosyasında eksik kolon(lar): {missing_poi}")

    # Threshold uygula
    filtered_pois = pois_df[pois_df["distance_to_edge_m"] <= EDGE_DISTANCE_THRESHOLD].copy()

    print(f"Total POIs: {len(pois_df)}")
    print(f"POIs within {EDGE_DISTANCE_THRESHOLD}m of edge: {len(filtered_pois)}")

    # Edge + poi_group bazında say
    grouped = (
        filtered_pois
        .groupby(
            ["nearest_edge_u", "nearest_edge_v", "nearest_edge_key", "poi_group"]
        )
        .size()
        .reset_index(name="count")
    )

    # Wide format
    poi_counts = (
        grouped
        .pivot_table(
            index=["nearest_edge_u", "nearest_edge_v", "nearest_edge_key"],
            columns="poi_group",
            values="count",
            fill_value=0
        )
        .reset_index()
    )

    poi_counts.columns.name = None

    expected_groups = [
        "food",
        "museum_historic",
        "park_garden",
        "viewpoint_attraction",
    ]

    for group in expected_groups:
        if group not in poi_counts.columns:
            poi_counts[group] = 0

    poi_counts = poi_counts.rename(columns={
        "nearest_edge_u": "u",
        "nearest_edge_v": "v",
        "nearest_edge_key": "key",
        "food": "food_count",
        "museum_historic": "museum_historic_count",
        "park_garden": "park_garden_count",
        "viewpoint_attraction": "viewpoint_attraction_count",
    })

    final_df = edges_df.merge(
        poi_counts,
        on=["u", "v", "key"],
        how="left"
    )

    count_cols = [
        "food_count",
        "museum_historic_count",
        "park_garden_count",
        "viewpoint_attraction_count",
    ]

    for col in count_cols:
        if col not in final_df.columns:
            final_df[col] = 0

    final_df[count_cols] = final_df[count_cols].fillna(0).astype(int)

    final_df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8")

    print(f"\nSaved: {OUTPUT_PATH}")
    print(f"Total edges: {len(final_df)}")
    print("\nPOI count column totals:")
    print(final_df[count_cols].sum())
    print("\nFirst 5 rows:")
    print(final_df[["u", "v", "key"] + count_cols].head())


if __name__ == "__main__":
    main()