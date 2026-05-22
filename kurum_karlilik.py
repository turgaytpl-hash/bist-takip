"""
kurum_karlilik.py — Kurum Bazlı Alış/Satış Karlılık Analizi

Her kurum için:
  - Ne zaman aldı, ne zaman sattı
  - Tutma süresi
  - Kazanç/kayıp
  - Kime devretti, devir alan ne kazandı

Kullanım: python kurum_karlilik.py
Çıkış   : kurum_karlilik.xlsx
"""

import pandas as pd
import numpy as np
import yfinance as yf
import warnings
from datetime import datetime, timedelta
import time

warnings.filterwarnings("ignore")

TAKAS_CSV    = "src/data/takas/kurum_takas.csv"
GETIRI_GUNLER = [15, 30, 60, 90]
HEDEF_KURUMLAR = [
    'TERA', 'MARBAS', 'INFO', 'BULLS', 'PUSULA', 'A1_CAPITAL', 'ALNUS',
    'HALK_YATIRIM', 'IS_YATIRIM', 'YAPI_KREDI', 'GARANTI', 'VAKIF',
    'AK_YATIRIM', 'TEB', 'ZIRAAT_YATIRIM', 'DENIZ_YATIRIM',
    'YABANCI', 'YAT_FONLARI', 'EMEKLILIK', 'MIDAS'
]

# ─── VERİ YÜKLE ───────────────────────────────────────────────────────────────
def veri_yukle():
    df = pd.read_csv(TAKAS_CSV, low_memory=False)
    df = df.dropna(subset=['donem', 'kurum', 'hisse'])
    df['kurum'] = df['kurum'].str.strip().str.upper()
    df['hisse'] = df['hisse'].str.strip().str.upper()
    df['oran2'] = pd.to_numeric(df['oran2'], errors='coerce').fillna(0)
    df['kurum'] = df['kurum'].replace({
        'DENIZ_YATIRUM': 'DENIZ_YATIRIM',
        'AK_YATRIRIM'  : 'AK_YATIRIM',
    })

    def donem_sira(d):
        d = str(d).strip()
        try:
            if len(d) == 8 and d.isdigit():
                return int(d)
            elif len(d) == 7 and '_' in d:
                y, m = d.split('_')
                return int(y) * 10000 + int(m) * 100 + 50
            elif len(d) == 9 and '_' in d:
                ym, w = d.split('_')
                return int(ym) * 100 + int(w) * 10
        except:
            pass
        return 0

    df['donem_sira'] = df['donem'].apply(donem_sira)
    df = df[df['donem_sira'] > 0]
    df = df.sort_values(['hisse', 'kurum', 'donem_sira'])
    return df

# ─── DÖNEM → TARİH ────────────────────────────────────────────────────────────
def donem_tarih(donem):
    d = str(donem).strip()
    try:
        if len(d) == 8 and d.isdigit():
            return pd.to_datetime(d, format='%Y%m%d')
        elif len(d) == 7 and '_' in d:
            y, m = d.split('_')
            return pd.to_datetime(f"{y}-{m}-01") + pd.offsets.MonthEnd(0)
        elif len(d) == 9 and '_' in d:
            ym, w = d.split('_')
            y, m = int(ym[:4]), int(ym[4:6])
            ilk = pd.to_datetime(f"{y}-{m}-01")
            gun_fark = (4 - ilk.weekday()) % 7
            return ilk + timedelta(days=gun_fark) + timedelta(weeks=int(w)-1)
    except:
        pass
    return None

# ─── FİYAT ÇEK ────────────────────────────────────────────────────────────────
_fiyat_cache = {}

def fiyat_al(hisse, tarih, delta_max=5):
    """Tarihe en yakın kapanış fiyatını döner."""
    if tarih is None:
        return None
    key = f"{hisse}_{tarih.date()}"
    if key in _fiyat_cache:
        return _fiyat_cache[key]
    try:
        df = yf.download(
            f"{hisse}.IS",
            start=tarih - timedelta(days=5),
            end=tarih + timedelta(days=delta_max+2),
            progress=False, auto_adjust=True
        )
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if df.empty:
            return None
        close = df['Close'].dropna()
        for delta in range(delta_max):
            t = tarih + timedelta(days=delta)
            sub = close[close.index.date >= t.date()]
            if not sub.empty:
                val = float(sub.iloc[0])
                _fiyat_cache[key] = val
                return val
    except:
        pass
    return None

# ─── KURUM POZİSYON TARİHÇESİ ─────────────────────────────────────────────────
def kurum_pozisyon_analiz(df, kurum):
    """
    Kurumun her hissede ne zaman aldığını, ne zaman sattığını tespit eder.
    Alış = oran2 artışı, Satış = oran2 azalışı
    """
    df_k = df[df['kurum'] == kurum].copy()
    hisseler = df_k['hisse'].unique()
    sonuclar = []

    for hisse in hisseler:
        df_h = df_k[df_k['hisse'] == hisse].sort_values('donem_sira').copy()
        if len(df_h) < 2:
            continue

        # Pozisyon değişimlerini tespit et
        df_h['oran_fark'] = df_h['oran2'].diff()

        # Önemli alışlar (>%1.5 artış)
        alislar = df_h[df_h['oran_fark'] > 1.5].copy()
        # Önemli satışlar (>%1.5 azalış)
        satislar = df_h[df_h['oran_fark'] < -1.5].copy()

        if alislar.empty or satislar.empty:
            continue

        # Her alış için sonraki satışı bul
        for _, alis in alislar.iterrows():
            sonraki_satis = satislar[satislar['donem_sira'] > alis['donem_sira']]
            if sonraki_satis.empty:
                continue

            satis = sonraki_satis.iloc[0]

            alis_tarih  = donem_tarih(alis['donem'])
            satis_tarih = donem_tarih(satis['donem'])

            if alis_tarih is None or satis_tarih is None:
                continue

            # Tutma süresi
            tutma_gun = (satis_tarih - alis_tarih).days

            # Fiyat çek
            alis_fiyat  = fiyat_al(hisse, alis_tarih)
            satis_fiyat = fiyat_al(hisse, satis_tarih)

            if alis_fiyat and satis_fiyat and alis_fiyat > 0:
                getiri = round((satis_fiyat / alis_fiyat - 1) * 100, 2)
            else:
                getiri = None

            # Satış sonrası getiriler (devir alan ne kazandı)
            devir_sonrasi = {}
            for g in GETIRI_GUNLER:
                hedef = satis_tarih + timedelta(days=g)
                if hedef.date() > datetime.today().date():
                    devir_sonrasi[f'devir_sonrasi_{g}g'] = None
                    continue
                fiyat_g = fiyat_al(hisse, hedef, delta_max=3)
                if fiyat_g and satis_fiyat and satis_fiyat > 0:
                    devir_sonrasi[f'devir_sonrasi_{g}g'] = round(
                        (fiyat_g / satis_fiyat - 1) * 100, 2)
                else:
                    devir_sonrasi[f'devir_sonrasi_{g}g'] = None

            sonuclar.append({
                'kurum'        : kurum,
                'hisse'        : hisse,
                'alis_donem'   : alis['donem'],
                'satis_donem'  : satis['donem'],
                'alis_oran'    : round(alis['oran2'], 2),
                'satis_oran'   : round(satis['oran2'], 2),
                'alis_fark'    : round(alis['oran_fark'], 2),
                'satis_fark'   : round(satis['oran_fark'], 2),
                'tutma_gun'    : tutma_gun,
                'alis_fiyat'   : alis_fiyat,
                'satis_fiyat'  : satis_fiyat,
                'kurum_getiri%': getiri,
                **devir_sonrasi,
            })
        time.sleep(0.05)

    return pd.DataFrame(sonuclar) if sonuclar else pd.DataFrame()

# ─── ANA AKIŞ ─────────────────────────────────────────────────────────────────
def main():
    print("=" * 65)
    print("  KURUM KARLILIK ANALİZİ")
    print(f"  {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print("=" * 65)
    print(f"  Analiz edilecek kurumlar: {HEDEF_KURUMLAR}")

    print("\n📂 Veri yükleniyor...")
    df = veri_yukle()
    print(f"  {len(df):,} satır yüklendi")

    tum_sonuclar = []

    for kurum in HEDEF_KURUMLAR:
        print(f"\n🔍 {kurum} analiz ediliyor...")
        sonuc = kurum_pozisyon_analiz(df, kurum)
        if not sonuc.empty:
            tum_sonuclar.append(sonuc)
            print(f"  {len(sonuc)} alış/satış döngüsü bulundu")
        else:
            print(f"  Yeterli veri yok")

    if not tum_sonuclar:
        print("❌ Hiç sonuç yok!")
        return

    ana_df = pd.concat(tum_sonuclar, ignore_index=True)

    # ─── Kurum bazlı özet ────────────────────────────────────────
    print("\n" + "=" * 65)
    print("  KURUM KARLILIK ÖZETİ")
    print("=" * 65)

    ozet = ana_df.groupby('kurum').agg(
        islem_sayisi     = ('hisse', 'count'),
        ort_tutma_gun    = ('tutma_gun', 'mean'),
        ort_getiri       = ('kurum_getiri%', 'mean'),
        win_rate         = ('kurum_getiri%', lambda x: (x.dropna() > 0).mean() * 100),
        ort_devir_15g    = ('devir_sonrasi_15g', 'mean'),
        ort_devir_30g    = ('devir_sonrasi_30g', 'mean'),
        ort_devir_60g    = ('devir_sonrasi_60g', 'mean'),
        win_devir_30g    = ('devir_sonrasi_30g', lambda x: (x.dropna() > 0).mean() * 100),
    ).round(2)

    print(ozet.to_string())

    # ─── TERA özel analiz ────────────────────────────────────────
    print("\n" + "=" * 65)
    print("  TERA ÖZEL ANALİZ")
    print("=" * 65)

    tera = ana_df[ana_df['kurum'] == 'TERA'].copy()
    if not tera.empty:
        print(f"\n  {len(tera)} alış/satış döngüsü")
        print(f"  Ort. tutma süresi : {tera['tutma_gun'].mean():.0f} gün")
        print(f"  Ort. kurum getirisi: %{tera['kurum_getiri%'].mean():.1f}")
        print(f"  Win rate          : %{(tera['kurum_getiri%'].dropna() > 0).mean()*100:.0f}")
        print(f"\n  Devir sonrası kazanç (TERA sattıktan sonra fiyat ne yaptı?):")
        for g in GETIRI_GUNLER:
            col = f'devir_sonrasi_{g}g'
            vals = tera[col].dropna()
            if len(vals) > 0:
                poz = (vals > 0).sum()
                print(f"    {g:2d}g → Ort:%{vals.mean():+.1f}  "
                      f"Win:{poz}/{len(vals)}(%{poz/len(vals)*100:.0f})")

        print(f"\n  TERA alış/satış detay:")
        print(tera[['hisse','alis_donem','satis_donem','tutma_gun',
                    'kurum_getiri%','devir_sonrasi_30g','devir_sonrasi_60g']].to_string(index=False))

    # ─── Excel ───────────────────────────────────────────────────
    out = "kurum_karlilik.xlsx"
    with pd.ExcelWriter(out, engine="openpyxl") as w:
        ozet.to_excel(w, sheet_name="OZET")
        ana_df.to_excel(w, sheet_name="Tum_Islemler", index=False)
        for kurum in HEDEF_KURUMLAR:
            df_k = ana_df[ana_df['kurum'] == kurum]
            if not df_k.empty:
                df_k.to_excel(w, sheet_name=kurum[:31], index=False)

    print(f"\n💾 {out} kaydedildi")
    print(f"   Toplam işlem : {len(ana_df)}")
    print("\n✅ Tamamlandı!")

if __name__ == "__main__":
    main()
