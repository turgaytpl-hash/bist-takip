"""
debug2.py — 609 hisse ile gerçek yapıyı incele
"""
import yfinance as yf
import pandas as pd
import warnings
warnings.filterwarnings("ignore")
import os

# bist_fd.xlsx'ten ilk 10 hisse al
df_fd = pd.read_excel("data/bist_fd.xlsx")
col = df_fd.columns[0]
hisseler = df_fd[col].dropna().astype(str).str.strip().str.upper().tolist()[:10]
print("Test hisseleri:", hisseler)

tickers = [f"{h}.IS" for h in hisseler]
data = yf.download(tickers, period="3mo", interval="1d",
                   group_by="ticker", auto_adjust=True,
                   progress=False, threads=True)

print("\nShape:", data.shape)
print("nlevels:", data.columns.nlevels)
print("\nLevel 0 (ilk 10):", data.columns.get_level_values(0).unique().tolist()[:10])
print("Level 1 (ilk 10):", data.columns.get_level_values(1).unique().tolist()[:10])
print("\nİlk 6 kolon:", data.columns[:6].tolist())

# İlk ticker'ı bulmaya çalış
ticker = tickers[0]
print(f"\n--- {ticker} erişim testi ---")
lvl0 = data.columns.get_level_values(0).unique().tolist()
lvl1 = data.columns.get_level_values(1).unique().tolist()
print(f"Level 0'da var mı: {ticker in lvl0}")
print(f"Level 1'de var mı: {ticker in lvl1}")

# data[ticker] dene
try:
    df = data[ticker]
    print(f"data[ticker] → shape: {df.shape}, kolonlar: {df.columns.tolist()}")
    print(df.tail(2))
except Exception as e:
    print(f"data[ticker] hata: {e}")
