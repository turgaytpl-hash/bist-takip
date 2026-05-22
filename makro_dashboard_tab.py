"""
makro_dashboard_tab.py — Kriz & Rali Kahini v3
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

SEMBOLLER = {
    'sp500'  : '^GSPC',
    'vix'    : '^VIX',
    'copper' : 'HG=F',
    'gold'   : 'GC=F',
    'btc'    : 'BTC-USD',
    'hyg'    : 'HYG',
    'lqd'    : 'LQD',
    'tlt'    : 'TLT',
    'eem'    : 'EEM',
    'sox'    : 'SOXX',
    'dxy'    : 'DX-Y.NYB',
    'us10y'  : '^TNX',
    'us2y'   : '^IRX',
    'usdtry' : 'USDTRY=X',
    'bist'   : 'XU100.IS',
    'oil'    : 'BZ=F',
}

@st.cache_data(ttl=3600)
def veri_cek():
    try:
        import yfinance as yf
    except ImportError:
        return None, None, "pip install yfinance"
    try:
        ham = yf.download(list(SEMBOLLER.values()), period='2y', interval='1d',
                          progress=False, auto_adjust=True)['Close']
        if isinstance(ham.columns, pd.MultiIndex):
            ham.columns = ham.columns.get_level_values(0)
        ters = {v: k for k, v in SEMBOLLER.items()}
        ham.columns = [ters.get(c, c) for c in ham.columns]
        ham = ham.dropna(how='all')
        ham['copper_gold'] = ham['copper'] / ham['gold']
        ham['hyg_tlt']     = ham['hyg'] / ham['tlt']
        ham['lqd_tlt']     = ham['lqd'] / ham['tlt']
        ham['btc_gold']    = ham['btc'] / ham['gold']
        ham['sox_sp500']   = ham['sox'] / ham['sp500']
        ham['eem_sp500']   = ham['eem'] / ham['sp500']
        # Yield Curve: 10Y - 2Y (pozitif = normal, negatif = inversion = kriz sinyali)
        if 'us10y' in ham.columns and 'us2y' in ham.columns:
            ham['yield_curve'] = ham['us10y'] - ham['us2y']

        # 5Y haftalık Z-Score için
        ham2y = yf.download(
            ['^GSPC','^VIX','HG=F','GC=F','HYG','TLT','DX-Y.NYB','^TNX','^IRX','BZ=F','BTC-USD'],
            period='5y', interval='1wk', progress=False, auto_adjust=True)['Close']
        if isinstance(ham2y.columns, pd.MultiIndex):
            ham2y.columns = ham2y.columns.get_level_values(0)
        ham2y.columns = [ters.get(c, c) for c in ham2y.columns]
        if 'us10y' in ham2y.columns and 'us2y' in ham2y.columns:
            ham2y['yield_curve'] = ham2y['us10y'] - ham2y['us2y']
        if 'copper' in ham2y.columns and 'gold' in ham2y.columns:
            ham2y['copper_gold'] = ham2y['copper'] / ham2y['gold']
        if 'hyg' in ham2y.columns and 'tlt' in ham2y.columns:
            ham2y['hyg_tlt'] = ham2y['hyg'] / ham2y['tlt']
        if 'btc' in ham2y.columns and 'gold' in ham2y.columns:
            ham2y['btc_gold'] = ham2y['btc'] / ham2y['gold']

        return ham, ham2y, None
    except Exception as e:
        return None, None, str(e)

def son(df, k):
    try: return float(df[k].dropna().iloc[-1])
    except: return None

def degisim(df, k, gun=30):
    try:
        s = df[k].dropna()
        if len(s) < gun: return None
        return float((s.iloc[-1] - s.iloc[-gun]) / abs(s.iloc[-gun]) * 100)
    except: return None

def oran_degisim(df, pay, payda, gun=30):
    try:
        s = (df[pay] / df[payda]).dropna()
        if len(s) < gun: return None
        return float((s.iloc[-1] - s.iloc[-gun]) / abs(s.iloc[-gun]) * 100)
    except: return None

def zscore_fn(df2y, k, pencere=52):
    try:
        s = df2y[k].dropna()
        if len(s) < pencere: return None
        mu  = float(s.iloc[-pencere:].mean())
        std = float(s.iloc[-pencere:].std())
        if std == 0: return None
        return float((float(s.iloc[-1]) - mu) / std)
    except: return None

def percentile_fn(df2y, k, pencere=52):
    try:
        s = df2y[k].dropna().iloc[-pencere:]
        return float((s < float(s.iloc[-1])).mean() * 100)
    except: return None

def sinyal_ikonu(val, esik_pos=2.0, esik_neg=-2.0, ters=False):
    if val is None: return '⚪'
    v = -val if ters else val
    if v > esik_pos: return '🟢'
    elif v < esik_neg: return '🔴'
    return '🟡'

def skor_hesapla(g):
    skor = 0.0
    detay = []
    AGIRLIKLAR = [
        ('copper_gold_30d', 2.5, False, "Copper/Gold"),
        ('hyg_tlt_30d',     3.0, False, "HYG/TLT Kredi"),
        ('eem_sp500_30d',   2.0, False, "EEM/SP500"),
        ('sox_sp500_30d',   1.5, False, "SOX/SP500"),
        ('dxy_30d',         1.5, True,  "DXY Dolar"),
        ('vix_30d',         2.0, True,  "VIX"),
        ('btc_gold_30d',    1.0, False, "BTC/Gold"),
        ('gold_sp500_30d',  1.5, True,  "Gold/SP500"),
        ('yield_curve_deg', 1.2, False, "Yield Curve"),
    ]
    for key, ag, ters, isim in AGIRLIKLAR:
        v = g.get(key)
        if v is None: continue
        etki = -v if ters else v
        norm = max(-3, min(3, etki / 3))
        katki = norm * ag
        skor += katki
        yon = '⬆️' if katki > 0 else '⬇️'
        detay.append(f"{yon} {isim}: {v:+.1f} → {katki:+.2f} puan")
    max_s = sum(a for _, a, _, _ in AGIRLIKLAR) * 3
    return round(skor / max_s * 10, 2), detay

def faz_belirle(skor):
    if skor >= 7:    return '🟢 GÜÇLÜ BOĞA', '#155724'
    elif skor >= 4:   return '🟢 ORTA-GÜÇLÜ BOĞA', '#1e7e34'
    elif skor >= 1.5: return '🟢 ERKEN BOĞA / RALİ', '#2d9e2d'
    elif skor >= 0:   return '🟡 NÖTR / GEÇ DÖNGÜ', '#856404'
    elif skor >= -2:  return '🟠 DİKKAT / ZAYIFLAMA', '#cc5500'
    elif skor >= -4:  return '🔴 KRİZ RİSKİ', '#bd2130'
    else:             return '🔴 YÜKSEK KRİZ', '#7b0000'

def tab_makro_dashboard():
    from breadth_tab import breadth_panel

    col_baslik, col_btn = st.columns([6, 1.2])
    with col_baslik:
        st.markdown("## 🌍 Makro Kahini v3")
        st.caption("Yahoo Finance • VIX • BTC/Gold • Yield Curve • Z-Score • Ağırlıklı Skor (-10/+10)")
    with col_btn:
        st.markdown("<div style='margin-top:18px'></div>", unsafe_allow_html=True)
        if st.button("🔄 Güncelle", type="primary", key="makro_guncelle", use_container_width=True):
            st.cache_data.clear()

    with st.spinner("Veriler çekiliyor..."):
        df, df2y, hata = veri_cek()

    if hata:
        st.error(f"Hata: {hata}")
        return
    if df is None:
        return

    yc_son = son(df, 'yield_curve')
    yc_deg = degisim(df, 'yield_curve', 30) if yc_son else None

    g = {
        'copper_gold_30d' : oran_degisim(df, 'copper', 'gold', 30),
        'copper_gold_3ay' : oran_degisim(df, 'copper', 'gold', 63),
        'gold_sp500_30d'  : oran_degisim(df, 'gold', 'sp500', 30),
        'gold_sp500_3ay'  : oran_degisim(df, 'gold', 'sp500', 63),
        'hyg_tlt_30d'     : oran_degisim(df, 'hyg', 'tlt', 30),
        'lqd_tlt_30d'     : oran_degisim(df, 'lqd', 'tlt', 30),
        'sox_sp500_30d'   : oran_degisim(df, 'sox', 'sp500', 30),
        'sox_sp500_3ay'   : oran_degisim(df, 'sox', 'sp500', 63),
        'eem_sp500_30d'   : oran_degisim(df, 'eem', 'sp500', 30),
        'eem_sp500_3ay'   : oran_degisim(df, 'eem', 'sp500', 63),
        'btc_gold_30d'    : oran_degisim(df, 'btc', 'gold', 30),
        'btc_gold_3ay'    : oran_degisim(df, 'btc', 'gold', 63),
        'dxy_30d'         : degisim(df, 'dxy', 30),
        'dxy_3ay'         : degisim(df, 'dxy', 63),
        'vix_son'         : son(df, 'vix'),
        'vix_30d'         : degisim(df, 'vix', 30),
        'vix_3ay'         : degisim(df, 'vix', 63),
        'us10y_son'       : son(df, 'us10y'),
        'usdtry_30d'      : degisim(df, 'usdtry', 30),
        'usdtry_son'      : son(df, 'usdtry'),
        'bist_30d'        : degisim(df, 'bist', 30),
        'bist_son'        : son(df, 'bist'),
        'oil_30d'         : degisim(df, 'oil', 30),
        'oil_3ay'         : degisim(df, 'oil', 63),
        'sp500_30d'       : degisim(df, 'sp500', 30),
        'yield_curve_son' : yc_son,
        'yield_curve_deg' : yc_deg,
    }

    # Z-Score ve Percentile — tüm ana göstergeler için
    Z_KEYS = ['vix','copper_gold','hyg_tlt','btc_gold','dxy','yield_curve','sp500','oil']
    z = {}
    if df2y is not None:
        for k in Z_KEYS:
            if k in df2y.columns:
                z[f'{k}_z']   = zscore_fn(df2y, k)
                z[f'{k}_pct'] = percentile_fn(df2y, k)

    skor, detay = skor_hesapla(g)
    faz, renk   = faz_belirle(skor)
    skor_bar    = int(max(0, min(100, (skor + 10) / 20 * 100)))

    # ── Skor Geçmişi Kaydet ───────────────────────────────────────
    import os, json
    SKOR_PATH = "data/makro_skor_gecmisi.json"
    os.makedirs("data", exist_ok=True)

    bugun = datetime.now().strftime("%Y-%m-%d")
    if os.path.exists(SKOR_PATH):
        with open(SKOR_PATH, encoding='utf-8') as f:
            gecmis = json.load(f)
    else:
        gecmis = []

    # Bugün zaten kayıtlıysa güncelle, yoksa ekle
    if gecmis and gecmis[-1]['tarih'] == bugun:
        gecmis[-1]['skor'] = skor
    else:
        gecmis.append({'tarih': bugun, 'skor': skor})

    # Son 52 hafta tut
    gecmis = gecmis[-52:]
    with open(SKOR_PATH, 'w', encoding='utf-8') as f:
        json.dump(gecmis, f, ensure_ascii=False, indent=2)

    # ── Erken Uyarı Alarmları ─────────────────────────────────────
    alarm = None
    if len(gecmis) >= 3:
        son3 = [x['skor'] for x in gecmis[-3:]]
        son5 = [x['skor'] for x in gecmis[-5:]] if len(gecmis) >= 5 else []

        # Yield Curve inversiyon
        yc_son = g.get('yield_curve_deg', 0) or 0
        vix_son = g.get('vix_son', 0) or 0
        dxy_30 = g.get('dxy_30d', 0) or 0

        kombinasyon = sum([
            yc_son < 0,
            vix_son > 25,
            dxy_30 > 5,
        ])

        if kombinasyon >= 3:
            alarm = ("🚨 KRİZ ÖN UYARISI",
                     "Yield Curve negatif + VIX 25+ + DXY güçlü — 3 sinyal aynı anda!",
                     "#7f1d1d")
        elif all(son3[i] > son3[i+1] for i in range(len(son3)-1)) and son3[0] - son3[-1] > 3:
            alarm = ("🔴 DÜŞÜŞ TRENDİ",
                     f"Skor 3 haftadır düşüyor: {son3[0]:+.1f} → {son3[-1]:+.1f}",
                     "#92400e")
        elif yc_son < 0:
            alarm = ("⚠️ YİELD CURVE İNVERSİYON",
                     f"10Y-2Y = %{yc_son:.2f} — tarihsel kriz öncüsü!",
                     "#78350f")
        elif len(son5) >= 5 and all(son5[i] >= son5[i+1] for i in range(len(son5)-1)):
            alarm = ("🟡 5 HAFTA DÜŞÜŞ",
                     f"Skor 5 haftadır sürekli düşüyor: {son5[0]:+.1f} → {son5[-1]:+.1f}",
                     "#713f12")

    # Alarm göster
    if alarm:
        alarim_baslik, alarm_aciklama, alarm_renk = alarm
        st.markdown(f"""
        <div style="background:{alarm_renk};padding:12px 16px;border-radius:8px;margin-bottom:12px">
            <b style="color:white;font-size:16px">{alarim_baslik}</b>
            <p style="color:#fca5a5;margin:4px 0 0 0;font-size:13px">{alarm_aciklama}</p>
        </div>""", unsafe_allow_html=True)

    st.markdown(f"""
    <div style="background:{renk};padding:20px;border-radius:12px;margin-bottom:16px">
        <h2 style="color:white;margin:0;text-align:center">{faz}</h2>
        <p style="color:white;margin:8px 0 4px 0;text-align:center;font-size:15px">
            Makro Skor: <b>{skor:+.1f} / 10</b> &nbsp;|&nbsp; {datetime.now().strftime('%B %Y')}
        </p>
        <div style="background:rgba(255,255,255,0.3);border-radius:6px;height:12px;margin-top:8px">
            <div style="background:white;width:{skor_bar}%;height:12px;border-radius:6px"></div>
        </div>
        <p style="color:white;font-size:11px;text-align:center;margin:4px 0 0 0">
            ◀ KRİZ &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; NÖTR &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; BOĞA ▶
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### 📊 Gösterge Tablosu")

    def ps(v): return f"{v:+.1f}%" if v is not None else "—"
    def zs(v): return f"{v:+.2f}σ" if v is not None else "—"
    def pp(v): return f"{v:.0f}." if v is not None else "—"
    def ns(v, fmt=".2f"): return f"{v:{fmt}}" if v is not None else "—"

    yc_yorum = "—"
    if yc_son is not None:
        if yc_son < 0:
            yc_yorum = f"⚠️ İNVERSİYON ({yc_son:.2f}%) — kriz öncü sinyali"
        elif yc_son < 0.5:
            yc_yorum = f"🟡 Düz ({yc_son:.2f}%) — dikkat"
        else:
            yc_yorum = f"✅ Normal ({yc_son:.2f}%) — sağlıklı"

    # (İsim, 30G, 3Ay, z_key, ters, yorum, güncel, esik_pos, esik_neg)
    GOST = [
        ("Copper/Gold",    g['copper_gold_30d'], g['copper_gold_3ay'], 'copper_gold', False,
         "↑ büyüme güçlü / ↓ resesyon",
         f"Güncel: {son(df,'copper_gold'):.3f}" if son(df,'copper_gold') else "", 2.0, -2.0),
        ("HYG/TLT Kredi",  g['hyg_tlt_30d'],     g['lqd_tlt_30d'],     'hyg_tlt',    False,
         "↑ kredi sağlıklı / ↓ kriz sinyali",
         f"Güncel: {son(df,'hyg_tlt'):.2f}" if son(df,'hyg_tlt') else "", 1.0, -1.0),
        ("VIX Korku",      g['vix_30d'],          g['vix_3ay'],          'vix',         True,
         "↓ korku azaldı, risk iştahı yüksek / ↑ panik",
         f"Güncel: {g['vix_son']:.1f}" if g['vix_son'] else "", 2.0, -2.0),
        ("Yield Curve 10Y-2Y", yc_deg,            None,                 'yield_curve', False,
         yc_yorum, f"Güncel: {yc_son:.2f}%" if yc_son else "", 0.5, -999),
        ("SOX/SP500 Semi",  g['sox_sp500_30d'],   g['sox_sp500_3ay'],   None,          False,
         "↑ büyüme devam / ↓ ekonomi yavaşlıyor",
         f"Güncel: {son(df,'sox_sp500'):.3f}" if son(df,'sox_sp500') else "", 2.0, -2.0),
        ("EEM/SP500",       g['eem_sp500_30d'],   g['eem_sp500_3ay'],   None,          False,
         "↑ global likidite bol / ↓ dolar baskısı",
         f"Güncel: {son(df,'eem_sp500'):.3f}" if son(df,'eem_sp500') else "", 2.0, -2.0),
        ("BTC/Gold",        g['btc_gold_30d'],    g['btc_gold_3ay'],    'btc_gold',    False,
         "↑ risk iştahı yüksek / ↓ güvenli liman talebi",
         f"Güncel: {son(df,'btc_gold'):.1f}" if son(df,'btc_gold') else "", 2.0, -2.0),
        ("DXY Dolar",       g['dxy_30d'],         g['dxy_3ay'],         'dxy',         True,
         "↑ risk-off, EM baskısı / ↓ EM için olumlu",
         f"Güncel: {son(df,'dxy'):.1f}" if son(df,'dxy') else "", 2.0, -2.0),
        ("Gold/SP500",      g['gold_sp500_30d'],  g['gold_sp500_3ay'],  None,          True,
         "↑ yatırımcılar korunmaya geçiyor / ↓ risk-on",
         f"Güncel: {son(df,'gold_sp500'):.4f}" if son(df,'gold_sp500') else "", 2.0, -2.0),
        ("Oil/Brent",       g['oil_30d'],         g['oil_3ay'],         'oil',         False,
         "↑ enerji maliyeti artıyor → enflasyon ve marj baskısı riski / ↓ talep zayıfladı",
         f"Güncel: {son(df,'oil'):.1f}$" if son(df,'oil') else "", 2.0, -2.0),
        ("US10Y Faiz",      None,                 None,                 None,          True,
         "↑ değerleme baskısı, borçlanma pahalı / ↓ hisselere olumlu",
         f"Güncel: %{g['us10y_son']:.2f}" if g['us10y_son'] else "", 2.0, -2.0),
    ]

    rows = []
    for isim, v30, v3ay, zk, ters, yorum, guncel, ep, en in GOST:
        z_val = z.get(f'{zk}_z') if zk else None
        p_val = z.get(f'{zk}_pct') if zk else None
        rows.append({
            'Gösterge'   : isim,
            'Sinyal'     : sinyal_ikonu(v30, esik_pos=ep, esik_neg=en, ters=ters),
            '30G Δ%'     : ps(v30),
            '3 Ay Δ%'    : ps(v3ay),
            'Z-Score'    : zs(z_val),
            'Percentile' : pp(p_val),
            'Güncel'     : guncel,
            'Yorum'      : yorum,
        })

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # ── BIST ÖZEL ─────────────────────────────────────────────────
    st.markdown("### 🇹🇷 BIST Özel")
    b1, b2, b3, b4 = st.columns(4)
    b1.metric("BIST100", f"{g['bist_son']:,.0f}" if g['bist_son'] else "—",
              delta=f"{g['bist_30d']:+.1f}%" if g['bist_30d'] else None)
    b2.metric("USDTRY", f"{g['usdtry_son']:.2f}" if g['usdtry_son'] else "—",
              delta=f"{g['usdtry_30d']:+.1f}%" if g['usdtry_30d'] else None,
              delta_color="inverse")
    b3.metric("US10Y", f"%{g['us10y_son']:.2f}" if g['us10y_son'] else "—",
              delta_color="inverse")
    b4.metric("VIX", f"{g['vix_son']:.1f}" if g['vix_son'] else "—",
              delta=f"{g['vix_30d']:+.1f}%" if g['vix_30d'] else None,
              delta_color="inverse")

    u = g['usdtry_30d'] or 0
    d = g['dxy_30d'] or 0
    v = g['vix_son'] or 20
    b = g['bist_30d'] or 0
    if u < 2 and d < 0 and v < 20 and b > 0:
        st.success("🇹🇷 BIST için makro tablo olumlu: Dolar sakin, VIX düşük, BIST yukarı.")
    elif u > 5 or v > 30:
        st.error("🇹🇷 Dikkat: USDTRY hızlı yükseliyor veya VIX yüksek — BIST baskı altında.")
    elif d > 3:
        st.warning("🇹🇷 Dolar güçleniyor — EM baskısı var, BIST izle.")
    else:
        st.info("🇹🇷 Makro tablo nötr — BIST kendi dinamikleriyle hareket edebilir.")

    # ── SKOR GEÇMİŞİ GRAFİĞİ ─────────────────────────────────────
    with st.expander("📈 Makro Skor Geçmişi & Trend", expanded=True):
        if len(gecmis) >= 2:
            gecmis_df = pd.DataFrame(gecmis)
            gecmis_df['tarih'] = pd.to_datetime(gecmis_df['tarih'])
            gecmis_df = gecmis_df.sort_values('tarih')

            # Trend hesapla
            son_skor = gecmis_df['skor'].iloc[-1]
            ilk_skor = gecmis_df['skor'].iloc[0]
            trend    = son_skor - ilk_skor
            haftalik = (son_skor - gecmis_df['skor'].iloc[-2]) if len(gecmis_df) >= 2 else 0

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Güncel Skor", f"{son_skor:+.1f}")
            c2.metric("Haftalık Δ", f"{haftalik:+.1f}", delta=f"{haftalik:+.1f}")
            c3.metric(f"{len(gecmis_df)} Haftalık Trend", f"{trend:+.1f}")
            c4.metric("Min / Max", f"{gecmis_df['skor'].min():+.1f} / {gecmis_df['skor'].max():+.1f}")

            import altair as alt
            chart_df = gecmis_df.copy()
            chart_df['renk'] = chart_df['skor'].apply(
                lambda x: 'kriz' if x < -3 else ('dikkat' if x < 0 else 'pozitif'))

            chart = alt.Chart(chart_df).mark_line(
                point=True, strokeWidth=2
            ).encode(
                x=alt.X('tarih:T', title='Tarih'),
                y=alt.Y('skor:Q', title='Makro Skor', scale=alt.Scale(domain=[-10, 10])),
                color=alt.condition(
                    alt.datum.skor > 0,
                    alt.value('#16a34a'),
                    alt.value('#dc2626')
                ),
                tooltip=['tarih:T', 'skor:Q']
            ).properties(height=250)

            # Sıfır çizgisi
            zero_line = alt.Chart(pd.DataFrame({'y': [0]})).mark_rule(
                strokeDash=[4, 4], color='gray', opacity=0.5
            ).encode(y='y:Q')

            st.altair_chart(chart + zero_line, use_container_width=True)

            # Alarm bölgeleri
            st.caption("🟢 > 0: Boğa  |  🔴 < 0: Ayı  |  ⚠️ < -3: Dikkat  |  🚨 < -6: Kriz bölgesi")
        else:
            st.info("Skor geçmişi biriktirilmektedir. Her Güncelle'de yeni kayıt eklenir.")

    # ── BIG SHORT DEDEKTÖRÜ ───────────────────────────────────────
    with st.expander("🚨 Big Short Dedektörü", expanded=True):
        yc_son  = g.get('yield_curve_deg', 0) or 0
        vix_son = g.get('vix_son', 0) or 0
        cg_30   = g.get('copper_gold_30d', 0) or 0
        hyg_30  = g.get('hyg_tlt_30d', 0) or 0
        dxy_30  = g.get('dxy_30d', 0) or 0
        skor_son = skor

        sinyaller = [
            ("Makro Skor < -4.0",     skor_son < -4.0,   f"Şu an: {skor_son:+.1f}",  skor_son < -6.0),
            ("Yield Curve < 0%",      yc_son < 0,        f"Şu an: %{yc_son:.2f}",    yc_son < -0.5),
            ("Copper/Gold < -15%",    cg_30 < -15,       f"Şu an: {cg_30:+.1f}%",    cg_30 < -25),
            ("VIX > 30",              vix_son > 30,      f"Şu an: {vix_son:.1f}",     vix_son > 40),
            ("HYG/TLT < -12%",        hyg_30 < -12,      f"Şu an: {hyg_30:+.1f}%",   hyg_30 < -20),
            ("DXY > +8%",             dxy_30 > 8,        f"Şu an: {dxy_30:+.1f}%",   dxy_30 > 12),
        ]

        aktif = sum(1 for _, tetiklendi, _, _ in sinyaller if tetiklendi)
        agir  = sum(1 for _, tetiklendi, _, agir in sinyaller if tetiklendi and agir)

        # Seviye
        if aktif >= 5:
            seviye = "🚨 BIG SHORT — 2008 Seviyesi"
            seviye_renk = "#7f1d1d"
        elif aktif >= 4:
            seviye = "🔴 GÜÇLÜ UYARI — 2020 Seviyesi"
            seviye_renk = "#991b1b"
        elif aktif >= 3:
            seviye = "🟠 DİKKAT — 2018 Q4 Seviyesi"
            seviye_renk = "#92400e"
        elif aktif >= 1:
            seviye = "🟡 ERKEN SİNYAL"
            seviye_renk = "#78350f"
        else:
            seviye = "🟢 Kriz sinyali yok"
            seviye_renk = "#14532d"

        st.markdown(f"""
        <div style="background:{seviye_renk};padding:10px 16px;border-radius:8px;margin-bottom:12px">
            <b style="color:white;font-size:16px">{seviye}</b>
            <span style="color:#fca5a5;margin-left:16px">Aktif: {aktif}/6 sinyal</span>
        </div>""", unsafe_allow_html=True)

        # Sinyal tablosu
        for isim, tetiklendi, deger, agir_mi in sinyaller:
            ikon  = "✅" if tetiklendi else "⬜"
            renk  = "#dc2626" if (tetiklendi and agir_mi) else ("#f97316" if tetiklendi else "var(--color-text-secondary)")
            st.markdown(
                f"<div style='padding:4px 0;color:{renk};font-size:13px'>"
                f"{ikon} <b>{isim}</b> — {deger}</div>",
                unsafe_allow_html=True
            )

        st.divider()
        st.caption("Tarihsel: 2008=5/6 ✅ | 2020=4/6 ✅ | 2018 Q4=3/6 ✅ | Şu an: 0/6")

    # ── PİYASA GENİŞLİĞİ ─────────────────────────────────────────
    with st.expander("📊 Piyasa Genişliği (Market Breadth)", expanded=False):
        breadth_panel()

    # ── SKOR DETAYI ───────────────────────────────────────────────
    with st.expander("🧮 Skor Hesaplama Detayı"):
        st.caption("Ağırlıklı normalize skor | HYG/TLT ağırlık: 3.0 | Copper/Gold: 2.5 | VIX: 2.0 | Yield Curve: 2.0")
        for d_str in detay:
            st.markdown(f"- {d_str}")
        st.markdown(f"**Toplam: {skor:+.2f} / 10**")

    # ── AI YORUMU ─────────────────────────────────────────────────
    st.markdown("### 🧠 AI Yorumu")
    if st.button("💬 Buffett & Burry Ne Der?", key="makro_ai_yorum"):
        with st.spinner("Analiz yapılıyor..."):
            try:
                import anthropic, json
                ozet = {k: round(v, 2) if isinstance(v, float) else v
                        for k, v in g.items() if v is not None}
                ozet['makro_skor']   = skor
                ozet['faz']          = faz
                ozet['yield_curve']  = yc_yorum
                client = anthropic.Anthropic()
                mesaj = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1000,
                    messages=[{"role": "user", "content": f"""
Sen deneyimli bir makro analistsin. Buffett ve Burry bakış açısıyla:
1. Buffett bu tabloyu nasıl yorumlar? (değerleme, faiz, uzun vadeli)
2. Burry bu tabloyu nasıl yorumlar? (kriz riski, kredi, yield curve)
3. BIST dolar bazlı için sonuç?
Kısa, net, Türkçe, veriye dayalı.
{json.dumps(ozet, ensure_ascii=False, indent=2)}
"""}])
                st.markdown(mesaj.content[0].text)
            except Exception as e:
                st.error(f"Hata: {e}")

    with st.expander("📖 Faz Rehberi"):
        st.markdown("""
| Skor | Faz | Örnek |
|------|-----|-------|
| +4/+10 | 🟢 Güçlü Boğa | 2017, 2021 |
| +1.5/+4 | 🟢 Erken Boğa | 2009, 2020 Nisan |
| 0/+1.5 | 🟡 Nötr | 2015, 2019 |
| -2/0 | 🟠 Dikkat | 2018 Q4 |
| -4/-2 | 🔴 Kriz Riski | 2011, 2018 TL |
| -10/-4 | 🔴 Yüksek Kriz | 2008, 2020 Mart |

**Yield Curve:** 10Y-2Y negatif = inversion = tarihsel olarak her resesyondan önce geldi (6-18 ay gecikme).
**Z-Score:** +2σ = tarihin en yüksek %97'si. -2σ = en düşük %3'ü.
        """)
