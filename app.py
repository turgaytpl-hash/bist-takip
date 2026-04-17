"""
app.py — BIST Akıllı Para Takip Sistemi
Çalıştırma: streamlit run app.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
from io import BytesIO

from depo import (
    haftalik_donemler, aylik_donemler,
    haftalik_ekle, haftalik_sil,
    aylik_ekle, aylik_sil,
    haftalik_ana_tablo, aylik_ana_tablo,
    pozisyon_getir, momentum_hesapla,
    ozel_fon_pozisyon,
)
from parser import takas_oku, mkk_oku, pozisyon_hesapla
from excel_export import excel_indir

# ── Sayfa Ayarları ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="BIST Akıllı Para Takip",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.main > div { padding-top: 0.8rem; }
.stTabs [data-baseweb="tab"] {
    height: 46px; padding: 0 24px;
    background: #F0F2F6; border-radius: 6px 6px 0 0;
    font-weight: 700; font-size: 14px;
}
.stTabs [aria-selected="true"] {
    background: #1A252F !important; color: white !important;
}
.blok {
    background: white; border-radius: 10px;
    padding: 14px 18px; margin-bottom: 10px;
    border-left: 4px solid #1A5276;
    box-shadow: 0 1px 4px rgba(0,0,0,0.07);
}
</style>
""", unsafe_allow_html=True)

# ── Renk Fonksiyonları ────────────────────────────────────────────────────────
def renk_net(val):
    if isinstance(val, (int, float)):
        if val > 0: return "color: #1A7A3E; font-weight:bold"
        if val < 0: return "color: #C0392B; font-weight:bold"
    return ""

def renk_pp(val):
    if isinstance(val, (int, float)):
        if val > 0: return "color: #1A5276; font-weight:bold"
        if val < 0: return "color: #C0392B"
    return ""

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📊 BIST Akıllı Para")
    st.markdown(f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    st.markdown("---")

    haf_list = haftalik_donemler()
    ayl_list = aylik_donemler()

    st.markdown("**📅 Haftalık Dönemler:**")
    if haf_list:
        for d in sorted(haf_list, reverse=True)[:6]:
            st.markdown(f"&nbsp;&nbsp;`{d}`", unsafe_allow_html=True)
    else:
        st.caption("Henüz yok")

    st.markdown("**📆 Aylık Dönemler:**")
    if ayl_list:
        for d in sorted(ayl_list, reverse=True)[:6]:
            st.markdown(f"&nbsp;&nbsp;`{d}`", unsafe_allow_html=True)
    else:
        st.caption("Henüz yok")

# ── Sekmeler ──────────────────────────────────────────────────────────────────
tab_haf, tab_ayl, tab_hisse, tab_yukle = st.tabs([
    "📅 HAFTALIK",
    "📆 AYLIK",
    "🔍 Hisse Detay",
    "⚙️ Veri Yükle",
])


# ════════════════════════════════════════════════════════════════════════════════
# TAB 1 — HAFTALIK
# ════════════════════════════════════════════════════════════════════════════════
with tab_haf:
    st.subheader("Haftalık Yabancı + MKK Analizi")

    haf_list = haftalik_donemler()
    if not haf_list:
        st.info("📂 Veri yok. **Veri Yükle** sekmesinden haftalık veri ekleyin.")
    else:
        # Kontroller
        c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
        with c1:
            secili = st.multiselect("Dönemler:", sorted(haf_list, reverse=True),
                                     default=sorted(haf_list, reverse=True)[:6],
                                     key="haf_donem")
        with c2:
            min_yesil = st.number_input("Min. yeşil dönem:", 1, 10, 2, key="haf_yesil")
        with c3:
            min_yab = st.number_input("Min. yab. oran %:", 0, 100, 0, key="haf_yab_min")
        with c4:
            sadece_artan = st.checkbox("Sadece 🚀 momentum", key="haf_artan")

        if not secili:
            st.warning("Dönem seçin.")
        else:
            df = haftalik_ana_tablo(secili)
            if df.empty:
                st.warning("Veri bulunamadı.")
            else:
                df = momentum_hesapla(df, tip="yab")

                # Pozisyon oranları ekle
                pos = pozisyon_getir()
                if not pos.empty:
                    pos_pivot = pos[pos["tip"].isin(["yabanci","fon","emeklilik"])].pivot_table(
                        index="hisse", columns="tip", values="oran", aggfunc="sum"
                    ).reset_index()
                    pos_pivot.columns = ["hisse"] + [f"{c}_oran" for c in pos_pivot.columns[1:]]
                    df = df.merge(pos_pivot, on="hisse", how="left")

                    # Özel fon ekle
                    ozel = ozel_fon_pozisyon(mod="aylik")
                    if not ozel.empty:
                        for kurum in ["tera", "bulls", "pusula"]:
                            k_data = ozel[ozel["kurum"].str.lower() == kurum][["hisse","oran"]]
                            k_data.columns = ["hisse", f"{kurum}_oran"]
                            df = df.merge(k_data, on="hisse", how="left")

                # Filtrele
                df_filtre = df.copy()
                df_filtre = df_filtre[df_filtre["kac_yesil"] >= min_yesil]
                if sadece_artan:
                    df_filtre = df_filtre[df_filtre["surekli_artis"]]

                # KPI
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Toplam Hisse", len(df_filtre))
                k2.metric("🚀 Momentum", (df_filtre["surekli_artis"]==True).sum())
                k3.metric("🟢 Son 3 Hep Yeşil", (df_filtre["son3_yesil"]==True).sum())
                k4.metric("Dönem Sayısı", len(secili))

                st.markdown("---")

                # Kolon düzenle
                yab_cols = sorted([c for c in df_filtre.columns if c.endswith("_yab")])
                mkk_cols = sorted([c for c in df_filtre.columns if c.endswith("_mkk")])
                oran_cols = [c for c in ["yabanci_oran","fon_oran","emeklilik_oran",
                                          "tera_oran","bulls_oran","pusula_oran"]
                             if c in df_filtre.columns]

                # Gösterilecek kolonlar — haftalık mantık:
                # Hisse | W1_yab | W1_mkk | W2_yab | W2_mkk | ... | Trend | Yab% | Fon% | Emk% | TERA% | BULLS%
                goster_cols = ["hisse", "trend", "kac_yesil"]

                # Dönem kolonlarını çift olarak sırala (yab + mkk yan yana)
                donem_listesi = sorted(set(
                    c.replace("_yab","").replace("_mkk","") for c in yab_cols + mkk_cols
                ))
                for d in donem_listesi:
                    if f"{d}_yab" in df_filtre.columns:
                        goster_cols.append(f"{d}_yab")
                    if f"{d}_mkk" in df_filtre.columns:
                        goster_cols.append(f"{d}_mkk")

                goster_cols += oran_cols
                goster_df = df_filtre[[c for c in goster_cols if c in df_filtre.columns]].copy()
                goster_df = goster_df.sort_values("kac_yesil", ascending=False)

                # Kolon isimleri güzelleştir
                yeniden_adlandir = {"hisse":"HİSSE","trend":"TREND","kac_yesil":"YEŞİL"}
                for d in donem_listesi:
                    yeniden_adlandir[f"{d}_yab"] = f"{d}\nYab↕"
                    yeniden_adlandir[f"{d}_mkk"] = f"{d}\nMKK pp"
                for c in oran_cols:
                    yeniden_adlandir[c] = c.replace("_oran","").upper() + "%"

                goster_df = goster_df.rename(columns=yeniden_adlandir)

                # Sayı kolonları
                sayi_cols = [c for c in goster_df.columns if c not in ["HİSSE","TREND","YEŞİL"]]

                st.dataframe(
                    goster_df.style
                        .applymap(renk_net, subset=[c for c in sayi_cols if "Yab" in c or "%" in c])
                        .applymap(renk_pp,  subset=[c for c in sayi_cols if "MKK" in c])
                        .format({c: "{:+,.0f}" for c in sayi_cols if "Yab" in c})
                        .format({c: "{:+.2f}" for c in sayi_cols if "MKK" in c})
                        .format({c: "{:.2f}" for c in sayi_cols if "%" in c}),
                    use_container_width=True, height=550
                )

                # Excel indir
                buf = excel_indir(goster_df, None,
                                  baslik="Haftalık Analiz",
                                  donem="-".join(secili))
                st.download_button("⬇️ Excel İndir", data=buf,
                    file_name=f"haftalik_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ════════════════════════════════════════════════════════════════════════════════
# TAB 2 — AYLIK
# ════════════════════════════════════════════════════════════════════════════════
with tab_ayl:
    st.subheader("Aylık Analiz — MKK + Yabancı + Fon + Emeklilik")

    ayl_list = aylik_donemler()
    if not ayl_list:
        st.info("📂 Veri yok. **Veri Yükle** sekmesinden aylık veri ekleyin.")
    else:
        c1, c2, c3, c4, c5 = st.columns([3, 1, 1, 1, 1])
        with c1:
            secili_ay = st.multiselect("Aylar:", sorted(ayl_list, reverse=True),
                                        default=sorted(ayl_list, reverse=True)[:4],
                                        key="ayl_donem")
        with c2:
            min_yesil_ay = st.number_input("Min. yeşil:", 1, 12, 2, key="ayl_yesil")
        with c3:
            min_mkk = st.number_input("Min. MKK pp:", 0, 50, 0, key="ayl_mkk")
        with c4:
            ozel_filtre = st.selectbox("Özel Fon:", ["Hepsi","TERA","BULLS","PUSULA","Yok"], key="ayl_ozel")
        with c5:
            sadece_artan_ay = st.checkbox("Sadece 🚀", key="ayl_artan")

        if not secili_ay:
            st.warning("Dönem seçin.")
        else:
            df = aylik_ana_tablo(secili_ay)
            if df.empty:
                st.warning("Veri bulunamadı.")
            else:
                df = momentum_hesapla(df, tip="net")

                # MKK momentum ekle
                mkk_cols = [c for c in df.columns if c.endswith("_mkk")]
                if mkk_cols:
                    df = momentum_hesapla(df, tip="mkk")

                # Pozisyon oranları
                son_ay = sorted(secili_ay)[-1]
                pos = pozisyon_getir(son_ay)
                if not pos.empty:
                    pos_pivot = pos.pivot_table(
                        index="hisse", columns="tip", values="oran", aggfunc="sum"
                    ).reset_index()
                    rename_map = {c: f"{c}_oran" for c in pos_pivot.columns if c != "hisse"}
                    pos_pivot = pos_pivot.rename(columns=rename_map)
                    df = df.merge(pos_pivot, on="hisse", how="left")

                # Filtrele
                df_filtre = df.copy()
                df_filtre = df_filtre[df_filtre["kac_yesil"] >= min_yesil_ay]
                if sadece_artan_ay:
                    df_filtre = df_filtre[df_filtre["surekli_artis"]]
                if min_mkk > 0 and mkk_cols:
                    mkk_toplam = df_filtre[mkk_cols].sum(axis=1)
                    df_filtre = df_filtre[mkk_toplam >= min_mkk]
                if ozel_filtre != "Hepsi":
                    ozel_col = f"{ozel_filtre.lower()}_oran"
                    if ozel_filtre == "Yok":
                        for k in ["tera_oran","bulls_oran","pusula_oran"]:
                            if k in df_filtre.columns:
                                df_filtre = df_filtre[df_filtre[k].fillna(0) == 0]
                    elif ozel_col in df_filtre.columns:
                        df_filtre = df_filtre[df_filtre[ozel_col].fillna(0) > 0]

                # KPI
                k1, k2, k3, k4, k5 = st.columns(5)
                k1.metric("Toplam Hisse", len(df_filtre))
                k2.metric("🚀 Momentum", (df_filtre["surekli_artis"]==True).sum())
                k3.metric("🟢 Son 3 Yeşil", (df_filtre["son3_yesil"]==True).sum())
                if "tera_oran" in df_filtre.columns:
                    k4.metric("TERA var", (df_filtre["tera_oran"].fillna(0) > 0).sum())
                if "bulls_oran" in df_filtre.columns:
                    k5.metric("BULLS var", (df_filtre["bulls_oran"].fillna(0) > 0).sum())

                st.markdown("---")

                # Kolon düzeni: Hisse | Trend | Oca_net | Oca_mkk | Şub_net | ... | Yab% | Fon% | Emk% | TERA% | BULLS% | PUSULA%
                donem_listesi = sorted(set(
                    c.replace("_net","").replace("_mkk","")
                    for c in df_filtre.columns if c.endswith(("_net","_mkk"))
                ))
                goster_cols = ["hisse","trend","kac_yesil"]
                for d in donem_listesi:
                    if f"{d}_net" in df_filtre.columns:
                        goster_cols.append(f"{d}_net")
                    if f"{d}_mkk" in df_filtre.columns:
                        goster_cols.append(f"{d}_mkk")

                oran_cols = [c for c in ["yabanci_oran","fon_oran","emeklilik_oran",
                                          "tera_oran","bulls_oran","pusula_oran"]
                             if c in df_filtre.columns]
                goster_cols += oran_cols

                goster_df = df_filtre[[c for c in goster_cols if c in df_filtre.columns]].copy()
                goster_df = goster_df.sort_values("kac_yesil", ascending=False)

                yeniden_adlandir = {"hisse":"HİSSE","trend":"TREND","kac_yesil":"YEŞİL"}
                for d in donem_listesi:
                    yeniden_adlandir[f"{d}_net"] = f"{d}\nNet↕"
                    yeniden_adlandir[f"{d}_mkk"] = f"{d}\nMKK pp"
                for c in oran_cols:
                    yeniden_adlandir[c] = c.replace("_oran","").upper() + "%"

                goster_df = goster_df.rename(columns=yeniden_adlandir)
                sayi_cols = [c for c in goster_df.columns if c not in ["HİSSE","TREND","YEŞİL"]]

                st.dataframe(
                    goster_df.style
                        .applymap(renk_net, subset=[c for c in sayi_cols if "Net" in c or "%" in c])
                        .applymap(renk_pp,  subset=[c for c in sayi_cols if "MKK" in c])
                        .format({c: "{:+,.0f}" for c in sayi_cols if "Net" in c})
                        .format({c: "{:+.2f}" for c in sayi_cols if "MKK" in c})
                        .format({c: "{:.2f}"  for c in sayi_cols if "%" in c}),
                    use_container_width=True, height=550
                )

                buf = excel_indir(goster_df, pos if not pos.empty else None,
                                  baslik="Aylık Analiz", donem="-".join(secili_ay))
                st.download_button("⬇️ Excel İndir", data=buf,
                    file_name=f"aylik_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ════════════════════════════════════════════════════════════════════════════════
# TAB 3 — HİSSE DETAY
# ════════════════════════════════════════════════════════════════════════════════
with tab_hisse:
    st.subheader("🔍 Hisse Bazlı Detay")

    sembol = st.text_input("Hisse kodu:", placeholder="THYAO", key="hisse_input").upper().strip()

    if sembol:
        col_haf, col_ayl = st.columns(2)

        # Haftalık
        with col_haf:
            haf_df = haftalik_ana_tablo()
            if not haf_df.empty and sembol in haf_df["hisse"].values:
                r = haf_df[haf_df["hisse"] == sembol].iloc[0]
                st.markdown(f"#### 📅 {sembol} — Haftalık Yabancı")
                yab_cols = sorted([c for c in r.index if c.endswith("_yab")])
                mkk_cols = sorted([c for c in r.index if c.endswith("_mkk")])

                rows = []
                for ycol in yab_cols:
                    d = ycol.replace("_yab","")
                    mcol = f"{d}_mkk"
                    rows.append({
                        "Dönem": d,
                        "Yab. Fark": int(r[ycol]),
                        "MKK pp": r[mcol] if mcol in r.index else None
                    })
                tablo = pd.DataFrame(rows)
                st.dataframe(
                    tablo.style
                        .applymap(renk_net, subset=["Yab. Fark"])
                        .applymap(renk_pp,  subset=["MKK pp"])
                        .format({"Yab. Fark": "{:+,.0f}", "MKK pp": "{:+.2f}"}),
                    use_container_width=True, hide_index=True
                )
            else:
                st.caption("Haftalık veri yok.")

        # Aylık + Pozisyon
        with col_ayl:
            ayl_df = aylik_ana_tablo()
            if not ayl_df.empty and sembol in ayl_df["hisse"].values:
                r = ayl_df[ayl_df["hisse"] == sembol].iloc[0]
                st.markdown(f"#### 📆 {sembol} — Aylık Net")
                net_cols = sorted([c for c in r.index if c.endswith("_net")])
                mkk_cols = sorted([c for c in r.index if c.endswith("_mkk")])
                rows = []
                for nc in net_cols:
                    d = nc.replace("_net","")
                    mc = f"{d}_mkk"
                    rows.append({
                        "Ay": d,
                        "Net Fark": int(r[nc]),
                        "MKK pp": r[mc] if mc in r.index else None
                    })
                tablo = pd.DataFrame(rows)
                st.dataframe(
                    tablo.style
                        .applymap(renk_net, subset=["Net Fark"])
                        .applymap(renk_pp,  subset=["MKK pp"])
                        .format({"Net Fark": "{:+,.0f}", "MKK pp": "{:+.2f}"}),
                    use_container_width=True, hide_index=True
                )
            else:
                st.caption("Aylık veri yok.")

        # Pozisyon pasta
        pos = pozisyon_getir()
        if not pos.empty:
            h_pos = pos[pos["hisse"] == sembol]
            if not h_pos.empty:
                st.markdown(f"#### 🥧 {sembol} — Pozisyon Dağılımı")
                col_pasta, col_info = st.columns([1,1])

                # Pasta grafik
                labels, values, colors = [], [], []
                renk_map = {
                    "yabanci": "#1A5276", "fon": "#1A7A3E",
                    "emeklilik": "#7D3C00", "tera": "#8E44AD",
                    "bulls": "#C0392B", "pusula": "#E67E22"
                }
                for tip in ["yabanci","fon","emeklilik","tera","bulls","pusula"]:
                    r = h_pos[h_pos["tip"] == tip]
                    if len(r) and r.iloc[0]["oran"] > 0:
                        labels.append(tip.upper())
                        values.append(r.iloc[0]["oran"])
                        colors.append(renk_map.get(tip, "#AAAAAA"))

                top = sum(values)
                labels.append("KALAN")
                values.append(max(0, 100 - top))
                colors.append("#CCCCCC")

                fig = go.Figure(go.Pie(
                    labels=labels, values=values, marker_colors=colors,
                    hole=0.45, textinfo="label+percent",
                ))
                fig.update_layout(
                    height=300, margin=dict(l=10,r=10,t=30,b=10),
                    annotations=[dict(text=f"{top:.1f}%", x=0.5, y=0.5,
                                      font_size=18, showarrow=False)]
                )
                with col_pasta:
                    st.plotly_chart(fig, use_container_width=True)

                with col_info:
                    st.markdown("**Detay:**")
                    for _, r in h_pos.iterrows():
                        if r["oran"] > 0:
                            st.markdown(f"**{r['tip'].upper()}**: `{r['oran']:.2f}%`")
                    st.markdown(f"---\n**Kurum Toplamı**: `{top:.2f}%`")
                    st.markdown(f"**Kalan**: `{max(0,100-top):.2f}%`")

        if sembol not in (haf_df["hisse"].values if not haftalik_ana_tablo().empty else []) and \
           sembol not in (ayl_df["hisse"].values if not aylik_ana_tablo().empty else []):
            st.warning(f"**{sembol}** için veri bulunamadı.")


# ════════════════════════════════════════════════════════════════════════════════
# TAB 4 — VERİ YÜKLE
# ════════════════════════════════════════════════════════════════════════════════
with tab_yukle:
    st.subheader("⚙️ Veri Yükle")

    col_h, col_a = st.columns(2)

    # ── Haftalık ──────────────────────────────────────────────────────────────
    with col_h:
        st.markdown("### 📅 Haftalık Veri")
        st.caption("Pazartesi yükleme — yabancı + MKK (1 gün geriden)")

        with st.form("haf_form"):
            haf_donem = st.text_input("Dönem (YYYY_HH):", placeholder="2025_17")
            haf_yab   = st.file_uploader("🔵 Yabancılar:", type=["xlsx"], key="h_yab")
            haf_mkk   = st.file_uploader("🟣 MKK:", type=["xlsx"], key="h_mkk")
            st.markdown("**Özel Fonlar:**")
            hc1, hc2, hc3 = st.columns(3)
            with hc1: haf_tera   = st.file_uploader("TERA",   type=["xlsx"], key="h_tera")
            with hc2: haf_bulls  = st.file_uploader("BULLS",  type=["xlsx"], key="h_bulls")
            with hc3: haf_pusula = st.file_uploader("PUSULA", type=["xlsx"], key="h_pusula")
            haf_submit = st.form_submit_button("✅ Haftalık Ekle", use_container_width=True)

        if haf_submit:
            if not haf_donem or not haf_yab:
                st.error("Dönem ve Yabancılar dosyası zorunlu!")
            else:
                try:
                    yab_df = takas_oku(haf_yab)
                    mkk_df = mkk_oku(haf_mkk) if haf_mkk else None
                    ozel = {}
                    if haf_tera:   ozel["TERA"]   = takas_oku(haf_tera)
                    if haf_bulls:  ozel["BULLS"]  = takas_oku(haf_bulls)
                    if haf_pusula: ozel["PUSULA"] = takas_oku(haf_pusula)
                    ok, msg = haftalik_ekle(haf_donem.strip(), yab_df, mkk_df, ozel)
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.warning(msg)
                except Exception as e:
                    st.error(f"Hata: {e}")

        # Sil
        haf_list2 = haftalik_donemler()
        if haf_list2:
            st.markdown("**Kayıtlı dönemler:**")
            for d in sorted(haf_list2, reverse=True):
                c1, c2 = st.columns([3,1])
                c1.markdown(f"`{d}`")
                if c2.button("🗑️", key=f"hs_{d}"):
                    haftalik_sil(d)
                    st.rerun()

    # ── Aylık ─────────────────────────────────────────────────────────────────
    with col_a:
        st.markdown("### 📆 Aylık Veri")
        st.caption("Ay sonu — yabancı + fon + emeklilik + MKK + özel fonlar")

        with st.form("ayl_form"):
            ayl_donem = st.text_input("Dönem (YYYY_MM):", placeholder="2025_04")
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
            ayl_submit = st.form_submit_button("✅ Aylık Ekle", use_container_width=True)

        if ayl_submit:
            if not ayl_donem:
                st.error("Dönem zorunlu!")
            elif not any([ayl_yab, ayl_fon, ayl_emk]):
                st.error("En az 1 takas dosyası yükleyin!")
            else:
                try:
                    yab_df  = takas_oku(ayl_yab)  if ayl_yab  else None
                    fon_df  = takas_oku(ayl_fon)  if ayl_fon  else None
                    emk_df  = takas_oku(ayl_emk)  if ayl_emk  else None
                    mkk_df  = mkk_oku(ayl_mkk)    if ayl_mkk  else None
                    ozel = {}
                    if ayl_tera:   ozel["TERA"]   = takas_oku(ayl_tera)
                    if ayl_bulls:  ozel["BULLS"]  = takas_oku(ayl_bulls)
                    if ayl_pusula: ozel["PUSULA"] = takas_oku(ayl_pusula)

                    ok, msg = aylik_ekle(ayl_donem.strip(), yab_df, fon_df, emk_df,
                                         mkk_df, ozel)
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.warning(msg)
                except Exception as e:
                    st.error(f"Hata: {e}")

        # Sil
        ayl_list2 = aylik_donemler()
        if ayl_list2:
            st.markdown("**Kayıtlı dönemler:**")
            for d in sorted(ayl_list2, reverse=True):
                c1, c2 = st.columns([3,1])
                c1.markdown(f"`{d}`")
                if c2.button("🗑️", key=f"as_{d}"):
                    aylik_sil(d)
                    st.rerun()
