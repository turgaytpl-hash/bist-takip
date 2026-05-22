"""
debug3.py — 609 hisse ile gerçek MultiIndex yapısını gör
"""
import yfinance as yf
import pandas as pd
import warnings
warnings.filterwarnings("ignore")

df_fd = pd.read_excel("data/bist_fd.xlsx")
col = df_fd.columns[0]
hisseler = df_fd[col].dropna().astype(str).str.strip().str.upper().tolist()
tickers  = [f"{h}.IS" for h in hisseler]
print(f"{len(tickers)} ticker indiriliyor...")

data = yf.download(tickers, period="6mo", interval="1d",
                   group_by="ticker", auto_adjust=True,
                   progress=False, threads=True)

print("Shape:", data.shape)
print("nlevels:", data.columns.nlevels)
print("İlk 6 kolon:", data.columns[:6].tolist())

lvl0 = data.columns.get_level_values(0).unique().tolist()
lvl1 = data.columns.get_level_values(1).unique().tolist()
print("\nLevel 0 ilk 5:", lvl0[:5])
print("Level 1 ilk 5:", lvl1[:5])

# A1CAP.IS erişim
ticker = "A1CAP.IS"
print(f"\n{ticker} level0'da mı: {ticker in lvl0}")
print(f"{ticker} level1'de mi: {ticker in lvl1}")

try:
    df = data[ticker]
    print(f"data[ticker] → shape={df.shape}, kolonlar={df.columns.tolist()}")
    print(df.tail(2))
except Exception as e:
    print(f"data[ticker] hata: {e}")

# Alternatif — xs dene
try:
    df2 = data.xs(ticker, axis=1, level=0)
    print(f"xs(level=0) → shape={df2.shape}")
except Exception as e:
    print(f"xs(level=0) hata: {e}")

try:
    df3 = data.xs(ticker, axis=1, level=1)
    print(f"xs(level=1) → shape={df3.shape}")
except Exception as e:
    print(f"xs(level=1) hata: {e}")
