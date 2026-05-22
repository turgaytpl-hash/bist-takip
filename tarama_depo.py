"""
tarama_depo.py — Tarama Sinyal Kayıt ve Performans Takip Sistemi
"""

import pandas as pd
from pathlib import Path
from datetime import date, datetime

DATA_DIR  = Path("data")
SINYAL_DB = DATA_DIR / "tarama_sinyaller.parquet"
DATA_DIR.mkdir(exist_ok=True)

TARAMALAR = [
    "Altın Tavuk",
    "20 Reverse",
    "Minervini",
    "Haftalık MACD",
    "Qullamaggie",
]

# ─── Yükle / Kaydet ──────────────────────────────────────────────────────────
def _yukle() -> pd.DataFrame:
    if SINYAL_DB.exists():
        df = pd.read_parquet(SINYAL_DB)
        # Sadece aktif taramaların kayıtları
        return df[df["tarama"].isin(TARAMALAR)].reset_index(drop=True)
    return pd.DataFrame(columns=[
        "id", "tarama", "tarih", "hisse", "giris_fiyat"
    ])

def _kaydet(df: pd.DataFrame):
    # Tüm DB'yi yükle (eski kayıtlarla birleştir)
    if SINYAL_DB.exists():
        mevcut_tum = pd.read_parquet(SINYAL_DB)
    else:
        mevcut_tum = pd.DataFrame()
    
    # Aktif taramaların yeni halini, diğerlerini olduğu gibi sakla
    diger = mevcut_tum[~mevcut_tum["tarama"].isin(TARAMALAR)] if not mevcut_tum.empty else pd.DataFrame()
    birlesik = pd.concat([diger, df], ignore_index=True)
    birlesik.to_parquet(SINYAL_DB, index=False)

# ─── Sinyal Kaydet ───────────────────────────────────────────────────────────
def sinyal_kaydet(tarama: str, hisseler: list) -> int:
    """
    hisseler: [{"hisse": "THYAO", "giris_fiyat": 120.5}, ...]
    Returns: kaç kayıt eklendi
    """
    mevcut = _yukle()
    bugun  = date.today().strftime("%Y-%m-%d")

    # Aynı gün aynı tarama varsa üzerine yaz
    mevcut = mevcut[~((mevcut["tarama"] == tarama) & (mevcut["tarih"] == bugun))]

    yeni = []
    for h in hisseler:
        yeni.append({
            "id":          f"{tarama}_{bugun}_{h['hisse']}",
            "tarama":      tarama,
            "tarih":       bugun,
            "hisse":       h["hisse"],
            "giris_fiyat": h.get("giris_fiyat"),
        })

    if yeni:
        df_yeni  = pd.DataFrame(yeni)
        birlesik = pd.concat([mevcut, df_yeni], ignore_index=True)
        _kaydet(birlesik)

    return len(yeni)

# ─── Performans Hesapla ───────────────────────────────────────────────────────
def performans_hesapla(guncel_fiyatlar: dict) -> pd.DataFrame:
    """
    guncel_fiyatlar: {"THYAO": 125.3, ...}
    Sadece fiyat günceller — tarama YAPILMAZ
    """
    db = _yukle()
    if db.empty:
        return pd.DataFrame()

    satirlar = []
    bugun = date.today().strftime("%Y-%m-%d")

    for _, row in db.iterrows():
        hisse  = row["hisse"]
        giris  = row["giris_fiyat"]
        guncel = guncel_fiyatlar.get(hisse)

        if giris and guncel and float(giris) > 0:
            degisim = round((float(guncel) / float(giris) - 1) * 100, 2)
        else:
            degisim = None

        try:
            giris_tarihi = datetime.strptime(row["tarih"], "%Y-%m-%d").date()
            gun_fark     = (date.today() - giris_tarihi).days
        except:
            gun_fark = None

        satirlar.append({
            "Tarama":       row["tarama"],
            "Giriş Tarihi": row["tarih"],
            "Hisse":        hisse,
            "Giriş Fiyatı": giris,
            "Güncel Tarih": bugun,
            "Güncel Fiyat": guncel,
            "Değişim%":     degisim,
            "Gün":          gun_fark,
        })

    df = pd.DataFrame(satirlar)
    if df.empty:
        return df

    df = df.sort_values(["Tarama","Değişim%"], ascending=[True, False])
    return df.reset_index(drop=True)

# ─── Tarama Özet ─────────────────────────────────────────────────────────────
def tarama_ozet() -> pd.DataFrame:
    db = _yukle()
    if db.empty:
        return pd.DataFrame()
    return db.groupby("tarama").agg(
        Sinyal=("hisse", "count"),
        Son_Tarih=("tarih", "max"),
        Hisse=("hisse", "nunique")
    ).reset_index()

# ─── Son Sinyaller ────────────────────────────────────────────────────────────
def son_sinyaller(tarama: str = None, son_n_gun: int = 90) -> pd.DataFrame:
    db = _yukle()
    if db.empty:
        return pd.DataFrame()
    sinir = (date.today() - pd.Timedelta(days=son_n_gun)).strftime("%Y-%m-%d")
    db    = db[db["tarih"] >= sinir]
    if tarama:
        db = db[db["tarama"] == tarama]
    return db.sort_values("tarih", ascending=False).reset_index(drop=True)

# ─── DB Özet ─────────────────────────────────────────────────────────────────
def db_ozet() -> dict:
    db = _yukle()
    if db.empty:
        return {"toplam": 0, "tarama_sayisi": 0, "son_tarih": "—", "hisse_sayisi": 0}
    return {
        "toplam":        len(db),
        "tarama_sayisi": db["tarama"].nunique(),
        "son_tarih":     db["tarih"].max(),
        "hisse_sayisi":  db["hisse"].nunique(),
    }
