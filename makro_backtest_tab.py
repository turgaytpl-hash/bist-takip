"""
makro_backtest_tab.py — BIST Kriz Öncü Gösterge Backtest
2003'ten bugüne öncü sinyallerin BIST dolar bazlı performansına etkisini ölçer.
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime


# ─────────────────────────────────────────────
# VERİ ÇEK
# ─────────────────────────────────────────────

@st.cache_data(ttl=86400)
def veri_cek_backtest():
    try:
        import yfinance as yf
    except ImportError:
        return None, "pip install yfinance"

    semboller = {
        'sp500'  : '^GSPC',
        'vix'    : '^VIX',
        'copper' : 'HG=F',
        'gold'   : 'GC=F',
        'hyg'    : 'HYG',
        'tlt'    : 'TLT',
        'djt'    : '^DJT',
        'bist'   : 'XU100.IS',
        'usdtry' : 'USDTRY=X',
        'dxy'    : 'DX-Y.NYB',
    }

    try:
        ham = yf.download(
            list(semboller.values()),
            start='2003-01-01',
            interval='1wk',
            progress=False,
            auto_adjust=True,
        )['Close']

        ters = {v: k for k, v in semboller.items()}
        ham.columns = [ters.get(c, c) for c in ham.columns]
        ham = ham.dropna(how='all')

        # BIST dolar bazlı
        ham['bist_usd'] = ham['bist'] / ham['usdtry']

        # Oranlar
        ham['copper_gold'] = ham['copper'] / ham['gold']
        ham['hyg_tlt']     = ham['hyg'] / ham['tlt']

        # Hareketli ortalamalar
        ham['sp500_ma200w'] = ham['sp500'].rolling(40).mean()   # 40 hafta ≈ 200 gün
        ham['djt_ma40w']    = ham['djt'].rolling(40).mean()
        ham['cg_ma20w']     = ham['copper_gold'].rolling(20).mean()
        ham['hyg_tlt_ma20'] = ham['hyg_tlt'].rolling(20).mean()

        return ham.dropna(subset=['bist_usd']), None

    except Exception as e:
        return None, str(e)


# ─────────────────────────────────────────────
# SİNYAL TANIMLARI
# ─────────────────────────────────────────────

def sinyaller_hesapla(df):
    """Her satır için hangi sinyallerin aktif olduğunu hesapla"""
    s = pd.DataFrame(index=df.index)

    # 1. SP500 200MA altına düştü
    s['sp500_200ma_alti'] = (
        (df['sp500'] < df['sp500_ma200w']) &
        (df['sp500'].shift(1) >= df['sp500_ma200w'].shift(1))
    )

    # 2. VIX 30 üzerine çıktı
    s['vix_30_ustune'] = (
        (df['vix'] > 30) &
        (df['vix'].shift(1) <= 30)
    )

    # 3. VIX 40 üzerine çıktı (panik)
    s['vix_40_ustune'] = (
        (df['vix'] > 40) &
        (df['vix'].shift(1) <= 40)
    )

    # 4. Copper/Gold MA altına düştü (büyüme zayıflıyor)
    s['copper_gold_kirilim'] = (
        (df['copper_gold'] < df['cg_ma20w']) &
        (df['copper_gold'].shift(1) >= df['cg_ma20w'].shift(1))
    )

    # 5. HYG/TLT MA altına düştü (kredi stresi)
    s['hyg_tlt_kirilim'] = (
        (df['hyg_tlt'] < df['hyg_tlt_ma20']) &
        (df['hyg_tlt'].shift(1) >= df['hyg_tlt_ma20'].shift(1))
    )

    # 6. DJT (taşımacılık) 40MA altına düştü
    s['djt_kirilim'] = (
        (df['djt'] < df['djt_ma40w']) &
        (df['djt'].shift(1) >= df['djt_ma40w'].shift(1))
    )

    # 7. Kombine sinyal: SP500 MA altı + VIX yüksek aynı anda
    s['kombine_kriz'] = (
        (df['sp500'] < df['sp500_ma200w']) &
        (df['vix'] > 25)
    ) & ~(
        (df['sp500'].shift(1) < df['sp500_ma200w'].shift(1)) &
        (df['vix'].shift(1) > 25)
    )

    return s


# ─────────────────────────────────────────────
# BACKTEST HESAPLA
# ─────────────────────────────────────────────

def backtest_hesapla(df, sinyal_serisi, sinyal_adi, haftalar=[4, 8, 12, 26]):
    """
    Sinyal ateşlendiğinde BIST dolar bazlı N hafta sonraki performansı
    """
    ates_tarihleri = df.index[sinyal_serisi]
    if len(ates_tarihleri) == 0:
        return None, []

    sonuclar = []
    bist = df['bist_usd']

    for tarih in ates_tarihleri:
        idx = df.index.get_loc(tarih)
        bist_sinyal = bist.iloc[idx]
        if bist_sinyal == 0 or pd.isna(bist_sinyal):
            continue

        row = {'Tarih': tarih, 'Sinyal': sinyal_adi, 'BIST_USD_o': bist_sinyal}
        for h in haftalar:
            if idx + h < len(bist):
                bist_sonra = bist.iloc[idx + h]
                row[f'{h}H_%'] = (bist_sonra - bist_sinyal) / bist_sinyal * 100
            else:
                row[f'{h}H_%'] = np.nan

        # Max drawdown — 26 hafta içinde
        pencere = min(26, len(bist) - idx - 1)
        if pencere > 0:
            bist_pencere = bist.iloc[idx+1: idx+pencere+1]
            row['MaxDD_%'] = (bist_pencere.min() - bist_sinyal) / bist_sinyal * 100
        else:
            row['MaxDD_%'] = np.nan

        sonuclar.append(row)

    if not sonuclar:
        return None, []

    df_s = pd.DataFrame(sonuclar)

    # Özet istatistik
    ozet = {
        'Sinyal'       : sinyal_adi,
        'Ateş Sayısı'  : len(df_s),
        'Ort 4H %'     : df_s['4H_%'].mean(),
        'Ort 8H %'     : df_s['8H_%'].mean(),
        'Ort 12H %'    : df_s['12H_%'].mean(),
        'Ort 26H %'    : df_s['26H_%'].mean(),
        'Ort MaxDD %'  : df_s['MaxDD_%'].mean(),
        'Negatif Oran' : (df_s['8H_%'] < 0).mean() * 100,
    }

    return ozet, df_s


# ─────────────────────────────────────────────
# ANA TAB FONKSİYONU
# ─────────────────────────────────────────────

SINYAL_TANIM = {
    'sp500_200ma_alti'  : 'SP500 200MA Altına Düştü',
    'vix_30_ustune'     : 'VIX 30 Üzerine Çıktı',
    'vix_40_ustune'     : 'VIX 40 Üzerine Çıktı (Panik)',
    'copper_gold_kirilim': 'Copper/Gold MA Kırılımı',
    'hyg_tlt_kirilim'   : 'HYG/TLT MA Kırılımı (Kredi Stresi)',
    'djt_kirilim'       : 'DJT Taşımacılık MA Kırılımı',
    'kombine_kriz'      : 'Kombine: SP500 MA Altı + VIX>25',
}


def tab_makro_backtest():
    st.markdown("## 🔬 BIST Kriz Öncü Gösterge Backtest")
    st.caption("2003'ten bugüne — öncü sinyallerin BIST dolar bazlı performansına etkisi")

    if st.button("📥 Verileri Yükle (2003-Bugün)", type="primary"):
        st.cache_data.clear()

    with st.spinner("2003'ten bugüne haftalık veri çekiliyor..."):
        df, hata = veri_cek_backtest()

    if hata:
        st.error(f"Hata: {hata}")
        return
    if df is None:
        st.info("Butona bas.")
        return

    st.success(f"✅ {len(df)} haftalık veri yüklendi ({df.index[0].strftime('%Y-%m')} → {df.index[-1].strftime('%Y-%m')})")

    # Sinyalleri hesapla
    sinyaller = sinyaller_hesapla(df)

    # Debug: kaç sinyal var
    with st.expander("🔧 Sinyal Sayıları (debug)"):
        for kod, isim in SINYAL_TANIM.items():
            n = int(sinyaller[kod].sum()) if kod in sinyaller.columns else 0
            st.write(f"{isim}: {n} sinyal")

    # ── ÖZET TABLO ────────────────────────────────────────────────
    st.markdown("### 📊 Tüm Sinyaller Özet — BIST Dolar Bazlı Ortalama Getiri")

    ozet_rows = []
    detay_dict = {}

    for kod, isim in SINYAL_TANIM.items():
        if kod not in sinyaller.columns:
            continue
        ozet, detay = backtest_hesapla(df, sinyaller[kod], isim)
        if ozet:
            ozet_rows.append(ozet)
            detay_dict[isim] = detay

    if ozet_rows:
        df_ozet = pd.DataFrame(ozet_rows).set_index('Sinyal')

        def renk_formatla(val):
            if pd.isna(val):
                return ''
            if isinstance(val, (int, float)):
                if val < -10:
                    return 'background-color:#8b0000;color:white'
                elif val < -5:
                    return 'background-color:#cc0000;color:white'
                elif val < 0:
                    return 'background-color:#ff6666'
                elif val > 5:
                    return 'background-color:#006600;color:white'
                elif val > 0:
                    return 'background-color:#90EE90'
            return ''

        st.dataframe(
            df_ozet.style
                .map(renk_formatla, subset=['Ort 4H %','Ort 8H %','Ort 12H %','Ort 26H %','Ort MaxDD %'])
                .format({
                    'Ort 4H %'     : '{:.1f}%',
                    'Ort 8H %'     : '{:.1f}%',
                    'Ort 12H %'    : '{:.1f}%',
                    'Ort 26H %'    : '{:.1f}%',
                    'Ort MaxDD %'  : '{:.1f}%',
                    'Negatif Oran' : '{:.0f}%',
                }),
            use_container_width=True,
        )
    else:
        st.warning("Sinyal tablosu hesplanamadı — debug bölümüne bak")

        # En iyi öncü gösterge
        df_ozet_s = df_ozet.copy()
        en_kotu = df_ozet_s['Ort 8H %'].idxmin()
        en_oncü = df_ozet_s['Ort MaxDD %'].idxmin()

        c1, c2 = st.columns(2)
        c1.error(f"🚨 **En güçlü 8 hafta sinyali:** {en_kotu}\nOrt: {df_ozet_s.loc[en_kotu,'Ort 8H %']:.1f}%")
        c2.error(f"📉 **En büyük ortalama drawdown:** {en_oncü}\nOrt: {df_ozet_s.loc[en_oncü,'Ort MaxDD %']:.1f}%")

    # ── DETAY ────────────────────────────────────────────────────
    st.markdown("### 🔍 Sinyal Detayı")
    secili = st.selectbox("Sinyal seç:", list(detay_dict.keys()))

    if secili and secili in detay_dict:
        df_d = detay_dict[secili]

        # Dağılım grafiği
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**8 Hafta Sonrası Dağılım — {df_d['8H_%'].dropna().count()} sinyal**")
            dist = df_d['8H_%'].dropna()
            neg = (dist < 0).sum()
            pos = (dist >= 0).sum()
            st.markdown(f"🔴 Negatif: **{neg}** ({neg/len(dist)*100:.0f}%) | 🟢 Pozitif: **{pos}** ({pos/len(dist)*100:.0f}%)")

            # Histogram benzeri basit tablo
            bins = [-60,-40,-20,-10,0,10,20,40,60]
            labels = ['<-40%','-40 -20','-20 -10','-10 0','0 10','10 20','20 40','>40%']
            counts = pd.cut(dist, bins=bins, labels=labels).value_counts().sort_index()
            st.dataframe(counts.rename('Sinyal Sayısı'), use_container_width=True)

        with col2:
            st.markdown("**Tüm Sinyaller Tarihleri**")
            fmt_cols = [c for c in df_d.columns if '%' in c]
            fmt_dict = {c: '{:.1f}%' for c in fmt_cols}
            st.dataframe(
                df_d[['Tarih'] + fmt_cols].style.format(fmt_dict),
                use_container_width=True,
                hide_index=True,
            )

    # ── NE YAPTIK AÇIKLAMASI ──────────────────────────────────────
    with st.expander("📖 Bu backtest ne yapıyor?", expanded=False):
        st.markdown("""
**Amaç:** Küresel kriz sinyalleri BIST'i etkiliyor mu? Kaç hafta önce geliyor?

**Yöntem:**
1. 2005'ten bugüne 7 farklı öncü sinyal tespit edildi
2. Her sinyal ateşlendiğinde BIST dolar bazlı 4/8/12/26 hafta sonra ne oldu ölçüldü
3. Ortalama düşüş, en kötü senaryo ve "negatif olma oranı" hesaplandı

**Sinyaller:**
- **SP500 200MA altı** → ABD borsası uzun vadeli trendini kaybetti
- **VIX 30/40 üzeri** → Piyasada panik var
- **Copper/Gold düşüşü** → Büyüme yavaşlıyor, altın öne geçiyor
- **HYG/TLT düşüşü** → Riskli şirket tahvilleri zayıflıyor = kredi stresi
- **DJT düşüşü** → Taşımacılık endeksi düştü = ekonomik aktivite azalıyor
- **Kombine** → SP500 MA altı + VIX yüksek aynı anda

**Sonuç tablosu nasıl okunur:**
- "Ort 8H %" = sinyal sonrası 8 haftada BIST ortalama kaç % değişti
- "MaxDD %" = 26 hafta içinde en derin düşüş ne kadardı
- "Negatif Oran" = sinyallerin kaçında BIST aşağı gitti
        """)

    # ── TARİHSEL KRİZ KARŞILAŞTIRMA ──────────────────────────────
    st.markdown("### 📅 Büyük Krizlerde BIST Dolar Bazlı Düşüş")

    krizler = [
        ('2008 Küresel Kriz',   '2007-10-01', '2009-03-01'),
        ('2011 Euro Krizi',     '2011-04-01', '2012-06-01'),
        ('2013 Taper Tantrum',  '2013-05-01', '2014-02-01'),
        ('2018 TL Krizi',       '2018-01-01', '2019-01-01'),
        ('2020 Covid',          '2020-02-01', '2020-04-01'),
        ('2021-22 Döviz Krizi', '2021-09-01', '2023-06-01'),
    ]

    kriz_rows = []
    bist = df['bist_usd']
    sp   = df['sp500']

    for isim, bas, bitis in krizler:
        try:
            b = bist[bas:bitis].dropna()
            s = sp[bas:bitis].dropna()
            if len(b) < 2 or len(s) < 2:
                continue
            bist_dd = float((b.min() - b.iloc[0]) / b.iloc[0] * 100)
            sp_dd   = float((s.min() - s.iloc[0]) / s.iloc[0] * 100)
            kriz_rows.append({
                'Kriz'          : isim,
                'BIST USD DD %' : round(bist_dd, 1),
                'SP500 DD %'    : round(sp_dd, 1),
                'BIST / SP500'  : round(bist_dd / sp_dd, 2) if sp_dd != 0 else 0,
            })
        except Exception:
            continue

    if kriz_rows:
        df_kriz = pd.DataFrame(kriz_rows).set_index('Kriz')
        st.dataframe(
            df_kriz.style.format({
                'BIST USD DD %' : '{:.1f}%',
                'SP500 DD %'    : '{:.1f}%',
                'BIST / SP500'  : '{:.2f}x',
            }),
            use_container_width=True,
        )
        ort_carp = float(df_kriz['BIST / SP500'].mean())
        st.info(f"📊 Ortalama: SP500 %1 düştüğünde BIST dolar bazlı **{ort_carp:.1f}x** düşüyor")

    # ── ŞU ANKİ DURUM ────────────────────────────────────────────
    st.markdown("### 🔴 Şu An Aktif Sinyaller")
    aktif = []
    son = sinyaller.iloc[-1]
    son_2 = sinyaller.iloc[-4:]  # son 4 hafta

    for kod, isim in SINYAL_TANIM.items():
        if son_2[kod].any():
            tarih = son_2[kod][son_2[kod]].index[-1]
            aktif.append(f"⚠️ **{isim}** — {tarih.strftime('%d.%m.%Y')} ateşlendi")

    if aktif:
        for a in aktif:
            st.warning(a)
    else:
        st.success("✅ Son 4 haftada aktif kriz sinyali yok")

    # ── CLAUDE YORUMU ─────────────────────────────────────────────
    st.markdown("### 🧠 AI Yorumu")
    if st.button("💬 Buffett & Burry Bu Tabloya Ne Der?", type="secondary"):
        with st.spinner("Analiz yapılıyor..."):
            try:
                import anthropic, json

                # Özet veriyi hazırla
                son_veri = {
                    'bist_usd_son'    : float(df['bist_usd'].iloc[-1]),
                    'bist_usd_3ay_pct': float((df['bist_usd'].iloc[-1]/df['bist_usd'].iloc[-12]-1)*100),
                    'sp500_son'       : float(df['sp500'].iloc[-1]),
                    'vix_son'         : float(df['vix'].iloc[-1]),
                    'copper_gold_son' : float(df['copper_gold'].iloc[-1]),
                    'hyg_tlt_son'     : float(df['hyg_tlt'].iloc[-1]),
                    'aktif_sinyaller' : aktif,
                    'tarih'           : datetime.now().strftime('%B %Y'),
                }

                ozet_str = json.dumps(son_veri, ensure_ascii=False, indent=2)

                client = anthropic.Anthropic()
                mesaj = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1000,
                    messages=[{
                        "role": "user",
                        "content": f"""Sen deneyimli bir makro analistsin. Warren Buffett ve Michael Burry'ın bakış açılarını beniyor.

Aşağıdaki güncel makro verilere bakarak:
1. Buffett bu tabloyu nasıl yorumlar? (değerleme, faiz, uzun vadeli bakış)
2. Burry bu tabloyu nasıl yorumlar? (kriz riski, kredi, aşırı iyimserlik)
3. BIST dolar bazlı için ne önerilir?

Kısa, net, Türkçe yaz. Spekülatif değil, veriye dayalı.

Güncel Veriler:
{ozet_str}"""
                    }]
                )

                yorum = mesaj.content[0].text
                st.markdown(yorum)

            except Exception as e:
                st.error(f"AI yorumu alınamadı: {e}")
