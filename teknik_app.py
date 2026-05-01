"""
teknik_app.py — Teknik Analiz + Performans Takip
Çalıştır: python -m streamlit run teknik_app.py
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
from datetime import date
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from tarama_depo import (sinyal_kaydet, performans_hesapla,
                          tarama_ozet, son_sinyaller, db_ozet, TARAMALAR)
from watchlist_tab import watchlist_sekme
from fon_analizi_tab import tab_fon_analizi

st.set_page_config(page_title="Teknik Analiz", layout="wide")
st.title("📈 Teknik Analiz — BIST Tarayıcı")

@st.cache_data
def bist_listesi_yukle() -> list:
    p = Path("data/bist_fd.xlsx")
    if not p.exists():
        return []
    df = pd.read_excel(p, header=None)
    kodlar = df.iloc[:, 0].astype(str).str.strip().str.upper()
    return kodlar[kodlar.str.len() >= 3].tolist()

@st.cache_data(ttl=3600)
def veri_cek(hisse: str, period: str = "2y", interval: str = "1d") -> pd.DataFrame:
    ticker = hisse if hisse.endswith(".IS") else hisse + ".IS"
    try:
        df = yf.download(ticker, period=period, interval=interval,
                         progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df if not df.empty else pd.DataFrame()
    except:
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def bist100_cek(period: str = "2y") -> pd.Series:
    try:
        df = yf.download("XU100.IS", period=period, interval="1d",
                         progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df["Close"].squeeze().astype(float) if not df.empty else pd.Series()
    except:
        return pd.Series()

def teknik_hesapla(df: pd.DataFrame, bist100: pd.Series = None) -> dict:
    if df.empty or len(df) < 50:
        return {}

    close  = df["Close"].squeeze().astype(float)
    volume = df["Volume"].squeeze().astype(float) if "Volume" in df.columns else None
    high   = df["High"].squeeze().astype(float)   if "High"   in df.columns else None
    low    = df["Low"].squeeze().astype(float)     if "Low"    in df.columns else None
    fiyat  = float(close.iloc[-1])
    r      = {"fiyat": round(fiyat, 2)}

    for p in [20, 50, 100, 150, 200]:
        if len(close) >= p:
            gha  = float(close.rolling(p).mean().iloc[-1])
            r[f"sma{p}"]  = round(gha, 2)
            r[f"uzak{p}"] = round((fiyat / gha - 1) * 100, 2)
        else:
            r[f"sma{p}"] = r[f"uzak{p}"] = None

    if len(close) >= 21:
        r["sma20_dun"]  = round(float(close.rolling(20).mean().iloc[-2]), 2)
    if len(close) >= 201:
        r["sma200_dun"] = round(float(close.rolling(200).mean().iloc[-2]), 2)
    if len(close) >= 151:
        r["sma150_dun"] = round(float(close.rolling(150).mean().iloc[-2]), 2)
    if low is not None and len(low) >= 2:
        r["low_dun"] = round(float(low.iloc[-2]), 2)
    r["close_dun"] = round(float(close.iloc[-2]), 2) if len(close) >= 2 else None

    son252 = close.tail(252)
    r["yil_yuksek"] = round(float(son252.max()), 2)
    r["yil_dusuk"]  = round(float(son252.min()), 2)
    r["ath_uzak"]   = round((fiyat / float(son252.max()) - 1) * 100, 2)
    r["atl_uzak"]   = round((fiyat / float(son252.min()) - 1) * 100, 2)

    if len(close) >= 244:
        r["sma200_22"] = float(close.tail(200).mean()) > float(close.tail(222).head(200).mean())
        r["sma200_44"] = float(close.tail(200).mean()) > float(close.tail(244).head(200).mean())
    else:
        r["sma200_22"] = r["sma200_44"] = None

    if high is not None and low is not None and len(df) >= 15:
        try:
            atr_s = ta.atr(high, low, close, length=14)
            atr   = float(atr_s.iloc[-1])
            r["atr"]        = round(atr, 2)
            r["atr_pct"]    = round(atr / fiyat * 100, 2)
            r["atr_uzak20"] = round(abs(fiyat - r["sma20"]) / atr, 2) if r.get("sma20") else None
        except:
            r["atr"] = r["atr_pct"] = r["atr_uzak20"] = None
    else:
        r["atr"] = r["atr_pct"] = r["atr_uzak20"] = None

    if low is not None and len(close) >= 21:
        sma20_seri = close.rolling(20).mean()
        r["sma20_dokundu"] = bool((low.iloc[-4:-1] <= sma20_seri.iloc[-4:-1]).any())
    else:
        r["sma20_dokundu"] = None

    if low is not None and len(close) >= 201:
        sma200_seri = close.rolling(200).mean()
        r["sma200_dokundu"] = bool((low.iloc[-6:-1] <= sma200_seri.iloc[-6:-1] * 1.01).any())
    else:
        r["sma200_dokundu"] = None

    if r.get("sma200") and r.get("sma200_dun") and r.get("close_dun"):
        r["sma200_kirildi"] = (fiyat > r["sma200"]) and (r["close_dun"] <= r["sma200_dun"])
    else:
        r["sma200_kirildi"] = None

    if low is not None and r.get("sma150") and r.get("sma100") and r.get("sma200"):
        dun_low = r.get("low_dun")
        r["sma150_dokundu"] = (
            dun_low is not None and
            (dun_low <= r["sma150"] * 1.025 or dun_low <= r["sma100"] * 1.02)
        )
    else:
        r["sma150_dokundu"] = None

    try:
        macd_df = ta.macd(close, fast=12, slow=26, signal=9)
        if macd_df is not None and len(macd_df.columns) >= 3:
            cols = macd_df.columns.tolist()
            r["macd"]      = round(float(macd_df[cols[0]].iloc[-1]), 4)
            r["macd_sig"]  = round(float(macd_df[cols[2]].iloc[-1]), 4)
            r["macd_val1"] = round(float(macd_df[cols[0]].iloc[-2]), 4)
            r["macd_sig1"] = round(float(macd_df[cols[2]].iloc[-2]), 4)
        else:
            r["macd"] = r["macd_sig"] = r["macd_val1"] = r["macd_sig1"] = None
    except:
        r["macd"] = r["macd_sig"] = r["macd_val1"] = r["macd_sig1"] = None

    try:
        rsi_s = ta.rsi(close, length=14)
        r["rsi"]  = round(float(rsi_s.iloc[-1]), 1)
        r["rsi1"] = round(float(rsi_s.iloc[-2]), 1)
    except:
        r["rsi"] = r["rsi1"] = None

    try:
        ich = ta.ichimoku(high, low, close, tenkan=9, kijun=26, senkou=52)
        if ich is not None:
            cols = ich[0].columns.tolist()
            r["tenkan"] = float(ich[0][cols[0]].iloc[-1]) if len(cols) > 0 else None
            r["kijun"]  = float(ich[0][cols[1]].iloc[-1]) if len(cols) > 1 else None
        else:
            r["tenkan"] = r["kijun"] = None
    except:
        r["tenkan"] = r["kijun"] = None

    if volume is not None and len(volume) >= 51:
        vol_b  = float(volume.iloc[-1])
        vol_50 = float(volume.tail(51).iloc[:-1].mean())
        vol_20 = float(volume.tail(21).iloc[:-1].mean())
        vol_10 = float(volume.tail(11).iloc[:-1].mean())
        r["hac_oran"]    = round(vol_b / vol_50 * 100, 1) if vol_50 > 0 else None
        r["hac_oran_20"] = round(vol_b / vol_20 * 100, 1) if vol_20 > 0 else None
        r["birikim"]     = round(vol_10 / vol_50 * 100, 1) if vol_50 > 0 else None
    else:
        r["hac_oran"] = r["hac_oran_20"] = r["birikim"] = None

    if len(close) >= 2:
        r["roc1"] = round((float(close.iloc[-1]) / float(close.iloc[-2]) - 1) * 100, 2)
    else:
        r["roc1"] = None

    if bist100 is not None and not bist100.empty:
        try:
            ortak = close.index.intersection(bist100.index)
            if len(ortak) >= 63:
                h_s = close.reindex(ortak)
                b_s = bist100.reindex(ortak)
                rs_seri = h_s / b_s
                if len(rs_seri) >= 200:
                    rs_sma200     = float(rs_seri.rolling(200).mean().iloc[-1])
                    rs_sma200_dun = float(rs_seri.rolling(200).mean().iloc[-2]) if len(rs_seri) >= 201 else None
                    rs_bugun      = float(rs_seri.iloc[-1])
                    bist100_bugun = float(b_s.iloc[-1])
                    r["rs_sma200_tl"]   = round(rs_sma200 * bist100_bugun, 2)
                    r["rs_sma200_uzak"] = round((rs_bugun / rs_sma200 - 1) * 100, 2)
                    if rs_sma200_dun:
                        rs_dun = float(rs_seri.iloc[-2])
                        r["rs_200_kirildi"] = (rs_bugun > rs_sma200) and (rs_dun <= rs_sma200_dun)
                        r["rs_200_ustunde"] = rs_bugun > rs_sma200
                    else:
                        r["rs_200_kirildi"] = r["rs_200_ustunde"] = None
                else:
                    r["rs_sma200_tl"] = r["rs_sma200_uzak"] = None
                    r["rs_200_kirildi"] = r["rs_200_ustunde"] = None
                perfs = {}
                for gun in [63, 126, 189, 252]:
                    if len(ortak) >= gun + 1:
                        perfs[gun] = (h_s.iloc[-1]/h_s.iloc[-(gun+1)]-1)*100 - \
                                     (b_s.iloc[-1]/b_s.iloc[-(gun+1)]-1)*100
                p63  = perfs.get(63, 0)
                p126 = perfs.get(126, p63)
                p189 = perfs.get(189, p63)
                p252 = perfs.get(252, p63)
                r["rs_komp"] = round((p63*2 + p126 + p189 + p252) / 5, 1)
            else:
                r["rs_komp"] = r["rs_sma200_tl"] = r["rs_sma200_uzak"] = None
                r["rs_200_kirildi"] = r["rs_200_ustunde"] = None
        except:
            r["rs_komp"] = r["rs_sma200_tl"] = r["rs_sma200_uzak"] = None
            r["rs_200_kirildi"] = r["rs_200_ustunde"] = None
    else:
        r["rs_komp"] = r["rs_sma200_tl"] = r["rs_sma200_uzak"] = None
        r["rs_200_kirildi"] = r["rs_200_ustunde"] = None

    return r

def teknik_haftalik(df_w: pd.DataFrame) -> dict:
    if df_w.empty or len(df_w) < 20:
        return {}
    close = df_w["Close"].squeeze().astype(float)
    low   = df_w["Low"].squeeze().astype(float) if "Low" in df_w.columns else None
    fiyat = float(close.iloc[-1])
    r = {}
    for p in [20, 50]:
        if len(close) >= p:
            sma = float(close.rolling(p).mean().iloc[-1])
            r[f"w_sma{p}"]  = round(sma, 2)
            r[f"w_uzak{p}"] = round((fiyat / sma - 1) * 100, 2)
        else:
            r[f"w_sma{p}"] = r[f"w_uzak{p}"] = None

    if low is not None and len(close) >= 21:
        sma20_w = close.rolling(20).mean()
        sma50_w = close.rolling(50).mean() if len(close) >= 50 else None
        son3_low = low.iloc[-4:-1]
        dokunan20 = (son3_low <= sma20_w.iloc[-4:-1]).any()
        dokunan50 = (son3_low <= sma50_w.iloc[-4:-1]).any() if sma50_w is not None else False
        r["w_dokundu"] = bool(dokunan20 or dokunan50)
        r["w_yukari"]  = float(close.iloc[-1]) > float(close.iloc[-2])
        if sma50_w is not None:
            sikisman = 0
            for i in range(1, min(52, len(close))):
                f   = float(close.iloc[-i])
                s20 = float(sma20_w.iloc[-i]) if not pd.isna(sma20_w.iloc[-i]) else None
                s50 = float(sma50_w.iloc[-i]) if not pd.isna(sma50_w.iloc[-i]) else None
                if s20 and s50 and s50 <= f <= s20 * 1.08:
                    sikisman += 1
                else:
                    break
            r["w_sikisman_hafta"] = sikisman
        else:
            r["w_sikisman_hafta"] = None
    else:
        r["w_dokundu"] = r["w_yukari"] = r["w_sikisman_hafta"] = None

    # ── Haftalık MACD ──
    try:
        macd_df = ta.macd(close, fast=12, slow=26, signal=9)
        if macd_df is not None and len(macd_df.columns) >= 3:
            cols = macd_df.columns.tolist()
            r["w_macd"]      = round(float(macd_df[cols[0]].iloc[-1]), 4)
            r["w_macd_sig"]  = round(float(macd_df[cols[2]].iloc[-1]), 4)
            r["w_macd1"]     = round(float(macd_df[cols[0]].iloc[-2]), 4)
            r["w_macd_sig1"] = round(float(macd_df[cols[2]].iloc[-2]), 4)
        else:
            r["w_macd"] = r["w_macd_sig"] = r["w_macd1"] = r["w_macd_sig1"] = None
    except:
        r["w_macd"] = r["w_macd_sig"] = r["w_macd1"] = r["w_macd_sig1"] = None

    # ── Haftalık RSI ──
    try:
        rsi_s = ta.rsi(close, length=14)
        r["w_rsi"]  = round(float(rsi_s.iloc[-1]), 1)
        r["w_rsi1"] = round(float(rsi_s.iloc[-2]), 1)
    except:
        r["w_rsi"] = r["w_rsi1"] = None

    return r

# ─── TARAMA FONKSİYONLARI ────────────────────────────────────────────────────

def tara_altin_tavuk(r: dict) -> bool:
    roc  = r.get("roc1")
    macd = r.get("macd");    sig = r.get("macd_sig")
    m1   = r.get("macd_val1"); s1 = r.get("macd_sig1")
    tenk = r.get("tenkan");  kij = r.get("kijun")
    if None in [roc, macd, sig, m1, s1, tenk, kij]: return False
    cross = (macd > sig) and (m1 <= s1)
    return (1 < roc < 10) and cross and (tenk > kij)

def tara_20_reverse(r: dict) -> bool:
    fiyat     = r.get("fiyat");  sma20     = r.get("sma20")
    sma50     = r.get("sma50");  low_dun   = r.get("low_dun")
    close_dun = r.get("close_dun")
    hac_20    = r.get("hac_oran_20")
    hac_50    = r.get("hac_oran")
    if None in [fiyat, sma20, sma50, low_dun, close_dun]: return False
    hac_ok = True
    if hac_20 is not None:
        hac_ok = hac_20 >= 120
    elif hac_50 is not None:
        hac_ok = hac_50 >= 120
    return (
        fiyat > sma50 and
        sma20 > sma50 and
        low_dun <= sma20 * 1.025 and
        fiyat > sma20 and
        fiyat > close_dun and
        hac_ok and
        fiyat > sma50 * 1.02
    )

def tara_200_reverse(r: dict) -> bool:
    fiyat   = r.get("fiyat");  sma200  = r.get("sma200")
    kirildi = r.get("sma200_kirildi"); uzak200 = r.get("uzak200")
    if None in [fiyat, sma200, uzak200]: return False
    bugun_kirilim = kirildi is True
    yakin_kirilim = (fiyat > sma200) and (0 < uzak200 <= 10)
    return bugun_kirilim or yakin_kirilim

def tara_150_reverse(r: dict) -> bool:
    fiyat    = r.get("fiyat");  sma200 = r.get("sma200")
    sma150   = r.get("sma150"); sma100 = r.get("sma100")
    uzak150  = r.get("uzak150"); rsi   = r.get("rsi")
    dokundu  = r.get("sma150_dokundu")
    close_dun = r.get("close_dun")
    if None in [fiyat, sma200, sma150, sma100, dokundu]: return False
    return (
        fiyat > sma200 and
        dokundu and
        fiyat > sma150 and
        (close_dun is None or fiyat > close_dun) and
        (uzak150 is not None and 0 < uzak150 <= 5) and
        (sma200 < sma150) and
        (rsi is None or rsi > 50)
    )

def tara_rs_200_kirilim(r: dict) -> bool:
    kirildi = r.get("rs_200_kirildi")
    ustunde = r.get("rs_200_ustunde")
    uzak    = r.get("rs_sma200_uzak")
    if kirildi: return True
    if ustunde and uzak is not None and 0 < uzak <= 10: return True
    if uzak is not None and -5 <= uzak < 0: return True
    return False

def rs_200_kategori(r: dict) -> str:
    kirildi = r.get("rs_200_kirildi")
    ustunde = r.get("rs_200_ustunde")
    uzak    = r.get("rs_sma200_uzak")
    tl      = r.get("rs_sma200_tl")
    tl_str  = f" ({tl:.2f}TL)" if tl else ""
    if kirildi: return f"🔥 BUGÜN KIRILDI{tl_str}"
    if ustunde and uzak is not None:
        return f"🟢 Üstünde %{uzak:+.1f}{tl_str}" if uzak <= 10 else f"🟡 Üstünde %{uzak:+.1f}{tl_str}"
    if uzak is not None:
        return f"🟡 Yaklaşıyor %{uzak:.1f}{tl_str}" if -5 <= uzak < 0 else f"🔴 Uzak %{uzak:.1f}{tl_str}"
    return "—"

def tara_haftalik_macd_erken(rw: dict) -> bool:
    """
    Haftalık MACD Erken Uyarı — Matriks formülü birebir:
    Trigger <= Önceki Trigger (trigger azalıyor)
    MACD > Önceki MACD (MACD artıyor)
    Trigger >= 0 (pozitif bölgede)
    MACD >= 0 (pozitif bölgede)
    RSI > Önceki RSI (RSI artıyor)
    RSI < 65 (aşırı alım yok)
    """
    macd  = rw.get("w_macd");    sig   = rw.get("w_macd_sig")
    macd1 = rw.get("w_macd1");   sig1  = rw.get("w_macd_sig1")
    rsi   = rw.get("w_rsi");     rsi1  = rw.get("w_rsi1")
    if None in [macd, sig, macd1, sig1, rsi, rsi1]: return False
    return (
        sig  <= sig1  and   # Trigger azalıyor
        macd > macd1  and   # MACD artıyor
        sig  >= 0     and   # Trigger >= 0
        macd >= 0     and   # MACD >= 0
        rsi  > rsi1   and   # RSI artıyor
        rsi  < 65           # Aşırı alım yok
    )
    if not rw: return False
    dokundu = rw.get("w_dokundu"); yukari = rw.get("w_yukari")
    uzak20  = rw.get("w_uzak20")
    if None in [dokundu, yukari, uzak20]: return False
    return dokundu and yukari and 0 < uzak20 <= 8

def tara_macd_erken(r: dict) -> bool:
    return False  # Kaldırıldı

def ikon_rs_200(r: dict) -> str:
    return rs_200_kategori(r)

def tara_minervini(r: dict) -> tuple[bool, int, list]:
    """
    Matriks formülü birebir:
    C > SMA50
    SMA50 > SMA150 > SMA200
    SMA200 > 22 gün önceki SMA200
    SMA200 > 44 gün önceki SMA200
    C >= 52H düşük × 1.30
    C >= 52H yüksek × 0.75
    (C - SMA50) / SMA50 <= 0.15
    V > SMA50_V × 1.50
    """
    fiyat = r.get("fiyat", 0)
    sartlar = [
        ("C>SMA50",       r.get("uzak50") is not None and r["uzak50"] > 0),
        ("SMA50>150>200", all(r.get(f"sma{p}") for p in [50,150,200]) and
                          r.get("sma50",0) > r.get("sma150",0) > r.get("sma200",0)),
        ("SMA200↑22g",    r.get("sma200_22") is True),
        ("SMA200↑44g",    r.get("sma200_44") is True),
        ("ATL+30%",       r.get("yil_dusuk") is not None and fiyat >= r["yil_dusuk"] * 1.30),
        ("ATH-25%",       r.get("yil_yuksek") is not None and fiyat >= r["yil_yuksek"] * 0.75),
        ("SMA50≤15%",     r.get("uzak50") is not None and 0 < r["uzak50"] <= 15),
        ("Hac>150%",      r.get("hac_oran") is not None and r["hac_oran"] >= 150),
    ]
    skor  = sum(1 for _, v in sartlar if v)
    eksik = [ad for ad, v in sartlar if not v]
    # Tüm 8 şart geçmeli
    return skor == 8, skor, eksik

def ikon_hac(v):
    if v is None: return "—"
    if v >= 150: return f"🟢 %{v:.0f}"
    if v >= 70:  return f"🟡 %{v:.0f}"
    return f"🔴 %{v:.0f}"

def ikon_atr(v):
    if v is None: return "—"
    if v >= 2.5: return f"🔴 {v:.1f}x"
    if v >= 1.5: return f"🟡 {v:.1f}x"
    return f"🟢 {v:.1f}x"

def ikon_rs(v):
    if v is None: return "—"
    if v > 10:  return f"🟢 {v:+.1f}"
    if v > 0:   return f"🟡 {v:+.1f}"
    return f"🔴 {v:+.1f}"

def ikon_degisim(v):
    if v is None: return "—"
    if v > 5:   return f"🟢 %{v:+.1f}"
    if v > 0:   return f"🟡 %{v:+.1f}"
    if v > -5:  return f"🟠 %{v:+.1f}"
    return f"🔴 %{v:+.1f}"

def sikisman_ikonu(hafta):
    if hafta is None: return "—"
    if hafta >= 26: return f"🔴 {hafta}H (PATLAMA YAKLAŞIYOR!)"
    if hafta >= 10: return f"🟡 {hafta}H (Olgunlaşıyor)"
    return f"🟢 {hafta}H (Erken)"

def _yukle_db() -> pd.DataFrame:
    """Sinyal DB'yi direkt yükle"""
    from pathlib import Path
    p = Path("data/tarama_sinyaller.parquet")
    if p.exists():
        return pd.read_parquet(p)
    return pd.DataFrame()

# ══════════════════════════════════════════════════════════════════════════════
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🔔 Takip & Alarm",
    "🔍 Hisse Detay",
    "🚀 BIST FD Tarama",
    "📊 Performans Takip",
    "📁 Fon Analizi",
])

with tab1:
    watchlist_sekme(
        veri_cek_fn=veri_cek,
        teknik_hesapla_fn=teknik_hesapla,
        teknik_haftalik_fn=teknik_haftalik,
        bist100_cek_fn=bist100_cek
    )

with tab2:
    st.subheader("Tek Hisse Teknik Kart")
    col1,col2,col3 = st.columns([2,1,1])
    with col1: hisse_sec = st.text_input("Hisse","THYAO").upper().strip()
    with col2: period2   = st.selectbox("Periyot",["1y","2y"],index=1,key="p2")
    with col3: detay_btn = st.button("📊 Getir",type="primary",use_container_width=True)

    if detay_btn and hisse_sec:
        with st.spinner(f"{hisse_sec} yükleniyor..."):
            df      = veri_cek(hisse_sec, period2)
            df_w    = veri_cek(hisse_sec, period2, "1wk")
            bist100 = bist100_cek(period2)
        if df.empty:
            st.error("Veri çekilemedi.")
        else:
            r  = teknik_hesapla(df, bist100)
            rw = teknik_haftalik(df_w)
            if not r:
                st.error("Yetersiz veri.")
            else:
                fiyat = r["fiyat"]
                st.markdown(f"### {hisse_sec} — {fiyat:.2f} TL")
                c1,c2,c3,c4 = st.columns(4)
                c1.metric("200 SMA", f"{r.get('sma200','—')}", f"{r.get('uzak200',0):+.1f}%")
                c2.metric("150 SMA", f"{r.get('sma150','—')}", f"{r.get('uzak150',0):+.1f}%")
                c3.metric("50 SMA",  f"{r.get('sma50','—')}",  f"{r.get('uzak50',0):+.1f}%")
                c4.metric("20 SMA",  f"{r.get('sma20','—')}",  f"{r.get('uzak20',0):+.1f}%")
                c1,c2,c3,c4 = st.columns(4)
                c1.metric("RS Komp",   ikon_rs(r.get("rs_komp")))
                c2.metric("RS 200 MA", ikon_rs_200(r))
                c3.metric("RS 200 TL", f"{r.get('rs_sma200_tl','—')} TL")
                c4.metric("RS Uzaklık",f"{r.get('rs_sma200_uzak',0):+.1f}%" if r.get('rs_sma200_uzak') else "—")
                c1,c2,c3,c4,c5 = st.columns(5)
                c1.metric("ATR(TL)",  f"{r.get('atr','—')}")
                c2.metric("ATR%",     f"%{r.get('atr_pct','—')}")
                c3.metric("20MA ATR", ikon_atr(r.get("atr_uzak20")))
                c4.metric("Hacim",    ikon_hac(r.get("hac_oran")))
                c5.metric("RSI",      f"{r.get('rsi','—')}")
                if rw:
                    st.divider()
                    st.markdown("**📅 Haftalık Durum:**")
                    c1,c2,c3,c4,c5 = st.columns(5)
                    c1.metric("H.SMA20",   f"{rw.get('w_sma20','—')}", f"{rw.get('w_uzak20',0):+.1f}%")
                    c2.metric("H.SMA50",   f"{rw.get('w_sma50','—')}", f"{rw.get('w_uzak50',0):+.1f}%")
                    c3.metric("H.Dokundu", "✅" if rw.get("w_dokundu") else "❌")
                    c4.metric("H.Yönü",    "📈" if rw.get("w_yukari") else "📉")
                    c5.metric("Sıkışma",   sikisman_ikonu(rw.get("w_sikisman_hafta")))
                st.divider()
                gecti_min, mskor, eksik = tara_minervini(r)
                sinyaller = {
                    "🐔 Altın Tavuk":   tara_altin_tavuk(r),
                    "🔄 20 Reverse":    tara_20_reverse(r),
                    f"⭐ Min {mskor}/8": gecti_min,
                    "🚀 MACD Erken":    tara_haftalik_macd_erken(rw) if rw else False,
                }
                cols = st.columns(len(sinyaller))
                for col,(isim,durum) in zip(cols,sinyaller.items()):
                    col.metric(isim,"✅" if durum else "❌")
                if eksik:
                    st.caption(f"❌ Minervini eksik: {' | '.join(eksik)}")
                st.divider()
                close = df["Close"].squeeze().astype(float)
                fig = make_subplots(rows=2,cols=1,shared_xaxes=True,
                                    row_heights=[0.75,0.25],vertical_spacing=0.03)
                fig.add_trace(go.Candlestick(
                    x=df.index,open=df["Open"].squeeze(),high=df["High"].squeeze(),
                    low=df["Low"].squeeze(),close=close,name="Fiyat",
                    increasing_line_color="#26a69a",decreasing_line_color="#ef5350"
                ),row=1,col=1)
                for p,rc in {20:"#4fc3f7",50:"#81c784",150:"#ff9800",200:"#ef5350"}.items():
                    if len(close) >= p:
                        fig.add_trace(go.Scatter(x=df.index,y=close.rolling(p).mean(),
                            name=f"{p}SMA",line=dict(color=rc,width=1.2)),row=1,col=1)
                if "Volume" in df.columns:
                    vol = df["Volume"].squeeze().astype(float)
                    fig.add_trace(go.Bar(x=df.index,y=vol,name="Hacim",
                        marker_color="rgba(100,150,250,0.35)"),row=2,col=1)
                    fig.add_trace(go.Scatter(x=df.index,y=vol.rolling(50).mean(),
                        name="50H Ort",line=dict(color="#ffb74d",width=1,dash="dot")),row=2,col=1)
                fig.update_layout(height=550,paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(14,17,23,1)",font=dict(color="white"),
                    xaxis_rangeslider_visible=False,legend=dict(orientation="h",y=1.02),
                    margin=dict(l=0,r=0,t=30,b=0))
                fig.update_xaxes(gridcolor="rgba(255,255,255,0.05)")
                fig.update_yaxes(gridcolor="rgba(255,255,255,0.05)")
                st.plotly_chart(fig,use_container_width=True)

with tab3:
    st.subheader("🚀 BIST FD — Otomatik Tarama")
    bist_liste = bist_listesi_yukle()
    if not bist_liste:
        st.error("❌ bist_fd.xlsx bulunamadı!")
    else:
        st.success(f"✅ {len(bist_liste)} hisse yüklendi")

        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown("**Tarama seç:**")
            chk_tavuk = st.checkbox("🐔 Altın Tavuk — ROC(1)>1<10 + MACD CROSS + Tenkan>Kijun")
            chk_rev20 = st.checkbox("🔄 20 Reverse — C>SMA50 + Dün Low≤SMA20×1.025 + Hacim>SMA20×1.20")
            chk_min   = st.checkbox("⭐ Minervini — SMA50>150>200 + SMA200↑ + ATL+30% + ATH-25% + Hac>150%")
            chk_hmacd = st.checkbox("📡 Haftalık MACD Erken — Trigger↓ + MACD↑ + İkisi≥0 + RSI↑<65")
        with col2:
            period3   = st.selectbox("Periyot", ["1y","2y"], index=1, key="p3")
            kaydet_cb = st.checkbox("💾 Kaydet", value=True)

        tara3 = st.button("🚀 TARAMAYI BAŞLAT", type="primary",
                           use_container_width=True, key="b3")

        if tara3:
            aktif = []
            if chk_tavuk: aktif.append("Altın Tavuk")
            if chk_rev20: aktif.append("20 Reverse")
            if chk_min:   aktif.append("Minervini")
            if chk_hmacd: aktif.append("Haftalık MACD")

            if not aktif:
                st.warning("En az bir tarama seç!")
            else:
                bist100 = bist100_cek(period3)
                prog3   = st.progress(0)
                rows3   = []
                kayit_buffer = {t: [] for t in aktif}

                for i, hisse in enumerate(bist_liste):
                    prog3.progress((i+1)/len(bist_liste),
                                   text=f"⏳ {hisse} ({i+1}/{len(bist_liste)})")
                    df = veri_cek(hisse, period3)
                    if df.empty: continue
                    r  = teknik_hesapla(df, bist100)
                    if not r: continue
                    df_w = veri_cek(hisse, period3, "1wk") if "Haftalık MACD" in aktif else pd.DataFrame()
                    rw   = teknik_haftalik(df_w) if not df_w.empty else {}

                    sinyal_sonuc = {}
                    gec_sayisi   = 0

                    if "Altın Tavuk" in aktif:
                        g = tara_altin_tavuk(r)
                        sinyal_sonuc["🐔"] = "✅" if g else "❌"
                        if g:
                            gec_sayisi += 1
                            kayit_buffer["Altın Tavuk"].append({
                                "hisse": hisse, "giris_fiyat": r["fiyat"],
                                "sma20": r.get("sma20"), "sma200": r.get("sma200"),
                                "atr": r.get("atr"), "rs_komp": r.get("rs_komp")
                            })

                    if "20 Reverse" in aktif:
                        g = tara_20_reverse(r)
                        sinyal_sonuc["🔄"] = "✅" if g else "❌"
                        if g:
                            gec_sayisi += 1
                            kayit_buffer["20 Reverse"].append({
                                "hisse": hisse, "giris_fiyat": r["fiyat"],
                                "sma20": r.get("sma20"), "sma200": r.get("sma200"),
                                "atr": r.get("atr"), "rs_komp": r.get("rs_komp")
                            })

                    if "Minervini" in aktif:
                        g, ms, _ = tara_minervini(r)
                        sinyal_sonuc["⭐"] = f"✅ {ms}/8" if g else f"❌ {ms}/8"
                        if g:
                            gec_sayisi += 1
                            kayit_buffer["Minervini"].append({
                                "hisse": hisse, "giris_fiyat": r["fiyat"],
                                "sma20": r.get("sma20"), "sma200": r.get("sma200"),
                                "atr": r.get("atr"), "rs_komp": r.get("rs_komp")
                            })

                    if "Haftalık MACD" in aktif:
                        g = tara_haftalik_macd_erken(rw)
                        sinyal_sonuc["📡"] = "✅" if g else "❌"
                        if g:
                            gec_sayisi += 1
                            kayit_buffer["Haftalık MACD"].append({
                                "hisse": hisse, "giris_fiyat": r["fiyat"],
                                "sma20": r.get("sma20"), "sma200": r.get("sma200"),
                                "atr": r.get("atr"), "rs_komp": r.get("rs_komp")
                            })

                    if gec_sayisi == 0: continue

                    rows3.append({
                        "Hisse":   hisse,
                        "Fiyat":   r.get("fiyat"),
                        "200SMA%": r.get("uzak200"),
                        "50SMA%":  r.get("uzak50"),
                        "20SMA%":  r.get("uzak20"),
                        "RS Komp": ikon_rs(r.get("rs_komp")),
                        "RSI":     r.get("rsi"),
                        "ATR(TL)": r.get("atr"),
                        "Hacim":   ikon_hac(r.get("hac_oran")),
                        **sinyal_sonuc
                    })

                prog3.empty()

                if kaydet_cb:
                    toplam_k = 0
                    for t_adi, liste in kayit_buffer.items():
                        if liste:
                            toplam_k += sinyal_kaydet(t_adi, liste)
                    if toplam_k > 0:
                        st.success(f"💾 {toplam_k} sinyal kaydedildi!")

                df3 = pd.DataFrame(rows3)
                if df3.empty:
                    st.warning("Hiç hisse bulunamadı.")
                else:
                    df3 = df3.sort_values("200SMA%", ascending=False)
                    cols_met = st.columns(len(aktif) + 1)
                    cols_met[0].metric("Taranan", len(bist_liste))
                    for idx, t in enumerate(aktif):
                        ikon = "🐔" if t == "Altın Tavuk" else "🔄" if t == "20 Reverse" else "📊"
                        cols_met[idx+1].metric(f"{ikon} {t}", len(df3))

                    st.dataframe(df3.reset_index(drop=True),
                                 use_container_width=True, height=500,
                                 column_config={
                                     "200SMA%": st.column_config.NumberColumn(format="%.1f%%"),
                                     "50SMA%":  st.column_config.NumberColumn(format="%.1f%%"),
                                     "20SMA%":  st.column_config.NumberColumn(format="%.1f%%"),
                                     "RSI":     st.column_config.NumberColumn(format="%.0f"),
                                     "ATR(TL)": st.column_config.NumberColumn(format="%.2f"),
                                 })

                    buf = __import__("io").BytesIO()
                    with pd.ExcelWriter(buf, engine="openpyxl") as w:
                        df3.to_excel(w, index=False, sheet_name="AltınTavuk")
                    st.download_button("📥 Excel İndir", buf.getvalue(),
                                       file_name=f"altin_tavuk_{date.today()}.xlsx")

with tab4:
    st.subheader("📊 Performans Takip")

    db = _yukle_db()

    if db.empty:
        st.info("Henüz sinyal yok. Tab 3'te tarama yap ve 💾 Kaydet'i işaretle.")
    else:
        # ── Filtreler ──────────────────────────────────────────────────────
        col1, col2, col3 = st.columns([2, 2, 1])

        with col1:
            tarama_listesi = sorted(db["tarama"].unique().tolist())
            sec_tarama = st.selectbox("Tarama Adı", ["Hepsi"] + tarama_listesi)

        with col2:
            if sec_tarama == "Hepsi":
                tarih_listesi = sorted(db["tarih"].unique().tolist(), reverse=True)
            else:
                tarih_listesi = sorted(
                    db[db["tarama"] == sec_tarama]["tarih"].unique().tolist(),
                    reverse=True
                )
            sec_tarih = st.selectbox("Giriş Tarihi", ["Hepsi"] + tarih_listesi)

        with col3:
            perf_btn = st.button("🔄 Fiyat Güncelle", type="primary", use_container_width=True)

        # ── Filtrele ───────────────────────────────────────────────────────
        df_sin = db.copy()
        if sec_tarama != "Hepsi":
            df_sin = df_sin[df_sin["tarama"] == sec_tarama]
        if sec_tarih != "Hepsi":
            df_sin = df_sin[df_sin["tarih"] == sec_tarih]

        c1, c2, c3 = st.columns(3)
        c1.metric("Toplam Sinyal", len(df_sin))
        c2.metric("Tarama", sec_tarama)
        c3.metric("Tarih", sec_tarih)

        st.divider()

        if perf_btn and not df_sin.empty:
            # SADECE güncel fiyat çek — tarama yapma!
            hisseler_u = df_sin["hisse"].unique().tolist()
            prog_p = st.progress(0)
            guncel = {}
            for i, h in enumerate(hisseler_u):
                prog_p.progress((i+1)/len(hisseler_u), text=f"⏳ {h}")
                df_tmp = veri_cek(h, "3mo")
                if not df_tmp.empty:
                    guncel[h] = round(float(df_tmp["Close"].squeeze().iloc[-1]), 2)
            prog_p.empty()

            # Performans hesapla
            rows = []
            bugun = date.today().strftime("%Y-%m-%d")
            for _, row in df_sin.iterrows():
                h       = row["hisse"]
                giris   = row.get("giris_fiyat")
                guncel_f= guncel.get(h)
                if giris and guncel_f and float(giris) > 0:
                    degisim = round((float(guncel_f) / float(giris) - 1) * 100, 2)
                else:
                    degisim = None

                rows.append({
                    "Tarama":       row["tarama"],
                    "Giriş Tarihi": row["tarih"],
                    "Hisse":        h,
                    "Giriş Fiyatı": giris,
                    "Güncel Tarih": bugun,
                    "Güncel Fiyat": guncel_f,
                    "Değişim%":     degisim,
                    "Durum":        ikon_degisim(degisim)
                })

            df_goster = pd.DataFrame(rows).sort_values("Değişim%", ascending=False)

            # Özet
            valid = df_goster["Değişim%"].dropna()
            if len(valid) > 0:
                pozitif = (valid > 0).sum()
                c1,c2,c3,c4 = st.columns(4)
                c1.metric("Sinyal",      len(valid))
                c2.metric("Pozitif",     f"{pozitif}/{len(valid)}")
                c3.metric("Ort. Getiri", f"%{valid.mean():.1f}")
                c4.metric("En İyi",      f"%{valid.max():.1f}")

            st.dataframe(
                df_goster[["Tarama","Giriş Tarihi","Hisse",
                           "Giriş Fiyatı","Güncel Tarih","Güncel Fiyat","Durum"]],
                use_container_width=True, height=500, hide_index=True,
                column_config={
                    "Giriş Fiyatı": st.column_config.NumberColumn(format="%.2f"),
                    "Güncel Fiyat": st.column_config.NumberColumn(format="%.2f"),
                }
            )

            buf = __import__("io").BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as w:
                df_goster.to_excel(w, index=False, sheet_name="Performans")
            st.download_button("📥 Excel İndir", buf.getvalue(),
                               file_name=f"performans_{date.today()}.xlsx")

        else:
            # Henüz güncellenmemiş — kayıtlı sinyalleri göster
            st.markdown(f"**{len(df_sin)} kayıtlı sinyal** — Fiyat Güncelle'ye bas:")
            st.dataframe(
                df_sin[["tarama","tarih","hisse","giris_fiyat"]].rename(columns={
                    "tarama":      "Tarama",
                    "tarih":       "Giriş Tarihi",
                    "hisse":       "Hisse",
                    "giris_fiyat": "Giriş Fiyatı"
                }),
                use_container_width=True, height=450, hide_index=True,
                column_config={
                    "Giriş Fiyatı": st.column_config.NumberColumn(format="%.2f"),
                }
            )
    st.subheader("📊 Performans Takip")

    # ── Veri Temizleme ────────────────────────────────────────────────────
    with st.expander("🗑️ Eski Verileri Temizle"):
        st.warning("Silinecek taramalar: 150 Reverse, 200 Reverse, Haftalık Dinlen, MACD Erken, RS 200 Kırılım ve eski Minervini kayıtları")
        if st.button("🗑️ Eski Taramaları Sil", type="secondary"):
            from pathlib import Path
            import json
            p = Path("data/tarama_sinyaller.parquet")
            if p.exists():
                df_temiz = pd.read_parquet(p)
                # Sadece bugünkü aktif taramaları tut
                aktif_taramalar = ["Altın Tavuk", "20 Reverse", "Minervini", "Haftalık MACD"]
                df_temiz = df_temiz[df_temiz["tarama"].isin(aktif_taramalar)]
                df_temiz.to_parquet(p, index=False)
                st.success(f"✅ Temizlendi! {len(df_temiz)} kayıt kaldı.")
                st.rerun()
            else:
                st.info("Veri dosyası bulunamadı.")


with tab5:
    tab_fon_analizi()
