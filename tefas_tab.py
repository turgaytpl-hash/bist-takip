"""
tefas_tab.py — TEFAS Fon Büyüklük Karşılaştırma Modülü
Fon Analizi sekmesinin üst bölümüne eklenir.
"""

import streamlit as st
import pandas as pd
import json
from pathlib import Path

# ── Veri dizini ────────────────────────────────────────────────────────────────
DATA_DIR  = Path(__file__).parent / "FON"
DATA_DIR.mkdir(parents=True, exist_ok=True)
TEFAS_JSON = DATA_DIR / "_tefas.json"


# ── Yardımcı ──────────────────────────────────────────────────────────────────

def _oku_tefas_excel(dosya, ay: str) -> pd.DataFrame:
    """TEFAS Excel dosyasını oku, temizle."""
    df = pd.read_excel(dosya, header=None)
    header_row = 0
    for i, row in df.iterrows():
        if 'Fon Kodu' in str(row.values):
            header_row = i
            break
    df = pd.read_excel(dosya, header=header_row)
    df = df.dropna(subset=['Fon Kodu'])
    df['Fon Kodu'] = df['Fon Kodu'].astype(str).str.strip()
    df['Ay'] = ay
    return df[['Fon Kodu','Fon Adı','Son Portföy Büyüklüğü',
               'Portföy Büyüklüğü Değişimi (%)','Pay Adedi Değişimi (%)',
               'Getiri Oranı (%)','Ay']]


def _yukle_tefas() -> dict:
    if TEFAS_JSON.exists():
        return json.loads(TEFAS_JSON.read_text(encoding='utf-8'))
    return {}


def _kaydet_tefas(d: dict):
    TEFAS_JSON.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding='utf-8')


def _tum_df(tefas: dict) -> pd.DataFrame:
    """JSON → DataFrame"""
    rows = []
    for ay, fonlar in tefas.items():
        for fon in fonlar:
            rows.append(fon)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def _buyukluk_str(val) -> str:
    if pd.isna(val) or val == 0:
        return '—'
    if val >= 1e9:
        return f'{val/1e9:.2f}B ₺'
    return f'{val/1e6:.1f}M ₺'


def _degisim_emoji(pct) -> str:
    if pd.isna(pct):
        return '—'
    if pct >= 50:  return f'🚀 %+{pct:.1f}'
    if pct >= 20:  return f'✅ %+{pct:.1f}'
    if pct >= 5:   return f'📈 %+{pct:.1f}'
    if pct >= 0:   return f'➡️ %+{pct:.1f}'
    if pct >= -10: return f'📉 %{pct:.1f}'
    return f'🔴 %{pct:.1f}'


# ── ANA FONKSİYON ─────────────────────────────────────────────────────────────

def tefas_bolumu(secili_fon_callback=None):
    """
    TEFAS bölümünü göster.
    secili_fon_callback: kullanıcı fona tıklayınca çağrılacak fonksiyon
    """

    st.markdown("### 📊 TEFAS — Fon Büyüklük Takibi")

    tefas = _yukle_tefas()

    # ── EXCEL YÜKLEME ─────────────────────────────────────────────────────────
    with st.expander("📤 TEFAS Excel Yükle", expanded=(len(tefas) == 0)):
        st.caption("TEFAS → Fon Getirileri → Büyüklük Bazlı → Excel aktar")

        uploaded = st.file_uploader(
            "TEFAS Excel dosyaları (2026-01.xlsx, 2026-02.xlsx...)",
            type=['xlsx'],
            accept_multiple_files=True,
            key='tefas_uploader',
        )

        if st.button("🔄 Yükle", type="primary", disabled=not uploaded):
            prog = st.progress(0)
            basarili, hatali = [], []

            for i, f in enumerate(uploaded):
                prog.progress((i+1)/len(uploaded), text=f"⏳ {f.name}")
                try:
                    # Dosya adından ay al: 2026-01_TEFAS.xlsx → 2026-01
                    isim = f.name.replace('.xlsx','').replace('_TEFAS','').replace(' TEFAS','').strip()
                    # Format kontrolü
                    if not (len(isim) == 7 and isim[4] == '-'):
                        isim = isim[:7]  # ilk 7 karakter: 2026-01

                    df = _oku_tefas_excel(f, isim)
                    tefas[isim] = df.to_dict('records')
                    basarili.append(f"{isim} ({len(df)} fon)")
                except Exception as e:
                    hatali.append(f"{f.name}: {e}")

            _kaydet_tefas(tefas)
            prog.empty()
            if basarili:
                st.success(f"✅ {', '.join(basarili)}")
            if hatali:
                st.error("❌ " + " | ".join(hatali))
            st.rerun()

        # Ay silme
        if tefas:
            sil = st.selectbox("Ay sil:", ["—"] + sorted(tefas.keys(), reverse=True), key="tefas_sil")
            if sil != "—" and st.button("🗑️ Sil", key="tefas_sil_btn"):
                del tefas[sil]
                _kaydet_tefas(tefas)
                st.rerun()

    if not tefas:
        st.info("TEFAS verisi yok. Yukarıdan Excel yükle.")
        return

    # ── DÖNEM SEÇİMİ ──────────────────────────────────────────────────────────
    aylar = sorted(tefas.keys())
    
    col1, col2 = st.columns([2, 3])
    with col1:
        secili_ay = st.selectbox(
            "📅 Dönem:",
            aylar,
            index=len(aylar)-1,  # Son ay varsayılan
            key="tefas_ay",
        )
    
    # Önceki ay
    secili_idx = aylar.index(secili_ay)
    onceki_ay = aylar[secili_idx - 1] if secili_idx > 0 else None

    with col2:
        if onceki_ay:
            st.info(f"Karşılaştırma: **{onceki_ay}** → **{secili_ay}**")
        else:
            st.warning("İlk ay seçili — karşılaştırma yok.")

    # ── VERİ HAZIRLA ──────────────────────────────────────────────────────────
    df_secili = pd.DataFrame(tefas[secili_ay])
    df_secili = df_secili.rename(columns={
        'Son Portföy Büyüklüğü': 'Büyüklük',
        'Portföy Büyüklüğü Değişimi (%)': 'AyİçiDeg',
        'Pay Adedi Değişimi (%)': 'PayDeg',
        'Getiri Oranı (%)': 'Getiri',
    })

    if onceki_ay:
        df_onceki = pd.DataFrame(tefas[onceki_ay])[['Fon Kodu','Son Portföy Büyüklüğü']].rename(
            columns={'Son Portföy Büyüklüğü': 'OncekiBüyüklük'}
        )
        df = pd.merge(df_secili, df_onceki, on='Fon Kodu', how='left')
        df['DönemDeg%'] = ((df['Büyüklük'] - df['OncekiBüyüklük']) / df['OncekiBüyüklük'] * 100).round(1)
    else:
        df = df_secili.copy()
        df['OncekiBüyüklük'] = None
        df['DönemDeg%'] = None

    df = df.sort_values('Büyüklük', ascending=False).reset_index(drop=True)
    df.index = range(1, len(df)+1)

    # ── FİLTRE ────────────────────────────────────────────────────────────────
    st.divider()
    col_f1, col_f2, col_f3 = st.columns(3)
    
    with col_f1:
        filtre = st.radio(
            "Göster:",
            ["Tümü", "🚀 Büyüyenler", "🔴 Küçülenler", "🆕 Yeni Girenler"],
            horizontal=True,
            key="tefas_filtre",
        )
    with col_f2:
        ara = st.text_input("Fon ara:", placeholder="PHE, PUSULA...", key="tefas_ara").upper().strip()
    with col_f3:
        min_buyukluk = st.number_input("Min büyüklük (M ₺):", value=0, step=10, key="tefas_min")

    # Filtre uygula
    df_goster = df.copy()

    if ara:
        df_goster = df_goster[
            df_goster['Fon Kodu'].str.contains(ara) |
            df_goster['Fon Adı'].str.upper().str.contains(ara)
        ]

    if min_buyukluk > 0:
        df_goster = df_goster[df_goster['Büyüklük'] >= min_buyukluk * 1e6]

    if filtre == "🚀 Büyüyenler" and onceki_ay:
        df_goster = df_goster[df_goster['DönemDeg%'] > 0].sort_values('DönemDeg%', ascending=False)
    elif filtre == "🔴 Küçülenler" and onceki_ay:
        df_goster = df_goster[df_goster['DönemDeg%'] < 0].sort_values('DönemDeg%', ascending=True)
    elif filtre == "🆕 Yeni Girenler" and onceki_ay:
        df_goster = df_goster[df_goster['OncekiBüyüklük'].isna()]

    # ── ÖZET METRİKLER ────────────────────────────────────────────────────────
    if onceki_ay:
        buyuyen = (df['DönemDeg%'] > 0).sum()
        kuculen = (df['DönemDeg%'] < 0).sum()
        yeni    = df['OncekiBüyüklük'].isna().sum()
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Toplam Fon", len(df))
        m2.metric("🚀 Büyüyen", buyuyen)
        m3.metric("🔴 Küçülen", kuculen)
        m4.metric("🆕 Yeni", yeni)

    st.divider()

    # ── ANA TABLO ─────────────────────────────────────────────────────────────
    st.markdown(f"**{secili_ay}** — {len(df_goster)} fon")

    # Tablo için hazırla
    tablo_rows = []
    for _, row in df_goster.iterrows():
        tablo_rows.append({
            'KOD'       : row['Fon Kodu'],
            'FON ADI'   : row['Fon Adı'][:50] if pd.notna(row['Fon Adı']) else '—',
            onceki_ay if onceki_ay else 'ÖNCEKİ': _buyukluk_str(row.get('OncekiBüyüklük')),
            secili_ay   : _buyukluk_str(row['Büyüklük']),
            'DEĞİŞİM'   : _degisim_emoji(row['DönemDeg%']) if onceki_ay else '—',
            'PAY DEĞ%'  : f"%{row['PayDeg']*100:.1f}" if pd.notna(row.get('PayDeg')) else '—',
            'GETİRİ'    : f"%{row['Getiri']*100:.1f}" if pd.notna(row.get('Getiri')) else '—',
        })

    df_tablo = pd.DataFrame(tablo_rows)

    # Renk uygula
    def _renk_satir(row):
        deg_str = row['DEĞİŞİM']
        if '🚀' in str(deg_str): bg, fg = '#1a5e20', 'white'
        elif '✅' in str(deg_str): bg, fg = '#2e7d32', 'white'
        elif '📈' in str(deg_str): bg, fg = '#388e3c', 'white'
        elif '🔴' in str(deg_str): bg, fg = '#7f0000', 'white'
        elif '📉' in str(deg_str): bg, fg = '#b71c1c', 'white'
        else: bg, fg = '', 'black'
        return [f'background-color:{bg};color:{fg}' if bg else ''] * len(row)

    styled = df_tablo.style.apply(_renk_satir, axis=1)
    st.dataframe(styled, use_container_width=True, height=min(700, 45 + len(df_tablo)*35))
