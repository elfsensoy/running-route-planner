from pathlib import Path
import pandas as pd
import osmnx as ox


BASE_DIR = Path(__file__).resolve().parents[2]

GRAPH_PATH = BASE_DIR / "data" / "raw" / "fatih_walk.graphml"
POIS_PATH = BASE_DIR / "data" / "processed" / "fatih_pois_filtered.csv"
OUTPUT_PATH = BASE_DIR / "data" / "processed" / "fatih_pois_mapped.csv"


def main():
    pois_df = pd.read_csv(POIS_PATH)

    required_poi_cols = {"poi_id", "lat", "lon"}
    missing_poi = required_poi_cols - set(pois_df.columns)
    if missing_poi:
        raise ValueError(f"POI dosyasında eksik kolon(lar) var: {missing_poi}")

    print("Graph yükleniyor...")
    G = ox.load_graphml(GRAPH_PATH)

    print("En yakın node'lar bulunuyor...")
    mapped_node_ids, distances = ox.distance.nearest_nodes(
        G,
        X=pois_df["lon"].to_list(),
        Y=pois_df["lat"].to_list(),
        return_dist=True
    )

    pois_df["mapped_node_id"] = mapped_node_ids
    pois_df["distance_to_node_m"] = distances

    # Graph node koordinatlarını da ekleyelim
    nodes_gdf, _ = ox.graph_to_gdfs(G)
    nodes_lookup = nodes_gdf[["x", "y"]].copy()
    nodes_lookup["mapped_node_id"] = nodes_lookup.index

    pois_df = pois_df.merge(
        nodes_lookup,
        on="mapped_node_id",
        how="left"
    )

    pois_df = pois_df.rename(
        columns={
            "x": "mapped_node_lon",
            "y": "mapped_node_lat"
        }
    )

    pois_df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8")
    print(f"Mapped POI dosyası kaydedildi: {OUTPUT_PATH}")
    print(f"Toplam mapped POI sayısı: {len(pois_df)}")


if __name__ == "__main__":
    main()