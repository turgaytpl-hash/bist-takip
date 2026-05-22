"""
siklik_tarama.py — Qullamaggie High Tight Flag Tarama
Tek tek veri çeker, hata toleranslı
"""

import yfinance as yf
import pandas as pd
import numpy as np
import os
import warnings
from datetime import datetime
import time

warnings.filterwarnings("ignore")

# ─── AYARLAR ──────────────────────────────────────────────────────────────────
BIST_FD_DOSYA   = "data/bist_fd.xlsx"
MIN_HACIM       = 1_000_000
BANT_ESIK       = 0.20
MA20_MAX_MESAFE = 0.07
MIN_MO6         = 20        # düşük tut, geniş tara
TOP_N           = 40
PERIOD          = "6mo"
XU100_TICKER    = "XU100.IS"
PAUSE           = 0.3

# ─── HİSSE LİSTESİ ────────────────────────────────────────────────────────────
def hisse_listesi_al():
    if os.path.exists(BIST_FD_DOSYA):
        df = pd.read_excel(BIST_FD_DOSYA)
        col = next((c for c in df.columns
                    if any(k in c.lower() for k in ["hisse","kod","sembol","ticker"])),
                   df.columns[0])
        lst = df[col].dropna().astype(str).str.strip().str.upper().tolist()
        print(f"  {len(lst)} hisse yüklendi ({BIST_FD_DOSYA})")
        return lst
    print("⚠️ bist_fd.xlsx bulunamadı")
    return ["THYAO","GARAN","EREGL","SISE","KCHOL","ASTOR","FONET","EUPWR"]

# ─── VERİ ÇEK ─────────────────────────────────────────────────────────────────
def hisse_veri_cek(hisse):
    try:
        df = yf.download(f"{hisse}.IS", period=PERIOD, interval="1d",
                         auto_adjust=True, progress=False, threads=False)
        if df is None or len(df) < 30:
            return None
        # Kolon adlarını düzleştir (MultiIndex gelebilir)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except:
        return None

def xu100_cek():
    try:
        df = yf.download(XU100_TICKER, period=PERIOD, interval="1d",
                         auto_adjust=True, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df["Close"].dropna()
    except:
        return None

# ─── ATR ──────────────────────────────────────────────────────────────────────
def atr_hesapla(high, low, close, n=14):
    prev  = close.shift(1)
    tr    = pd.concat([(high-low),(high-prev).abs(),(low-prev).abs()],axis=1).max(axis=1)
    return tr.rolling(n).mean()

# ─── ANALİZ ───────────────────────────────────────────────────────────────────
def hisse_analiz(hisse, xu100=None):
    df = hisse_veri_cek(hisse)
    if df is None:
        return None

    try:
        close = df["Close"].dropna()
        high  = df["High"].dropna()
        low   = df["Low"].dropna()
        vol   = df["Volume"].dropna()

        if len(close) < 30:
            return None

        son = float(close.iloc[-1])

        # Momentum
        m1 = (son/float(close.iloc[-21]) -1)*100 if len(close)>=21  else np.nan
        m3 = (son/float(close.iloc[-63]) -1)*100 if len(close)>=63  else np.nan
        m6 = (son/float(close.iloc[-126])-1)*100 if len(close)>=126 else np.nan

        # MA
        ma20 = float(close.rolling(20).mean().iloc[-1])
        ma50 = float(close.rolling(50).mean().iloc[-1]) if len(close)>=50 else np.nan

        d20  = (son/ma20 -1)*100
        d50  = (son/ma50 -1)*100 if not np.isnan(ma50) else np.nan

        # Sıkılık
        h20      = float(high.iloc[-20:].max())
        l20      = float(low.iloc[-20:].min())
        bant     = (h20-l20)/son

        atr_s      = atr_hesapla(high, low, close)
        atr_son    = float(atr_s.iloc[-5:].mean())
        atr_once   = float(atr_s.iloc[-20:-5].mean())
        atr_iniyor = atr_son < atr_once * 0.95

        ma20_yakin = abs(d20) < (MA20_MAX_MESAFE*100)
        bant_dar   = bant < BANT_ESIK

        # Price-MA band (son 15 günde MA'dan max uzaklaşma)
        ma20_seri  = close.rolling(20).mean()
        band_max   = float(abs(close.iloc[-15:]/ma20_seri.iloc[-15:]-1).max())

        # Higher lows
        h_lows = float(low.iloc[-10:].mean()) > float(low.iloc[-20:-10].mean())

        # Hacim
        ort_hcm = float(vol.iloc[-20:].mean())
        hcm_ok  = ort_hcm >= MIN_HACIM

        # RS
        rs1 = np.nan
        if xu100 is not None and len(xu100)>=21:
            xu_m1 = (float(xu100.iloc[-1])/float(xu100.iloc[-21])-1)*100
            rs1   = m1 - xu_m1 if not np.isnan(m1) else np.nan

        # Skorlar
        mo  = (m6 if not np.isnan(m6) else 0)*0.50 + \
              (m3 if not np.isnan(m3) else 0)*0.30 + \
              (m1 if not np.isnan(m1) else 0)*0.20

        sk  = (25 if bant_dar   else 0) + \
              (20 if atr_iniyor else 0) + \
              (20 if ma20_yakin else 0) + \
              (15 if band_max<0.085 else 0) + \
              (10 if h_lows    else 0) + \
              (10 if (not np.isnan(rs1) and rs1>0) else 0)

        return {
            "Hisse"         : hisse,
            "Fiyat"         : round(son, 2),
            "MA20_%"        : round(d20, 1),
            "MA50_%"        : round(d50, 1) if not np.isnan(d50) else "-",
            "Bant%"         : round(bant*100, 1),
            "ATR_↓"         : "✅" if atr_iniyor else "❌",
            "Bant_Dar"      : "✅" if bant_dar   else "❌",
            "MA20_Yakın"    : "✅" if ma20_yakin else "❌",
            "Higher_Low"    : "✅" if h_lows     else "❌",
            "Hacim_OK"      : "✅" if hcm_ok     else "❌",
            "Mo_1ay%"       : round(m1, 1) if not np.isnan(m1) else "-",
            "Mo_3ay%"       : round(m3, 1) if not np.isnan(m3) else "-",
            "Mo_6ay%"       : round(m6, 1) if not np.isnan(m6) else "-",
            "RS_1ay%"       : round(rs1,1) if not np.isnan(rs1) else "-",
            "Mo_Skor"       : round(mo, 1),
            "Sıklık_Skor"   : sk,
            "Toplam_Skor"   : round(mo*0.55 + sk*0.45, 1),
        }
    except Exception as e:
        return None

# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    print("="*65)
    print("  QULLAMAGGIE HIGH TIGHT FLAG TARAMA")
    print(f"  {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print("="*65)

    hisseler = hisse_listesi_al()

    print("\n📡 XU100 çekiliyor...")
    xu100 = xu100_cek()
    print(f"  XU100: {'✅' if xu100 is not None else '❌'}")

    print(f"\n🔍 {len(hisseler)} hisse analiz ediliyor...")
    print("  (her 50 hissede ilerleme gösterilecek)\n")

    sonuclar = []
    bos = 0
    for i, hisse in enumerate(hisseler, 1):
        r = hisse_analiz(hisse, xu100)
        if r:
            sonuclar.append(r)
        else:
            bos += 1
        if i % 50 == 0:
            print(f"  {i}/{len(hisseler)} — ✅{len(sonuclar)} analiz, ⚠️{bos} veri yok")
        time.sleep(PAUSE)

    print(f"\n  Toplam: ✅{len(sonuclar)} analiz edildi, ⚠️{bos} veri yetersiz")

    if not sonuclar:
        print("❌ Hiç sonuç alınamadı!")
        return

    df = pd.DataFrame(sonuclar)

    # Filtreler
    df_h   = df[df["Hacim_OK"]=="✅"].copy()
    df_mo  = df_h[df_h["Mo_6ay%"] != "-"].copy()
    df_mo["Mo_6ay%"] = pd.to_numeric(df_mo["Mo_6ay%"], errors="coerce")
    df_mo  = df_mo[df_mo["Mo_6ay%"] >= MIN_MO6].copy()

    print(f"\n  Hacim filtresi : {len(df_h)} hisse")
    print(f"  Mo6ay>={MIN_MO6}%  : {len(df_mo)} hisse")

    df_top  = df_mo.nlargest(TOP_N, "Mo_Skor") if not df_mo.empty else df_h.nlargest(TOP_N,"Mo_Skor")

    df_final = df_top[
        (df_top["Bant_Dar"]   == "✅") &
        (df_top["ATR_↓"]      == "✅") &
        (df_top["MA20_Yakın"] == "✅")
    ].sort_values("Toplam_Skor", ascending=False)

    # Rapor
    print("\n" + "="*65)
    print(f"  🏆 FİNAL: {len(df_final)} hisse  |  Top{TOP_N} → sıkılık filtresi")
    print("="*65)

    cols = ["Hisse","Fiyat","Mo_6ay%","Mo_3ay%","Mo_1ay%","RS_1ay%",
            "Bant%","ATR_↓","MA20_%","Toplam_Skor"]

    if df_final.empty:
        print("\n  ⚠️  Sıkılık kriterini geçen hisse yok.")
        print(f"\n  Top {min(15,len(df_top))} Momentum:")
        print(df_top.head(15)[cols].to_string(index=False))
    else:
        print(df_final[cols].to_string(index=False))

    # Excel
    out = "siklik_sonuclar.xlsx"
    with pd.ExcelWriter(out, engine="openpyxl") as w:
        df_final.to_excel(w, sheet_name="High_Tight_Flag", index=False)
        df_top.to_excel(  w, sheet_name="Top_Momentum",    index=False)
        df_h.to_excel(    w, sheet_name="Tum_Analiz",      index=False)

    print(f"\n💾 {out} kaydedildi")
    print(f"   High_Tight_Flag : {len(df_final)} hisse")
    print(f"   Top_Momentum    : {len(df_top)} hisse")
    print(f"   Tum_Analiz      : {len(df_h)} hisse")
    print("\n✅ Tamamlandı!")

if __name__ == "__main__":
    main()
