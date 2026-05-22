"""
debug_yfinance.py — yfinance veri yapısını incele
Çalıştır: python debug_yfinance.py
"""
import yfinance as yf
import pandas as pd
import warnings
warnings.filterwarnings("ignore")

test = ["THYAO", "EREGL", "KCHOL", "ASTOR", "FONET"]
tickers = [f"{h}.IS" for h in test]

print("Veri çekiliyor...")
data = yf.download(
    tickers, period="3mo", interval="1d",
    group_by="ticker", auto_adjust=True,
    progress=False, threads=True
)

print("\n--- YAPI BİLGİSİ ---")
print("Shape:", data.shape)
print("Columns type:", type(data.columns).__name__)
print("Columns nlevels:", data.columns.nlevels)
print("\nİlk 10 kolon:")
for i, c in enumerate(data.columns[:10]):
    print(f"  [{i}] {c}")

print("\nLevel 0 unique:", data.columns.get_level_values(0).unique().tolist()[:5])
print("Level 1 unique:", data.columns.get_level_values(1).unique().tolist()[:8])

print("\n--- TEK HİSSE ERİŞİM TEST ---")
for yontem in ["level0", "level1", "xs0", "xs1"]:
    try:
        if yontem == "level0":
            df = data["THYAO.IS"]
        elif yontem == "level1":
            df = data.xs("THYAO.IS", axis=1, level=0)
        elif yontem == "xs0":
            df = data.xs("THYAO.IS", axis=1, level=1)
        elif yontem == "xs1":
            df = data["THYAO.IS"]["Close"] if isinstance(data["THYAO.IS"], pd.DataFrame) else None
        
        if df is not None and len(df) > 0:
            print(f"  ✅ {yontem}: shape={df.shape}, kolonlar={df.columns.tolist() if hasattr(df,'columns') else 'Series'}")
            print(f"     Son satır: {df.iloc[-1].to_dict() if hasattr(df,'iloc') else df.iloc[-1]}")
        else:
            print(f"  ⚠️  {yontem}: boş")
    except Exception as e:
        print(f"  ❌ {yontem}: {e}")
