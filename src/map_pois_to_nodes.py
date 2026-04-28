import networkx as nx
import pandas as pd
import math


def euclidean_distance(lat1, lon1, lat2, lon2):
    """Basit yakınlık hesabı. Şimdilik yeterli."""
    return math.sqrt((lat1 - lat2) ** 2 + (lon1 - lon2) ** 2)


# 1) Graph'i yükle
graph_path = "data/raw/fatih_walk.graphml"
print("Graph yükleniyor...")
G = nx.read_graphml(graph_path)
print("Graph yüklendi.")

# 2) POI dosyasını yükle
poi_path = "data/processed/fatih_pois_manual.csv"
pois = pd.read_csv(poi_path)
print("POI dosyası yüklendi.")

# 3) Node koordinatlarını hazırla
node_list = []
for node_id, data in G.nodes(data=True):
    if "y" in data and "x" in data:
        lat = float(data["y"])
        lon = float(data["x"])
        node_list.append((node_id, lat, lon))

print(f"Toplam kullanılabilir node: {len(node_list)}")

# 4) Her POI için en yakın node'u bul
mapped_nodes = []

for _, row in pois.iterrows():
    poi_lat = float(row["lat"])
    poi_lon = float(row["lon"])

    best_node = None
    best_dist = float("inf")

    for node_id, node_lat, node_lon in node_list:
        dist = euclidean_distance(poi_lat, poi_lon, node_lat, node_lon)

        if dist < best_dist:
            best_dist = dist
            best_node = node_id

    mapped_nodes.append(best_node)

# 5) Sonucu tabloya ekle
pois["mapped_node_id"] = mapped_nodes

# 6) Yeni dosya olarak kaydet
output_path = "data/processed/fatih_pois_manual_mapped.csv"
pois.to_csv(output_path, index=False)

print(f"Eşleştirme tamamlandı. Dosya kaydedildi: {output_path}")
print("\nİlk 5 satır:")
print(pois.head())
