"""
bist_ma_tarama.py — BIST FD Haftalik MA Sikisma Taramasi v3
Kosullar:
  - Fiyat tum ortalamalarin ustunde
  - Fiyat MA20'den max %15 uzakta (cok kopuk degil)
  - MA20-MA50 arasi < %5 (sikisma)
  - MA200 yukari egimli
Calistir: python bist_ma_tarama.py
"""

import yfinance as yf
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

df_fd = pd.read_excel('data/bist_fd.xlsx', header=None)
HISSELER = df_fd.iloc[:, 0].astype(str).str.strip().str.upper().tolist()
HISSELER = [h for h in HISSELER if len(h) >= 3 and h != 'SEMBOL']

print(f"Tarama basliyor... {len(HISSELER)} hisse")
print("Yaklasik 20-25 dakika surer.")
print("-" * 70)

sonuclar = []

for i, hisse in enumerate(HISSELER, 1):
    try:
        ticker = hisse + ".IS"
        df = yf.download(ticker, period="5y", interval="1wk",
                         progress=False, auto_adjust=True)

        if df.empty or len(df) < 50:
            continue

        close = df["Close"].squeeze().astype(float)
        fiyat = close.iloc[-1]

        ma20_seri  = close.rolling(20).mean()
        ma50_seri  = close.rolling(50).mean()
        ma150_seri = close.rolling(150).mean()
        ma200_seri = close.rolling(200).mean()

        ma20  = ma20_seri.iloc[-1]
        ma50  = ma50_seri.iloc[-1]
        ma150 = ma150_seri.iloc[-1]
        ma200 = ma200_seri.iloc[-1]

        if pd.isna(ma20) or pd.isna(ma50):
            continue

        # MA20 yonu
        ma20_yon = "+" if len(ma20_seri.dropna()) >= 3 and ma20_seri.iloc[-1] > ma20_seri.iloc[-3] else "-"

        # MA200 yonu
        ma200_yon = None
        if not pd.isna(ma200):
            ma200_yon = "+" if ma200_seri.iloc[-1] > ma200_seri.iloc[-4] else "-"

        # MACD
        ema12 = close.ewm(span=12).mean().iloc[-1]
        ema26 = close.ewm(span=26).mean().iloc[-1]
        macd  = round(ema12 - ema26, 3)

        # Mesafeler
        def mesafe(a, b):
            if pd.isna(a) or pd.isna(b) or b == 0:
                return None
            return round(abs(a - b) / b * 100, 2)

        m20_50   = mesafe(ma20, ma50)
        m50_150  = mesafe(ma50, ma150)
        m150_200 = mesafe(ma150, ma200)

        # Fiyat-MA20 uzakligi
        fiyat_ma20_uzak = round((fiyat - ma20) / ma20 * 100, 2) if not pd.isna(ma20) else None

        # ANA FILTRELER
        f1 = not pd.isna(ma200) and fiyat > ma200          # fiyat MA200 ustunde
        f2 = not pd.isna(ma150) and fiyat > ma150          # fiyat MA150 ustunde
        f3 = fiyat > ma50                                   # fiyat MA50 ustunde
        f4 = fiyat > ma20                                   # fiyat MA20 ustunde
        f5 = fiyat_ma20_uzak is not None and fiyat_ma20_uzak <= 15  # MA20'den max %15 uzak
        f6 = m20_50 is not None and m20_50 < 5             # MA20-MA50 sikisma
        f7 = ma200_yon == "+"                               # MA200 yukari

        tum_filtreler = f1 and f2 and f3 and f4 and f5 and f6 and f7

        # Sikisma skoru (kac ortalama arasi < %5)
        sikisma_sayisi = sum([
            1 for m in [m20_50, m50_150, m150_200]
            if m is not None and m < 5
        ])

        # Durum
        if tum_filtreler:
            if sikisma_sayisi == 3:
                durum = "MUHTESEM"
            elif sikisma_sayisi == 2:
                durum = "IYI_SIKISMA"
            else:
                durum = "SIKISMA"
        elif f1 and f2 and f3 and f4 and f6 and not f5:
            durum = "UZAKLASTI"   # sıkışma var ama fiyat çok kopmuş
        elif f1 and f2 and f3 and f4 and f7 and m20_50 and m20_50 < 10:
            durum = "YAKIN"
        else:
            durum = "BEKLIYOR"

        mesafe_sort = m20_50 if m20_50 else 999

        if i % 50 == 0:
            print(f"  [{i:3d}/{len(HISSELER)}] isleniyor...")

        sonuclar.append({
            "Hisse":        hisse,
            "Fiyat":        round(fiyat, 2),
            "MA20_H":       round(ma20, 2),
            "MA50_H":       round(ma50, 2) if not pd.isna(ma50) else "-",
            "MA150_H":      round(ma150, 2) if not pd.isna(ma150) else "-",
            "MA200_H":      round(ma200, 2) if not pd.isna(ma200) else "-",
            "F-MA20%":      fiyat_ma20_uzak,
            "M20_50%":      m20_50 if m20_50 else "-",
            "M50_150%":     m50_150 if m50_150 else "-",
            "M150_200%":    m150_200 if m150_200 else "-",
            "Sikisma":      sikisma_sayisi,
            "MA20_Yon":     ma20_yon,
            "MA200_Yon":    ma200_yon if ma200_yon else "-",
            "MACD_H":       macd,
            "Durum":        durum,
            "_sort":        mesafe_sort,
        })

    except Exception:
        continue

print("\n" + "=" * 70)
df_son = pd.DataFrame(sonuclar)

if df_son.empty:
    print("Hic veri gelmedi!")
else:
    df_son = df_son.sort_values("_sort").drop("_sort", axis=1)

    print(f"\nToplam taranan: {len(df_son)} hisse")
    for d in ["MUHTESEM","IYI_SIKISMA","SIKISMA","UZAKLASTI","YAKIN","BEKLIYOR"]:
        print(f"  {d:20s}: {len(df_son[df_son['Durum']==d])}")

    with pd.ExcelWriter("bist_ma_tarama.xlsx", engine="openpyxl") as w:
        df_son.to_excel(w, sheet_name="Tum Liste", index=False)

        for durum_adi, sekme_adi in [
            ("MUHTESEM",    "Muhtesem"),
            ("IYI_SIKISMA", "Iyi Sikisma"),
            ("SIKISMA",     "Sikisma"),
            ("UZAKLASTI",   "Uzaklasti"),
            ("YAKIN",       "Yakin"),
        ]:
            filtre = df_son[df_son["Durum"] == durum_adi]
            if not filtre.empty:
                filtre.to_excel(w, sheet_name=sekme_adi, index=False)

    print(f"\nKaydedildi: bist_ma_tarama.xlsx")
    print("Sekmeler: Muhtesem / Iyi Sikisma / Sikisma / Uzaklasti / Yakin")
