"""
UYUYAN DEVLER v3
================
Mantık: Hisse zirve yapmış, düşmüş, dibine yakın uyuyor.
        2023-2026 arası bu pozisyonda olanları bul.

Kriterler:
  1. Son fiyat, 3 yıllık ZİRVEDEN uzakta   → (Zirve - Son) / Zirve > %35
  2. Son fiyat, 3 yıllık DİBE yakın        → (Son - Dip) / Dip < %35
  3. Son 6 ayda fiyat hareketsiz           → MAX(126gün)/MIN(126gün) < 1.30
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings("ignore")

BIST_HISSELER = [
    "ACSEL","ADEL","AEFES","AFYON","AGYO","AKCNS","AKENR","AKGRT","AKSA",
    "AKSEN","ALARK","ALBRK","ALCAR","ALGYO","ALKA","ALKIM","ANHYT","ANSGR",
    "ARCLK","ARFYE","ASELS","ASUZU","ATAGY","ATEKS","ATLAS","ATSYH","AVTUR",
    "AYCES","AYEN","AYGAZ","BAGFS","BAKAB","BANVT","BIMAS","BJKAS","BOSSA",
    "BRISA","BRMEN","BRSAN","BRYAT","BTCIM","BUCIM","BURCE","BURVA","BVSAN",
    "CCOLA","CELHA","CEMTS","CIMSA","CLEBI","CMENT","DAPGM","DARDL",
    "DESAS","DEVA","DGATE","DMSAS","DOHOL","DOKTA","DURDO","DZGYO",
    "ECILC","ECZYT","EDIP","EGEEN","EKGYO","EMKEL","EMPAE","EMNIS",
    "ENKAI","ENJSA","ENTRA","ERBOS","EREGL","ERSU","ETYAT","EUYO",
    "FENER","FMIZP","FONET","FRIGO","GARAN","GLYHO","GOLTS","GOODY",
    "GRNYO","GSDHO","GSRAY","GUBRF","GUNDG","HALKB","HATSN","HEDEF",
    "HEKTS","HURGZ","ICBCT","IHLGM","IHLAS","INDES","INTEM","INVEO",
    "ISCTR","ISGSY","ISGYO","ISKUR","ISYAT","IZMDC","JANTS","KAREL",
    "KARSN","KCHOL","KENT","KERVN","KFEIN","KLMSN","KNFRT","KONYA",
    "KORDS","KOZAA","KOZAL","KRDMA","KRDMB","KRDMD","KRSTL","KTLEV",
    "KUTPO","LOGO","LUKSK","LYDHO","MAALT","MAKTK","MANAS","MCARD",
    "MEMS","MERKO","METAL","METRO","MGROS","MNDRS","MRSHL","MTRYO",
    "NATEN","NETAS","NETCD","NTHOL","NUGYO","NUHCM","ODINE","OLMK",
    "OTKAR","OYAYO","OYLUM","PARSN","PASEU","PEKGY","PETUN","PINSU",
    "PKART","PKENT","PNSUT","PRKAB","PRKME","QNBFK","RAYSG","RYSAS",
    "SAHOL","SANKO","SARKY","SASA","SELEC","SEKFK","SEKUR","SISE",
    "SKTAS","SMART","SNGYO","SNPAM","SONME","TATGD","TAVHL","TCELL",
    "TEKTU","THYAO","TKFEN","TMSN","TOASO","TRCAS","TSKB","TSPOR",
    "TTKOM","TTRAK","TUKAS","TUPRS","TURSG","UFUK","ULKER","VAKBN",
    "VAKKO","VESTL","VKGYO","YKBNK","YUNSA","YYAPI","ZOREN",
]

# ── PARAMETRELER ──────────────────────────────────────────────────────────────
ZIRVE_UZAKLIK_MIN = 0.35   # Zirveden en az %35 aşağıda
DIP_YAKINLIK_MAX  = 0.35   # Dipten en fazla %35 yukarıda
SON_6AY_BANT_MAX  = 1.30   # Son 6 ayda MAX/MIN < 1.30 (hareketsiz)
MIN_FIYAT         = 3.0
MIN_HACIM         = 150_000

def tarama(hisseler, verbose=True):
    bitis     = datetime.today()
    baslangic = datetime(2023, 1, 1)

    sonuclar = []
    toplam = len(hisseler)

    for i, sembol in enumerate(hisseler, 1):
        ticker = f"{sembol}.IS"
        if verbose:
            print(f"[{i:3d}/{toplam}] {sembol:8s}", end=" ")

        try:
            df = yf.download(ticker, start=baslangic, end=bitis,
                             progress=False, auto_adjust=True)

            if df is None or len(df) < 200:
                if verbose: print("→ yetersiz veri")
                continue

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            df = df[["High","Low","Close","Volume"]].copy()
            df.dropna(inplace=True)

            son_fiyat = float(df["Close"].iloc[-1])
            if son_fiyat < MIN_FIYAT:
                if verbose: print(f"→ fiyat düşük")
                continue

            hacim_ort = float(df["Volume"].mean())
            if hacim_ort < MIN_HACIM:
                if verbose: print(f"→ hacim yetersiz")
                continue

            # 2023-2026 arası zirve & dip
            zirve = float(df["High"].max())
            dip   = float(df["Low"].min())

            # Kriter 1: Zirveden uzak
            zirve_uzaklik = (zirve - son_fiyat) / zirve

            # Kriter 2: Dibe yakın
            dip_yakinlik = (son_fiyat - dip) / dip

            # Kriter 3: Son 6 ay hareketsiz
            son_6ay  = df.iloc[-126:]
            bant_6ay = float(son_6ay["High"].max()) / float(son_6ay["Low"].min())

            k1 = zirve_uzaklik >= ZIRVE_UZAKLIK_MIN
            k2 = dip_yakinlik  <= DIP_YAKINLIK_MAX
            k3 = bant_6ay      <= SON_6AY_BANT_MAX

            gecen = sum([k1, k2, k3])

            if verbose:
                print(f"Zirve:{zirve:8.2f} Dip:{dip:8.2f} Son:{son_fiyat:8.2f} "
                      f"{'✓' if k1 else '✗'}Zirve%{zirve_uzaklik*100:.0f} "
                      f"{'✓' if k2 else '✗'}Dip%{dip_yakinlik*100:.0f} "
                      f"{'✓' if k3 else '✗'}Bant{bant_6ay:.2f} "
                      f"→ {gecen}/3")

            if gecen == 3:
                sonuclar.append({
                    "Sembol"         : sembol,
                    "Son Fiyat"      : round(son_fiyat, 2),
                    "3Y Zirve"       : round(zirve, 2),
                    "3Y Dip"         : round(dip, 2),
                    "Zirveden %"     : round(zirve_uzaklik * 100, 1),
                    "Dipten %"       : round(dip_yakinlik * 100, 1),
                    "6Ay Bant"       : round(bant_6ay, 2),
                    "Zirve/Dip"      : round(zirve / dip, 2),
                })

        except Exception as e:
            if verbose: print(f"→ HATA: {e}")

    return pd.DataFrame(sonuclar)


if __name__ == "__main__":
    print("=" * 75)
    print("  UYUYAN DEVLER — Zirveden uzak, dibe yakın, hareketsiz")
    print(f"  Dönem  : 01.01.2023 → {datetime.today().strftime('%d.%m.%Y')}")
    print(f"  Hisse  : {len(BIST_HISSELER)}")
    print("=" * 75)
    print(f"  Kriter 1 — Zirveden uzaklık >= %{ZIRVE_UZAKLIK_MIN*100:.0f}")
    print(f"  Kriter 2 — Dipten yakınlık  <= %{DIP_YAKINLIK_MAX*100:.0f}")
    print(f"  Kriter 3 — 6 aylık bant     <= {SON_6AY_BANT_MAX}")
    print("=" * 75)
    print()

    df = tarama(BIST_HISSELER)

    print()
    print("=" * 75)
    print(f"  SONUÇ: {len(df)} hisse bulundu")
    print("=" * 75)

    if not df.empty:
        df = df.sort_values("Zirveden %", ascending=False)
        print()
        print(df.to_string(index=False))
        dosya = f"uyuyan_devler_v3_{datetime.today().strftime('%Y%m%d')}.csv"
        df.to_csv(dosya, index=False, encoding="utf-8-sig")
        print(f"\n  Kaydedildi: {dosya}")
    else:
        print("  Bulunamadı. Şu değerleri gevşet:")
        print(f"    ZIRVE_UZAKLIK_MIN = {ZIRVE_UZAKLIK_MIN} → 0.25 dene")
        print(f"    DIP_YAKINLIK_MAX  = {DIP_YAKINLIK_MAX}  → 0.50 dene")
        print(f"    SON_6AY_BANT_MAX  = {SON_6AY_BANT_MAX}  → 1.40 dene")
