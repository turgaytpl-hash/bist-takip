"""
parser.py — Matriks xlsx dosyalarını okur ve normalize eder.
"""

import pandas as pd
from io import BytesIO


# ── Takas Parser ──────────────────────────────────────────────────────────────

def takas_oku(kaynak) -> pd.DataFrame:
    """Yabancı/Fon/Emeklilik/Özel Fon takas dosyasını okur."""
    if hasattr(kaynak, "read"):
        data = BytesIO(kaynak.read())
        xl = pd.ExcelFile(data)
    else:
        xl = pd.ExcelFile(str(kaynak))

    df = pd.read_excel(xl, sheet_name=xl.sheet_names[0])

    zorunlu = ["Hisse", "1.Adet", "2.Adet", "Adet Fark", "Tks(2)"]
    eksik = [c for c in zorunlu if c not in df.columns]
    if eksik:
        raise ValueError(f"Eksik kolonlar: {eksik}")

    df = df[zorunlu].copy()
    df["Hisse"]     = df["Hisse"].astype(str).str.strip().str.upper()
    df["1.Adet"]    = pd.to_numeric(df["1.Adet"],    errors="coerce").fillna(0)
    df["2.Adet"]    = pd.to_numeric(df["2.Adet"],    errors="coerce").fillna(0)
    df["Adet Fark"] = pd.to_numeric(df["Adet Fark"], errors="coerce").fillna(0)
    df["Tks(2)"]    = pd.to_numeric(df["Tks(2)"],    errors="coerce")

    # BIST hisse filtresi: 4-6 harf, Tks(2) > 1M
    df = df[df["Hisse"].str.match(r"^[A-Z]{4,6}$")]
    df = df[df["Tks(2)"].notna() & (df["Tks(2)"] > 1_000_000)]

    # Oran hesapla
    df["Oran_1"] = (df["1.Adet"] / df["Tks(2)"] * 100).round(2)
    df["Oran_2"] = (df["2.Adet"] / df["Tks(2)"] * 100).round(2)
    df["PP_Fark"] = (df["Oran_2"] - df["Oran_1"]).round(2)

    return df.reset_index(drop=True)


# ── MKK Parser ────────────────────────────────────────────────────────────────

def mkk_oku(kaynak) -> pd.DataFrame:
    """
    MKK kurumsal oran dosyasını okur.
    
    Beklenen format (Matriks MKK raporu):
    Satır 0: üst başlık (İlk Tarih / Son Tarih / Fark)
    Satır 1: alt başlık (Sembol, Birey.Lot, Birey.Oran, Kurum.Lot, Kurum.Oran, ...)
    Satır 2+: veri
    
    Hesaplama:
    PP_Fark  = Kur_Oran_2 - Kur_Oran_1  ← ana sinyal (patlama yok)
    Lot_Fark = Kurum Lot farkı (bilgi amaçlı)
    """
    if hasattr(kaynak, "read"):
        data = BytesIO(kaynak.read())
        df_raw = pd.read_excel(data, header=None)
    else:
        df_raw = pd.read_excel(str(kaynak), header=None)

    # Kolon isimlerini ata
    df_raw.columns = [
        "Hisse",
        "Bir_Lot_1", "Bir_Oran_1", "Kur_Lot_1", "Kur_Oran_1",
        "Bir_Lot_2", "Bir_Oran_2", "Kur_Lot_2", "Kur_Oran_2",
        "Fark_Bir_Lot", "Fark_Bir_Oran", "Fark_Kur_Lot", "Fark_Kur_Oran",
        "Son_Yat"
    ]

    # İlk 2 satır başlık — atla
    df = df_raw.iloc[2:].reset_index(drop=True).copy()

    def parse_num(x):
        if isinstance(x, str):
            return pd.to_numeric(
                x.strip().replace(".", "").replace(",", "."), errors="coerce"
            )
        return pd.to_numeric(x, errors="coerce")

    for col in df.columns[1:]:
        df[col] = df[col].apply(parse_num)

    # Sadece gerçek hisseler (endeks kodları değil)
    df = df[~df["Hisse"].isin(["XU030", "XU050", "XU100", "XUTUM", "XBANK"])]
    df = df[df["Hisse"].astype(str).str.match(r"^[A-Z]{4,6}$")]
    df = df[df["Kur_Lot_1"].notna() & df["Kur_Lot_2"].notna()]

    # Ana hesaplamalar — MADDE 3
    df["PP_Fark"]  = (df["Kur_Oran_2"] - df["Kur_Oran_1"]).round(2)   # ← kullanılacak
    df["Lot_Fark"] = df["Fark_Kur_Lot"]                                 # bilgi amaçlı

    # Bireysel fark (bonus)
    df["Birey_PP"] = (df["Bir_Oran_2"] - df["Bir_Oran_1"]).round(2)

    return df[["Hisse", "Kur_Oran_1", "Kur_Oran_2", "PP_Fark",
               "Lot_Fark", "Birey_PP"]].reset_index(drop=True)


# ── Pozisyon Hesapla ──────────────────────────────────────────────────────────

def pozisyon_hesapla(yab_df=None, fon_df=None, emk_df=None,
                     tera_df=None, bulls_df=None, pusula_df=None) -> pd.DataFrame:
    """
    Tüm kurumların Tks(2) bazlı pozisyon oranlarını hesaplar.
    Formül: 2.Adet / Tks(2) × 100  ← MADDE 4
    """
    tum_hisseler = set()
    tks2_map = {}

    def topla_hisseler(df):
        if df is None or df.empty:
            return
        for _, r in df.iterrows():
            h = r["Hisse"]
            tum_hisseler.add(h)
            tks = r.get("Tks(2)", None)
            if pd.notna(tks) and tks > 0:
                tks2_map[h] = tks

    for df in [yab_df, fon_df, emk_df, tera_df, bulls_df, pusula_df]:
        topla_hisseler(df)

    if not tum_hisseler:
        return pd.DataFrame()

    def get_oran(df, hisse):
        if df is None or df.empty:
            return 0.0
        r = df[df["Hisse"] == hisse]
        if len(r) == 0:
            return 0.0
        adet = float(r.iloc[0]["2.Adet"])
        tks  = tks2_map.get(hisse, 0)
        return round(adet / tks * 100, 2) if tks > 0 else 0.0

    rows = []
    for h in sorted(tum_hisseler):
        tks2 = tks2_map.get(h, 0)
        if tks2 == 0:
            continue
        yab_o    = get_oran(yab_df,    h)
        fon_o    = get_oran(fon_df,    h)
        emk_o    = get_oran(emk_df,    h)
        tera_o   = get_oran(tera_df,   h)
        bulls_o  = get_oran(bulls_df,  h)
        pusula_o = get_oran(pusula_df, h)
        top_o    = round(yab_o + fon_o + emk_o, 2)

        # Hangi özel fonlar var?
        ozel_var = []
        if tera_o   > 0: ozel_var.append(f"TERA({tera_o:.1f}%)")
        if bulls_o  > 0: ozel_var.append(f"BULLS({bulls_o:.1f}%)")
        if pusula_o > 0: ozel_var.append(f"PUSULA({pusula_o:.1f}%)")

        rows.append({
            "Hisse":    h,
            "Tks2":     int(tks2),
            "Yab_Oran": yab_o,
            "Fon_Oran": fon_o,
            "Emk_Oran": emk_o,
            "Top_Oran": top_o,
            "Kalan":    max(0, round(100 - top_o, 2)),
            "Tera_Oran":   tera_o,
            "Bulls_Oran":  bulls_o,
            "Pusula_Oran": pusula_o,
            "Ozel_Var": ", ".join(ozel_var) if ozel_var else "—",
        })

    return pd.DataFrame(rows).sort_values("Top_Oran", ascending=False).reset_index(drop=True)
