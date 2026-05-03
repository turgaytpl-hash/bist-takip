"""
mkk_depo.py — MKK Oran Analizi veri katmanı.

Klasör yapısı:
  data/mkk/
    haftalik/  → parquet dosyaları (donem_tip.parquet)
    aylik/     → parquet dosyaları
"""

import pandas as pd
from pathlib import Path

BASE   = Path(__file__).parent.parent / "data" / "mkk"
HAF    = BASE / "haftalik"
AYL    = BASE / "aylik"


def _ensure():
    HAF.mkdir(parents=True, exist_ok=True)
    AYL.mkdir(parents=True, exist_ok=True)


def _parse_mkk(kaynak) -> pd.DataFrame:
    """
    MKK Excel dosyasını okur ve normalize eder.
    
    Kolon haritası:
      Col 0  → Hisse (Sembol)
      Col 4  → İlk Tarih Kurum Oran (E)
      Col 8  → Son Tarih Kurum Oran (I)
      Col 12 → Fark Kurum Oran (M)
    
    Hesaplar:
      pp_fark      = Col8 - Col4  (Son - İlk)
      kur_oran_fark = Col12       (Excel'deki hazır fark)
    """
    from io import BytesIO
    if hasattr(kaynak, "read"):
        data = BytesIO(kaynak.read())
        df_raw = pd.read_excel(data, header=None)
    else:
        df_raw = pd.read_excel(str(kaynak), header=None)

    df_raw.columns = [
        "hisse",
        "bir_lot_1", "bir_oran_1", "kur_lot_1", "kur_oran_1",
        "bir_lot_2", "bir_oran_2", "kur_lot_2", "kur_oran_2",
        "fark_bir_lot", "fark_bir_oran", "fark_kur_lot", "fark_kur_oran",
        "son_yat"
    ]

    # İlk 2 satır başlık — atla
    df = df_raw.iloc[2:].reset_index(drop=True).copy()

    def parse_num(x):
        if isinstance(x, str):
            return pd.to_numeric(x.strip().replace(",", "."), errors="coerce")
        return pd.to_numeric(x, errors="coerce")

    for col in df.columns[1:]:
        df[col] = df[col].apply(parse_num)

    # Endeks kodlarını filtrele
    endeks = ["XU030", "XU050", "XU100", "XUTUM", "XBANK", "XBANA"]
    df = df[~df["hisse"].isin(endeks)]
    df = df[df["kur_oran_1"].notna() & df["kur_oran_2"].notna()]
    df["hisse"] = df["hisse"].astype(str).str.strip().str.upper()

    # Hesaplamalar
    df["pp_fark"]       = (df["kur_oran_2"] - df["kur_oran_1"]).round(2)  # Col8 - Col4
    df["kur_oran_fark"] = df["fark_kur_oran"]                              # Col12 direkt

    return df[["hisse", "kur_oran_1", "kur_oran_2", "pp_fark", "kur_oran_fark"]].reset_index(drop=True)


def yukle(donem: str, tip: str, kaynak) -> tuple[bool, str]:
    """
    tip: 'haftalik' veya 'aylik'
    donem: '2026_04_05' (haftalık) veya '2026_04' (aylık)
    """
    _ensure()
    klasor = HAF if tip == "haftalik" else AYL
    path = klasor / f"{donem}.parquet"

    if path.exists():
        return False, f"⚠️ {donem} zaten kayıtlı."

    try:
        df = _parse_mkk(kaynak)
        if df.empty:
            return False, "❌ Dosyadan veri okunamadı."
        df["donem"] = donem
        df["tip"]   = tip
        df.to_parquet(path, index=False)
        return True, f"✅ {tip} MKK yüklendi: {donem} ({len(df)} hisse)"
    except Exception as e:
        return False, f"❌ Hata: {e}"


def sil(donem: str, tip: str) -> tuple[bool, str]:
    klasor = HAF if tip == "haftalik" else AYL
    path = klasor / f"{donem}.parquet"
    if path.exists():
        path.unlink()
        return True, f"🗑️ {donem} silindi"
    return False, f"⚠️ {donem} bulunamadı"


def donemler_listele(tip: str) -> list:
    klasor = HAF if tip == "haftalik" else AYL
    if not klasor.exists():
        return []
    return sorted([p.stem for p in klasor.glob("*.parquet")])


def veri_getir(donemler: list, tip: str) -> pd.DataFrame:
    """Seçili dönemleri birleştirip döndürür."""
    klasor = HAF if tip == "haftalik" else AYL
    parcalar = []
    for d in donemler:
        path = klasor / f"{d}.parquet"
        if path.exists():
            parcalar.append(pd.read_parquet(path))
    if not parcalar:
        return pd.DataFrame()
    return pd.concat(parcalar, ignore_index=True)


def pivot_olustur(donemler: list, tip: str, kolon: str = "pp_fark") -> pd.DataFrame:
    """
    kolon: 'pp_fark' (Col8-Col4) veya 'kur_oran_fark' (Col12)
    
    Döndürür: hisse × dönem pivot tablosu + KÜMÜLATİF + TREND
    """
    df = veri_getir(donemler, tip)
    if df.empty:
        return pd.DataFrame()

    pivot = df.pivot_table(
        index="hisse", columns="donem", values=kolon, aggfunc="last"
    ).reset_index()
    pivot.columns.name = None

    donem_cols = sorted([c for c in pivot.columns if c != "hisse"])
    pivot = pivot[["hisse"] + donem_cols]

    pivot["KÜMÜLATİF"] = pivot[donem_cols].sum(axis=1).round(2)

    def trend(row):
        vals = [row[c] for c in donem_cols if pd.notna(row[c])]
        if len(vals) < 2:
            return "—"
        son3 = vals[-3:] if len(vals) >= 3 else vals
        if all(v > 0 for v in son3) and all(son3[i] > son3[i-1] for i in range(1, len(son3))):
            return "🚀"
        if all(v > 0 for v in vals):
            return "🟢"
        if sum(1 for v in vals if v > 0) > sum(1 for v in vals if v < 0):
            return "🟡"
        return "🔴"

    pivot["TREND"] = pivot.apply(trend, axis=1)
    pivot = pivot.sort_values("KÜMÜLATİF", ascending=False).reset_index(drop=True)
    return pivot


def hisse_mkk_getir(hisse: str, tip: str, son_n: int = 4) -> pd.DataFrame:
    """
    Tek bir hisse için son N dönemin MKK pp_fark değerlerini döndürür.
    Hisse Detay sekmesindeki bar grafik için kullanılır.

    Döndürür: DataFrame — kolonlar: donem, pp_fark
    """
    donemler = donemler_listele(tip)
    if not donemler:
        return pd.DataFrame()

    son_donemler = sorted(donemler, reverse=True)[:son_n]
    df = veri_getir(son_donemler, tip)
    if df.empty:
        return pd.DataFrame()

    df_hisse = df[df["hisse"].str.upper() == hisse.upper()][["donem", "pp_fark"]].copy()
    df_hisse = df_hisse.sort_values("donem").reset_index(drop=True)
    return df_hisse
