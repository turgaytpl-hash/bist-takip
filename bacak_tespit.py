"""
bacak_tespit.py — AKD vs Takas T+2 Bacak Tespit Modülü
"""

import pandas as pd
import numpy as np
from pathlib import Path
from pandas.tseries.offsets import CustomBusinessDay

TATILLER = pd.to_datetime([
    '2026-01-01', '2026-04-23', '2026-05-01',
    '2026-05-19', '2026-07-15', '2026-08-30', '2026-10-29',
])
TR_IS_GUNU = CustomBusinessDay(holidays=TATILLER)

def parse_sayi(s):
    try:
        return float(str(s).replace('.', '').replace(',', '.'))
    except:
        return np.nan

def eslesme_tablosu() -> pd.DataFrame:
    akd_tarihleri = pd.to_datetime([
        '2026-04-21','2026-04-22','2026-04-24',
        '2026-04-27','2026-04-28','2026-04-29','2026-04-30',
    ])
    rows = []
    for t in akd_tarihleri:
        t2 = t + 2 * TR_IS_GUNU
        rows.append({
            'AKD_TARIHI':   t.strftime('%Y%m%d'),
            'TAKAS_TARIHI': t2.strftime('%Y%m%d'),
            'AKD_LABEL':    t.strftime('%d.%m.%Y'),
            'TAKAS_LABEL':  t2.strftime('%d.%m.%Y'),
        })
    return pd.DataFrame(rows)

def oku_takas_gunu(takas_klasor: Path, tarih_str: str) -> pd.DataFrame:
    klasor = takas_klasor / tarih_str
    if klasor.exists():
        dosyalar = list(klasor.glob(f"*_{tarih_str}.xlsx"))
    else:
        dosyalar = list(takas_klasor.glob(f"*_{tarih_str}.xlsx"))

    if not dosyalar:
        return pd.DataFrame()

    parcalar = []
    for dosya in dosyalar:
        kurum = dosya.stem.replace(f"_{tarih_str}", "")
        try:
            df = pd.read_excel(dosya)
            df.columns = df.columns.str.strip()
            if 'HiSSE' not in df.columns or 'NET(Adet)' not in df.columns:
                continue
            df = df[['HiSSE', 'NET(Adet)']].copy()
            df.columns = ['HISSE', 'NET_ADET']
            df['NET_ADET'] = df['NET_ADET'].apply(parse_sayi)
            df['KURUM'] = kurum
            df = df.dropna(subset=['HISSE'])
            df['HISSE'] = df['HISSE'].astype(str).str.strip()
            df = df[df['HISSE'].str.len() >= 3]
            parcalar.append(df)
        except:
            pass

    return pd.concat(parcalar, ignore_index=True) if parcalar else pd.DataFrame()

def oku_akd_gunu(akd_klasor: Path, tarih_str: str) -> pd.DataFrame:
    ay_str = tarih_str[:6]
    dosyalar = list(akd_klasor.glob(f"AKD_*_{ay_str}.xlsx"))

    if not dosyalar:
        return pd.DataFrame()

    parcalar = []
    for dosya in dosyalar:
        kurum = dosya.stem.replace("AKD_", "").replace(f"_{ay_str}", "")
        try:
            xl = pd.ExcelFile(dosya)
            if tarih_str not in xl.sheet_names:
                continue
            df = xl.parse(tarih_str)
            df.columns = df.columns.str.strip()
            if 'HiSSE' not in df.columns or 'NET(Adet)' not in df.columns:
                continue
            df = df[['HiSSE', 'NET(Adet)']].copy()
            df.columns = ['HISSE', 'NET_ADET']
            df['NET_ADET'] = df['NET_ADET'].apply(parse_sayi)
            df['KURUM'] = kurum
            df = df.dropna(subset=['HISSE'])
            df['HISSE'] = df['HISSE'].astype(str).str.strip()
            df = df[df['HISSE'].str.len() >= 3]
            parcalar.append(df)
        except:
            pass

    return pd.concat(parcalar, ignore_index=True) if parcalar else pd.DataFrame()

def bacak_tespit_hesapla(akd_df: pd.DataFrame, takas_df: pd.DataFrame, esik: float = 0.80) -> pd.DataFrame:
    if akd_df.empty or takas_df.empty:
        return pd.DataFrame()

    sonuclar = []
    hisseler = set(akd_df['HISSE'].unique()) & set(takas_df['HISSE'].unique())

    for hisse in hisseler:
        akd_h   = akd_df[akd_df['HISSE'] == hisse]
        takas_h = takas_df[takas_df['HISSE'] == hisse]

        akd_poz   = akd_h[akd_h['NET_ADET'] > 0][['KURUM','NET_ADET']]
        takas_poz = takas_h[takas_h['NET_ADET'] > 0][['KURUM','NET_ADET']]

        if akd_poz.empty or takas_poz.empty:
            continue

        for _, akd_row in akd_poz.iterrows():
            akd_kurum = akd_row['KURUM']
            akd_adet  = akd_row['NET_ADET']
            if akd_adet < 10000:
                continue

            takas_ayni = takas_h[takas_h['KURUM'] == akd_kurum]['NET_ADET']
            takas_ayni_adet = float(takas_ayni.values[0]) if len(takas_ayni) > 0 else 0.0
            if pd.isna(takas_ayni_adet):
                takas_ayni_adet = 0.0

            if takas_ayni_adet < akd_adet * 0.30:
                for _, takas_row in takas_poz.iterrows():
                    takas_kurum = takas_row['KURUM']
                    takas_adet  = takas_row['NET_ADET']
                    if takas_kurum == akd_kurum or takas_adet < 10000:
                        continue

                    eslesme = min(akd_adet, takas_adet) / max(akd_adet, takas_adet)
                    if eslesme >= esik:
                        sonuclar.append({
                            'HISSE'       : hisse,
                            'BACAK_KURUM' : akd_kurum,
                            'BACAK_ADET'  : int(akd_adet),
                            'GERCEK_KURUM': takas_kurum,
                            'TAKAS_ADET'  : int(takas_adet),
                            'ESLESME_%'   : round(eslesme * 100, 1),
                        })

    df = pd.DataFrame(sonuclar)
    if not df.empty:
        df = df.sort_values('ESLESME_%', ascending=False)
    return df

def tum_bacaklari_getir(takas_klasor: Path, akd_klasor: Path, esik: float = 0.80) -> tuple:
    eslesmeler = eslesme_tablosu()
    tum = []

    for _, row in eslesmeler.iterrows():
        akd_df   = oku_akd_gunu(akd_klasor,   row['AKD_TARIHI'])
        takas_df = oku_takas_gunu(takas_klasor, row['TAKAS_TARIHI'])

        if akd_df.empty or takas_df.empty:
            continue

        bacaklar = bacak_tespit_hesapla(akd_df, takas_df, esik)
        if not bacaklar.empty:
            bacaklar['AKD_TARIHI']   = row['AKD_LABEL']
            bacaklar['TAKAS_TARIHI'] = row['TAKAS_LABEL']
            tum.append(bacaklar)

    if not tum:
        return pd.DataFrame(), pd.DataFrame()

    detay = pd.concat(tum, ignore_index=True)
    harita = detay.groupby(['BACAK_KURUM','GERCEK_KURUM']).agg(
        TEKRAR      = ('HISSE', 'count'),
        HISSELER    = ('HISSE', lambda x: ', '.join(sorted(set(x)))),
        ORT_ESLESME = ('ESLESME_%', 'mean'),
    ).reset_index().sort_values('TEKRAR', ascending=False)
    harita['ORT_ESLESME'] = harita['ORT_ESLESME'].round(1)

    return detay, harita
