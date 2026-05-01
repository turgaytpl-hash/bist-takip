"""
watchlist_depo.py — Trader Not Defteri & Alarm Sistemi
Çoklu alarm desteği — aynı hisseye birden fazla alarm satırı
"""

import json
from pathlib import Path
from datetime import datetime

WATCHLIST_FILE = Path("data/watchlist.json")
WATCHLIST_FILE.parent.mkdir(exist_ok=True)

def _yukle() -> list:
    """Liste olarak sakla — her satır bağımsız alarm"""
    if WATCHLIST_FILE.exists():
        with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Eski dict formatını listeye çevir
            if isinstance(data, dict):
                yeni = []
                for h, v in data.items():
                    v["id"] = f"{h}_1"
                    yeni.append(v)
                return yeni
            return data
    return []

def _kaydet(data: list):
    with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _yeni_id(hisse: str, mevcut: list) -> str:
    """Hisse için benzersiz ID üret"""
    mevcut_idler = [a.get("id","") for a in mevcut]
    i = 1
    while f"{hisse}_{i}" in mevcut_idler:
        i += 1
    return f"{hisse}_{i}"

def alarm_ekle(hisse: str, seviye: float, yon: str,
               teknik_alarmlar: list = None, not_: str = "") -> str:
    """
    Yeni alarm satırı ekle.
    yon: "yukari" veya "asagi"
    Returns: alarm ID
    """
    data = _yukle()
    alarm_id = _yeni_id(hisse.upper(), data)
    
    data.append({
        "id":              alarm_id,
        "hisse":           hisse.upper(),
        "seviye":          seviye,
        "yon":             yon,          # "yukari" veya "asagi"
        "teknik_alarmlar": teknik_alarmlar or [],
        "not":             not_,
        "eklenme_tarihi":  datetime.now().strftime("%Y-%m-%d"),
        "durum":           "bekliyor",   # bekliyor / tetiklendi / gecti
        "tetikleme_tarihi": None,
        "tetikleme_fiyat":  None,
    })
    _kaydet(data)
    return alarm_id

def alarm_sil(alarm_id: str) -> bool:
    data = _yukle()
    yeni = [a for a in data if a.get("id") != alarm_id]
    if len(yeni) < len(data):
        _kaydet(yeni)
        return True
    return False

def alarm_guncelle(alarm_id: str, seviye: float = None,
                   teknik_alarmlar: list = None, not_: str = None,
                   durum: str = None):
    data = _yukle()
    for a in data:
        if a.get("id") == alarm_id:
            if seviye is not None:         a["seviye"] = seviye
            if teknik_alarmlar is not None: a["teknik_alarmlar"] = teknik_alarmlar
            if not_ is not None:           a["not"] = not_
            if durum is not None:          a["durum"] = durum
    _kaydet(data)

def alarm_tetiklendi_kaydet(alarm_id: str, fiyat: float):
    data = _yukle()
    for a in data:
        if a.get("id") == alarm_id:
            a["durum"]            = "tetiklendi"
            a["tetikleme_tarihi"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            a["tetikleme_fiyat"]  = fiyat
    _kaydet(data)

def liste_al() -> list:
    return _yukle()

def hisse_alarmlari(hisse: str) -> list:
    return [a for a in _yukle() if a.get("hisse") == hisse.upper()]

def alarm_sayisi() -> int:
    return len(_yukle())

TEKNİK_ALARMLAR = [
    "200MA Kırılımı",
    "RS 200MA Kırılımı",
    "RS 200MA Yaklaşıyor (%5)",
    "20 Reverse",
    "150 Reverse",
    "Altın Tavuk",
    "MACD Erken",
    "Haftalık Dinlen",
]
