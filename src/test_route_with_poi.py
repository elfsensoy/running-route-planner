import networkx as nx
import pandas as pd

# Dosya yolları
graph_path = "data/raw/fatih_walk.graphml"
poi_path = "data/processed/fatih_pois_manual_mapped.csv"

# Graph'i yükle
print("Graph yükleniyor...")
G = nx.read_graphml(graph_path)
print("Graph yüklendi.")

# Edge length'leri float yap
for u, v, data in G.edges(data=True):
    if "length" in data:
        data["length"] = float(data["length"])

# POI dosyasını yükle
pois = pd.read_csv(poi_path)
print("POI dosyası yüklendi.")

# Başlangıç node'u seç
start_node = "4078371620"

# İlk POI'yi seç
selected_poi = pois.iloc[2]   # örnek: Gülhane Parkı
poi_name = selected_poi["name"]
poi_node = str(selected_poi["mapped_node_id"])

print(f"\nBaşlangıç node: {start_node}")
print(f"Seçilen POI: {poi_name}")
print(f"POI node: {poi_node}")

# Start -> POI path
path_to_poi = nx.shortest_path(G, source=start_node, target=poi_node, weight="length")

# POI -> Start path
path_back = nx.shortest_path(G, source=poi_node, target=start_node, weight="length")

# Loop route oluştur
full_route = path_to_poi + path_back[1:]

print("\nRoute bulundu.")
print("Gidilen node sayısı:", len(full_route))


def compute_path_length(graph, path):
    total = 0.0
    for i in range(len(path) - 1):
        u = path[i]
        v = path[i + 1]
        edge_data = graph.get_edge_data(u, v)

        if edge_data and "length" in edge_data:
            total += edge_data["length"]
        else:
            print(f"UYARI: {u} -> {v} edge'inde length yok")

    return total


total_length = compute_path_length(G, full_route)

print(f"Toplam rota uzunluğu: {total_length:.2f} metre")
print("\nİlk 20 node:")
print(full_route[:20])