"""
handoff_analiz.py v3 — Smart Money Handoff / Tahta Teslim Algoritması

v3 Değişiklikler:
  - 20 kurumun tamamı takip ediliyor
  - Kurum rolleri tanımlandı (Birikimci/Dağıtıcı/Büyük Yerli/Fon-Yabancı)
  - Getiri süresi 30/60/90/180 güne uzatıldı
  - Alarm tipleri: Akıllı Para Devri / Büyük Kurum Çıkışı / Fon Girişi

Kullanım: python handoff_analiz.py
Çıkış   : handoff_sonuclar.xlsx
"""

import pandas as pd
import numpy as np
import yfinance as yf
import warnings
from datetime import datetime, timedelta
import time

warnings.filterwarnings("ignore")

# ─── AYARLAR ──────────────────────────────────────────────────────────────────
TAKAS_CSV        = "src/data/takas/kurum_takas.csv"
MIN_POZISYON     = 1.5    # dönem bazında min oran değişimi %
MIN_SURE         = 3      # accumulation için min ardışık dönem
MIN_HANDOFF_GUCU = 2.0    # satan_fark + alan_fark toplamı min
GETIRI_GUNLER    = [30, 60, 90, 180]

# ─── KURUM ROLLERİ ────────────────────────────────────────────────────────────
BIRIKIMCI   = ['MARBAS', 'BULLS', 'PUSULA', 'ALNUS', 'A1_CAPITAL']
DAGITICI    = ['INFO', 'TERA']
BUYUK_YERLI = ['IS_YATIRIM', 'YAPI_KREDI', 'AK_YATIRIM', 'GARANTI',
               'VAKIF', 'TEB', 'HALK_YATIRIM', 'ZIRAAT_YATIRIM', 'DENIZ_YATIRIM']
FON_YABANCI = ['YABANCI', 'YAT_FONLARI', 'EMEKLILIK', 'MIDAS']

TUM_KURUMLAR = BIRIKIMCI + DAGITICI + BUYUK_YERLI + FON_YABANCI

def kurum_rol(kurum):
    if kurum in BIRIKIMCI:   return "Birikimci"
    if kurum in DAGITICI:    return "Dağıtıcı"
    if kurum in BUYUK_YERLI: return "Büyük Yerli"
    if kurum in FON_YABANCI: return "Fon/Yabancı"
    return "Diğer"

def alarm_tipi(satan, alan):
    """Handoff tipini belirler."""
    s_rol = kurum_rol(satan)
    a_rol = kurum_rol(alan)

    if s_rol == "Birikimci" and a_rol in ["Birikimci", "Dağıtıcı"]:
        return "🔄 Akıllı Para Devri"
    if s_rol == "Büyük Yerli" and a_rol in ["Birikimci", "Fon/Yabancı"]:
        return "🏦 Büyük Kurum Çıkışı"
    if a_rol == "Fon/Yabancı":
        return "📦 Fon/Yabancı Girişi"
    if s_rol == "Dağıtıcı":
        return "⚠️ Dağıtım Başladı"
    if a_rol == "Birikimci":
        return "🟢 Birikim Başladı"
    return "📊 Kurum Değişimi"

# ─── VERİ YÜKLE ───────────────────────────────────────────────────────────────
def veri_yukle():
    df = pd.read_csv(TAKAS_CSV, low_memory=False)
    df = df.dropna(subset=['donem', 'kurum', 'hisse'])
    df['kurum'] = df['kurum'].str.strip().str.upper()
    df['hisse'] = df['hisse'].str.strip().str.upper()
    df['oran2'] = pd.to_numeric(df['oran2'], errors='coerce').fillna(0)

    # Kurum adı normalizasyonu
    df['kurum'] = df['kurum'].replace({
        'DENIZ_YATIRUM': 'DENIZ_YATIRIM',
        'AK_YATRIRIM':   'AK_YATIRIM',
    })

    def donem_sira(d):
        d = str(d).strip()
        try:
            if len(d) == 8 and d.isdigit():
                return int(d)
            elif len(d) == 7 and '_' in d:
                y, m = d.split('_')
                return int(y) * 10000 + int(m) * 100
            elif len(d) == 9 and '_' in d:
                ym, w = d.split('_')
                return int(ym[:4]) * 10000 + int(ym[4:6]) * 100 + int(w)
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
            ilk_cuma = ilk + timedelta(days=gun_fark)
            return ilk_cuma + timedelta(weeks=int(w) - 1)
    except:
        pass
    return None

# ─── ACCUMULATION DOĞRULAMA ───────────────────────────────────────────────────
def accumulation_var_mi(df_hisse_kurum, handoff_donem_sira):
    df_s = df_hisse_kurum[
        df_hisse_kurum['donem_sira'] < handoff_donem_sira
    ].sort_values('donem_sira').tail(MIN_SURE + 2)

    if len(df_s) < MIN_SURE:
        return False, 0

    son = df_s.tail(MIN_SURE)
    oranlar = son['oran2'].values
    artan = sum(1 for i in range(1, len(oranlar)) if oranlar[i] > oranlar[i-1])
    toplam_artis = float(oranlar[-1]) - float(oranlar[0])

    if artan >= (MIN_SURE - 1) and toplam_artis >= MIN_POZISYON * 1.5:
        return True, round(toplam_artis, 2)
    return False, 0

# ─── HANDOFF TESPİTİ ──────────────────────────────────────────────────────────
def handoff_tespit(df, hisse):
    df_h = df[df['hisse'] == hisse].copy()
    if len(df_h) < 2:
        return []

    donemler = sorted(df_h['donem_sira'].unique())
    handoffler = []

    for i in range(1, len(donemler)):
        onceki_sira  = donemler[i-1]
        simdiki_sira = donemler[i]

        df_once  = df_h[df_h['donem_sira'] == onceki_sira]
        df_simdi = df_h[df_h['donem_sira'] == simdiki_sira]

        if df_simdi.empty:
            continue

        donem = df_simdi['donem'].iloc[0]
        tip   = df_simdi['tip'].iloc[0]

        # 20 kurumun tamamı için değişim hesapla
        degisim = {}
        oran_map = {}  # kurum → (oran_once, oran_simdi)
        for kurum in TUM_KURUMLAR:
            o = df_once[df_once['kurum'] == kurum]
            s = df_simdi[df_simdi['kurum'] == kurum]
            oran_once  = float(o['oran2'].iloc[0]) if not o.empty else 0.0
            oran_simdi = float(s['oran2'].iloc[0]) if not s.empty else 0.0
            degisim[kurum] = oran_simdi - oran_once
            oran_map[kurum] = (round(oran_once, 2), round(oran_simdi, 2))

        satanlar = {k: v for k, v in degisim.items() if v < -MIN_POZISYON}
        alanlar  = {k: v for k, v in degisim.items() if v >  MIN_POZISYON}

        for satan, s_fark in satanlar.items():
            for alan, a_fark in alanlar.items():
                if satan == alan:
                    continue
                if abs(s_fark) + a_fark < MIN_HANDOFF_GUCU:
                    continue

                # Accumulation validasyonu
                df_satan = df_h[df_h['kurum'] == satan]
                acc_var, acc_artis = accumulation_var_mi(df_satan, simdiki_sira)

                # Net % pozisyonlar
                satan_once, satan_simdi = oran_map.get(satan, (0, 0))
                alan_once,  alan_simdi  = oran_map.get(alan,  (0, 0))

                handoffler.append({
                    'hisse'         : hisse,
                    'donem'         : donem,
                    'tip'           : tip,
                    'donem_sira'    : simdiki_sira,
                    'satan'         : satan,
                    'satan_rol'     : kurum_rol(satan),
                    'satan_once%'   : satan_once,
                    'satan_simdi%'  : satan_simdi,
                    'alan'          : alan,
                    'alan_rol'      : kurum_rol(alan),
                    'alan_once%'    : alan_once,
                    'alan_simdi%'   : alan_simdi,
                    'alarm_tipi'    : alarm_tipi(satan, alan),
                    'satan_fark'    : round(s_fark, 2),
                    'alan_fark'     : round(a_fark, 2),
                    'toplam_guc'    : round(abs(s_fark) + a_fark, 2),
                    'accumulation'  : acc_var,
                    'acc_artis_pct' : acc_artis,
                    'handoff_tarih' : donem_tarih(donem),
                })

    return handoffler

# ─── GETİRİ HESAPLA ───────────────────────────────────────────────────────────
def getiri_hesapla(hisse, tarih):
    if tarih is None:
        return {f'getiri_{g}g': None for g in GETIRI_GUNLER}
    try:
        bitis = tarih + timedelta(days=max(GETIRI_GUNLER) + 15)
        df = yf.download(f"{hisse}.IS",
                         start=tarih - timedelta(days=5),
                         end=bitis,
                         progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if df.empty:
            return {f'getiri_{g}g': None for g in GETIRI_GUNLER}

        close = df['Close'].dropna()
        giris = None
        for delta in range(6):
            t = tarih + timedelta(days=delta)
            sub = close[close.index.date >= t.date()]
            if not sub.empty:
                giris = float(sub.iloc[0])
                break

        if not giris:
            return {f'getiri_{g}g': None for g in GETIRI_GUNLER}

        sonuclar = {}
        for g in GETIRI_GUNLER:
            hedef = tarih + timedelta(days=g)
            sub = close[close.index.date >= hedef.date()]
            sonuclar[f'getiri_{g}g'] = round(
                (float(sub.iloc[0]) / giris - 1) * 100, 2
            ) if not sub.empty else None
        return sonuclar
    except:
        return {f'getiri_{g}g': None for g in GETIRI_GUNLER}

# ─── ANA AKIŞ ─────────────────────────────────────────────────────────────────
def main():
    print("=" * 65)
    print("  SMART MONEY HANDOFF ANALİZİ v3")
    print(f"  {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print("=" * 65)
    print(f"\n  Takip edilen kurum sayısı: {len(TUM_KURUMLAR)}")
    print(f"  MIN_POZISYON={MIN_POZISYON}%  MIN_SURE={MIN_SURE}  MIN_HANDOFF_GUCU={MIN_HANDOFF_GUCU}")
    print(f"  Getiri ölçüm: {GETIRI_GUNLER} gün")

    print("\n📂 Veri yükleniyor...")
    df = veri_yukle()
    sira_map = df.groupby('donem')['donem_sira'].first().to_dict()
    donemler = sorted(df['donem'].unique(), key=lambda d: sira_map.get(d, 0))
    print(f"  {len(df):,} satır | {df['hisse'].nunique()} hisse | {len(donemler)} dönem")
    print(f"  Aralık: {donemler[0]} → {donemler[-1]}")

    print("\n🔍 Handoff tespiti (20 kurum)...")
    hisseler = sorted(df['hisse'].unique())
    tum = []
    for i, hisse in enumerate(hisseler):
        tum.extend(handoff_tespit(df, hisse))
        if (i+1) % 100 == 0:
            print(f"  {i+1}/{len(hisseler)} — {len(tum)} handoff")

    print(f"\n  Toplam: {len(tum)} handoff")
    if not tum:
        print("❌ Hiç handoff bulunamadı!")
        return

    hdf = pd.DataFrame(tum).sort_values(
        ['donem_sira', 'toplam_guc'], ascending=[True, False]
    ).reset_index(drop=True)

    acc_n = (hdf['accumulation'] == True).sum()
    print(f"  Accumulation doğrulanmış: {acc_n} ({acc_n/len(hdf)*100:.0f}%)")

    # Alarm tipi dağılımı
    print("\n  Alarm Tipi Dağılımı:")
    print(hdf['alarm_tipi'].value_counts().to_string())

    print("\n📈 Getiriler hesaplanıyor...")
    benzersiz = hdf[['hisse', 'handoff_tarih']].drop_duplicates()
    gmap = {}
    for i, (_, row) in enumerate(benzersiz.iterrows()):
        key = (row['hisse'], str(row['handoff_tarih']))
        gmap[key] = getiri_hesapla(row['hisse'], row['handoff_tarih'])
        if (i+1) % 20 == 0:
            print(f"  {i+1}/{len(benzersiz)}")
        time.sleep(0.1)

    for col in [f'getiri_{g}g' for g in GETIRI_GUNLER]:
        hdf[col] = hdf.apply(
            lambda r: gmap.get((r['hisse'], str(r['handoff_tarih'])), {}).get(col), axis=1
        )

    # ─── Sonuçlar ────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("  BACKTEST SONUÇLARI")
    print("=" * 65)

    for filtre_ad, filtre in [
        ("Tüm Handoffler", None),
        ("🔄 Akıllı Para Devri", hdf['alarm_tipi'] == "🔄 Akıllı Para Devri"),
        ("🏦 Büyük Kurum Çıkışı", hdf['alarm_tipi'] == "🏦 Büyük Kurum Çıkışı"),
        ("📦 Fon/Yabancı Girişi", hdf['alarm_tipi'] == "📦 Fon/Yabancı Girişi"),
        ("Accumulation Doğrulanmış", hdf['accumulation'] == True),
    ]:
        df_f = hdf if filtre is None else hdf[filtre]
        if len(df_f) == 0:
            continue
        print(f"\n  [{filtre_ad}] — {len(df_f)} handoff")
        for g in GETIRI_GUNLER:
            col = f'getiri_{g}g'
            vals = df_f[col].dropna()
            if len(vals) == 0:
                continue
            poz = (vals > 0).sum()
            print(f"    {g:3d}g → Ort:%{vals.mean():+.1f}  "
                  f"Med:%{vals.median():+.1f}  "
                  f"Win:{poz}/{len(vals)}(%{poz/len(vals)*100:.0f})  "
                  f"Min:%{vals.min():.1f} Max:%{vals.max():.1f}")

    # Çift istatistikleri
    print("\n  Top Handoff Çiftleri (min 2 örnek, 60g getiri):")
    ciftler = hdf.groupby(['satan', 'alan', 'alarm_tipi']).agg(
        sayi      = ('hisse', 'count'),
        ort_60g   = ('getiri_60g', 'mean'),
        ort_90g   = ('getiri_90g', 'mean'),
        win_60g   = ('getiri_60g', lambda x: (x > 0).sum()),
        acc_onay  = ('accumulation', 'sum'),
        ort_guc   = ('toplam_guc', 'mean'),
    ).reset_index()
    ciftler['win_%'] = (ciftler['win_60g'] / ciftler['sayi'] * 100).round(0)
    ciftler = ciftler[ciftler['sayi'] >= 2].sort_values('sayi', ascending=False)
    print(ciftler.to_string(index=False))

    # Matris
    print("\n  Kurum İlişki Matrisi:")
    matris = hdf.groupby(['satan', 'alan']).size().unstack(fill_value=0)
    print(matris.to_string())

    # ─── Parquet (dashboard için hızlı okuma) ────────────────────
    import os
    parquet_dir = "src/data/takas"
    os.makedirs(parquet_dir, exist_ok=True)
    parquet_path = f"{parquet_dir}/handoff_sonuclar.parquet"
    hdf.to_parquet(parquet_path, index=False)
    print(f"\n💾 Parquet kaydedildi: {parquet_path}")

    # ─── Excel ───────────────────────────────────────────────────
    out = "handoff_sonuclar.xlsx"
    with pd.ExcelWriter(out, engine="openpyxl") as w:
        hdf.to_excel(w, sheet_name="Handoff_Listesi", index=False)
        ciftler.to_excel(w, sheet_name="Cift_Istatistik", index=False)
        matris.to_excel(w, sheet_name="Iliski_Matrisi")
        hdf[hdf['accumulation'] == True].to_excel(
            w, sheet_name="Acc_Dogrulanmis", index=False)

        # Alarm tipi bazlı sheetler
        for alarm in hdf['alarm_tipi'].unique():
            sheet_ad = alarm.split(' ', 1)[-1][:25]
            sheet_ad = sheet_ad.replace('/', '-').replace('\\', '-').replace('*', '').replace('?', '').replace('[', '').replace(']', '')
            hdf[hdf['alarm_tipi'] == alarm].to_excel(
                w, sheet_name=sheet_ad, index=False)

    print(f"\n💾 {out} kaydedildi")
    print(f"   Handoff_Listesi : {len(hdf)}")
    print(f"   Acc_Dogrulanmis : {acc_n}")
    print("\n✅ Tamamlandı!")

if __name__ == "__main__":
    main()
