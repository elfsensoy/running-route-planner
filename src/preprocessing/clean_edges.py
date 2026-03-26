import pandas as pd
from pathlib import Path
import numpy as np

# Proje root
BASE_DIR = Path(__file__).resolve().parents[2]

# Dosya yolları
INPUT_FILE = BASE_DIR / "data" / "processed" / "fatih_edges_enriched.csv"
OUTPUT_FILE = BASE_DIR / "data" / "processed" / "fatih_edges_clean.csv"

# Dosyayı oku
edges = pd.read_csv(INPUT_FILE)

# 2) Sayısal kolonları garantiye al
numeric_cols = ["length", "u_elevation", "v_elevation", "elevation_dif", "slope", "abs_slope"]
for col in numeric_cols:
    edges[col] = pd.to_numeric(edges[col], errors="coerce")

# 5) Running-friendly road type işareti
runner_friendly = ["footway", "path", "pedestrian", "residential", "living_street", "track"]

def check_runner_friendly(val):
    if pd.isna(val):
        return False
    val = str(val).lower()
    return any(rt in val for rt in runner_friendly)

edges["is_runner_friendly"] = edges["highway"].apply(check_runner_friendly)

# 8) Kaydet
edges.to_csv(OUTPUT_FILE, index=False)

print(f"Bitti. Dosya kaydedildi: {OUTPUT_FILE}")
print("Toplam edge sayısı:", len(edges))
print("Runner-friendly edge sayısı:", edges["is_runner_friendly"].sum())
print("Kolonlar:")
print(edges.columns.tolist())
