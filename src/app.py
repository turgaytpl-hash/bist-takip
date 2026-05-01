"""
app.py — BIST Akıllı Para Takip Sistemi
Çalıştırma: python -m streamlit run src/app.py --server.port 8501
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

from app_takas import takas_sekmesi, takas_veri_yukle_bolumu
from mkk_app import mkk_sekmesi, _veri_yukle_bolumu as mkk_yukle_bolumu

st.set_page_config(
    page_title="BIST Akıllı Para Takip",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
.main > div { padding-top: 0.5rem; }
.stTabs [data-baseweb="tab"] {
    height: 46px; padding: 0 24px;
    background: #F0F2F6; border-radius: 6px 6px 0 0;
    font-weight: 700; font-size: 14px;
}
.stTabs [aria-selected="true"] {
    background: #1A252F !important; color: white !important;
}
</style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📊 BIST Akıllı Para")
    st.markdown(f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}")

# ── Ana Sekmeler ──────────────────────────────────────────────────────────────
tab_takas, tab_mkk, tab_hisse, tab_kurum, tab_bebek, tab_endeks, tab_yukle = st.tabs([
    "🚨 TAKAS ANALİZİ",
    "📊 MKK ANALİZ",
    "🔍 Hisse Detay",
    "🏦 Kurum Detay",
    "🐣 Bebek Hisse",
    "📊 Endeks Takip",
    "⚙️ Veri Yükle",
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — TAKAS ANALİZİ
# ══════════════════════════════════════════════════════════════════════════════
with tab_takas:
    takas_sekmesi()

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — MKK ANALİZ
# ══════════════════════════════════════════════════════════════════════════════
with tab_mkk:
    mkk_sekmesi()

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — HİSSE DETAY
# ══════════════════════════════════════════════════════════════════════════════
with tab_hisse:
    from takas_depo import (
        hisse_kurum_detay, _oku as takas_oku_raw,
        AKILLI_PARA, BUYUK_YERLI
    )

    st.subheader("🔍 Hisse Bazlı Detay")
    default_hisse = st.session_state.get("secili_hisse", "")
    sembol = st.text_input(
        "Hisse kodu:", value=default_hisse,
        placeholder="THYAO", key="hisse_kodu"
    ).upper().strip()

    if sembol:
        st.session_state["secili_hisse"] = sembol

        # Takas kurum detayı
        takas_det = hisse_kurum_detay(sembol)
        if not takas_det.empty:
            st.markdown(f"#### 🏦 {sembol} — Kurum Takas Detayı")
            st.dataframe(takas_det, hide_index=True, use_container_width=True)

        # Pozisyon pasta
        t2_df = takas_oku_raw()
        if not t2_df.empty:
            t2_hisse = t2_df[t2_df["hisse"] == sembol].copy()
            if not t2_hisse.empty:
                idx_son = t2_hisse.groupby("kurum")["donem"].idxmax()
                t2_son  = t2_hisse.loc[idx_son].copy()
                t2_son  = t2_son[t2_son["oran2"] > 0].sort_values("oran2", ascending=False)

                if not t2_son.empty:
                    st.markdown(f"#### 🥧 {sembol} — Pozisyon Dağılımı (T2 Güncel)")
                    col_p, col_i = st.columns([1, 1])

                    def kurum_renk(k):
                        if k in AKILLI_PARA: return "#1A5276"
                        if k in BUYUK_YERLI: return "#1A7A3E"
                        return "#E67E22"

                    labels = t2_son["kurum"].tolist()
                    values = t2_son["oran2"].tolist()
                    colors = [kurum_renk(k) for k in labels]
                    top = sum(values)
                    labels.append("KALAN")
                    values.append(max(0, 100 - top))
                    colors.append("#DDDDDD")

                    fig_pie = go.Figure(go.Pie(
                        labels=labels, values=values,
                        marker_colors=colors, hole=0.45,
                        textinfo="label+percent"
                    ))
                    fig_pie.update_layout(
                        height=350, margin=dict(l=10, r=10, t=30, b=10),
                        annotations=[dict(text=f"{top:.1f}%", x=0.5, y=0.5,
                                         font_size=18, showarrow=False)]
                    )
                    with col_p:
                        st.plotly_chart(fig_pie, use_container_width=True)
                    with col_i:
                        st.markdown("**Detay:**")
                        for _, r in t2_son.iterrows():
                            st.markdown(f"**{r['kurum']}**: `{r['oran2']:.2f}%`")
                        st.markdown(f"---\n**Toplam**: `{top:.2f}%` | **Kalan**: `{max(0,100-top):.2f}%`")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — KURUM DETAY
# ══════════════════════════════════════════════════════════════════════════════
with tab_kurum:
    from takas_depo import (
        kurum_elindeki_hisseler, donemler_listele,
        KURUMLAR, AKILLI_PARA, BUYUK_YERLI
    )

    st.subheader("🏦 Kurum Detay")

    col_k1, col_k2, col_k3, col_k4 = st.columns([2, 1, 2, 1])
    with col_k1:
        secili_kurum = st.selectbox("Kurum seç:", KURUMLAR, key="kurum_sec")
    with col_k2:
        filtre_tip = st.selectbox(
            "Veri tipi:", ["otomatik", "gunluk", "haftalik", "aylik"],
            key="kurum_tip"
        )
        if filtre_tip == "otomatik": filtre_tip = None
    with col_k3:
        tum_donemler = (
            donemler_listele("gunluk") +
            donemler_listele("haftalik") +
            donemler_listele("aylik")
        )
        karsilastirma = st.selectbox(
            "Karşılaştırma dönemi:", [""] + sorted(tum_donemler, reverse=True),
            key="kurum_kars"
        ) or None
    with col_k4:
        if secili_kurum in AKILLI_PARA:
            grup_label, grup_renk = "🔵 Akıllı Para", "#1A5276"
        elif secili_kurum in BUYUK_YERLI:
            grup_label, grup_renk = "🟢 Büyük Yerli", "#1A7A3E"
        else:
            grup_label, grup_renk = "🟡 Fon / Yabancı", "#E67E22"
        st.markdown(
            f"<br><span style='color:{grup_renk};font-weight:bold;font-size:16px;'>{grup_label}</span>",
            unsafe_allow_html=True
        )

    st.divider()

    el_df = kurum_elindeki_hisseler(secili_kurum, tip=filtre_tip, karsilastirma_donem=karsilastirma)
    tip_label = {"gunluk": "📅 Günlük", "haftalik": "📆 Haftalık", "aylik": "🗓️ Aylık"}.get(filtre_tip, "🔄 Otomatik")
    kars_label = karsilastirma if karsilastirma else "ilk dönem"

    if el_df.empty:
        st.info(f"{secili_kurum} için veri bulunamadı.")
    else:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("📊 Toplam Hisse", len(el_df))
        m2.metric("💰 Ort. Pozisyon %", f"%{el_df['oran2'].mean():.2f}")
        m3.metric("🔝 Max Pozisyon %", f"%{el_df['oran2'].max():.2f}")
        m4.metric("📦 Toplam Adet", f"{el_df['adet2'].sum():,.0f}")

        st.caption(f"Veri tipi: **{tip_label}** | Son dönem: **{el_df['donem'].max()}** | Karşılaştırma: **{kars_label}**")

        top20 = el_df.head(20)
        fig_k = go.Figure(go.Bar(
            x=top20["hisse"].tolist(), y=top20["oran2"].tolist(),
            marker_color=grup_renk,
            text=[f"%{v:.2f}" for v in top20["oran2"].tolist()],
            textposition="outside"
        ))
        fig_k.update_layout(
            title=f"{secili_kurum} — Top 20 | {tip_label}",
            height=350, margin=dict(l=10, r=10, t=40, b=10),
            plot_bgcolor="#FAFAFA", paper_bgcolor="white",
            xaxis_tickangle=-45
        )
        st.plotly_chart(fig_k, use_container_width=True)

        tablo_cols  = ["hisse", "oran2", "adet2", "adet_fark", "dolasim_pct", "donem", "tip"]
        tablo_names = ["Hisse", "T2 Oran %", "T2 Adet", "Adet Fark", "Dolaşım %", "Son Dönem", "Tip"]
        fmt = {"T2 Oran %": "{:.2f}", "T2 Adet": "{:,.0f}", "Adet Fark": "{:+,.0f}", "Dolaşım %": "{:+.2f}"}

        if "oran_degisim" in el_df.columns:
            tablo_cols.insert(2, "oran_degisim")
            tablo_names.insert(2, "Oran Δ%")
            fmt["Oran Δ%"] = "{:+.2f}"

        tablo = el_df[tablo_cols].copy()
        tablo.columns = tablo_names

        def renk_oran(val):
            if isinstance(val, float):
                if val >= 5: return "background-color:#D5F5E3;color:#1A5276;font-weight:bold"
                if val >= 2: return "color:#1A5276;font-weight:bold"
                if val > 0:  return "color:#1A7A3E"
            return ""

        def renk_degisim(val):
            if isinstance(val, float):
                if val > 0: return "color:#1A5276;font-weight:bold"
                if val < 0: return "color:#C0392B;font-weight:bold"
            return ""

        styled = tablo.style.map(renk_oran, subset=["T2 Oran %"])
        if "Oran Δ%" in tablo.columns:
            styled = styled.map(renk_degisim, subset=["Oran Δ%"])
        styled = styled.map(renk_degisim, subset=["Dolaşım %"])
        styled = styled.format(fmt, na_rep="—")
        st.dataframe(styled, hide_index=True, use_container_width=True, height=500)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — BEBEK HİSSE
# ══════════════════════════════════════════════════════════════════════════════
with tab_bebek:
    from bebek_hisse_tab import bebek_hisse_sekme
    bebek_hisse_sekme()

# ══════════════════════════════════════════════════════════════════════════════
# TAB 6 — ENDEKS TAKİP
# ══════════════════════════════════════════════════════════════════════════════
with tab_endeks:
    from endeks_takip import endeks_takip_sekme
    endeks_takip_sekme()

# ══════════════════════════════════════════════════════════════════════════════
# TAB 7 — VERİ YÜKLE
# ══════════════════════════════════════════════════════════════════════════════
with tab_yukle:
    st.subheader("⚙️ Veri Yükle")
    veri_tab1, veri_tab2 = st.tabs(["🏦 Kurum Takas", "📊 MKK"])
    with veri_tab1:
        takas_veri_yukle_bolumu()
    with veri_tab2:
        mkk_yukle_bolumu()
