"""
takas_hafiza.py — BIST AI Takas Hafıza Sistemi

Her hisse için ayrı JSON dosyası:
  data/hafiza/OZATD.json
  data/hafiza/RUBNS.json

Yapı:
{
  "hisse": "OZATD",
  "son_guncelleme": "2026-05-22",
  "tarihsel_senaryolar": [
    {
      "donem": "202604_04",
      "senaryo": "🟢 Birikim",
      "wyckoff_faz": "Accumulation_C",
      "aciklama": "TERA 3 dönemdir kademeli alım yapıyor. FD sabit.",
      "guc_skoru": 8.2,
      "ana_kurum": "TERA",
      "ana_kurum_oran": 52.8,
      "net_alis": 12.4,
      "net_satis": 1.2,
      "fd_pct": 0.8,
      "mkk_trend": "azalıyor"
    }
  ],
  "mevcut_durum": {
    "wyckoff_faz": "Accumulation_D",
    "en_guclu_kurum": "TERA",
    "en_guclu_oran": 52.8,
    "toplam_birikim_donemi": 7,
    "fd_sabit_mi": true,
    "ai_yorumu": "Temiz birikim devam ediyor.",
    "guven_skoru": 8.7,
    "son_senaryo": "🟢 Birikim"
  },
  "istatistikler": {
    "toplam_kayit": 7,
    "birikim_sayisi": 5,
    "mal_devri_sayisi": 1,
    "dagitim_sayisi": 0,
    "en_uzun_birikim_serisi": 4
  }
}
"""

import json
import pandas as pd
from pathlib import Path
from datetime import date, datetime
from typing import Optional

# ── Hafıza dizini ─────────────────────────────────────────────────────────────
def _hafiza_dir() -> Path:
    """Hafıza dizinini bul ve oluştur."""
    adaylar = [
        Path(__file__).parent / "data" / "hafiza",
        Path(__file__).parent.parent / "data" / "hafiza",
    ]
    for p in adaylar:
        if p.parent.exists():
            p.mkdir(parents=True, exist_ok=True)
            return p
    # Fallback
    p = Path("data/hafiza")
    p.mkdir(parents=True, exist_ok=True)
    return p


def _hafiza_yolu(hisse: str) -> Path:
    return _hafiza_dir() / f"{hisse.upper()}.json"


# ═══════════════════════════════════════════════════════════════════════════════
# OKUMA
# ═══════════════════════════════════════════════════════════════════════════════

def hafiza_oku(hisse: str) -> dict:
    """Hisse hafızasını oku. Yoksa boş yapı döndür."""
    yol = _hafiza_yolu(hisse)
    if yol.exists():
        try:
            with open(yol, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return _bos_hafiza(hisse)


def _bos_hafiza(hisse: str) -> dict:
    return {
        "hisse": hisse,
        "son_guncelleme": str(date.today()),
        "tarihsel_senaryolar": [],
        "mevcut_durum": {
            "wyckoff_faz": "Belirsiz",
            "en_guclu_kurum": None,
            "en_guclu_oran": 0,
            "toplam_birikim_donemi": 0,
            "fd_sabit_mi": True,
            "ai_yorumu": "",
            "guven_skoru": 0,
            "son_senaryo": "",
        },
        "istatistikler": {
            "toplam_kayit": 0,
            "birikim_sayisi": 0,
            "mal_devri_sayisi": 0,
            "dagitim_sayisi": 0,
            "en_uzun_birikim_serisi": 0,
        }
    }


# ═══════════════════════════════════════════════════════════════════════════════
# YAZMA
# ═══════════════════════════════════════════════════════════════════════════════

def hafiza_kaydet(hisse: str, veri: dict):
    """Hisse hafızasını kaydet."""
    yol = _hafiza_yolu(hisse)
    with open(yol, "w", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False, indent=2)


def hafiza_guncelle(hisse: str, donem: str, senaryo_sonuc: dict,
                     ai_yorumu: str = "") -> dict:
    """
    Yeni bir senaryo sonucunu hafızaya ekle / güncelle.

    senaryo_sonuc: k3_wyckoff_senaryo() çıktısından tek hisse verisi
    """
    hafiza = hafiza_oku(hisse)

    # ── Yeni senaryo kaydı ────────────────────────────────────────────────────
    yeni_kayit = {
        "donem":          donem,
        "senaryo":        senaryo_sonuc.get("senaryo", ""),
        "wyckoff_faz":    senaryo_sonuc.get("wyckoff_faz", "Belirsiz"),
        "aciklama":       ai_yorumu,
        "guc_skoru":      senaryo_sonuc.get("guven_skoru", 0),
        "ana_kurum":      _ana_kurum_bul(senaryo_sonuc),
        "net_alis":       senaryo_sonuc.get("net_alis", 0),
        "net_satis":      senaryo_sonuc.get("net_satis", 0),
        "fd_pct":         senaryo_sonuc.get("fd_pct", 0),
        "fd_supheli":     senaryo_sonuc.get("fd_supheli", False),
        "mkk_trend":      senaryo_sonuc.get("mkk_trend", None),
        "tarih":          str(date.today()),
    }

    # Aynı dönem varsa güncelle, yoksa ekle
    mevcut = hafiza["tarihsel_senaryolar"]
    idx = next((i for i, s in enumerate(mevcut) if s["donem"] == donem), None)
    if idx is not None:
        mevcut[idx] = yeni_kayit
    else:
        mevcut.append(yeni_kayit)

    # Döneme göre sırala
    hafiza["tarihsel_senaryolar"] = sorted(mevcut, key=lambda x: x["donem"])

    # ── Mevcut durum güncelle ─────────────────────────────────────────────────
    hafiza["mevcut_durum"] = {
        "wyckoff_faz":           senaryo_sonuc.get("wyckoff_faz", "Belirsiz"),
        "en_guclu_kurum":        _ana_kurum_bul(senaryo_sonuc),
        "en_guclu_oran":         _ana_kurum_oran_bul(senaryo_sonuc),
        "toplam_birikim_donemi": _birikim_serisi_say(hafiza["tarihsel_senaryolar"]),
        "fd_sabit_mi":           not senaryo_sonuc.get("fd_supheli", False),
        "ai_yorumu":             ai_yorumu,
        "guven_skoru":           senaryo_sonuc.get("guven_skoru", 0),
        "son_senaryo":           senaryo_sonuc.get("senaryo", ""),
    }

    # ── İstatistikler güncelle ────────────────────────────────────────────────
    hafiza["istatistikler"] = _istatistik_hesapla(hafiza["tarihsel_senaryolar"])
    hafiza["son_guncelleme"] = str(date.today())

    hafiza_kaydet(hisse, hafiza)
    return hafiza


def _ana_kurum_bul(senaryo_sonuc: dict) -> Optional[str]:
    alan = senaryo_sonuc.get("en_guclu_alan", "")
    if alan:
        return alan.split(" ")[0]
    return None


def _ana_kurum_oran_bul(senaryo_sonuc: dict) -> float:
    alan = senaryo_sonuc.get("en_guclu_alan", "")
    if alan and "+" in alan:
        try:
            return float(alan.split("+")[1].replace("%", ""))
        except:
            pass
    return 0.0


def _birikim_serisi_say(senaryolar: list) -> int:
    """Son ardışık birikim/toplama dönem sayısı."""
    birikim_sinyalleri = {"🟢 Birikim", "🎯 Toplama", "📈 Güçlü Alım", "🔁 Re-Accumulation"}
    ardisik = 0
    for s in reversed(senaryolar):
        if s.get("senaryo", "") in birikim_sinyalleri:
            ardisik += 1
        else:
            break
    return ardisik


def _istatistik_hesapla(senaryolar: list) -> dict:
    birikim    = sum(1 for s in senaryolar if "Birikim" in s.get("senaryo", "") or "Toplama" in s.get("senaryo", ""))
    mal_devri  = sum(1 for s in senaryolar if "Mal Devri" in s.get("senaryo", ""))
    dagitim    = sum(1 for s in senaryolar if "Dağıtım" in s.get("senaryo", ""))

    # En uzun birikim serisi
    birikim_sinyalleri = {"🟢 Birikim", "🎯 Toplama", "📈 Güçlü Alım", "🔁 Re-Accumulation"}
    maks = ardisik = 0
    for s in senaryolar:
        if s.get("senaryo", "") in birikim_sinyalleri:
            ardisik += 1
            maks = max(maks, ardisik)
        else:
            ardisik = 0

    return {
        "toplam_kayit":          len(senaryolar),
        "birikim_sayisi":        birikim,
        "mal_devri_sayisi":      mal_devri,
        "dagitim_sayisi":        dagitim,
        "en_uzun_birikim_serisi": maks,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# TOPLU İŞLEMLER
# ═══════════════════════════════════════════════════════════════════════════════

def hafiza_toplu_guncelle(senaryo_df: pd.DataFrame, donem: str,
                           ai_yorumlar: dict = None):
    """
    senaryo_tara() çıktısını toplu hafızaya yaz.

    Args:
        senaryo_df:  senaryo_tespit.senaryo_tara() sonucu
        donem:       dönem kodu (örn: "20260522")
        ai_yorumlar: {hisse: yorum_str} dict (opsiyonel)
    """
    if senaryo_df.empty:
        return

    ai_yorumlar = ai_yorumlar or {}

    for _, row in senaryo_df.iterrows():
        hisse = row["hisse"]
        sonuc = row.to_dict()
        yorum = ai_yorumlar.get(hisse, "")
        hafiza_guncelle(hisse, donem, sonuc, yorum)


def hafiza_ozet(hisse: str) -> str:
    """Hisse hafızasının kısa özetini döndür."""
    h = hafiza_oku(hisse)
    if not h["tarihsel_senaryolar"]:
        return f"{hisse}: Hafızada kayıt yok."

    md = h["mevcut_durum"]
    ist = h["istatistikler"]
    son = h["tarihsel_senaryolar"][-1]

    ozet = (
        f"**{hisse}** — {md['son_senaryo']} | "
        f"Wyckoff: {md['wyckoff_faz']} | "
        f"Güven: {md['guven_skoru']}/10\n"
        f"Ana Kurum: {md['en_guclu_kurum']} | "
        f"Ardışık Birikim: {md['toplam_birikim_donemi']} dönem | "
        f"Son: {son['donem']}\n"
        f"Toplam: {ist['toplam_kayit']} kayıt | "
        f"Birikim: {ist['birikim_sayisi']} | "
        f"Mal Devri: {ist['mal_devri_sayisi']} | "
        f"Dağıtım: {ist['dagitim_sayisi']}"
    )
    return ozet


def hafiza_gecmis_kontrol(hisse: str, kurum: str) -> dict:
    """
    Belirli bir kurumun bu hissedeki geçmiş hareketlerini getir.
    AI'nin 'Bu kurum daha önce de bu hissede alım yaptı mı?' sorusunu yanıtlar.
    """
    h = hafiza_oku(hisse)
    ilgili = [
        s for s in h["tarihsel_senaryolar"]
        if s.get("ana_kurum") == kurum
    ]
    return {
        "hisse":       hisse,
        "kurum":       kurum,
        "kayit_sayisi": len(ilgili),
        "senaryolar":  ilgili,
        "ilk_gorulme": ilgili[0]["donem"] if ilgili else None,
        "son_gorulme": ilgili[-1]["donem"] if ilgili else None,
    }


def tum_hafiza_listele() -> list:
    """Hafızadaki tüm hisseleri listele."""
    hdir = _hafiza_dir()
    return [f.stem for f in hdir.glob("*.json")]


def hafiza_istatistik() -> dict:
    """Tüm hafıza istatistiklerini getir."""
    hisseler = tum_hafiza_listele()
    toplam_birikim = toplam_dagitim = toplam_mal_devri = 0

    for h in hisseler:
        veri = hafiza_oku(h)
        ist  = veri.get("istatistikler", {})
        toplam_birikim   += ist.get("birikim_sayisi", 0)
        toplam_dagitim   += ist.get("dagitim_sayisi", 0)
        toplam_mal_devri += ist.get("mal_devri_sayisi", 0)

    return {
        "toplam_hisse":    len(hisseler),
        "toplam_birikim":  toplam_birikim,
        "toplam_dagitim":  toplam_dagitim,
        "toplam_mal_devri": toplam_mal_devri,
    }


# ── Test ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Test verisi
    test_sonuc = {
        "senaryo": "🟢 Birikim",
        "wyckoff_faz": "Accumulation_C",
        "guven_skoru": 8.2,
        "net_alis": 12.4,
        "net_satis": 1.2,
        "fd_pct": 0.8,
        "fd_supheli": False,
        "mkk_trend": "azalıyor",
        "en_guclu_alan": "TERA +12.4%",
        "en_guclu_satan": "YABANCI -1.2%",
    }

    hafiza = hafiza_guncelle("TEST", "20260522", test_sonuc, "Test yorumu.")
    print("Hafıza kaydedildi:")
    print(json.dumps(hafiza, ensure_ascii=False, indent=2))
    print()
    print(hafiza_ozet("TEST"))
