"""
senaryo_tespit.py — BIST AI Takas Dedektifi — Senaryo Motoru

3 Katman:
  K1: Temel Tespit (%5+ eşik, FD değişim, net bakiye)
  K2: Özel Durum (Blok, Virman, Açığa Satış Kapama, FD Manipülasyon)
  K3: Wyckoff + Senaryo Ataması + Güven Skoru

Kullanım:
  from senaryo_tespit import senaryo_tara
  sonuclar = senaryo_tara(df, donem_listesi)
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, date
from typing import Optional

# ── Kurum Grupları ────────────────────────────────────────────────────────────
AKILLI_PARA   = ["TERA", "MARBAS", "BULLS", "PUSULA", "ALNUS", "A1_CAPITAL"]
DAGITICI      = ["INFO", "IS_YATIRIM", "GARANTI", "YAPI_KREDI", "HALK_YATIRIM"]
BUYUK_YERLI   = ["ZIRAAT_YATIRIM", "AK_YATIRIM", "DENIZ_YATIRIM", "VAKIF", "TEB"]
FON           = ["YAT_FONLARI", "EMEKLILIK"]
YABANCI       = ["YABANCI", "BANKOF", "CITIBANK", "HSBC"]
TUM_KURUMLAR  = AKILLI_PARA + DAGITICI + BUYUK_YERLI + FON + YABANCI

def _kurum_grubu(kurum: str) -> str:
    if kurum in AKILLI_PARA:   return "Akıllı Para"
    if kurum in DAGITICI:      return "Dağıtıcı"
    if kurum in BUYUK_YERLI:   return "Büyük Yerli"
    if kurum in FON:           return "Fon"
    if kurum in YABANCI:       return "Yabancı"
    return "Diğer"

# ── Eşik Sistemi ─────────────────────────────────────────────────────────────
ESIK_TAKIP    = 5.0   # %5  → Takip Modu
ESIK_YUKSEK   = 8.0   # %8  → Yüksek Öncelik
ESIK_KRITIK   = 12.0  # %12 → Kritik
ESIK_TAHTA    = 20.0  # %20 → Tahta Hakimiyeti
ESIK_BLOK     = 20.0  # %20 tek günde → Blok işlem
ESIK_FD_SUPH  = 10.0  # %10 FD artışı → Şüpheli

# ── Wyckoff Faz Tanımları ─────────────────────────────────────────────────────
WYCKOFF_FAZLARI = {
    "Accumulation_A": "Durdurma ve Başlangıç (Selling Climax)",
    "Accumulation_B": "Birikim Bölgesi (Testler)",
    "Accumulation_C": "Son Test / Shakeout",
    "Accumulation_D": "Güçlenme (SOS)",
    "Accumulation_E": "Kırılım / Markup Başlangıcı",
    "Re_Accumulation": "Markup Konsolidasyonu",
    "Distribution_A":  "Zirve / Buying Climax",
    "Distribution_B":  "Dağıtım Bölgesi",
    "Distribution_C":  "Upthrust / Son Zirve",
    "Distribution_D":  "Zayıflama",
    "Distribution_E":  "Kırılım Aşağı",
    "Belirsiz":        "Faz Tespit Edilemedi",
}


# ═══════════════════════════════════════════════════════════════════════════════
# KATMAN 1 — TEMEL TESPİT
# ═══════════════════════════════════════════════════════════════════════════════

def k1_temel_tespit(df: pd.DataFrame, donemler: list) -> dict:
    """
    Seçili dönemlerde her hisse+kurum için:
    - Net alım/satım bakiyesi
    - Eşik geçip geçmediği
    - FD değişimi (tks2)
    """
    df_sec = df[df["donem"].isin(donemler)].copy()
    if df_sec.empty:
        return {}

    # Günlük verilerden tks2 değişimi
    df_gunluk = df_sec[df_sec["tip"] == "gunluk"].copy() if "tip" in df_sec.columns else df_sec.copy()

    sonuclar = {}

    for hisse, h_df in df_sec.groupby("hisse"):
        # FD değişimi
        tks2_bas, tks2_son, fd_degisim_pct = _fd_degisim(df_gunluk, hisse)

        # Kurum bazlı net pozisyon
        kurum_ozet = {}
        for kurum, k_df in h_df.groupby("kurum"):
            net_degisim = k_df["dolasim_pct"].sum() if "dolasim_pct" in k_df.columns else 0
            son_oran    = k_df.sort_values("donem")["oran2"].iloc[-1] if "oran2" in k_df.columns else 0
            ilk_oran    = k_df.sort_values("donem")["oran2"].iloc[0]  if "oran2" in k_df.columns else 0

            if abs(net_degisim) < 0.1:
                continue

            esik = _esik_seviye(abs(net_degisim))
            kurum_ozet[kurum] = {
                "net_degisim":   round(net_degisim, 2),
                "son_oran":      round(son_oran, 2),
                "ilk_oran":      round(ilk_oran, 2),
                "grup":          _kurum_grubu(kurum),
                "esik":          esik,
                "yon":           "ALIŞ" if net_degisim > 0 else "SATIŞ",
            }

        if not kurum_ozet:
            continue

        # Net toplam
        net_alis  = sum(v["net_degisim"] for v in kurum_ozet.values() if v["net_degisim"] > 0)
        net_satis = sum(abs(v["net_degisim"]) for v in kurum_ozet.values() if v["net_degisim"] < 0)

        sonuclar[hisse] = {
            "kurumlar":        kurum_ozet,
            "net_alis":        round(net_alis, 2),
            "net_satis":       round(net_satis, 2),
            "tks2_bas":        tks2_bas,
            "tks2_son":        tks2_son,
            "fd_degisim_pct":  round(fd_degisim_pct, 1),
            "fd_supheli":      fd_degisim_pct > ESIK_FD_SUPH,
        }

    return sonuclar


def _fd_degisim(df_gunluk: pd.DataFrame, hisse: str) -> tuple:
    h = df_gunluk[df_gunluk["hisse"] == hisse]
    if h.empty or "tks2" not in h.columns:
        return 0, 0, 0
    donemler = sorted(h["donem"].unique())
    bas = h[h["donem"] == donemler[0]]["tks2"].mean()
    son = h[h["donem"] == donemler[-1]]["tks2"].mean()
    pct = ((son - bas) / bas * 100) if bas > 0 else 0
    return bas, son, pct


def _esik_seviye(pct: float) -> str:
    if pct >= ESIK_TAHTA: return "🔴 Tahta Hakimiyeti"
    if pct >= ESIK_KRITIK: return "🟠 Kritik"
    if pct >= ESIK_YUKSEK: return "🟡 Yüksek Öncelik"
    if pct >= ESIK_TAKIP:  return "🔵 Takip"
    return "⚪ Normal"


# ═══════════════════════════════════════════════════════════════════════════════
# KATMAN 2 — ÖZEL DURUM TESPİTİ
# ═══════════════════════════════════════════════════════════════════════════════

def k2_ozel_durum(df: pd.DataFrame, donemler: list, k1_sonuc: dict) -> dict:
    """
    Blok işlem, virman, açığa satış kapama, FD manipülasyon tespiti.
    """
    df_sec = df[df["donem"].isin(donemler)].copy()
    sonuclar = {}

    for hisse, k1 in k1_sonuc.items():
        h_df = df_sec[df_sec["hisse"] == hisse]
        ozel = {}

        # ── Açığa Satış Kapama ──────────────────────────────────────────────
        # Kural 1: ADT1_ prefix
        # Kural 2: 1.Adet < 0 VE 2.Adet > 0 → açığa satış kapatıldı
        adt1_kurumlar = [k for k in k1["kurumlar"] if k.startswith("ADT1_")]

        # Veri kolonlarından tespit
        aciga_kurumlar = list(adt1_kurumlar)
        if "oran1" in h_df.columns and "oran2" in h_df.columns:
            for kurum, k_df in h_df.groupby("kurum"):
                ilk_oran = k_df.sort_values("donem")["oran1"].iloc[0] if "oran1" in k_df.columns else 0
                son_oran = k_df.sort_values("donem")["oran2"].iloc[-1] if "oran2" in k_df.columns else 0
                if ilk_oran < 0 and son_oran > 0 and kurum not in aciga_kurumlar:
                    aciga_kurumlar.append(kurum)

        if aciga_kurumlar:
            ozel["aciga_satis_kapama"] = {
                "var": True,
                "kurumlar": aciga_kurumlar,
                "aciklama": f"{', '.join(aciga_kurumlar)} açığa satış kapatıyor (1.Adet<0 → 2.Adet>0).",
            }

        # ── Blok İşlem Tespiti ───────────────────────────────────────────────
        # Tek bir günde/dönemde tek kurumun oranı %20+ sıçramış
        blok_tespitler = []
        for donem in donemler:
            d_df = h_df[h_df["donem"] == donem]
            for _, row in d_df.iterrows():
                if "dolasim_pct" in row and abs(row["dolasim_pct"]) >= ESIK_BLOK:
                    blok_tespitler.append({
                        "kurum":   row["kurum"],
                        "donem":   donem,
                        "degisim": round(row["dolasim_pct"], 2),
                        "tip":     "Alış" if row["dolasim_pct"] > 0 else "Satış",
                        "grup":    _kurum_grubu(row["kurum"]),
                    })
        if blok_tespitler:
            ozel["blok_islem"] = {
                "var": True,
                "tespitler": blok_tespitler,
                "aciklama": f"{len(blok_tespitler)} blok işlem tespit edildi.",
            }

        # ── Virman Tespiti ───────────────────────────────────────────────────
        # Aynı dönemde aynı hissede büyük alım + büyük satış yakın miktarda
        alanlar = {k: v for k, v in k1["kurumlar"].items() if v["net_degisim"] > ESIK_TAKIP}
        satanlar = {k: v for k, v in k1["kurumlar"].items() if v["net_degisim"] < -ESIK_TAKIP}

        if alanlar and satanlar:
            max_alan  = max(alanlar.values(), key=lambda x: x["net_degisim"])
            max_satan = min(satanlar.values(), key=lambda x: x["net_degisim"])
            oran = abs(max_satan["net_degisim"]) / max_alan["net_degisim"] if max_alan["net_degisim"] > 0 else 0

            if 0.7 <= oran <= 1.3:
                alan_k  = [k for k, v in alanlar.items() if v == max_alan][0]
                satan_k = [k for k, v in satanlar.items() if v == max_satan][0]
                alan_grup  = _kurum_grubu(alan_k)
                satan_grup = _kurum_grubu(satan_k)

                if alan_grup != satan_grup:
                    tip = "Mal Devri"
                    aciklama = f"{satan_k} ({satan_grup}) → {alan_k} ({alan_grup})"
                else:
                    tip = "Virman"
                    aciklama = f"{satan_k} → {alan_k} (aynı grup: {alan_grup})"

                ozel["virman_mal_devri"] = {
                    "var": True,
                    "tip": tip,
                    "alan": alan_k,
                    "satan": satan_k,
                    "aciklama": aciklama,
                }

        # ── FD Manipülasyon ──────────────────────────────────────────────────
        if k1["fd_supheli"]:
            ozel["fd_manipulasyon"] = {
                "var": True,
                "fd_degisim_pct": k1["fd_degisim_pct"],
                "aciklama": f"FD %{k1['fd_degisim_pct']:.1f} artmış. Tüm sinyaller şüpheli.",
            }

        sonuclar[hisse] = ozel

    return sonuclar


# ═══════════════════════════════════════════════════════════════════════════════
# KATMAN 3 — WYCKOFF + SENARYO ATAMASI
# ═══════════════════════════════════════════════════════════════════════════════

def k3_wyckoff_senaryo(df: pd.DataFrame, donemler: list,
                        k1: dict, k2: dict,
                        mkk_df: pd.DataFrame = None) -> dict:
    """
    K1 ve K2 bulgularına göre:
    - Wyckoff fazı ata
    - Senaryo belirle
    - Güven skoru hesapla (0-10)
    - MKK verisi varsa birleştir
    """
    sonuclar = {}

    for hisse in k1:
        k1_h = k1[hisse]
        k2_h = k2.get(hisse, {})

        kurumlar  = k1_h["kurumlar"]
        alanlar   = {k: v for k, v in kurumlar.items() if v["net_degisim"] > 0}
        satanlar  = {k: v for k, v in kurumlar.items() if v["net_degisim"] < 0}
        fd_suph   = k1_h["fd_supheli"]
        fd_pct    = k1_h["fd_degisim_pct"]
        net_alis  = k1_h["net_alis"]
        net_satis = k1_h["net_satis"]

        alan_gruplar  = set(v["grup"] for v in alanlar.values())
        satan_gruplar = set(v["grup"] for v in satanlar.values())
        alan_sayi     = len(alanlar)
        satan_sayi    = len(satanlar)

        # ── MKK verisi ────────────────────────────────────────────────────────
        mkk_trend = None
        mkk_delta = 0
        if mkk_df is not None and not mkk_df.empty:
            mkk_h = mkk_df[mkk_df["hisse"] == hisse] if "hisse" in mkk_df.columns else pd.DataFrame()
            if not mkk_h.empty:
                mkk_delta = mkk_h["bireysel_delta"].sum() if "bireysel_delta" in mkk_h.columns else 0
                mkk_trend = "azalıyor" if mkk_delta < -2 else "artıyor" if mkk_delta > 2 else "nötr"

        # ── Senaryo ve Wyckoff Faz ────────────────────────────────────────────
        senaryo, wyckoff_faz, guven = _senaryo_belirle(
            alanlar, satanlar, alan_gruplar, satan_gruplar,
            alan_sayi, satan_sayi, fd_suph, fd_pct,
            net_alis, net_satis, k2_h, mkk_trend, mkk_delta,
            df, donemler, hisse
        )

        # ── Özet ─────────────────────────────────────────────────────────────
        en_guclu_alan  = max(alanlar.items(), key=lambda x: x[1]["net_degisim"], default=None)
        en_guclu_satan = min(satanlar.items(), key=lambda x: x[1]["net_degisim"], default=None)

        sonuclar[hisse] = {
            "senaryo":       senaryo,
            "wyckoff_faz":   wyckoff_faz,
            "guven_skoru":   round(guven, 1),
            "net_alis":      net_alis,
            "net_satis":     net_satis,
            "fd_supheli":    fd_suph,
            "fd_pct":        fd_pct,
            "mkk_trend":     mkk_trend,
            "mkk_delta":     round(mkk_delta, 2),
            "en_guclu_alan": f"{en_guclu_alan[0]} +{en_guclu_alan[1]['net_degisim']:.1f}%" if en_guclu_alan else None,
            "en_guclu_satan": f"{en_guclu_satan[0]} {en_guclu_satan[1]['net_degisim']:.1f}%" if en_guclu_satan else None,
            "k2_ozel":       k2_h,
        }

    return sonuclar


def _senaryo_belirle(alanlar, satanlar, alan_gruplar, satan_gruplar,
                     alan_sayi, satan_sayi, fd_suph, fd_pct,
                     net_alis, net_satis, k2, mkk_trend, mkk_delta,
                     df, donemler, hisse):
    """Senaryo, Wyckoff fazı ve güven skoru belirle."""

    guven = 5.0  # başlangıç skoru

    # ── FD şüpheli → tüm sinyaller geçersiz ─────────────────────────────────
    if fd_suph:
        return "⚠️ Takas FD Değişti", "Belirsiz", 2.0

    # ── Mal Devri / Virman ───────────────────────────────────────────────────
    if "virman_mal_devri" in k2:
        tip = k2["virman_mal_devri"]["tip"]
        if tip == "Mal Devri":
            # Wyckoff: hangi gruptan hangi gruba?
            alan_k  = k2["virman_mal_devri"]["alan"]
            satan_k = k2["virman_mal_devri"]["satan"]
            alan_g  = _kurum_grubu(alan_k)
            satan_g = _kurum_grubu(satan_k)

            if satan_g == "Akıllı Para" and alan_g == "Fon":
                wyckoff = "Distribution_B"
                guven += 1.5
            elif satan_g in ("Büyük Yerli", "Yabancı") and alan_g == "Akıllı Para":
                wyckoff = "Accumulation_C"
                guven += 2.0
            elif satan_g == "Dağıtıcı" and alan_g == "Akıllı Para":
                wyckoff = "Accumulation_B"
                guven += 1.0
            else:
                wyckoff = "Belirsiz"

            if mkk_trend == "azalıyor":
                guven += 1.0

            return "🔄 Mal Devri", wyckoff, min(guven, 10.0)

        else:
            return "↔️ Virman", "Belirsiz", 3.0

    # ── Birikim ──────────────────────────────────────────────────────────────
    akilli_aliyor = bool(alan_gruplar & {"Akıllı Para"})
    info_aliyor   = "INFO" in alanlar
    info_satiyor  = "INFO" in satanlar

    if akilli_aliyor and alan_sayi <= 3 and net_satis < net_alis * 0.3:
        guven += 1.5
        if mkk_trend == "azalıyor":
            guven += 1.5  # Bireysel satıyor, kurum alıyor → güçlü sinyal

        # Wyckoff faz: kaç dönemdir alıyor?
        ardisik = _ardisik_alim_say(df, donemler, hisse,
                                     list(alan_gruplar & {"Akıllı Para"}))
        if ardisik >= 4:
            wyckoff = "Accumulation_D"
            guven += 1.0
        elif ardisik >= 2:
            wyckoff = "Accumulation_C"
        else:
            wyckoff = "Accumulation_B"

        return "🟢 Birikim", wyckoff, min(guven, 10.0)

    # ── Dağıtım ──────────────────────────────────────────────────────────────
    # INFO %3+ alıyorsa = dağıtım sinyali (küçük miktarlar hariç)
    info_buyuk_alim = "INFO" in alanlar and alanlar["INFO"]["net_degisim"] >= 3.0
    if info_buyuk_alim or (alan_sayi >= 5 and satan_sayi <= 2 and
                       bool(satan_gruplar & {"Akıllı Para", "Büyük Yerli"}) and
                       net_satis >= 5.0):
        guven += 1.0
        if info_buyuk_alim:
            guven += 1.5  # INFO girişi = Phase C/D sinyali
        if mkk_trend == "artıyor":
            guven += 1.0  # Bireysel alıyor, kurum satıyor → dağıtım

        wyckoff = "Distribution_C" if info_buyuk_alim else "Distribution_B"
        return "🔴 Dağıtım", wyckoff, min(guven, 10.0)

    # ── Toplu Dağıtım ────────────────────────────────────────────────────────
    if alan_sayi >= 5 and satan_sayi <= 2 and net_satis < net_alis:
        return "📤 Toplu Dağıtım", "Distribution_B", min(guven + 0.5, 10.0)

    # ── Toplama / Güçlü Alım ─────────────────────────────────────────────────
    if alan_sayi <= 2 and satan_sayi >= 5:
        if akilli_aliyor:
            guven += 2.0
            if mkk_trend == "azalıyor":
                guven += 1.5
            return "🎯 Toplama", "Accumulation_C", min(guven, 10.0)
        return "📈 Güçlü Alım", "Accumulation_B", min(guven + 1.0, 10.0)

    # ── Re-Accumulation ──────────────────────────────────────────────────────
    if akilli_aliyor and net_satis > 0 and net_satis < net_alis * 0.5:
        return "🔁 Re-Accumulation", "Re_Accumulation", min(guven + 1.0, 10.0)

    # ── Varsayılan ───────────────────────────────────────────────────────────
    if net_alis > net_satis:
        return "📊 Net Alım", "Belirsiz", min(guven, 10.0)
    elif net_satis > net_alis:
        return "📊 Net Satım", "Belirsiz", min(guven, 10.0)

    return "➖ Nötr", "Belirsiz", 3.0


def _ardisik_alim_say(df: pd.DataFrame, donemler: list,
                       hisse: str, gruplar: list) -> int:
    """Verilen grup kurumlarının ardışık alım dönem sayısını hesapla."""
    h_df = df[(df["hisse"] == hisse) & (df["donem"].isin(donemler))].copy()
    h_df = h_df[h_df["kurum"].isin(
        [k for k in TUM_KURUMLAR if _kurum_grubu(k) in gruplar]
    )]
    if h_df.empty:
        return 0

    donem_net = h_df.groupby("donem")["dolasim_pct"].sum().sort_index()
    ardisik = 0
    maks = 0
    for v in donem_net:
        if v > 0:
            ardisik += 1
            maks = max(maks, ardisik)
        else:
            ardisik = 0
    return maks


# ═══════════════════════════════════════════════════════════════════════════════
# ANA FONKSİYON
# ═══════════════════════════════════════════════════════════════════════════════

def senaryo_tara(df: pd.DataFrame, donemler: list,
                  mkk_df: pd.DataFrame = None,
                  min_net_alis: float = 3.0) -> pd.DataFrame:
    """
    Tüm hisseler için 3 katmanlı senaryo tespiti yapar.

    Args:
        df:           kurum_takas.csv DataFrame
        donemler:     analiz edilecek dönemler listesi
        mkk_df:       MKK bireysel yatırımcı verisi (opsiyonel)
        min_net_alis: minimum net alış filtresi

    Returns:
        DataFrame: her hisse için senaryo, Wyckoff fazı, güven skoru
    """
    if df.empty or not donemler:
        return pd.DataFrame()

    # K1
    k1 = k1_temel_tespit(df, donemler)

    # Min filtre
    k1 = {h: v for h, v in k1.items() if v["net_alis"] >= min_net_alis}

    if not k1:
        return pd.DataFrame()

    # K2
    k2 = k2_ozel_durum(df, donemler, k1)

    # K3
    k3 = k3_wyckoff_senaryo(df, donemler, k1, k2, mkk_df)

    # DataFrame'e çevir
    satirlar = []
    for hisse, s in k3.items():
        satirlar.append({
            "hisse":          hisse,
            "senaryo":        s["senaryo"],
            "wyckoff_faz":    s["wyckoff_faz"],
            "guven_skoru":    s["guven_skoru"],
            "net_alis":       s["net_alis"],
            "net_satis":      s["net_satis"],
            "fd_supheli":     s["fd_supheli"],
            "fd_pct":         s["fd_pct"],
            "mkk_trend":      s["mkk_trend"],
            "en_guclu_alan":  s["en_guclu_alan"],
            "en_guclu_satan": s["en_guclu_satan"],
            "k2_ozel":        str(s["k2_h"]) if "k2_h" in s else "",
        })

    result = pd.DataFrame(satirlar)
    result = result.sort_values("guven_skoru", ascending=False)
    return result


# ── Test ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("senaryo_tespit.py yüklendi.")
    print(f"Kurum grupları:")
    print(f"  Akıllı Para: {AKILLI_PARA}")
    print(f"  Dağıtıcı:    {DAGITICI}")
    print(f"  Büyük Yerli: {BUYUK_YERLI}")
    print(f"  Fon:         {FON}")
    print(f"  Yabancı:     {YABANCI}")
