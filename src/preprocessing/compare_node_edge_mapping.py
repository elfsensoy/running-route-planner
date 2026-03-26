from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[2]

NODE_PATH = BASE_DIR / "data" / "processed" / "fatih_pois_mapped_nearest.csv"
EDGE_PATH = BASE_DIR / "data" / "processed" / "fatih_pois_edge_mapped.csv"


def main():
    node_df = pd.read_csv(NODE_PATH)
    edge_df = pd.read_csv(EDGE_PATH)

    print("NODE DISTANCE SUMMARY")
    print(node_df["distance_to_node_m"].describe())
    print()

    print("EDGE DISTANCE SUMMARY")
    print(edge_df["distance_to_edge_m"].describe())
    print()

    print("Node > 25m:", (node_df["distance_to_node_m"] > 25).sum())
    print("Edge > 25m:", (edge_df["distance_to_edge_m"] > 25).sum())
    print()

    print("Node > 30m:", (node_df["distance_to_node_m"] > 30).sum())
    print("Edge > 30m:", (edge_df["distance_to_edge_m"] > 30).sum())
    print()

    comparison_df = node_df[["poi_id", "name", "poi_group", "distance_to_node_m"]].merge(
        edge_df[["poi_id", "distance_to_edge_m"]],
        on="poi_id",
        how="inner"
    )

    comparison_df["improvement_m"] = (
        comparison_df["distance_to_node_m"] - comparison_df["distance_to_edge_m"]
    )

    print("Ortalama iyileşme (m):", comparison_df["improvement_m"].mean())
    print("Medyan iyileşme (m):", comparison_df["improvement_m"].median())
    print()

    print("En çok iyileşen ilk 20 kayıt:")
    print(
        comparison_df.sort_values("improvement_m", ascending=False)
        .head(20)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()