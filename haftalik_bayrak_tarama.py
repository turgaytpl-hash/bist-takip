"""
haftalik_bayrak_tarama.py — Haftalık Mum Bazlı Bayrak/Flama Tarama
Qullamaggie metodolojisi — haftalık timeframe

Pole  : 8-26 haftada %30+ yükseliş
Flag  : 4-12 hafta dar konsolidasyon, bant daralıyor, hacim azalıyor

Kullanım: python haftalik_bayrak_tarama.py
Çıkış   : haftalik_bayrak_sonuclar.xlsx
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
BIST_FD_DOSYA    = "data/bist_fd.xlsx"
MIN_HACIM        = 100_000        # haftalık ort. hacim

# Pole kriterleri
POLE_HAFTA_MIN   = 8              # min kaç haftada yükseliş
POLE_HAFTA_MAX   = 26             # max kaç haftada yükseliş (~6 ay)
POLE_MIN_GETIRI  = 30             # pole minimum getirisi %

# Flag kriterleri
FLAG_HAFTA_MIN   = 4              # min flag süresi (hafta)
FLAG_HAFTA_MAX   = 12             # max flag süresi (hafta)
FLAG_BANT_ESIK   = 0.18           # flag bant genişliği < %18
FLAG_BANT_ESIK2  = 0.25           # esnek eşik
ATR_DUSUS_ESIK   = 0.85           # flag ATR < pole ATR'nın %85'i

# MA kriterleri
MA10_MESAFE      = 0.08           # haftalık MA10'dan max %8 uzak
MA_SIRALI        = True           # MA5 > MA10 > MA20

# Momentum
MIN_MO_13HFT     = 15             # 13 haftalık (~3 ay) min %15
TOP_N            = 60
PERIOD           = "2y"           # 2 yıllık veri
INTERVAL         = "1wk"          # HAFTALIK mumlar
XU100_TICKER     = "XU100.IS"
PAUSE            = 0.3

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
    return ["THYAO","SAHOL","NETAS","ISMEN","GOODY","GWIND","KONKA","SANKO","PETUN"]

# ─── VERİ ÇEK ─────────────────────────────────────────────────────────────────
def hisse_veri_cek(hisse):
    try:
        df = yf.download(
            f"{hisse}.IS", period=PERIOD, interval=INTERVAL,
            auto_adjust=True, progress=False, threads=False
        )
        if df is None or len(df) < 20:
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

# ─── ATR ──────────────────────────────────────────────────────────────────────
def atr_hesapla(high, low, close, n=5):
    prev = close.shift(1)
    tr   = pd.concat([(high-low),(high-prev).abs(),(low-prev).abs()],axis=1).max(axis=1)
    return tr.rolling(n).mean()

# ─── POLE TESPİT ──────────────────────────────────────────────────────────────
def pole_tespit(close, high):
    n = len(close)
    if n < POLE_HAFTA_MIN + FLAG_HAFTA_MIN + 2:
        return None

    best_pole    = None
    best_getiri  = 0

    for pole_bitis in range(n - FLAG_HAFTA_MIN, n - FLAG_HAFTA_MAX - 1, -1):
        for pole_uzunluk in range(POLE_HAFTA_MIN, POLE_HAFTA_MAX + 1):
            pole_baslangic = pole_bitis - pole_uzunluk
            if pole_baslangic < 0:
                break

            bas_fiyat   = float(close.iloc[pole_baslangic])
            zirve_fiyat = float(high.iloc[pole_bitis])

            if bas_fiyat <= 0:
                continue

            getiri = (zirve_fiyat / bas_fiyat - 1) * 100

            if getiri >= POLE_MIN_GETIRI and getiri > best_getiri:
                best_getiri = getiri
                best_pole = {
                    "pole_baslangic" : pole_baslangic,
                    "pole_bitis"     : pole_bitis,
                    "pole_uzunluk"   : pole_uzunluk,
                    "pole_getiri"    : round(getiri, 1),
                    "pole_bas"       : round(bas_fiyat, 2),
                    "pole_zirve"     : round(zirve_fiyat, 2),
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

        if len(close) < 30:
            return None

        son = float(close.iloc[-1])

        # ── Pole Tespiti ───────────────────────────────────────────
        pole = pole_tespit(close, high)
        if pole is None:
            return None

        pole_bitis_idx = pole["pole_bitis"]
        flag_hafta     = len(close) - 1 - pole_bitis_idx

        if not (FLAG_HAFTA_MIN <= flag_hafta <= FLAG_HAFTA_MAX):
            return None

        # ── Flag Bölgesi ───────────────────────────────────────────
        flag_close = close.iloc[pole_bitis_idx:]
        flag_high  = high.iloc[pole_bitis_idx:]
        flag_low   = low.iloc[pole_bitis_idx:]
        flag_vol   = volume.iloc[pole_bitis_idx:]
        pole_vol   = volume.iloc[pole["pole_baslangic"]:pole_bitis_idx]

        flag_h    = float(flag_high.max())
        flag_l    = float(flag_low.min())
        flag_bant = (flag_h - flag_l) / son

        # Bant daralıyor mu? (son yarı vs ilk yarı)
        orta = len(flag_close) // 2
        if orta > 0 and len(flag_close) > orta:
            b_ilk = (float(flag_high.iloc[:orta].max()) - float(flag_low.iloc[:orta].min())) / son
            b_son = (float(flag_high.iloc[orta:].max()) - float(flag_low.iloc[orta:].min())) / son
            bant_daralıyor = b_son < b_ilk
        else:
            bant_daralıyor = False

        # ── ATR (flag vs pole) ─────────────────────────────────────
        atr_s        = atr_hesapla(high, low, close, n=4)
        atr_flag     = float(atr_s.iloc[-4:].mean()) if len(atr_s) >= 4 else np.nan
        atr_pole     = float(atr_s.iloc[pole["pole_baslangic"]:pole_bitis_idx].mean()) \
                       if pole_bitis_idx > pole["pole_baslangic"] + 1 else np.nan
        atr_iniyor   = (not np.isnan(atr_flag) and not np.isnan(atr_pole) and
                        atr_pole > 0 and atr_flag < atr_pole * ATR_DUSUS_ESIK)

        # ── Hacim Azalması ─────────────────────────────────────────
        ort_flag_vol   = float(flag_vol.mean())   if len(flag_vol) > 0   else 0
        ort_pole_vol   = float(pole_vol.mean())   if len(pole_vol) > 0   else 0
        hacim_azaliyor = ort_flag_vol < ort_pole_vol * 0.80 if ort_pole_vol > 0 else False
        hacim_ok       = float(volume.iloc[-4:].mean()) >= MIN_HACIM

        # ── MA (haftalık) ──────────────────────────────────────────
        ma5  = float(close.rolling(5).mean().iloc[-1])  if len(close)>=5  else np.nan
        ma10 = float(close.rolling(10).mean().iloc[-1]) if len(close)>=10 else np.nan
        ma20 = float(close.rolling(20).mean().iloc[-1]) if len(close)>=20 else np.nan
        ma40 = float(close.rolling(40).mean().iloc[-1]) if len(close)>=40 else np.nan

        d_ma10 = (son/ma10 - 1)*100 if not np.isnan(ma10) else np.nan
        d_ma20 = (son/ma20 - 1)*100 if not np.isnan(ma20) else np.nan
        d_ma40 = (son/ma40 - 1)*100 if not np.isnan(ma40) else np.nan

        ma10_yakin = abs(d_ma10) < (MA10_MESAFE*100) if not np.isnan(d_ma10) else False

        # MA sıralı mı?
        if MA_SIRALI and not any(np.isnan(x) for x in [ma5, ma10, ma20]):
            ma_sirali = ma5 > ma10 > ma20
        else:
            ma_sirali = True

        # MA40 üzerinde mi? (uzun vadeli trend sağlıklı)
        ma40_uzeri = son > ma40 if not np.isnan(ma40) else True

        # ── Momentum (haftalık mum bazlı) ──────────────────────────
        m4  = (son/float(close.iloc[-5]) -1)*100  if len(close)>=5  else np.nan   # ~1 ay
        m13 = (son/float(close.iloc[-14])-1)*100  if len(close)>=14 else np.nan   # ~3 ay
        m26 = (son/float(close.iloc[-27])-1)*100  if len(close)>=27 else np.nan   # ~6 ay
        m52 = (son/float(close.iloc[-53])-1)*100  if len(close)>=53 else np.nan   # ~1 yıl

        if np.isnan(m13) or m13 < MIN_MO_13HFT:
            return None

        # ── RS (XU100'e göre 13 haftalık) ─────────────────────────
        rs13 = np.nan
        if xu100 is not None and len(xu100) >= 14:
            xu_m13 = (float(xu100.iloc[-1])/float(xu100.iloc[-14])-1)*100
            rs13   = m13 - xu_m13

        # ── SKORLAR ────────────────────────────────────────────────
        s = 0
        if flag_bant < FLAG_BANT_ESIK:    s += 30
        elif flag_bant < FLAG_BANT_ESIK2: s += 15
        if bant_daralıyor:                s += 20
        if atr_iniyor:                    s += 20
        if hacim_azaliyor:                s += 15
        if ma10_yakin:                    s += 10
        if ma_sirali:                     s += 5
        if ma40_uzeri:                    s += 5
        if not np.isnan(rs13) and rs13>0: s += 5

        mo = (m26 if not np.isnan(m26) else 0)*0.40 + \
             (m13 if not np.isnan(m13) else 0)*0.35 + \
             (m4  if not np.isnan(m4)  else 0)*0.25

        return {
            "Hisse"           : hisse,
            "Fiyat"           : round(son, 2),
            "Pole_Getiri%"    : pole["pole_getiri"],
            "Pole_Hafta"      : pole["pole_uzunluk"],
            "Pole_Zirve"      : pole["pole_zirve"],
            "Flag_Hafta"      : flag_hafta,
            "Flag_Bant%"      : round(flag_bant*100, 1),
            "Bant_Dar"        : "✅" if flag_bant < FLAG_BANT_ESIK
                                else ("🟡" if flag_bant < FLAG_BANT_ESIK2 else "❌"),
            "Bant_Daralıyor"  : "✅" if bant_daralıyor  else "❌",
            "ATR_↓"           : "✅" if atr_iniyor      else "❌",
            "Hacim_Azalıyor"  : "✅" if hacim_azaliyor  else "❌",
            "MA_Sıralı"       : "✅" if ma_sirali       else "❌",
            "MA40_Üzeri"      : "✅" if ma40_uzeri      else "❌",
            "MA10_%"          : round(d_ma10, 1) if not np.isnan(d_ma10) else "-",
            "MA20_%"          : round(d_ma20, 1) if not np.isnan(d_ma20) else "-",
            "MA40_%"          : round(d_ma40, 1) if not np.isnan(d_ma40) else "-",
            "Mo_4hft%"        : round(m4,  1) if not np.isnan(m4)  else "-",
            "Mo_13hft%"       : round(m13, 1) if not np.isnan(m13) else "-",
            "Mo_26hft%"       : round(m26, 1) if not np.isnan(m26) else "-",
            "Mo_52hft%"       : round(m52, 1) if not np.isnan(m52) else "-",
            "RS_13hft%"       : round(rs13,1) if not np.isnan(rs13) else "-",
            "Mo_Skor"         : round(mo, 1),
            "Sıklık_Skor"     : s,
            "Toplam_Skor"     : round(mo*0.45 + s*0.55, 1),
        }
    except:
        return None

# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    print("="*65)
    print("  HAFTALIK BAYRAK / FLAMA TARAMA")
    print("  Haftalık mumlar — Pole + Flag tespiti")
    print(f"  {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print("="*65)
    print(f"\n  Pole : {POLE_HAFTA_MIN}-{POLE_HAFTA_MAX} haftada min %{POLE_MIN_GETIRI}")
    print(f"  Flag : {FLAG_HAFTA_MIN}-{FLAG_HAFTA_MAX} hafta konsolidasyon")
    print(f"  Bant : <%{FLAG_BANT_ESIK*100:.0f} (esnek <%{FLAG_BANT_ESIK2*100:.0f})")
    print(f"  Mo   : 13 haftalık min %{MIN_MO_13HFT}")

    hisseler = hisse_listesi_al()

    print("\n📡 XU100 çekiliyor...")
    xu100 = xu100_cek()
    print(f"  XU100: {'✅' if xu100 is not None else '❌'}")

    print(f"\n🔍 {len(hisseler)} hisse analiz ediliyor (haftalık mumlar)...")
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

    # Filtreler
    df_top   = df.nlargest(TOP_N, "Mo_Skor")
    df_final = df[
        (df["Bant_Dar"].isin(["✅","🟡"])) &
        (df["ATR_↓"] == "✅")
    ].sort_values("Toplam_Skor", ascending=False)

    df_bant_dar = df[
        df["Bant_Dar"].isin(["✅","🟡"])
    ].sort_values("Toplam_Skor", ascending=False)

    # ─── RAPOR ───────────────────────────────────────────────────
    print("\n" + "="*65)
    print(f"  🏆 FİNAL: {len(df_final)} hisse (Bant_Dar + ATR_↓)")
    print(f"  📊 Bant Dar (ATR şartsız): {len(df_bant_dar)} hisse")
    print(f"  📋 Tüm Analiz: {len(df)} hisse")
    print("="*65)

    cols = ["Hisse","Fiyat","Pole_Getiri%","Pole_Hafta","Flag_Hafta",
            "Flag_Bant%","Bant_Dar","Bant_Daralıyor","ATR_↓",
            "Hacim_Azalıyor","Mo_13hft%","Mo_26hft%","Toplam_Skor"]

    if df_final.empty:
        print(f"\n  ⚠️  ATR filtreli final boş — Bant Dar olanlar:")
        print(df_bant_dar.head(20)[cols].to_string(index=False))
    else:
        print(df_final[cols].to_string(index=False))

    # ─── EXCEL ───────────────────────────────────────────────────
    out = "haftalik_bayrak_sonuclar.xlsx"
    with pd.ExcelWriter(out, engine="openpyxl") as w:
        df_final.to_excel(   w, sheet_name="Final_BantDar_ATR",  index=False)
        df_bant_dar.to_excel(w, sheet_name="Bant_Dar",           index=False)
        df_top.to_excel(     w, sheet_name="Top_Momentum",       index=False)
        df.to_excel(         w, sheet_name="Tum_Analiz",         index=False)

    print(f"\n💾 {out} kaydedildi")
    print(f"   Final_BantDar_ATR : {len(df_final)} hisse")
    print(f"   Bant_Dar          : {len(df_bant_dar)} hisse")
    print(f"   Top_Momentum      : {len(df_top)} hisse")
    print(f"   Tum_Analiz        : {len(df)} hisse")
    print("\n✅ Tamamlandı!")

if __name__ == "__main__":
    main()
