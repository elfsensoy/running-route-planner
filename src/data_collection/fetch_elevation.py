import pandas as pd
import requests
import time
import os
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")
from pathlib import Path

# Proje root'unu bul
BASE_DIR = Path(__file__).resolve().parents[2]

# Dosya yolları
INPUT_FILE = BASE_DIR / "data" / "processed" / "fatih_nodes.csv"
OUTPUT_FILE = BASE_DIR / "data" / "processed" / "fatih_node_elevation.csv"

# Nodes dosyasını oku
nodes = pd.read_csv(INPUT_FILE)

# Sadece gerekli kolonları al
nodes = nodes[["osmid", "y", "x"]].copy()

def get_elevation_batch(coords):
    locations = "|".join([f"{lat},{lon}" for lat, lon in coords])
    url = f"https://maps.googleapis.com/maps/api/elevation/json?locations={locations}&key={API_KEY}"

    response = requests.get(url)
    data = response.json()

    if response.status_code == 200 and data.get("status") == "OK":
        return [r["elevation"] for r in data["results"]]
    else:
        print("API hatası:", data)
        return [None] * len(coords)

batch_size = 100
all_elevations = []

for i in range(0, len(nodes), batch_size):
    batch = nodes.iloc[i:i + batch_size]
    coords = list(zip(batch["y"], batch["x"]))  # lat, lon

    elevations = get_elevation_batch(coords)
    all_elevations.extend(elevations)

    print(f"{i} - {min(i + batch_size, len(nodes))} işlendi")
    time.sleep(0.2)

nodes["elevation"] = all_elevations

nodes.to_csv(OUTPUT_FILE, index=False)

print(f"Bitti. Dosya kaydedildi: {OUTPUT_FILE}")