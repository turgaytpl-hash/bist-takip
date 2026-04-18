"""
app.py — BIST Akıllı Para Takip Sistemi
Çalıştırma: python -m streamlit run app.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from io import BytesIO

from depo import (
    haftalik_donemler, aylik_donemler,
    haftalik_ekle, haftalik_sil,
    aylik_ekle, aylik_sil,
    pozisyon_getir, haftalik_pozisyon_getir,
    _oku, AYL_MKK, AYL_TAKAS, HAF_TAKAS, HAF_MKK, HAF_OZEL,
)
from parser import takas_oku, mkk_oku, pozisyon_hesapla
from excel_export import excel_indir

st.set_page_config(
    page_title="BIST Akıllı Para Takip",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
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
    st.markdown("---")
    haf_list = haftalik_donemler()
    ayl_list = aylik_donemler()
    st.markdown("**📅 Haftalık:**")
    for d in sorted(haf_list, reverse=True)[:5]:
        st.markdown(f"&nbsp;&nbsp;`{d}`", unsafe_allow_html=True)
    if not haf_list: st.caption("Henüz yok")
    st.markdown("**📆 Aylık:**")
    for d in sorted(ayl_list, reverse=True)[:5]:
        st.markdown(f"&nbsp;&nbsp;`{d}`", unsafe_allow_html=True)
    if not ayl_list: st.caption("Henüz yok")

tab_ayl, tab_haf, tab_hisse, tab_yukle = st.tabs([
    "📆 AYLIK ANALİZ",
    "📅 HAFTALIK ANALİZ", 
    "🔍 Hisse Detay",
    "⚙️ Veri Yükle",
])

# ══════════════════════════════════════════════════════════════════════════════
# YARDIMCI FONKSİYONLAR
# ══════════════════════════════════════════════════════════════════════════════

def ana_tablo_olustur(secili_donemler: list) -> pd.DataFrame:
    """
    Ana tablo: MKK pp kolonları + pozisyon oranları
    Her satır bir hisse, kolonlar:
    Hisse | Ay1_pp | Ay2_pp | ... | Kümülatif | Yab% | Fon% | Emk% | TERA% | BULLS% | PUSULA%
    """
    mkk_df = _oku(AYL_MKK)
    if mkk_df.empty:
        return pd.DataFrame()

    # Seçili dönemleri filtrele
    mkk_df = mkk_df[mkk_df['donem'].isin(secili_donemler)]
    if mkk_df.empty:
        return pd.DataFrame()

    # MKK pivot: her dönem için pp_fark kolonu
    pivot = mkk_df.pivot_table(
        index='hisse', columns='donem', values='pp_fark', aggfunc='sum'
    ).reset_index()
    pivot.columns.name = None

    donem_cols = sorted([c for c in pivot.columns if c != 'hisse'])
    pivot = pivot[['hisse'] + donem_cols]

    # Kolon isimlerini güzelleştir
    rename = {'hisse': 'HİSSE'}
    for d in donem_cols:
        rename[d] = f"{d} MKK"
    pivot = pivot.rename(columns=rename)

    mkk_cols = [f"{d} MKK" for d in donem_cols]

    # Kümülatif
    pivot['KÜMÜLATİF'] = pivot[mkk_cols].sum(axis=1).round(2)

    # Trend - Roket = son 3 dönem pozitif VE düzenli artan
    def trend(row):
        vals = [row[c] for c in mkk_cols if pd.notna(row[c])]
        if len(vals) < 2:
            return "—"
        son3 = vals[-3:] if len(vals) >= 3 else vals
        if (len(son3) >= 2 and
                all(v > 0 for v in son3) and
                all(son3[i] > son3[i-1] for i in range(1, len(son3)))):
            return "🚀"
        if all(v > 0 for v in vals):
            return "🟢"
        if sum(1 for v in vals if v > 0) > sum(1 for v in vals if v < 0):
            return "🟡"
        return "🔴"

    pivot['TREND'] = pivot.apply(trend, axis=1)

    # Pozisyon oranları — en son dönemden
    son_donem = sorted(secili_donemler)[-1]
    pos = pozisyon_getir(son_donem)

    if not pos.empty:
        for tip, col in [('yabanci','YAB%'), ('fon','FON%'),
                         ('emeklilik','EMK%'), ('tera','TERA%'),
                         ('bulls','BULLS%'), ('pusula','PUSULA%')]:
            t = pos[pos['tip'] == tip][['hisse', 'oran']].copy()
            t.columns = ['HİSSE', col]
            pivot = pivot.merge(t, on='HİSSE', how='left')

    # Sıralama: Kümülatif azalan
    pivot = pivot.sort_values('KÜMÜLATİF', ascending=False).reset_index(drop=True)

    return pivot


def renk_uygula(df: pd.DataFrame) -> object:
    """Sayı kolonlarına renk uygula"""
    mkk_cols = [c for c in df.columns if 'MKK' in c or 'KÜMÜLATİF' in c]
    oran_cols = [c for c in df.columns if c.endswith('%')]

    def renk_mkk(val):
        if isinstance(val, (int, float)):
            if val > 0: return 'color: #1A5276; font-weight: bold'
            if val < 0: return 'color: #C0392B; font-weight: bold'
        return 'color: #888888'

    def renk_oran(val):
        if isinstance(val, (int, float)) and val > 0:
            return 'color: #1A7A3E; font-weight: bold'
        return 'color: #AAAAAA'

    fmt = {}
    for c in mkk_cols:
        fmt[c] = '{:+.2f}'
    for c in oran_cols:
        fmt[c] = '{:.2f}'

    styled = df.style
    if mkk_cols:
        styled = styled.map(renk_mkk, subset=mkk_cols)
    if oran_cols:
        styled = styled.map(renk_oran, subset=oran_cols)
    if fmt:
        styled = styled.format(fmt, na_rep='—')

    return styled


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — AYLIK ANALİZ
# ══════════════════════════════════════════════════════════════════════════════
with tab_ayl:
    st.subheader("Aylık MKK + Pozisyon Analizi")

    ayl_list = aylik_donemler()
    if not ayl_list:
        st.info("📂 Veri yok. **Veri Yükle** sekmesinden aylık veri ekleyin.")
    else:
        # Kontroller
        c1, c2, c3 = st.columns([4, 1, 1])
        with c1:
            secili = st.multiselect(
                "Aylar:", sorted(ayl_list, reverse=True),
                default=sorted(ayl_list, reverse=True),
                key="ayl_donem"
            )
        with c2:
            filtre = st.selectbox("Filtre:", 
                ["Tümü", "🚀 Sürekli Artan", "🟢 Hep Yeşil",
                 "Son 2 Ay Yeşil", "Son 3 Ay Yeşil", "Özel Fon Var"],
                key="ayl_filtre"
            )
        with c3:
            ozel_sec = st.selectbox("Özel Fon:",
                ["Hepsi", "TERA", "BULLS", "PUSULA"], key="ayl_ozel")

        if not secili:
            st.warning("En az 1 ay seçin.")
        else:
            df = ana_tablo_olustur(secili)

            if df.empty:
                st.warning("Veri bulunamadı.")
            else:
                # Filtrele
                df_f = df.copy()

                mkk_cols_f = [c for c in df_f.columns if "MKK" in c]

                if filtre == "🚀 Sürekli Artan":
                    df_f = df_f[df_f['TREND'] == '🚀']
                elif filtre == "🟢 Hep Yeşil":
                    df_f = df_f[df_f['TREND'].isin(['🚀', '🟢'])]
                elif filtre == "Son 2 Ay Yeşil":
                    if len(mkk_cols_f) >= 2:
                        son2 = mkk_cols_f[-2:]
                        df_f = df_f[(df_f[son2] > 0).all(axis=1)]
                elif filtre == "Son 3 Ay Yeşil":
                    if len(mkk_cols_f) >= 3:
                        son3 = mkk_cols_f[-3:]
                        df_f = df_f[(df_f[son3] > 0).all(axis=1)]
                elif filtre == "Özel Fon Var":
                    mask = pd.Series([False] * len(df_f))
                    for col in ['TERA%', 'BULLS%', 'PUSULA%']:
                        if col in df_f.columns:
                            mask = mask | (df_f[col].fillna(0) > 0)
                    df_f = df_f[mask]

                if ozel_sec != "Hepsi":
                    col = f"{ozel_sec}%"
                    if col in df_f.columns:
                        df_f = df_f[df_f[col].fillna(0) > 0]
                        df_f = df_f.sort_values(col, ascending=False)

                # KPI
                k1, k2, k3, k4, k5 = st.columns(5)
                k1.metric("Toplam Hisse", len(df_f))
                k2.metric("🚀 Son 3 Artan", (df_f['TREND'] == '🚀').sum())
                k3.metric("🟢 Hep Yeşil", (df_f['TREND'].isin(['🚀','🟢'])).sum())
                if 'TERA%' in df_f.columns:
                    k4.metric("TERA >%3", (df_f['TERA%'].fillna(0) >= 3).sum())
                if 'BULLS%' in df_f.columns:
                    k5.metric("BULLS >%3", (df_f['BULLS%'].fillna(0) >= 3).sum())

                st.markdown("---")
                st.caption("💡 Kolona tıklayarak sıralayabilirsiniz")

                # Gösterilecek kolonlar
                mkk_cols = [c for c in df_f.columns if 'MKK' in c]
                oran_cols = [c for c in df_f.columns if c.endswith('%')]
                goster = ['HİSSE', 'TREND'] + mkk_cols + oran_cols
                goster = [c for c in goster if c in df_f.columns]

                st.dataframe(
                    renk_uygula(df_f[goster].reset_index(drop=True)),
                    use_container_width=True,
                    height=600,
                )

                # Excel
                buf = excel_indir(df_f[goster], None,
                    baslik="Aylık MKK Analizi",
                    donem="-".join(secili))
                st.download_button("⬇️ Excel İndir", data=buf,
                    file_name=f"aylik_mkk_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — HAFTALIK ANALİZ
# ══════════════════════════════════════════════════════════════════════════════
with tab_haf:
    st.subheader("Haftalık MKK + Pozisyon Analizi")

    haf_list = haftalik_donemler()
    if not haf_list:
        st.info("📂 Veri yok. **Veri Yükle** sekmesinden haftalık veri ekleyin.")
    else:
        # Varsayılan: son 4 hafta
        son4 = sorted(haf_list, reverse=True)[:4]

        c1, c2, c3 = st.columns([4, 1, 1])
        with c1:
            secili_haf = st.multiselect(
                "Haftalar:", sorted(haf_list, reverse=True),
                default=son4, key="haf_donem"
            )
        with c2:
            haf_filtre = st.selectbox("Filtre:",
                ["Tümü", "🚀 Sürekli Artan", "🟢 Hep Yeşil",
                 "Son 2 Hafta Yeşil", "Son 3 Hafta Yeşil", "Özel Fon Var"],
                key="haf_filtre"
            )
        with c3:
            haf_ozel = st.selectbox("Özel Fon:",
                ["Hepsi", "TERA", "BULLS", "PUSULA"], key="haf_ozel"
            )

        if not secili_haf:
            st.warning("En az 1 hafta seçin.")
        else:
            mkk = _oku(HAF_MKK)
            ozel = _oku(HAF_OZEL)

            if mkk.empty:
                st.warning("MKK verisi bulunamadı.")
            else:
                # MKK pivot - aylıkla aynı mantık
                mkk_f = mkk[mkk["donem"].isin(secili_haf)]
                pivot = mkk_f.pivot_table(
                    index="hisse", columns="donem", values="pp_fark", aggfunc="sum"
                ).reset_index()
                pivot.columns.name = None
                donem_cols = sorted([c for c in pivot.columns if c != "hisse"])
                pivot = pivot[["hisse"] + donem_cols]

                rename = {"hisse": "HİSSE"}
                for d in donem_cols:
                    rename[d] = f"{d} MKK"
                pivot = pivot.rename(columns=rename)
                mkk_cols = [f"{d} MKK" for d in donem_cols]

                # Trend - Roket = son 3 dönem düzenli artan
                def trend(row):
                    vals = [row[c] for c in mkk_cols if pd.notna(row.get(c))]
                    if len(vals) < 2: return "—"
                    son3 = vals[-3:] if len(vals) >= 3 else vals
                    if (len(son3) >= 2 and
                            all(v > 0 for v in son3) and
                            all(son3[i] > son3[i-1] for i in range(1, len(son3)))):
                        return "🚀"
                    if all(v > 0 for v in vals): return "🟢"
                    if sum(1 for v in vals if v > 0) > sum(1 for v in vals if v < 0): return "🟡"
                    return "🔴"
                pivot["TREND"] = pivot.apply(trend, axis=1)

                # Pozisyon oranları - önce haftalık, yoksa aylık
                son_haf_donem = sorted(secili_haf)[-1]
                pos = haftalik_pozisyon_getir(son_haf_donem)
                if pos.empty:
                    ayl_list_s = aylik_donemler()
                    if ayl_list_s:
                        pos = pozisyon_getir(sorted(ayl_list_s)[-1])
                if not pos.empty:
                    for tip, col in [("yabanci","YAB%"),("fon","FON%"),
                                     ("emeklilik","EMK%"),("tera","TERA%"),
                                     ("bulls","BULLS%"),("pusula","PUSULA%")]:
                        t = pos[pos["tip"]==tip][["hisse","oran"]].copy()
                        t.columns = ["HİSSE", col]
                        pivot = pivot.merge(t, on="HİSSE", how="left")

                # Filtrele
                df_f = pivot.copy()
                if haf_filtre == "🚀 Sürekli Artan":
                    df_f = df_f[df_f["TREND"] == "🚀"]
                elif haf_filtre == "🟢 Hep Yeşil":
                    df_f = df_f[df_f["TREND"].isin(["🚀", "🟢"])]
                elif haf_filtre == "Son 2 Hafta Yeşil":
                    if len(mkk_cols) >= 2:
                        df_f = df_f[(df_f[mkk_cols[-2:]] > 0).all(axis=1)]
                elif haf_filtre == "Son 3 Hafta Yeşil":
                    if len(mkk_cols) >= 3:
                        df_f = df_f[(df_f[mkk_cols[-3:]] > 0).all(axis=1)]
                elif haf_filtre == "Özel Fon Var":
                    mask = pd.Series([False] * len(df_f))
                    for col in ["TERA%", "BULLS%", "PUSULA%"]:
                        if col in df_f.columns:
                            mask = mask | (df_f[col].fillna(0) > 0)
                    df_f = df_f[mask]

                if haf_ozel != "Hepsi":
                    col = f"{haf_ozel}%"
                    if col in df_f.columns:
                        df_f = df_f[df_f[col].fillna(0) > 0]
                        df_f = df_f.sort_values(col, ascending=False)

                df_f = df_f.sort_values("KÜMÜLATİF" if "KÜMÜLATİF" in df_f.columns else mkk_cols[-1],
                                        ascending=False).reset_index(drop=True)

                # KPI
                k1, k2, k3, k4, k5 = st.columns(5)
                k1.metric("Toplam Hisse", len(df_f))
                k2.metric("🚀 Son 3 Artan", (df_f["TREND"] == "🚀").sum())
                k3.metric("🟢 Hep Yeşil", (df_f["TREND"].isin(["🚀","🟢"])).sum())
                if "TERA%" in df_f.columns:
                    k4.metric("TERA >%3", (df_f["TERA%"].fillna(0) >= 3).sum())
                if "BULLS%" in df_f.columns:
                    k5.metric("BULLS >%3", (df_f["BULLS%"].fillna(0) >= 3).sum())

                st.markdown("---")
                st.caption("💡 Kolona tıklayarak sıralayabilirsiniz")

                oran_cols = [c for c in df_f.columns if c.endswith("%")]
                goster = ["HİSSE", "TREND"] + mkk_cols + oran_cols
                goster = [c for c in goster if c in df_f.columns]

                fmt = {}
                for c in mkk_cols: fmt[c] = "{:+.2f}"
                for c in oran_cols: fmt[c] = "{:.2f}"

                st.dataframe(
                    renk_uygula(df_f[goster].reset_index(drop=True)),
                    use_container_width=True, height=600
                )

                buf = excel_indir(df_f[goster], None,
                    baslik="Haftalık MKK Analizi", donem="-".join(sorted(secili_haf)))
                st.download_button("⬇️ Excel İndir", data=buf,
                    file_name=f"haftalik_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

with tab_hisse:
    st.subheader("🔍 Hisse Bazlı Detay")

    sembol = st.text_input("Hisse kodu:", placeholder="THYAO", key="hisse_inp").upper().strip()

    if sembol:
        # MKK geçmişi
        mkk_df = _oku(AYL_MKK)
        if not mkk_df.empty:
            h_mkk = mkk_df[mkk_df['hisse'] == sembol].sort_values('donem')
            if not h_mkk.empty:
                st.markdown(f"#### 📊 {sembol} — MKK Kurumsal Oran")
                col1, col2 = st.columns([1, 1])
                with col1:
                    tablo = h_mkk[['donem','pp_fark']].copy()
                    tablo.columns = ['Dönem', 'MKK pp']
                    st.dataframe(
                        tablo.style.map(
                            lambda v: 'color:#1A5276;font-weight:bold' if isinstance(v,(int,float)) and v>0
                            else 'color:#C0392B' if isinstance(v,(int,float)) and v<0 else '',
                            subset=['MKK pp']
                        ).format({'MKK pp': '{:+.2f}'}),
                        hide_index=True, use_container_width=True
                    )
                with col2:
                    fig = go.Figure(go.Bar(
                        x=h_mkk['donem'].tolist(),
                        y=h_mkk['pp_fark'].tolist(),
                        marker_color=['#1A5276' if v >= 0 else '#C0392B' 
                                     for v in h_mkk['pp_fark'].tolist()],
                        text=[f"{v:+.2f}" for v in h_mkk['pp_fark'].tolist()],
                        textposition='outside'
                    ))
                    fig.update_layout(
                        title=f"{sembol} MKK pp Değişimi",
                        height=300, margin=dict(l=10,r=10,t=40,b=10),
                        plot_bgcolor='#FAFAFA', paper_bgcolor='white'
                    )
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning(f"{sembol} için MKK verisi yok.")

        # Pozisyon pasta
        pos = pozisyon_getir()
        if not pos.empty:
            h_pos = pos[pos['hisse'] == sembol]
            if not h_pos.empty:
                st.markdown(f"#### 🥧 {sembol} — Pozisyon Dağılımı")
                col_p, col_i = st.columns([1, 1])
                renk_map = {
                    'yabanci':'#1A5276','fon':'#1A7A3E',
                    'emeklilik':'#7D3C00','tera':'#8E44AD',
                    'bulls':'#C0392B','pusula':'#E67E22'
                }
                labels, values, colors = [], [], []
                for _, r in h_pos.iterrows():
                    if r['oran'] > 0:
                        labels.append(r['tip'].upper())
                        values.append(r['oran'])
                        colors.append(renk_map.get(r['tip'], '#AAAAAA'))
                top = sum(values)
                labels.append('KALAN')
                values.append(max(0, 100 - top))
                colors.append('#DDDDDD')

                fig = go.Figure(go.Pie(
                    labels=labels, values=values,
                    marker_colors=colors, hole=0.45,
                    textinfo='label+percent'
                ))
                fig.update_layout(
                    height=320, margin=dict(l=10,r=10,t=30,b=10),
                    annotations=[dict(text=f"{top:.1f}%", x=0.5, y=0.5,
                                     font_size=18, showarrow=False)]
                )
                with col_p:
                    st.plotly_chart(fig, use_container_width=True)
                with col_i:
                    st.markdown("**Detay:**")
                    for _, r in h_pos.iterrows():
                        if r['oran'] > 0:
                            st.markdown(f"**{r['tip'].upper()}**: `{r['oran']:.2f}%`")
                    st.markdown(f"---\n**Toplam Kurum**: `{top:.2f}%`\n**Kalan**: `{max(0,100-top):.2f}%`")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — VERİ YÜKLE
# ══════════════════════════════════════════════════════════════════════════════
with tab_yukle:
    st.subheader("⚙️ Veri Yükle")

    col_h, col_a = st.columns(2)

    # ── Haftalık ──────────────────────────────────────────────────────────────
    with col_h:
        st.markdown("### 📅 Haftalık")
        st.caption("Pazartesi — yabancı + fon + emeklilik + MKK + özel fonlar")
        with st.form("haf_form"):
            haf_donem = st.text_input("Dönem (YYYY_MM_HH):", placeholder="2026_01_01")
            hc1, hc2 = st.columns(2)
            with hc1:
                haf_yab = st.file_uploader("🔵 Yabancılar:", type=["xlsx"], key="h_yab")
                haf_fon = st.file_uploader("🟢 Yat. Fonları:", type=["xlsx"], key="h_fon")
            with hc2:
                haf_emk = st.file_uploader("🟠 Emeklilik:", type=["xlsx"], key="h_emk")
                haf_mkk = st.file_uploader("🟣 MKK:", type=["xlsx"], key="h_mkk")
            st.markdown("**Özel Fonlar:**")
            ho1, ho2, ho3 = st.columns(3)
            with ho1: haf_tera   = st.file_uploader("TERA",   type=["xlsx"], key="h_tera")
            with ho2: haf_bulls  = st.file_uploader("BULLS",  type=["xlsx"], key="h_bulls")
            with ho3: haf_pusula = st.file_uploader("PUSULA", type=["xlsx"], key="h_pusula")
            haf_sub = st.form_submit_button("✅ Haftalık Ekle", use_container_width=True)

        if haf_sub:
            if not haf_donem:
                st.error("Dönem zorunlu!")
            elif not any([haf_yab, haf_fon, haf_emk, haf_mkk]):
                st.error("En az 1 dosya yükleyin!")
            else:
                try:
                    yab = takas_oku(haf_yab) if haf_yab else None
                    fon = takas_oku(haf_fon) if haf_fon else None
                    emk = takas_oku(haf_emk) if haf_emk else None
                    mkk = mkk_oku(haf_mkk)   if haf_mkk else None
                    ozel = {}
                    if haf_tera:   ozel["TERA"]   = takas_oku(haf_tera)
                    if haf_bulls:  ozel["BULLS"]  = takas_oku(haf_bulls)
                    if haf_pusula: ozel["PUSULA"] = takas_oku(haf_pusula)
                    ok, msg = haftalik_ekle(haf_donem.strip(), yab, mkk, ozel, fon, emk)
                    if ok: st.success(msg); st.rerun()
                    else:  st.warning(msg)
                except Exception as e:
                    st.error(f"Hata: {e}")

        haf_list2 = haftalik_donemler()
        if haf_list2:
            st.markdown("**Kayıtlı dönemler:**")
            for d in sorted(haf_list2, reverse=True):
                c1, c2 = st.columns([3,1])
                c1.markdown(f"`{d}`")
                if c2.button("🗑️", key=f"hs_{d}"):
                    haftalik_sil(d); st.rerun()

    # ── Aylık ─────────────────────────────────────────────────────────────────
    with col_a:
        st.markdown("### 📆 Aylık")
        st.caption("Ay sonu — yabancı + fon + emeklilik + MKK + özel fonlar")
        with st.form("ayl_form"):
            ayl_donem = st.text_input("Dönem (YYYY_MM):", placeholder="2026_04")
            ac1, ac2 = st.columns(2)
            with ac1:
                ayl_yab = st.file_uploader("🔵 Yabancılar:", type=["xlsx"], key="a_yab")
                ayl_fon = st.file_uploader("🟢 Yat. Fonları:", type=["xlsx"], key="a_fon")
            with ac2:
                ayl_emk = st.file_uploader("🟠 Emeklilik:", type=["xlsx"], key="a_emk")
                ayl_mkk = st.file_uploader("🟣 MKK:", type=["xlsx"], key="a_mkk")
            st.markdown("**Özel Fonlar:**")
            ao1, ao2, ao3 = st.columns(3)
            with ao1: ayl_tera   = st.file_uploader("TERA",   type=["xlsx"], key="a_tera")
            with ao2: ayl_bulls  = st.file_uploader("BULLS",  type=["xlsx"], key="a_bulls")
            with ao3: ayl_pusula = st.file_uploader("PUSULA", type=["xlsx"], key="a_pusula")
            ayl_sub = st.form_submit_button("✅ Aylık Ekle", use_container_width=True)

        if ayl_sub:
            if not ayl_donem:
                st.error("Dönem zorunlu!")
            elif not any([ayl_yab, ayl_fon, ayl_emk]):
                st.error("En az 1 takas dosyası yükleyin!")
            else:
                try:
                    yab = takas_oku(ayl_yab) if ayl_yab else None
                    fon = takas_oku(ayl_fon) if ayl_fon else None
                    emk = takas_oku(ayl_emk) if ayl_emk else None
                    mkk = mkk_oku(ayl_mkk)   if ayl_mkk else None
                    ozel = {}
                    if ayl_tera:   ozel["TERA"]   = takas_oku(ayl_tera)
                    if ayl_bulls:  ozel["BULLS"]  = takas_oku(ayl_bulls)
                    if ayl_pusula: ozel["PUSULA"] = takas_oku(ayl_pusula)
                    ok, msg = aylik_ekle(ayl_donem.strip(), yab, fon, emk, mkk, ozel)
                    if ok: st.success(msg); st.rerun()
                    else:  st.warning(msg)
                except Exception as e:
                    st.error(f"Hata: {e}")

        ayl_list2 = aylik_donemler()
        if ayl_list2:
            st.markdown("**Kayıtlı dönemler:**")
            for d in sorted(ayl_list2, reverse=True):
                c1, c2 = st.columns([3,1])
                c1.markdown(f"`{d}`")
                if c2.button("🗑️", key=f"as_{d}"):
                    aylik_sil(d); st.rerun()

        # Veri durumu
        st.markdown("---")
        st.markdown("**📂 Veri Durumu:**")
        from depo import POZISYON
        for label, path in [("Aylık MKK", AYL_MKK), ("Aylık Takas", AYL_TAKAS), ("Pozisyon", POZISYON)]:
            if path.exists():
                df_c = pd.read_csv(path)
                st.success(f"✅ {label}: {len(df_c)} satır")
            else:
                st.warning(f"⚠️ {label}: Henüz yok")
