import networkx as nx

graph_path = "data/raw/fatih_walk.graphml"

print("Graph yükleniyor...")
G = nx.read_graphml(graph_path)
print("Yüklendi.")

print(f"Node sayısı: {G.number_of_nodes()}")
print(f"Edge sayısı: {G.number_of_edges()}")

# Edge length değerlerini float'a çevir
for u, v, data in G.edges(data=True):
    if "length" in data:
        data["length"] = float(data["length"])

# Node listesini al
nodes = list(G.nodes())

# Test için iki node seç
start_node = nodes[0]
end_node = nodes[50]

print(f"\nStart node: {start_node}")
print(f"End node: {end_node}")

# Shortest path bul
path = nx.shortest_path(G, source=start_node, target=end_node, weight="length")

print("\nPath bulundu.")
print("Path:", path)
print("Path üzerindeki node sayısı:", len(path))

total_length = 0.0

for i in range(len(path) - 1):
    u = path[i]
    v = path[i + 1]

    edge_data = G.get_edge_data(u, v)

    if edge_data and "length" in edge_data:
        total_length += edge_data["length"]
    else:
        print(f"UYARI: {u} -> {v} edge'inde length yok")