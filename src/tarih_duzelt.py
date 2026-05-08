"""
Mevcut parquet dosyalarındaki DD.MM.YYYY tarihlerini YYYY-MM-DD formatına çevirir.
Bir kez çalıştır, sonra sil.
"""
from pathlib import Path
import pandas as pd
from datetime import datetime

DATA_DIR = Path("data/bebek_hisse")

if not DATA_DIR.exists():
    print("data/bebek_hisse klasörü bulunamadı.")
    exit()

for p in DATA_DIR.glob("*.parquet"):
    try:
        df = pd.read_parquet(p)
        if "donem" not in df.columns:
            continue

        def donustur(d):
            d = str(d).strip()
            if "." in d:
                try:
                    return datetime.strptime(d, "%d.%m.%Y").strftime("%Y-%m-%d")
                except:
                    return d
            return d

        onceki = df["donem"].unique().tolist()
        df["donem"] = df["donem"].apply(donustur)
        sonraki = df["donem"].unique().tolist()

        df.to_parquet(p, index=False)
        print(f"✅ {p.name}: {onceki} → {sonraki}")
    except Exception as e:
        print(f"❌ {p.name}: {e}")

print("\nBitti. Bu dosyayı silebilirsin.")
