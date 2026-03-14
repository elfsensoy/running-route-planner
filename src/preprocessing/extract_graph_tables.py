import os
import osmnx as ox

INPUT_PATH = "data/raw/fatih_walk.graphml"
NODES_OUTPUT_PATH = "data/processed/fatih_nodes.csv"
EDGES_OUTPUT_PATH = "data/processed/fatih_edges.csv"


def main():
    print(f"Loading graph from: {INPUT_PATH}")

    G = ox.load_graphml(INPUT_PATH)

    nodes_gdf, edges_gdf = ox.graph_to_gdfs(G)

    os.makedirs("data/processed", exist_ok=True)

    nodes_gdf.to_csv(NODES_OUTPUT_PATH)
    edges_gdf.to_csv(EDGES_OUTPUT_PATH)

    print("Extraction completed.")
    print(f"Nodes saved to: {NODES_OUTPUT_PATH}")
    print(f"Edges saved to: {EDGES_OUTPUT_PATH}")
    print(f"Nodes shape: {nodes_gdf.shape}")
    print(f"Edges shape: {edges_gdf.shape}")


if __name__ == "__main__":
    main()