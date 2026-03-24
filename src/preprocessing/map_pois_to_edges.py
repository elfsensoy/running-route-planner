from pathlib import Path
import pandas as pd
import geopandas as gpd
import osmnx as ox


BASE_DIR = Path(__file__).resolve().parents[2]

GRAPH_PATH = BASE_DIR / "data" / "raw" / "fatih_walk.graphml"
POIS_PATH = BASE_DIR / "data" / "processed" / "fatih_pois_filtered.csv"
OUTPUT_PATH = BASE_DIR / "data" / "processed" / "fatih_pois_edge_mapped.csv"


def main():
    pois_df = pd.read_csv(POIS_PATH)

    required_poi_cols = {"poi_id", "lat", "lon"}
    missing_poi = required_poi_cols - set(pois_df.columns)
    if missing_poi:
        raise ValueError(f"POI dosyasında eksik kolon(lar) var: {missing_poi}")

    print("Graph yükleniyor...")
    G = ox.load_graphml(GRAPH_PATH)

    print("Graph project ediliyor...")
    G_proj = ox.project_graph(G)

    print("POI'ler GeoDataFrame'e çevriliyor...")
    pois_gdf = gpd.GeoDataFrame(
        pois_df.copy(),
        geometry=gpd.points_from_xy(pois_df["lon"], pois_df["lat"]),
        crs="EPSG:4326"
    )

    print("POI'ler graph CRS'ine project ediliyor...")
    pois_gdf = pois_gdf.to_crs(G_proj.graph["crs"])

    print("En yakın edge'ler bulunuyor...")
    nearest_edges, distances = ox.distance.nearest_edges(
        G_proj,
        X=pois_gdf.geometry.x.to_list(),
        Y=pois_gdf.geometry.y.to_list(),
        return_dist=True
    )

    u_list = []
    v_list = []
    key_list = []

    for u, v, k in nearest_edges:
        u_list.append(u)
        v_list.append(v)
        key_list.append(k)

    pois_df["nearest_edge_u"] = u_list
    pois_df["nearest_edge_v"] = v_list
    pois_df["nearest_edge_key"] = key_list
    pois_df["distance_to_edge_m"] = distances

    pois_df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8")

    print(f"Edge mapped POI dosyası kaydedildi: {OUTPUT_PATH}")
    print(f"Toplam POI sayısı: {len(pois_df)}")
    print("\nDistance to edge özeti:")
    print(pois_df["distance_to_edge_m"].describe())


if __name__ == "__main__":
    main()