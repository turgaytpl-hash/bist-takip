"""
halka_arz_tarama.py — 2023-2026 Halka Arz Hisselerinde Haftalık MA20/MA50 Yakınlık Taraması
Çalıştır: python halka_arz_tarama.py
"""

import yfinance as yf
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

HISSELER = {
    # 2023
    "SOKE": 2023, "TABGD": 2023, "KBORU": 2023, "MEGMT": 2023,
    "AVPGY": 2023, "EKOS": 2023, "DOFER": 2023, "DMRGD": 2023,
    "AGESA": 2023, "MEKA": 2023,
    # 2024
    "HRKET": 2024, "ODINE": 2024, "LILAK": 2024, "ALTNY": 2024,
    "KOTON": 2024, "SEGMN": 2024, "PASEU": 2024,
    "BIGEN": 2024, "DAPGM": 2024, "HEDEF": 2024,
    # 2025
    "GLRMK": 2025, "KLYPV": 2025, "ENDAE": 2025, "BULGS": 2025,
    "VAKFA": 2025, "PAHOL": 2025, "ECOGR": 2025, "DOFRB": 2025,
    "VSNMD": 2025, "MOPAS": 2025, "AKFIS": 2025, "EGEGY": 2025,
    # 2026
    "ARFYE": 2026, "EMPAE": 2026, "FRMPL": 2026, "UCAYM": 2026,
    "ZGYO": 2026, "AKHAN": 2026, "NETCD": 2026, "MCARD": 2026,
    "BESTE": 2026,
}

print(f"Tarama basliyor... {len(HISSELER)} hisse")
print("-" * 60)
sonuclar = []

for i, (hisse, yil) in enumerate(HISSELER.items(), 1):
    try:
        ticker = hisse + ".IS"
        df = yf.download(ticker, period="2y", interval="1wk",
                         progress=False, auto_adjust=True)

        if df.empty or len(df) < 15:
            print(f"  [{i:2d}] -- {hisse} -- veri yok/yetersiz")
            continue

        close = df["Close"].squeeze().astype(float)
        fiyat = close.iloc[-1]

        ma20_seri = close.rolling(20).mean()
        ma50_seri = close.rolling(50).mean()
        ma20 = ma20_seri.iloc[-1]
        ma50 = ma50_seri.iloc[-1]

        if pd.isna(ma20):
            print(f"  [{i:2d}] -- {hisse} -- MA20 hesaplanamadi ({len(close)} bar)")
            continue

        ma20_yon = "+" if len(ma20_seri.dropna()) >= 3 and ma20_seri.iloc[-1] > ma20_seri.iloc[-3] else "-"

        ema12 = close.ewm(span=12).mean().iloc[-1]
        ema26 = close.ewm(span=26).mean().iloc[-1]
        macd  = round(ema12 - ema26, 3)

        if pd.isna(ma50):
            mesafe_pct = None
            durum = "Yeni Arz"
        else:
            mesafe_pct = round(abs(ma20 - ma50) / ma50 * 100, 2)
            if ma20 > ma50:
                durum = "TREND" if mesafe_pct >= 3 else "TREND+SIKISMA"
            else:
                durum = "YAKLASIYOR" if mesafe_pct < 5 else "BEKLIYOR"

        print(f"  [{i:2d}] {hisse:8s} {yil} | {fiyat:8.2f} | {durum}")

        sonuclar.append({
            "Hisse":    hisse,
            "Yil":      yil,
            "Fiyat":    round(fiyat, 2),
            "MA20_H":   round(ma20, 2),
            "MA50_H":   round(ma50, 2) if not pd.isna(ma50) else 0,
            "Mesafe_pct": mesafe_pct if mesafe_pct else 999,
            "MA20_Yon": ma20_yon,
            "MACD_H":   macd,
            "Durum":    durum,
        })

    except Exception as e:
        print(f"  [{i:2d}] HATA {hisse} -- {str(e)[:50]}")

print("\n" + "=" * 60)
df_son = pd.DataFrame(sonuclar)

if df_son.empty:
    print("Hic veri gelmedi!")
else:
    df_son = df_son.sort_values("Mesafe_pct")

    print("\n*** KESISIM YAKLASIYOR (Mesafe < 5%) ***")
    yakin = df_son[df_son["Durum"].isin(["YAKLASIYOR","TREND+SIKISMA"])]
    if not yakin.empty:
        print(yakin.to_string(index=False))
    else:
        print("  Su an yok")

    print("\n*** TREND ICINDE (MA20 > MA50) ***")
    trend = df_son[df_son["Durum"] == "TREND"]
    if not trend.empty:
        print(trend.to_string(index=False))

    print("\n*** BEKLIYOR / YENi ARZ ***")
    bekle = df_son[df_son["Durum"].isin(["BEKLIYOR","Yeni Arz"])]
    if not bekle.empty:
        print(bekle.to_string(index=False))

    df_son.to_excel("halka_arz_ma_tarama.xlsx", index=False)
    print(f"\nKaydedildi: halka_arz_ma_tarama.xlsx -- {len(df_son)} hisse")
