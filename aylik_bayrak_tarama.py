"""
aylik_bayrak_tarama.py — Aylık Mum Bazlı High Tight Flag Tarama
Qullamaggie metodolojisi — aylık timeframe

Pole  : 6-18 ayda %100-400+ yükseliş
Flag  : 3-8 ay dar konsolidasyon, bant daralıyor, hacim azalıyor

Kullanım: python aylik_bayrak_tarama.py
Çıkış   : aylik_bayrak_sonuclar.xlsx
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
MIN_HACIM_AYLIK = 500_000         # aylık ort. hacim (günlük x20)

# Pole kriterleri
POLE_PERIOD_MIN = 6               # min kaç ayda yükseliş
POLE_PERIOD_MAX = 18              # max kaç ayda yükseliş
POLE_MIN_GETIRI = 80              # pole minimum getirisi %

# Flag kriterleri
FLAG_AY_MIN     = 3               # min flag süresi (ay)
FLAG_AY_MAX     = 8               # max flag süresi (ay)
FLAG_BANT_ESIK  = 0.25            # flag bant genişliği < %25
FLAG_BANT_ESIK2 = 0.28            # daha esnek eşik (ikinci filtre)
ATR_DUSUS_ESIK  = 0.85            # flag ATR < pole ATR'nın %85'i

# MA kriterleri
MA10_MESAFE     = 0.12            # aylık MA10'dan max %12 uzak
MA_SIRALI       = True            # MA5 > MA10 > MA20 sıralı olmalı

# Momentum
MIN_MO_6AY      = 30              # aylık bazda son 6 ay min %30
TOP_N           = 50
PERIOD          = "5y"            # 5 yıllık veri
INTERVAL        = "1mo"           # AYLIK mumlar
XU100_TICKER    = "XU100.IS"
PAUSE           = 0.4

# ─── HİSSE LİSTESİ ────────────────────────────────────────────────────────────
def hisse_listesi_al():
    if os.path.exists(BIST_FD_DOSYA):
        df  = pd.read_excel(BIST_FD_DOSYA)
        col = next((c for c in df.columns
                    if any(k in c.lower() for k in ["hisse","kod","sembol","ticker"])),
                   df.columns[0])
        lst = df[col].dropna().astype(str).str.strip().str.upper().tolist()
        print(f"  {len(lst)} hisse yüklendi")
        return lst
    print("⚠️ bist_fd.xlsx bulunamadı")
    return ["THYAO","GARAN","EREGL","SISE","KCHOL","ASTOR","FONET","EUPWR","SEKUR","DMRGD"]

# ─── VERİ ÇEK ─────────────────────────────────────────────────────────────────
def hisse_veri_cek(hisse):
    try:
        df = yf.download(
            f"{hisse}.IS", period=PERIOD, interval=INTERVAL,
            auto_adjust=True, progress=False, threads=False
        )
        if df is None or len(df) < 12:   # en az 12 aylık veri
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df.dropna(subset=["Close"])
    except:
        return None

def xu100_cek():
    try:
        df = yf.download(XU100_TICKER, period=PERIOD, interval=INTERVAL,
                         auto_adjust=True, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df["Close"].dropna()
    except:
        return None

# ─── ATR (aylık) ──────────────────────────────────────────────────────────────
def atr_hesapla(high, low, close, n=5):
    """Aylık ATR — n=5 ay varsayılan"""
    prev = close.shift(1)
    tr   = pd.concat([(high-low),(high-prev).abs(),(low-prev).abs()],axis=1).max(axis=1)
    return tr.rolling(n).mean()

# ─── POLE TESPİT ──────────────────────────────────────────────────────────────
def pole_tespit(close, high):
    """
    Son FLAG_AY_MAX aydan önceki bölgede pole arar.
    Pole: POLE_PERIOD_MIN - POLE_PERIOD_MAX ay içinde POLE_MIN_GETIRI% yükseliş.
    Pole sonunu ve büyüklüğünü döner.
    """
    n = len(close)
    if n < POLE_PERIOD_MIN + FLAG_AY_MIN + 2:
        return None

    # Flag başlangıcını bul — son FLAG_AY_MAX ayın en yüksek noktası
    flag_baslangic_idx = max(n - FLAG_AY_MAX - 1, POLE_PERIOD_MIN)

    best_pole = None
    best_getiri = 0

    # Son FLAG_AY_MIN ile FLAG_AY_MAX ay öncesi arasında pole bitişini ara
    for pole_bitis in range(n - FLAG_AY_MIN, n - FLAG_AY_MAX - 1, -1):
        # Pole başlangıcını ara — POLE_PERIOD_MIN ile POLE_PERIOD_MAX ay önce
        for pole_uzunluk in range(POLE_PERIOD_MIN, POLE_PERIOD_MAX + 1):
            pole_baslangic = pole_bitis - pole_uzunluk
            if pole_baslangic < 0:
                break

            bas_fiyat  = float(close.iloc[pole_baslangic])
            bitis_fiyat = float(high.iloc[pole_bitis])

            if bas_fiyat <= 0:
                continue

            getiri = (bitis_fiyat / bas_fiyat - 1) * 100

            if getiri >= POLE_MIN_GETIRI and getiri > best_getiri:
                best_getiri = getiri
                best_pole = {
                    "pole_baslangic" : pole_baslangic,
                    "pole_bitis"     : pole_bitis,
                    "pole_uzunluk"   : pole_uzunluk,
                    "pole_getiri"    : round(getiri, 1),
                    "pole_bas"       : round(bas_fiyat, 2),
                    "pole_zirve"     : round(bitis_fiyat, 2),
                }

    return best_pole

# ─── ANALİZ ───────────────────────────────────────────────────────────────────
def hisse_analiz(hisse, xu100=None):
    df = hisse_veri_cek(hisse)
    if df is None:
        return None

    try:
        close  = df["Close"]
        high   = df["High"]
        low    = df["Low"]
        volume = df["Volume"]

        if len(close) < 18:
            return None

        son = float(close.iloc[-1])

        # ── Pole Tespiti ───────────────────────────────────────────
        pole = pole_tespit(close, high)
        if pole is None:
            return None

        pole_bitis_idx = pole["pole_bitis"]
        flag_ay        = len(close) - 1 - pole_bitis_idx  # kaç aydır flag

        if not (FLAG_AY_MIN <= flag_ay <= FLAG_AY_MAX):
            return None

        # ── Flag Bölgesi ───────────────────────────────────────────
        flag_close  = close.iloc[pole_bitis_idx:]
        flag_high   = high.iloc[pole_bitis_idx:]
        flag_low    = low.iloc[pole_bitis_idx:]
        flag_vol    = volume.iloc[pole_bitis_idx:]
        pole_vol    = volume.iloc[pole["pole_baslangic"]:pole_bitis_idx]

        flag_h      = float(flag_high.max())
        flag_l      = float(flag_low.min())
        flag_bant   = (flag_h - flag_l) / son

        # Flag içinde bant daralıyor mu? (son yarı vs ilk yarı)
        orta        = len(flag_close) // 2
        if orta > 0 and len(flag_close) > orta:
            bant_ilk  = (float(flag_high.iloc[:orta].max()) - float(flag_low.iloc[:orta].min())) / son
            bant_son  = (float(flag_high.iloc[orta:].max()) - float(flag_low.iloc[orta:].min())) / son
            bant_daralıyor = bant_son < bant_ilk
        else:
            bant_daralıyor = False

        # ── ATR Karşılaştırma (flag vs pole) ──────────────────────
        atr_s        = atr_hesapla(high, low, close, n=3)
        atr_flag_now = float(atr_s.iloc[-3:].mean()) if len(atr_s) >= 3 else np.nan
        atr_pole_avg = float(atr_s.iloc[pole["pole_baslangic"]:pole_bitis_idx].mean()) \
                       if pole_bitis_idx > pole["pole_baslangic"] else np.nan

        atr_iniyor = False
        if not np.isnan(atr_flag_now) and not np.isnan(atr_pole_avg) and atr_pole_avg > 0:
            atr_iniyor = atr_flag_now < atr_pole_avg * ATR_DUSUS_ESIK

        # ── Hacim Azalması (flag hacmi < pole hacmi) ───────────────
        ort_flag_vol = float(flag_vol.mean()) if len(flag_vol) > 0 else 0
        ort_pole_vol = float(pole_vol.mean()) if len(pole_vol) > 0 else 0
        hacim_azaliyor = ort_flag_vol < ort_pole_vol * 0.80 if ort_pole_vol > 0 else False
        hacim_ok       = float(volume.iloc[-3:].mean()) >= MIN_HACIM_AYLIK

        # ── MA (aylık) ─────────────────────────────────────────────
        ma5   = float(close.rolling(5).mean().iloc[-1])   if len(close)>=5  else np.nan
        ma10  = float(close.rolling(10).mean().iloc[-1])  if len(close)>=10 else np.nan
        ma20  = float(close.rolling(20).mean().iloc[-1])  if len(close)>=20 else np.nan

        d_ma10  = (son/ma10 -1)*100  if not np.isnan(ma10)  else np.nan
        d_ma20  = (son/ma20 -1)*100  if not np.isnan(ma20)  else np.nan
        ma10_yakin = abs(d_ma10) < (MA10_MESAFE*100) if not np.isnan(d_ma10) else False

        # MA sıralı mı? (MA5 > MA10 > MA20)
        if MA_SIRALI and not (np.isnan(ma5) or np.isnan(ma10) or np.isnan(ma20)):
            ma_sirali = ma5 > ma10 > ma20
        else:
            ma_sirali = True

        # ── Momentum (aylık mum bazlı) ─────────────────────────────
        m3  = (son/float(close.iloc[-4]) -1)*100  if len(close)>=4  else np.nan  # 3 ay
        m6  = (son/float(close.iloc[-7]) -1)*100  if len(close)>=7  else np.nan  # 6 ay
        m12 = (son/float(close.iloc[-13])-1)*100  if len(close)>=13 else np.nan  # 12 ay

        if np.isnan(m6) or m6 < MIN_MO_6AY:
            return None

        # ── RS (XU100'e göre) ──────────────────────────────────────
        rs6 = np.nan
        if xu100 is not None and len(xu100) >= 7:
            xu_m6 = (float(xu100.iloc[-1])/float(xu100.iloc[-7])-1)*100
            rs6   = m6 - xu_m6

        # ── SKORLAR ────────────────────────────────────────────────
        s = 0
        if flag_bant < FLAG_BANT_ESIK:   s += 30
        elif flag_bant < FLAG_BANT_ESIK2: s += 15
        if bant_daralıyor:               s += 20
        if atr_iniyor:                   s += 20
        if hacim_azaliyor:               s += 15
        if ma10_yakin:                   s += 10
        if ma_sirali:                    s += 5

        mo = (m6  if not np.isnan(m6)  else 0)*0.40 + \
             (m3  if not np.isnan(m3)  else 0)*0.35 + \
             (m12 if not np.isnan(m12) else 0)*0.25

        return {
            "Hisse"          : hisse,
            "Fiyat"          : round(son, 2),
            "Pole_Getiri%"   : pole["pole_getiri"],
            "Pole_Uzunluk_Ay": pole["pole_uzunluk"],
            "Pole_Zirve"     : pole["pole_zirve"],
            "Flag_Ay"        : flag_ay,
            "Flag_Bant%"     : round(flag_bant*100, 1),
            "Bant_Dar"       : "✅" if flag_bant < FLAG_BANT_ESIK   else ("🟡" if flag_bant < FLAG_BANT_ESIK2 else "❌"),
            "Bant_Daralıyor" : "✅" if bant_daralıyor else "❌",
            "ATR_↓"          : "✅" if atr_iniyor    else "❌",
            "Hacim_Azalıyor" : "✅" if hacim_azaliyor else "❌",
            "MA_Sıralı"      : "✅" if ma_sirali     else "❌",
            "MA10_%"         : round(d_ma10, 1) if not np.isnan(d_ma10) else "-",
            "MA20_%"         : round(d_ma20, 1) if not np.isnan(d_ma20) else "-",
            "Mo_3ay%"        : round(m3,  1) if not np.isnan(m3)  else "-",
            "Mo_6ay%"        : round(m6,  1) if not np.isnan(m6)  else "-",
            "Mo_12ay%"       : round(m12, 1) if not np.isnan(m12) else "-",
            "RS_6ay%"        : round(rs6, 1) if not np.isnan(rs6) else "-",
            "Mo_Skor"        : round(mo, 1),
            "Sıklık_Skor"    : s,
            "Toplam_Skor"    : round(mo*0.45 + s*0.55, 1),
        }
    except:
        return None

# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    print("="*65)
    print("  AYLIK BAYRAK / DİNLENME TARAMA")
    print("  Aylık mumlar — Pole + Flag tespiti")
    print(f"  {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print("="*65)
    print(f"\n  Pole : {POLE_PERIOD_MIN}-{POLE_PERIOD_MAX} ayda min %{POLE_MIN_GETIRI} yükseliş")
    print(f"  Flag : {FLAG_AY_MIN}-{FLAG_AY_MAX} ay konsolidasyon")
    print(f"  Bant : <%{FLAG_BANT_ESIK*100:.0f} (esnek <%{FLAG_BANT_ESIK2*100:.0f})")
    print(f"  ATR  : Flag ATR < Pole ATR x{ATR_DUSUS_ESIK}")

    hisseler = hisse_listesi_al()

    print("\n📡 XU100 çekiliyor...")
    xu100 = xu100_cek()
    print(f"  XU100: {'✅' if xu100 is not None else '❌'}")

    print(f"\n🔍 {len(hisseler)} hisse analiz ediliyor (aylık mumlar)...")
    print("  (her 50 hissede ilerleme)\n")

    sonuclar = []
    bos = 0
    for i, hisse in enumerate(hisseler, 1):
        r = hisse_analiz(hisse, xu100)
        if r:
            sonuclar.append(r)
        else:
            bos += 1
        if i % 50 == 0:
            print(f"  {i}/{len(hisseler)} — ✅{len(sonuclar)} geçti, ⚠️{bos} elendi")
        time.sleep(PAUSE)

    print(f"\n  Toplam: ✅{len(sonuclar)} geçti, ⚠️{bos} elendi")

    if not sonuclar:
        print("❌ Sonuç yok!")
        return

    df = pd.DataFrame(sonuclar)
    df_h = df[df["Hacim_OK"] == "✅"].copy() if "Hacim_OK" in df.columns else df.copy()

    # Skor sırala
    df_top   = df.nlargest(TOP_N, "Mo_Skor")
    df_final = df[
        (df["Bant_Dar"].isin(["✅","🟡"])) &
        (df["ATR_↓"] == "✅")
    ].sort_values("Toplam_Skor", ascending=False)

    # ─── RAPOR ───────────────────────────────────────────────────
    print("\n" + "="*65)
    print(f"  🏆 FİNAL: {len(df_final)} hisse")
    print(f"  Pole + Flag + Bant_Dar + ATR_↓ kriterleri")
    print("="*65)

    cols = ["Hisse","Fiyat","Pole_Getiri%","Pole_Uzunluk_Ay","Flag_Ay",
            "Flag_Bant%","Bant_Daralıyor","ATR_↓","Hacim_Azalıyor","Mo_6ay%","Toplam_Skor"]

    if df_final.empty:
        print("\n  ⚠️  Final boş — ATR filtresi olmadan:")
        df_bant = df[df["Bant_Dar"].isin(["✅","🟡"])].sort_values("Toplam_Skor", ascending=False)
        if not df_bant.empty:
            print(df_bant.head(15)[cols].to_string(index=False))
        else:
            print("  Bant filtresi de boş — tüm sonuçlar:")
            print(df.sort_values("Toplam_Skor", ascending=False).head(15)[cols].to_string(index=False))
    else:
        print(df_final[cols].to_string(index=False))

    # ─── EXCEL ───────────────────────────────────────────────────
    out = "aylik_bayrak_sonuclar.xlsx"
    with pd.ExcelWriter(out, engine="openpyxl") as w:
        df_final.to_excel(w, sheet_name="Aylik_Bayrak",  index=False)
        df_top.to_excel(  w, sheet_name="Top_Momentum",  index=False)
        df.to_excel(      w, sheet_name="Tum_Analiz",    index=False)

    print(f"\n💾 {out} kaydedildi")
    print(f"   Aylik_Bayrak : {len(df_final)} hisse — tam kriterler")
    print(f"   Top_Momentum : {len(df_top)} hisse")
    print(f"   Tum_Analiz   : {len(df)} hisse — pole+flag geçenler")
    print("\n✅ Tamamlandı!")

if __name__ == "__main__":
    main()
