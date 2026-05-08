"""
UYUYAN DEVLER TARAMASI
======================
2-3 yıldır hareketsiz kalmış BIST hisselerini tespit eder.

Kriterler:
  1. 3 yıllık fiyat değişimi < %40  (dar bant)
  2. 1 yıllık fiyat değişimi < %20  (son dönem de sakin)
  3. Son 20 gün hacim < 1 yıllık ortalama hacim  (hacim kuruyor)
  4. ATR/Fiyat < %3  (düşük volatilite)

Kullanım:
  python uyuyan_devler.py

Çıktı:
  uyuyan_devler_sonuc.csv
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings("ignore")

# ── BIST HİSSE LİSTESİ ──────────────────────────────────────────────────────
# bist_fd.xlsx varsa oradan okuyabilirsin, yoksa örnek liste kullanılır
# Kendi tam listenle değiştir:

BIST_HISSELER = [
    "ACSEL","ADEL","AEFES","AFYON","AGYO","AKCNS","AKENR","AKGRT","AKSA",
    "AKSEN","ALARK","ALBRK","ALCAR","ALGYO","ALKA","ALKIM","ANHYT","ANSGR",
    "ARCLK","ARFYE","ASELS","ASUZU","ATAGY","ATEKS","ATLAS","ATSYH","AVTUR",
    "AYCES","AYEN","AYGAZ","BAGFS","BAKAB","BANVT","BIMAS","BJKAS","BOSSA",
    "BRISA","BRMEN","BRSAN","BRYAT","BTCIM","BUCIM","BURCE","BURVA","BVSAN",
    "CCOLA","CELHA","CEMTS","CIMSA","CLEBI","CMENT","COSMO","DAPGM","DARDL",
    "DESAS","DEVA","DGATE","DGKLB","DMSAS","DOHOL","DOKTA","DURDO","DZGYO",
    "ECILC","ECZYT","EDIP","EGEEN","EGPRO","EGSER","EKGYO","EMKEL","EMPAE",
    "EMNIS","ENKAI","ENJSA","ENTRA","ERBOS","EREGL","ERSU","ESCOM","ESEN",
    "ETYAT","EUYO","FENER","FLAP","FMIZP","FONET","FRIGO","GARAN","GLYHO",
    "GOLTS","GOODY","GRNYO","GRSEL","GSDHO","GSRAY","GUBRF","GUNDG","HALKB",
    "HATSN","HEDEF","HEKTS","HURGZ","ICBCT","IHLGM","IHLAS","IHYAY","INDES",
    "INTEM","INVEO","IPEKE","ISCTR","ISGSY","ISGYO","ISKUR","ISYAT","IZMDC",
    "JANTS","KAREL","KARSN","KAYSE","KCHOL","KENT","KERVN","KFEIN","KLMSN",
    "KNFRT","KONYA","KORDS","KOZAA","KOZAL","KRDMA","KRDMB","KRDMD","KRGYO",
    "KRSTL","KTLEV","KUTPO","LOGO","LUKSK","LYDHO","MAARD","MAALT","MAKTK",
    "MANAS","MCARD","MEGAP","MEMS","MERKO","METAL","METRO","MGROS","MNDRS",
    "MRSHL","MTRYO","MZHLD","NATEN","NETAS","NETCD","NTHOL","NUGYO","NUHCM",
    "ODINE","OLMK","OTKAR","OYAYO","OYLUM","PARSN","PASEU","PEKGY","PEKGY",
    "PETUN","PINSU","PKART","PKENT","PNSUT","PRKAB","PRKME","QNBFK","RAYSG",
    "RHYME","RISEC","RYSAS","SAHOL","SANKO","SARKY","SASA","SELEC","SELGD",
    "SEKFK","SEKUR","SISE","SISMK","SKTAS","SMART","SNGYO","SNPAM","SONME",
    "TATGD","TAVHL","TCELL","TEKTU","THYAO","TKFEN","TMSN","TOASO","TRCAS",
    "TSKB","TSPOR","TTKOM","TTRAK","TUKAS","TUPRS","TURSG","UFUK","ULKER",
    "USDTR","VAKBN","VAKKO","VESTL","VKGYO","VKGYO","WNSA","YKBNK","YUNSA",
    "YYAPI","ZOREN",
]

# .IS eki ekle (Yahoo Finance BIST formatı)
def bist_ticker(sembol):
    return f"{sembol}.IS"

# ── PARAMETRELER ─────────────────────────────────────────────────────────────
ROC_3YIL_ESIK   = 40    # 3 yıllık değişim % üst sınırı
ROC_1YIL_ESIK   = 20    # 1 yıllık değişim % üst sınırı
HACIM_ORAN_ESIK = 1.0   # son 20 gün hacim / 1 yıl ort. hacim (< 1 = azalıyor)
ATR_ESIK        = 3.0   # ATR/Fiyat % üst sınırı
MIN_FIYAT       = 2.0   # Çok ucuz hisseleri ele (TL)
MIN_HACIM       = 100_000  # Minimum günlük hacim (likidite filtresi)

# ── TARAMA FONKSİYONU ────────────────────────────────────────────────────────
def tarama(hisseler, verbose=True):
    bitis  = datetime.today()
    baslangic = bitis - timedelta(days=4*365)  # 4 yıl veri çek (3 yıl hesap için buffer)

    sonuclar = []
    hata_listesi = []

    toplam = len(hisseler)
    for i, sembol in enumerate(hisseler, 1):
        ticker = bist_ticker(sembol)
        if verbose:
            print(f"[{i:3d}/{toplam}] {sembol:8s}", end=" ")

        try:
            df = yf.download(ticker, start=baslangic, end=bitis,
                             progress=False, auto_adjust=True)

            if df is None or len(df) < 200:
                if verbose: print("→ yetersiz veri")
                continue

            # yfinance yeni versiyonu multi-level column döndürüyor, düzelt
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            df = df[["Open","High","Low","Close","Volume"]].copy()
            df.dropna(inplace=True)

            son_fiyat = float(df["Close"].iloc[-1])

            # Fiyat filtresi
            if son_fiyat < MIN_FIYAT:
                if verbose: print(f"→ fiyat çok düşük ({son_fiyat:.2f})")
                continue

            # ── 1. ROC hesapları ──────────────────────────────────────────
            # 3 yıl = ~756 işlem günü
            bar_3yil = min(756, len(df)-1)
            bar_1yil = min(252, len(df)-1)

            fiyat_3yil_once = float(df["Close"].iloc[-bar_3yil])
            fiyat_1yil_once = float(df["Close"].iloc[-bar_1yil])

            roc_3yil = abs((son_fiyat - fiyat_3yil_once) / fiyat_3yil_once * 100)
            roc_1yil = abs((son_fiyat - fiyat_1yil_once) / fiyat_1yil_once * 100)

            # ── 2. Hacim karşılaştırması ──────────────────────────────────
            hacim_20  = df["Volume"].iloc[-20:].mean()
            hacim_252 = df["Volume"].iloc[-252:].mean()
            hacim_oran = hacim_20 / hacim_252 if hacim_252 > 0 else 99

            son_hacim = float(df["Volume"].iloc[-1])

            # Likidite filtresi
            if hacim_252 < MIN_HACIM:
                if verbose: print(f"→ hacim çok düşük")
                continue

            # ── 3. ATR hesabı (14 günlük) ─────────────────────────────────
            high = df["High"].iloc[-15:]
            low  = df["Low"].iloc[-15:]
            close_prev = df["Close"].iloc[-15:].shift(1)

            tr = pd.concat([
                high - low,
                (high - close_prev).abs(),
                (low  - close_prev).abs()
            ], axis=1).max(axis=1)

            atr14 = tr.iloc[-14:].mean()
            atr_oran = (atr14 / son_fiyat) * 100

            # ── 4. Bant genişliği (3 yıl) ────────────────────────────────
            pencere = df["Close"].iloc[-bar_3yil:]
            bant_max = float(pencere.max())
            bant_min = float(pencere.min())
            bant_genisligi = (bant_max - bant_min) / bant_min * 100

            # ── KRİTERLER ────────────────────────────────────────────────
            kriter1 = roc_3yil   < ROC_3YIL_ESIK
            kriter2 = roc_1yil   < ROC_1YIL_ESIK
            kriter3 = hacim_oran < HACIM_ORAN_ESIK
            kriter4 = atr_oran   < ATR_ESIK

            gecen = sum([kriter1, kriter2, kriter3, kriter4])

            if verbose:
                isaretler = f"{'✓' if kriter1 else '✗'}ROC3y " \
                            f"{'✓' if kriter2 else '✗'}ROC1y " \
                            f"{'✓' if kriter3 else '✗'}Hacim " \
                            f"{'✓' if kriter4 else '✗'}ATR  " \
                            f"→ {gecen}/4"
                print(isaretler)

            # En az 3 kriter geçenleri al
            if gecen >= 3:
                sonuclar.append({
                    "Sembol"          : sembol,
                    "Son Fiyat"       : round(son_fiyat, 2),
                    "ROC 3Yıl %"      : round(roc_3yil, 1),
                    "ROC 1Yıl %"      : round(roc_1yil, 1),
                    "Bant Genişliği %": round(bant_genisligi, 1),
                    "Hacim Oran"      : round(hacim_oran, 2),
                    "ATR/Fiyat %"     : round(atr_oran, 2),
                    "Kriter"          : f"{gecen}/4",
                    "3Y Min"          : round(bant_min, 2),
                    "3Y Max"          : round(bant_max, 2),
                })

        except Exception as e:
            hata_listesi.append((sembol, str(e)))
            if verbose: print(f"→ HATA: {e}")

    return pd.DataFrame(sonuclar), hata_listesi


# ── ANA ÇALIŞTIRMA ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  UYUYAN DEVLER TARAMASI — BIST")
    print(f"  Tarih: {datetime.today().strftime('%d.%m.%Y')}")
    print(f"  Toplam hisse: {len(BIST_HISSELER)}")
    print("=" * 60)
    print()
    print("Kriterler:")
    print(f"  ROC 3 yıl  < %{ROC_3YIL_ESIK}")
    print(f"  ROC 1 yıl  < %{ROC_1YIL_ESIK}")
    print(f"  Hacim oran < {HACIM_ORAN_ESIK} (azalıyor)")
    print(f"  ATR/Fiyat  < %{ATR_ESIK}")
    print()

    df_sonuc, hatalar = tarama(BIST_HISSELER)

    print()
    print("=" * 60)
    print(f"  SONUÇ: {len(df_sonuc)} hisse bulundu")
    print("=" * 60)

    if not df_sonuc.empty:
        # Sıralama: en az hareket eden önce
        df_sonuc = df_sonuc.sort_values("ROC 3Yıl %", ascending=True)

        print()
        print(df_sonuc.to_string(index=False))

        # CSV kaydet
        cikti = f"uyuyan_devler_{datetime.today().strftime('%Y%m%d')}.csv"
        df_sonuc.to_csv(cikti, index=False, encoding="utf-8-sig")
        print()
        print(f"  Kaydedildi: {cikti}")
    else:
        print("  Kriterleri karşılayan hisse bulunamadı.")
        print("  Eşik değerlerini gevşetmeyi dene.")

    if hatalar:
        print()
        print(f"  Hata olan hisseler ({len(hatalar)}):")
        for s, e in hatalar[:10]:
            print(f"    {s}: {e}")
