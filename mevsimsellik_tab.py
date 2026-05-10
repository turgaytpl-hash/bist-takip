"""
mevsimsellik_tab.py — BIST100 Aylık Mevsimsellik Analizi
2002'den bugüne BIST100'ün ay bazında performansını gösterir.
"""

import streamlit as st
import pandas as pd
import numpy as np

AYLAR = ['Ocak','Şubat','Mart','Nisan','Mayıs','Haziran',
         'Temmuz','Ağustos','Eylül','Ekim','Kasım','Aralık']

@st.cache_data(ttl=86400)
def bist_aylik_cek():
    try:
        import yfinance as yf
    except ImportError:
        return None, "pip install yfinance"
    try:
        df = yf.download('XU100.IS', start='2002-01-01', interval='1mo',
                         progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        close = df['Close'].dropna()
        # Aylık % değişim
        ret = close.pct_change().dropna() * 100
        ret.index = pd.to_datetime(ret.index)
        return ret, None
    except Exception as e:
        return None, str(e)


def tab_mevsimsellik():
    st.markdown("## 📅 BIST100 Aylık Mevsimsellik")
    st.caption("2002'den bugüne — hangi ay tarihsel olarak nasıl performans gösterdi?")

    if st.button("🔄 Verileri Güncelle", type="primary", key="mevs_guncelle"):
        st.cache_data.clear()

    with st.spinner("Veriler yükleniyor..."):
        ret, hata = bist_aylik_cek()

    if hata:
        st.error(f"Hata: {hata}")
        return
    if ret is None or ret.empty:
        st.error("Veri gelmedi.")
        return

    st.success(f"✅ {ret.index[0].strftime('%Y-%m')} → {ret.index[-1].strftime('%Y-%m')} arası {len(ret)} aylık veri")

    # Yıl ve ay kolonları
    df = pd.DataFrame({'ret': ret.values, 'yil': ret.index.year, 'ay': ret.index.month})

    # ── YIL FİLTRESİ ─────────────────────────────────────────────
    min_yil = int(df['yil'].min())
    max_yil = int(df['yil'].max())

    c1, c2 = st.columns(2)
    with c1:
        bas_yil = st.slider("Başlangıç yılı:", min_yil, max_yil - 1, min_yil)
    with c2:
        bit_yil = st.slider("Bitiş yılı:", bas_yil + 1, max_yil, max_yil)

    df = df[(df['yil'] >= bas_yil) & (df['yil'] <= bit_yil)]
    n_yil = bit_yil - bas_yil + 1

    # ── ÖZET TABLO ────────────────────────────────────────────────
    st.markdown(f"### 📊 Aylık Özet ({bas_yil}–{bit_yil}, {n_yil} yıl)")

    ozet = []
    for ay_no in range(1, 13):
        ay_data = df[df['ay'] == ay_no]['ret'].dropna()
        if len(ay_data) == 0:
            continue
        pozitif = (ay_data > 0).sum()
        ozet.append({
            'Ay'            : AYLAR[ay_no - 1],
            'Ort %'         : round(float(ay_data.mean()), 2),
            'Medyan %'      : round(float(ay_data.median()), 2),
            'En İyi %'      : round(float(ay_data.max()), 2),
            'En Kötü %'     : round(float(ay_data.min()), 2),
            'Pozitif'       : f"{pozitif}/{len(ay_data)}",
            'Pozitif %'     : round(pozitif / len(ay_data) * 100, 0),
        })

    df_ozet = pd.DataFrame(ozet).set_index('Ay')

    def renk(val):
        if not isinstance(val, (int, float)):
            return ''
        if val > 3:
            return 'background-color:#006600;color:white'
        elif val > 0:
            return 'background-color:#90EE90'
        elif val < -3:
            return 'background-color:#8b0000;color:white'
        elif val < 0:
            return 'background-color:#ffcccc'
        return ''

    st.dataframe(
        df_ozet.style
            .map(renk, subset=['Ort %','Medyan %'])
            .format({'Ort %':'{:.2f}%','Medyan %':'{:.2f}%',
                     'En İyi %':'{:.2f}%','En Kötü %':'{:.2f}%','Pozitif %':'{:.0f}%'}),
        use_container_width=True,
    )

    # En iyi / en kötü aylar
    en_iyi  = df_ozet['Ort %'].idxmax()
    en_kotu = df_ozet['Ort %'].idxmin()
    c1, c2, c3 = st.columns(3)
    c1.success(f"🏆 En iyi ay: **{en_iyi}** ({df_ozet.loc[en_iyi,'Ort %']:+.2f}%)")
    c2.error(f"💀 En kötü ay: **{en_kotu}** ({df_ozet.loc[en_kotu,'Ort %']:+.2f}%)")
    c3.info(f"📈 Yıllık ort: **{df['ret'].mean()*12:.1f}%** (aylık {df['ret'].mean():.2f}%)")

    # ── YIL × AY ISISI ───────────────────────────────────────────
    st.markdown("### 🗓️ Yıl × Ay Performans Tablosu")

    pivot = df.pivot_table(values='ret', index='yil', columns='ay', aggfunc='first')
    pivot.columns = [AYLAR[c-1] for c in pivot.columns]
    pivot.index.name = 'Yıl'
    pivot['YILLIK'] = pivot.sum(axis=1)

    def renk2(val):
        if pd.isna(val) or not isinstance(val, (int, float)):
            return ''
        if val > 10:
            return 'background-color:#006600;color:white'
        elif val > 3:
            return 'background-color:#90EE90'
        elif val > 0:
            return 'background-color:#d4edda'
        elif val > -3:
            return 'background-color:#ffcccc'
        elif val > -10:
            return 'background-color:#ff6666'
        else:
            return 'background-color:#8b0000;color:white'

    fmt = {c: '{:.1f}%' for c in pivot.columns}
    st.dataframe(
        pivot.style.map(renk2).format(fmt, na_rep='—'),
        use_container_width=True,
        height=600,
    )

    # ── TEK AY ANALİZİ ───────────────────────────────────────────
    st.markdown("### 🔍 Tek Ay Detayı")
    secili_ay = st.selectbox("Ay seç:", AYLAR)
    ay_no = AYLAR.index(secili_ay) + 1
    ay_data = df[df['ay'] == ay_no].sort_values('yil')

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**{secili_ay} — Yıllara Göre Performans**")
        ay_tablo = ay_data[['yil','ret']].copy()
        ay_tablo.columns = ['Yıl', 'Getiri %']
        ay_tablo['Getiri %'] = ay_tablo['Getiri %'].round(2)
        st.dataframe(
            ay_tablo.style.map(
                lambda v: 'color:green;font-weight:bold' if isinstance(v,(int,float)) and v > 0
                          else ('color:red;font-weight:bold' if isinstance(v,(int,float)) and v < 0 else ''),
                subset=['Getiri %']
            ).format({'Getiri %':'{:.2f}%'}),
            use_container_width=True, hide_index=True,
        )

    with col2:
        st.markdown(f"**{secili_ay} İstatistikleri**")
        vals = ay_data['ret'].dropna()
        pos = (vals > 0).sum()
        st.metric("Ortalama", f"{vals.mean():.2f}%")
        st.metric("Medyan", f"{vals.median():.2f}%")
        st.metric("Pozitif yıl", f"{pos}/{len(vals)} (%{pos/len(vals)*100:.0f})")
        st.metric("En iyi", f"{vals.max():.2f}% ({int(ay_data.loc[vals.idxmax(),'yil'])})")
        st.metric("En kötü", f"{vals.min():.2f}% ({int(ay_data.loc[vals.idxmin(),'yil'])})")
