"""
debug4.py — analiz fonksiyonundaki gerçek hatayı bul
"""
import yfinance as yf
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings("ignore")

df_fd = pd.read_excel("data/bist_fd.xlsx")
hisseler = df_fd.iloc[:,0].dropna().astype(str).str.strip().str.upper().tolist()
tickers  = [f"{h}.IS" for h in hisseler]

print(f"{len(tickers)} ticker indiriliyor...")
data = yf.download(tickers, period="6mo", interval="1d",
                   group_by="ticker", auto_adjust=True,
                   progress=False, threads=True)

# İlk 3 hisseyi manuel analiz et — tam hata mesajı ile
test_hisseler = hisseler[:3]
xu100 = yf.download("XU100.IS", period="6mo", interval="1d",
                    auto_adjust=True, progress=False)["Close"].dropna()

for hisse in test_hisseler:
    ticker = f"{hisse}.IS"
    print(f"\n{'='*40}")
    print(f"HİSSE: {hisse}")
    try:
        df = data[ticker]
        print(f"  df.shape: {df.shape}")
        print(f"  kolonlar: {df.columns.tolist()}")
        print(f"  dropna sonrası: {len(df.dropna(how='all'))} satır")
        
        close  = df["Close"].dropna()
        high   = df["High"].dropna()
        low    = df["Low"].dropna()
        volume = df["Volume"].dropna()
        
        print(f"  close len: {len(close)}, son: {close.iloc[-1]:.2f}")
        
        son = float(close.iloc[-1])
        m1  = (son / float(close.iloc[-21])  - 1)*100
        m6  = (son / float(close.iloc[-126]) - 1)*100 if len(close)>=126 else float('nan')
        ma20 = float(close.rolling(20).mean().iloc[-1])
        
        h20  = float(high.iloc[-20:].max())
        l20  = float(low.iloc[-20:].min())
        bant = (h20-l20)/son
        
        ort_hcm = float(volume.iloc[-20:].mean())
        
        print(f"  Mo_1ay: {m1:.1f}%  Mo_6ay: {m6:.1f}%")
        print(f"  MA20_mesafe: {(son/ma20-1)*100:.1f}%")
        print(f"  Bant: {bant*100:.1f}%")
        print(f"  Ort Hacim: {ort_hcm:,.0f}")
        print(f"  ✅ Analiz başarılı")
        
    except Exception as e:
        import traceback
        print(f"  ❌ HATA: {e}")
        print(traceback.format_exc())
