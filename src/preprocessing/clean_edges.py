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

# 1) Sadece gerekli kolonları bırak
keep_cols = [
    "u", "v", "length", "geometry", "highway", "name",
    "oneway", "bridge", "tunnel", "access",
    "u_elevation", "v_elevation", "elevation_gain", "slope", "abs_slope"
]

edges = edges[keep_cols].copy()

# 2) Sayısal kolonları garantiye al
numeric_cols = ["length", "u_elevation", "v_elevation", "elevation_gain", "slope", "abs_slope"]
for col in numeric_cols:
    edges[col] = pd.to_numeric(edges[col], errors="coerce")

# 3) Çok kısa edge işareti
edges["is_too_short"] = edges["length"] < 5

# 4) Aşırı dik edge işareti
edges["is_steep_outlier"] = edges["abs_slope"] > 0.25

# 5) Running-friendly road type işareti
runner_friendly = ["footway", "path", "pedestrian", "residential", "living_street", "track"]

def check_runner_friendly(val):
    if pd.isna(val):
        return False
    val = str(val).lower()
    return any(rt in val for rt in runner_friendly)

edges["is_runner_friendly"] = edges["highway"].apply(check_runner_friendly)

# 6) Kullanışlı slope kolonu üret
# çok kısa edge ise slope'u NaN yapabiliriz
edges["clean_slope"] = np.where(edges["is_too_short"], np.nan, edges["slope"])

# 7) İstersen absolute clean slope da ekle
edges["clean_abs_slope"] = edges["clean_slope"].abs()

# 8) Kaydet
edges.to_csv(OUTPUT_FILE, index=False)

print(f"Bitti. Dosya kaydedildi: {OUTPUT_FILE}")
print("Toplam edge sayısı:", len(edges))
print("Çok kısa edge sayısı:", edges["is_too_short"].sum())
print("Dik outlier sayısı:", edges["is_steep_outlier"].sum())
print("Runner-friendly edge sayısı:", edges["is_runner_friendly"].sum())
