import pandas as pd
from pathlib import Path
import numpy as np

# Proje root'unu bul
BASE_DIR = Path(__file__).resolve().parents[2]

# Dosya yolları
EDGES_FILE = BASE_DIR / "data" / "processed" / "fatih_edges.csv"
ELEV_FILE = BASE_DIR / "data" / "processed" / "fatih_node_elevation.csv"
OUTPUT_FILE = BASE_DIR / "data" / "processed" / "fatih_edges_enriched.csv"

# Dosyaları oku
edges = pd.read_csv(EDGES_FILE)
elev = pd.read_csv(ELEV_FILE)

# Elevation tablosunda kolonları sadeleştir
elev_u = elev[["osmid", "elevation"]].copy()
elev_u.columns = ["u", "u_elevation"]

elev_v = elev[["osmid", "elevation"]].copy()
elev_v.columns = ["v", "v_elevation"]

# Edge tablosuna u ve v elevation eklemeleri: 
edges = edges.merge(elev_u, on="u", how="left")
edges = edges.merge(elev_v, on="v", how="left")

# Length kolonu sayısal olsun
edges["length"] = pd.to_numeric(edges["length"], errors="coerce")

# Elevation gain hesaplama
edges["elevation_gain"] = edges["v_elevation"] - edges["u_elevation"]

# Slope hesaplama
edges["slope"] = np.where(
    edges["length"] > 0,
    edges["elevation_gain"] / edges["length"],
    np.nan
)

# Absolute slope, may be useful for certain analyses
edges["abs_slope"] = edges["slope"].abs()

# Kaydet
edges.to_csv(OUTPUT_FILE, index=False)

print(f"Bitti. Dosya kaydedildi: {OUTPUT_FILE}")
