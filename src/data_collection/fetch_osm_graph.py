import os
import osmnx as ox

PLACE_NAME = "Fatih, Istanbul, Turkey"
OUTPUT_PATH = "data/raw/fatih_walk.graphml"


def main():
    print(f"Downloading walking graph for: {PLACE_NAME}")

    # Fatih için walking graph çek
    G = ox.graph_from_place(PLACE_NAME, network_type="walk")

    # data/raw klasörü garanti olsun
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    # graph kaydet
    ox.save_graphml(G, OUTPUT_PATH)

    print("Download completed.")
    print(f"Saved to: {OUTPUT_PATH}")
    print(f"Number of nodes: {len(G.nodes)}")
    print(f"Number of edges: {len(G.edges)}")


if __name__ == "__main__":
    main()