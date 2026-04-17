"""
depo.py — Tüm CSV geçmiş verilerini yönetir.

Klasör yapısı:
  data/haftalik/
    haftalik_takas.csv     → yabancı haftalık
    haftalik_mkk.csv       → MKK haftalık PP fark
    ozel_fon_haftalik.csv  → TERA/BULLS/PUSULA haftalık
  data/aylik/
    aylik_takas.csv        → yabancı + fon + emeklilik aylık
    aylik_mkk.csv          → MKK aylık PP fark
    ozel_fon_aylik.csv     → TERA/BULLS/PUSULA aylık
    pozisyon.csv           → en son dönem pozisyon oranları
"""

import pandas as pd
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).parent.parent / "data"
HAF  = BASE / "haftalik"
AYL  = BASE / "aylik"

# CSV dosyaları
HAF_TAKAS   = HAF / "haftalik_takas.csv"
HAF_MKK     = HAF / "haftalik_mkk.csv"
HAF_OZEL    = HAF / "ozel_fon_haftalik.csv"
AYL_TAKAS   = AYL / "aylik_takas.csv"
AYL_MKK     = AYL / "aylik_mkk.csv"
AYL_OZEL    = AYL / "ozel_fon_aylik.csv"
POZISYON    = AYL / "pozisyon.csv"

OZEL_FONLAR = ["TERA", "BULLS", "PUSULA"]


def _ensure():
    for d in [HAF, AYL]:
        d.mkdir(parents=True, exist_ok=True)

def _oku(path: Path) -> pd.DataFrame:
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame()

def _kaydet(df: pd.DataFrame, path: Path):
    _ensure()
    df.to_csv(path, index=False)

def _simdi():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


# ── Dönem listesi ─────────────────────────────────────────────────────────────

def haftalik_donemler() -> list:
    df = _oku(HAF_TAKAS)
    if df.empty or "donem" not in df.columns:
        return []
    return sorted(df["donem"].unique().tolist())

def aylik_donemler() -> list:
    df = _oku(AYL_TAKAS)
    if df.empty or "donem" not in df.columns:
        return []
    return sorted(df["donem"].unique().tolist())


# ── Haftalık Ekle ─────────────────────────────────────────────────────────────

def haftalik_ekle(donem: str,
                  yab_df: pd.DataFrame,
                  mkk_df: pd.DataFrame,
                  ozel: dict) -> tuple[bool, str]:
    """
    donem   : '2025_16'
    yab_df  : takas parser çıktısı (Hisse, 2.Adet, Adet Fark, Tks(2))
    mkk_df  : MKK parser çıktısı (Hisse, PP_Fark, Lot_Fark)
    ozel    : {'TERA': df, 'BULLS': df, 'PUSULA': df}
    """
    mesajlar = []

    # Yabancı takas
    mevcut = _oku(HAF_TAKAS)
    if not mevcut.empty and donem in mevcut["donem"].values:
        return False, f"⚠️ {donem} zaten kayıtlı."

    yeni = yab_df[["Hisse", "Adet Fark", "Tks(2)"]].copy()
    yeni.columns = ["hisse", "yab_fark", "tks2"]
    yeni["donem"] = donem
    yeni["yukleme"] = _simdi()
    _kaydet(pd.concat([mevcut, yeni], ignore_index=True), HAF_TAKAS)
    mesajlar.append(f"✅ Yabancı takas: {len(yeni)} hisse")

    # MKK
    if mkk_df is not None and not mkk_df.empty:
        mevcut_mkk = _oku(HAF_MKK)
        mkk_yeni = mkk_df[["Hisse", "PP_Fark", "Lot_Fark"]].copy()
        mkk_yeni.columns = ["hisse", "pp_fark", "lot_fark"]
        mkk_yeni["donem"] = donem
        mkk_yeni["yukleme"] = _simdi()
        _kaydet(pd.concat([mevcut_mkk, mkk_yeni], ignore_index=True), HAF_MKK)
        mesajlar.append(f"✅ MKK: {len(mkk_yeni)} hisse")

    # Özel fonlar
    if ozel:
        mevcut_ozel = _oku(HAF_OZEL)
        parcalar = []
        for kurum, df in ozel.items():
            if df is not None and not df.empty:
                d = df[["Hisse", "Adet Fark", "2.Adet", "Tks(2)"]].copy()
                d.columns = ["hisse", "fark", "adet2", "tks2"]
                d["kurum"] = kurum
                d["donem"] = donem
                d["yukleme"] = _simdi()
                parcalar.append(d)
        if parcalar:
            _kaydet(pd.concat([mevcut_ozel] + parcalar, ignore_index=True), HAF_OZEL)
            mesajlar.append(f"✅ Özel fonlar: {', '.join(ozel.keys())}")

    return True, "\n".join(mesajlar)


def haftalik_sil(donem: str) -> tuple[bool, str]:
    for csv in [HAF_TAKAS, HAF_MKK, HAF_OZEL]:
        df = _oku(csv)
        if not df.empty and "donem" in df.columns:
            _kaydet(df[df["donem"] != donem], csv)
    return True, f"🗑️ {donem} silindi"


# ── Aylık Ekle ────────────────────────────────────────────────────────────────

def aylik_ekle(donem: str,
               yab_df: pd.DataFrame,
               fon_df: pd.DataFrame,
               emk_df: pd.DataFrame,
               mkk_df: pd.DataFrame,
               ozel: dict) -> tuple[bool, str]:
    mesajlar = []

    mevcut = _oku(AYL_TAKAS)
    if not mevcut.empty and donem in mevcut["donem"].values:
        return False, f"⚠️ {donem} zaten kayıtlı."

    # Takas (yab + fon + emk)
    parcalar = []
    for df, tip in [(yab_df,"yabanci"), (fon_df,"fon"), (emk_df,"emeklilik")]:
        if df is not None and not df.empty:
            d = df[["Hisse", "Adet Fark", "2.Adet", "Tks(2)"]].copy()
            d.columns = ["hisse", "fark", "adet2", "tks2"]
            d["tip"] = tip
            d["donem"] = donem
            d["yukleme"] = _simdi()
            parcalar.append(d)
    if parcalar:
        _kaydet(pd.concat([mevcut] + parcalar, ignore_index=True), AYL_TAKAS)
        mesajlar.append(f"✅ Takas (yab+fon+emk): {sum(len(p) for p in parcalar)} kayıt")

    # MKK
    if mkk_df is not None and not mkk_df.empty:
        mevcut_mkk = _oku(AYL_MKK)
        mkk_yeni = mkk_df[["Hisse", "PP_Fark", "Lot_Fark"]].copy()
        mkk_yeni.columns = ["hisse", "pp_fark", "lot_fark"]
        mkk_yeni["donem"] = donem
        mkk_yeni["yukleme"] = _simdi()
        _kaydet(pd.concat([mevcut_mkk, mkk_yeni], ignore_index=True), AYL_MKK)
        mesajlar.append(f"✅ MKK: {len(mkk_yeni)} hisse")

    # Özel fonlar
    if ozel:
        mevcut_ozel = _oku(AYL_OZEL)
        parcalar_ozel = []
        for kurum, df in ozel.items():
            if df is not None and not df.empty:
                d = df[["Hisse", "Adet Fark", "2.Adet", "Tks(2)"]].copy()
                d.columns = ["hisse", "fark", "adet2", "tks2"]
                d["kurum"] = kurum
                d["donem"] = donem
                d["yukleme"] = _simdi()
                parcalar_ozel.append(d)
        if parcalar_ozel:
            _kaydet(pd.concat([mevcut_ozel] + parcalar_ozel, ignore_index=True), AYL_OZEL)
            mesajlar.append(f"✅ Özel fonlar: {', '.join(ozel.keys())}")

    # Pozisyon oranları
    _pozisyon_hesapla_kaydet(donem, yab_df, fon_df, emk_df, ozel)
    mesajlar.append("✅ Pozisyon oranları hesaplandı")

    return True, "\n".join(mesajlar)


def aylik_sil(donem: str) -> tuple[bool, str]:
    for csv in [AYL_TAKAS, AYL_MKK, AYL_OZEL, POZISYON]:
        df = _oku(csv)
        if not df.empty and "donem" in df.columns:
            _kaydet(df[df["donem"] != donem], csv)
    return True, f"🗑️ {donem} silindi"


# ── Pozisyon Hesapla ──────────────────────────────────────────────────────────

def _pozisyon_hesapla_kaydet(donem, yab_df, fon_df, emk_df, ozel):
    parcalar = []

    def ekle(df, tip):
        if df is None or df.empty:
            return
        d = df[["Hisse", "2.Adet", "Tks(2)"]].copy()
        d.columns = ["hisse", "adet2", "tks2"]
        d["adet2"] = pd.to_numeric(d["adet2"], errors="coerce").fillna(0)
        d["tks2"]  = pd.to_numeric(d["tks2"],  errors="coerce")
        d = d[d["tks2"].notna() & (d["tks2"] > 0)]
        d["oran"]  = (d["adet2"] / d["tks2"] * 100).round(2)
        d["tip"]   = tip
        parcalar.append(d)

    ekle(yab_df, "yabanci")
    ekle(fon_df, "fon")
    ekle(emk_df, "emeklilik")
    if ozel:
        for kurum, df in ozel.items():
            ekle(df, kurum.lower())

    if not parcalar:
        return

    tum = pd.concat(parcalar, ignore_index=True)
    tum["donem"] = donem
    tum["yukleme"] = _simdi()

    mevcut = _oku(POZISYON)
    if not mevcut.empty and "donem" in mevcut.columns:
        mevcut = mevcut[mevcut["donem"] != donem]
    _kaydet(pd.concat([mevcut, tum], ignore_index=True), POZISYON)


# ── Veri Getir ────────────────────────────────────────────────────────────────

def haftalik_ana_tablo(donemler: list = None) -> pd.DataFrame:
    """
    Ana tablo: Her hisse için dönem × (yab_fark, mkk_pp) pivot
    """
    takas = _oku(HAF_TAKAS)
    mkk   = _oku(HAF_MKK)

    if takas.empty:
        return pd.DataFrame()

    if donemler:
        takas = takas[takas["donem"].isin(donemler)]
        if not mkk.empty:
            mkk = mkk[mkk["donem"].isin(donemler)]

    # Yabancı pivot
    yab_pivot = takas.pivot_table(
        index="hisse", columns="donem", values="yab_fark", aggfunc="sum"
    ).fillna(0)
    yab_pivot.columns = [f"{c}_yab" for c in yab_pivot.columns]

    # MKK pivot
    if not mkk.empty:
        mkk_pivot = mkk.pivot_table(
            index="hisse", columns="donem", values="pp_fark", aggfunc="sum"
        ).fillna(0)
        mkk_pivot.columns = [f"{c}_mkk" for c in mkk_pivot.columns]
        sonuc = yab_pivot.join(mkk_pivot, how="outer").fillna(0)
    else:
        sonuc = yab_pivot

    # Tks2 (son dönemden)
    son_donem = sorted(takas["donem"].unique())[-1]
    tks = takas[takas["donem"] == son_donem][["hisse","tks2"]].drop_duplicates("hisse")
    sonuc = sonuc.reset_index().merge(tks, on="hisse", how="left")

    # Toplam yab fark
    yab_cols = [c for c in sonuc.columns if c.endswith("_yab")]
    sonuc["yab_net"] = sonuc[yab_cols].sum(axis=1)

    return sonuc


def aylik_ana_tablo(donemler: list = None) -> pd.DataFrame:
    takas = _oku(AYL_TAKAS)
    mkk   = _oku(AYL_MKK)

    if takas.empty:
        return pd.DataFrame()

    if donemler:
        takas = takas[takas["donem"].isin(donemler)]
        if not mkk.empty:
            mkk = mkk[mkk["donem"].isin(donemler)]

    # Net (yab+fon+emk) pivot
    net = takas.groupby(["hisse","donem"])["fark"].sum().reset_index()
    net_pivot = net.pivot_table(
        index="hisse", columns="donem", values="fark", aggfunc="sum"
    ).fillna(0)
    net_pivot.columns = [f"{c}_net" for c in net_pivot.columns]

    # MKK pivot
    if not mkk.empty:
        mkk_pivot = mkk.pivot_table(
            index="hisse", columns="donem", values="pp_fark", aggfunc="sum"
        ).fillna(0)
        mkk_pivot.columns = [f"{c}_mkk" for c in mkk_pivot.columns]
        sonuc = net_pivot.join(mkk_pivot, how="outer").fillna(0)
    else:
        sonuc = net_pivot

    # Net toplam
    net_cols = [c for c in sonuc.columns if c.endswith("_net")]
    sonuc["net_toplam"] = sonuc[net_cols].sum(axis=1)

    return sonuc.reset_index()


def pozisyon_getir(donem: str = None) -> pd.DataFrame:
    df = _oku(POZISYON)
    if df.empty:
        return df
    if donem:
        return df[df["donem"] == donem]
    son = sorted(df["donem"].unique())[-1]
    return df[df["donem"] == son]


def ozel_fon_pozisyon(donem: str = None, mod: str = "aylik") -> pd.DataFrame:
    """Her özel fon için hisse bazlı pozisyon oranları."""
    csv = AYL_OZEL if mod == "aylik" else HAF_OZEL
    df = _oku(csv)
    if df.empty:
        return pd.DataFrame()
    if donem:
        df = df[df["donem"] == donem]
    else:
        son = sorted(df["donem"].unique())[-1]
        df = df[df["donem"] == son]

    df["tks2"]  = pd.to_numeric(df["tks2"],  errors="coerce")
    df["adet2"] = pd.to_numeric(df["adet2"], errors="coerce").fillna(0)
    df = df[df["tks2"].notna() & (df["tks2"] > 0)]
    df["oran"] = (df["adet2"] / df["tks2"] * 100).round(2)
    return df


# ── Momentum Hesapla ──────────────────────────────────────────────────────────

def momentum_hesapla(df: pd.DataFrame, tip: str = "yab") -> pd.DataFrame:
    """
    df: ana tablo (haftalik_ana_tablo veya aylik_ana_tablo)
    tip: 'yab' veya 'net' veya 'mkk'
    
    Her hisse için:
    - kac_yesil: kaç dönem pozitif
    - kac_kirmizi: kaç dönem negatif
    - surekli_artis: son N dönem sürekli artıyor mu
    - trend: ↑↑ / ↑↓ / ↓↓ emoji
    """
    suffix = f"_{tip}" if tip != "mkk" else "_mkk"
    donem_cols = sorted([c for c in df.columns if c.endswith(suffix)])

    if not donem_cols:
        return df

    df = df.copy()
    df["kac_yesil"]    = (df[donem_cols] > 0).sum(axis=1)
    df["kac_kirmizi"]  = (df[donem_cols] < 0).sum(axis=1)
    df["toplam_donem"] = len(donem_cols)

    # Son 3 dönem hep pozitif mi?
    son3 = donem_cols[-3:] if len(donem_cols) >= 3 else donem_cols
    df["son3_yesil"] = (df[son3] > 0).all(axis=1)

    # Sürekli artış: her dönem bir öncekinden büyük mü?
    def surekli_artis(row):
        vals = [row[c] for c in donem_cols]
        return all(vals[i] > vals[i-1] for i in range(1, len(vals)))

    df["surekli_artis"] = df.apply(surekli_artis, axis=1)

    # Trend emoji
    def trend_emoji(row):
        if row["surekli_artis"]:
            return "🚀"
        if row["son3_yesil"]:
            return "🟢"
        if row["kac_yesil"] > row["kac_kirmizi"]:
            return "🟡"
        return "🔴"

    df["trend"] = df.apply(trend_emoji, axis=1)
    return df
