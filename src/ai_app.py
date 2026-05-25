"""
ai_app.py — BIST AI Takas Dedektifi
Port: 8503

Kullanım:
  cd Desktop/bist-takip/bist_app
  python -m streamlit run src/ai_app.py --server.port 8503
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta
from pathlib import Path

# Local imports
import sys
sys.path.insert(0, str(Path(__file__).parent))

from takas_depo import _oku as takas_oku
from senaryo_tespit import senaryo_tara, AKILLI_PARA, DAGITICI, BUYUK_YERLI, FON, YABANCI
from takas_hafiza import (
    hafiza_oku, hafiza_ozet, hafiza_toplu_guncelle,
    tum_hafiza_listele, hafiza_istatistik, hafiza_gecmis_kontrol
)
from ai_yorum import hisse_yorumla, hisse_sorgula, tarama_yorumla, _kural_tabanli_yorum

def _donem_tarih_cevir2(d: str):
    """Dönem adını date'e çevir."""
    import re
    from datetime import date, timedelta
    d = str(d).strip()
    if re.match(r'^\d{8}$', d):
        try: return date(int(d[:4]), int(d[4:6]), int(d[6:8]))
        except: return None
    m = re.match(r'^(\d{4})(\d{2})_(\d{2})$', d)
    if m:
        yil,ay,hafta = int(m.group(1)),int(m.group(2)),int(m.group(3))
        try:
            ilk = date(yil,ay,1)
            ilk_pzt = ilk + timedelta(days=(7-ilk.weekday())%7)
            return ilk_pzt + timedelta(weeks=hafta-1)
        except: return None
    m = re.match(r'^(\d{4})_(\d{2})', d)
    if m:
        try: return date(int(m.group(1)), int(m.group(2)), 1)
        except: return None
    return None

# ── Sayfa yapılandırması ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="🤖 AI Takas Dedektifi",
    page_icon="🔍",
    layout="wide"
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.sinyal-kart {
    border-left: 4px solid #C0392B;
    padding: 8px 12px;
    margin: 4px 0;
    background: #FAFAFA;
    border-radius: 0 4px 4px 0;
}
.birikim-kart { border-left-color: #1A7A3E; }
.maldevri-kart { border-left-color: #1A5276; }
.dagitim-kart { border-left-color: #C0392B; }
.uyari-kart { border-left-color: #F39C12; }
</style>
""", unsafe_allow_html=True)

st.title("🤖 AI Takas Dedektifi")
st.caption("BIST Kurumsal Takas + Wyckoff + Hafıza Analizi")

# ── Veriyi yükle ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def _veri_yukle():
    return takas_oku()

df_tum = _veri_yukle()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📊 Veri Durumu")
    if df_tum.empty:
        st.error("Veri yok. Takas Dashboard'dan veri yükleyin.")
    else:
        donemler_tum = sorted(df_tum["donem"].astype(str).unique().tolist())
        st.success(f"✅ {len(df_tum):,} satır | {len(donemler_tum)} dönem")
        # Son dönemi tarih bazlı bul
        tarih_donem = []
        for d in donemler_tum:
            t = _donem_tarih_cevir2(d)
            if t:
                tarih_donem.append((t, d))
        son_donem_goster = max(tarih_donem, key=lambda x: x[0])[1] if tarih_donem else donemler_tum[-1]
        st.caption(f"Son dönem: **{son_donem_goster}**")

    st.divider()
    st.markdown("### ⚙️ Tarama Ayarları")
    min_guven  = st.slider("Min Güven Skoru", 4.0, 10.0, 6.0, 0.5, key="min_guven")
    min_net    = st.number_input("Min Net Alış (%)", value=3.0, step=0.5, key="min_net")
    max_sonuc  = st.number_input("Max Sonuç", value=20, step=5, key="max_sonuc")

    st.divider()
    if st.button("🔄 Önbelleği Temizle"):
        st.cache_data.clear()
        st.rerun()

# ── Ana Sekmeler ──────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "💬 Hızlı Sorgu",
    "🔍 Dönem Tarama",
    "🚨 Kritik Sinyaller",
    "📜 Hafıza Bankası",
])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — HIZLI SORGU
# ═══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown("### 💬 Hisse / Kurum Sorgula")
    st.caption("`OZATD` · `RUBNS detay` · `RUBNS 30` · `TERA` · `TERA OZATD`")

    col1, col2 = st.columns([4, 1])
    with col1:
        sorgu = st.text_input(
            "Sorgu:", placeholder="OZATD veya TERA RUBNS...",
            label_visibility="collapsed", key="ai_sorgu"
        )
    with col2:
        analiz_btn = st.button("🔍 Analiz Et", type="primary", use_container_width=True)

    if analiz_btn and sorgu.strip():
        with st.spinner("Analiz ediliyor..."):
            cevap = hisse_sorgula(sorgu.strip().upper())
        st.markdown(f"**{sorgu.upper()}**")
        st.info(cevap)

        # Hafıza geçmişi göster
        parcalar = sorgu.strip().upper().split()
        if len(parcalar) >= 1:
            hisse_kod = parcalar[-1]
            hafiza = hafiza_oku(hisse_kod)
            if hafiza["tarihsel_senaryolar"]:
                with st.expander(f"📜 {hisse_kod} Geçmişi ({hafiza['istatistikler']['toplam_kayit']} kayıt)"):
                    df_gecmis = pd.DataFrame(hafiza["tarihsel_senaryolar"])
                    cols_goster = ["donem","senaryo","wyckoff_faz","guc_skoru","ana_kurum","net_alis","net_satis"]
                    cols_var    = [c for c in cols_goster if c in df_gecmis.columns]
                    st.dataframe(df_gecmis[cols_var], use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — DÖNEM TARAMA
# ═══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown("### 🔍 Dönem Seç ve Tara")

    if df_tum.empty:
        st.warning("Veri yok.")
    else:
        # Tarih aralığı
        from ai_yorum import WYCKOFF_ACIKLAMA
        # _donem_tarih_cevir2 modül seviyesinde tanımlı

        # Tüm dönemlerin tarihlerini bul
        tum_tarihler = []
        for d in donemler_tum:
            t = _donem_tarih_cevir2(d)
            if t: tum_tarihler.append(t)

        min_t = min(tum_tarihler) if tum_tarihler else date.today() - timedelta(days=90)
        max_t = max(tum_tarihler) if tum_tarihler else date.today()

        c1, c2, c3 = st.columns([1.5, 1.5, 1])
        with c1:
            bas = st.date_input("Başlangıç:", value=max_t - timedelta(days=14),
                                min_value=min_t, max_value=max_t,
                                key="ai_bas", format="DD.MM.YYYY")
        with c2:
            bit = st.date_input("Bitiş:", value=max_t,
                                min_value=min_t, max_value=max_t,
                                key="ai_bit", format="DD.MM.YYYY")
        with c3:
            st.markdown("<br>", unsafe_allow_html=True)
            tara_btn = st.button("🚀 Tara", type="primary", use_container_width=True)

        # Seçilen dönemler
        secili = [d for d in donemler_tum
                  if (t := _donem_tarih_cevir2(d)) and t and bas <= t <= bit]

        st.caption(f"**{len(secili)}** dönem seçildi: {', '.join(secili[:5])}{'...' if len(secili)>5 else ''}")

        if tara_btn and secili:
            with st.spinner(f"🔍 {len(secili)} dönem taranıyor — 3 katmanlı analiz..."):
                sonuc_df = senaryo_tara(df_tum, secili, min_net_alis=min_net)

            if sonuc_df.empty:
                st.info("Kritik sinyal bulunamadı.")
            else:
                # Güven filtreesi
                goster = sonuc_df[sonuc_df["guven_skoru"] >= min_guven].head(int(max_sonuc))
                st.success(f"✅ **{len(sonuc_df)}** hisse analiz edildi | **{len(goster)}** kritik sinyal")

                # Otomatik hafızaya kaydet (yorum olmadan)
                hafiza_toplu_guncelle(goster, secili[-1], {})
                st.session_state["son_tarama"] = goster
                st.session_state["son_donem"]  = secili[-1]

                # Senaryo ikonları
                senaryo_renk = {
                    "🟢 Birikim":          "#1A7A3E",
                    "🎯 Toplama":          "#1A5276",
                    "🔄 Mal Devri":        "#2874A6",
                    "🔴 Dağıtım":          "#C0392B",
                    "📤 Toplu Dağıtım":    "#E74C3C",
                    "⚠️ Takas FD Değişti": "#F39C12",
                    "🔁 Re-Accumulation":  "#117A65",
                }

                # AI yorum butonu
                if st.button("🤖 Kritik Sinyalleri Yorumla (AI)", key="ai_yorum_btn"):
                    with st.spinner("AI yorumları üretiliyor..."):
                        yorumlar = tarama_yorumla(goster)
                        hafiza_toplu_guncelle(goster, secili[-1], yorumlar)
                        st.session_state["son_yorumlar"] = yorumlar
                    st.success("Yorumlar hafızaya kaydedildi!")

                yorumlar = st.session_state.get("son_yorumlar", {})

                # Sonuçları kart olarak göster
                cols = st.columns(3)
                for i, (_, row) in enumerate(goster.iterrows()):
                    hisse   = row["hisse"]
                    senaryo = row.get("senaryo", "")
                    wyckoff = row.get("wyckoff_faz", "")
                    guven   = row.get("guven_skoru", 0)
                    renk    = senaryo_renk.get(senaryo, "#888")
                    yorum   = yorumlar.get(hisse, "")

                    with cols[i % 3]:
                        with st.expander(
                            f"{hisse}  ·  {senaryo}  ·  {guven:.1f}/10",
                            expanded=False
                        ):
                            st.markdown(
                                f"<div style='font-size:12px;'>"
                                f"<b>Wyckoff:</b> {wyckoff}<br>"
                                f"<b>Net Alış:</b> +{row.get('net_alis',0):.1f}% &nbsp;"
                                f"<b>Net Satış:</b> -{row.get('net_satis',0):.1f}%<br>"
                                f"<b>FD:</b> {'⚠️ Şüpheli' if row.get('fd_supheli') else '✓ Sabit'} &nbsp;"
                                f"<b>MKK:</b> {row.get('mkk_trend','—')}<br>"
                                f"<b>Alan:</b> {row.get('en_guclu_alan','—')}<br>"
                                f"<b>Satan:</b> {row.get('en_guclu_satan','—')}"
                                f"</div>",
                                unsafe_allow_html=True
                            )
                            if yorum:
                                st.info(yorum)
                            else:
                                kural_yorum = _kural_tabanli_yorum(hisse, row.to_dict())
                                st.caption(kural_yorum)

                # Tablo görünümü
                with st.expander("📋 Tablo Görünümü"):
                    cols_goster = ["hisse","senaryo","wyckoff_faz","guven_skoru",
                                   "net_alis","net_satis","en_guclu_alan","en_guclu_satan"]
                    cols_var    = [c for c in cols_goster if c in goster.columns]
                    st.dataframe(goster[cols_var], use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — KRİTİK SİNYALLER
# ═══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown("### 🚨 Kritik Sinyaller")
    st.caption("Hafızadan güven skoru 7+ olan aktif sinyaller")

    hisseler = tum_hafiza_listele()
    if not hisseler:
        st.info("Henüz hafızada sinyal yok. Önce Dönem Tarama yapın.")
    else:
        kritik = []
        for h in hisseler:
            veri = hafiza_oku(h)
            md   = veri.get("mevcut_durum", {})
            if md.get("guven_skoru", 0) >= 7.0:
                kritik.append({
                    "hisse":       h,
                    "senaryo":     md.get("son_senaryo", ""),
                    "wyckoff":     md.get("wyckoff_faz", ""),
                    "guven":       md.get("guven_skoru", 0),
                    "ana_kurum":   md.get("en_guclu_kurum", ""),
                    "birikim_don": md.get("toplam_birikim_donemi", 0),
                    "ai_yorumu":   md.get("ai_yorumu", ""),
                    "son_guncelleme": veri.get("son_guncelleme", ""),
                })

        kritik = sorted(kritik, key=lambda x: -x["guven"])

        st.caption(f"**{len(kritik)}** kritik sinyal")

        senaryo_renk = {
            "🟢 Birikim":   "#1A7A3E",
            "🎯 Toplama":   "#1A5276",
            "🔄 Mal Devri": "#2874A6",
            "🔴 Dağıtım":  "#C0392B",
        }

        cols = st.columns(3)
        for i, s in enumerate(kritik[:30]):
            renk = senaryo_renk.get(s["senaryo"], "#888")
            with cols[i % 3]:
                with st.expander(
                    f"{s['hisse']}  ·  {s['senaryo']}  ·  {s['guven']:.1f}/10",
                    expanded=False
                ):
                    st.markdown(
                        f"<div style='font-size:12px;'>"
                        f"<b>Wyckoff:</b> {s['wyckoff']}<br>"
                        f"<b>Ana Kurum:</b> {s['ana_kurum']}<br>"
                        f"<b>Ardışık Birikim:</b> {s['birikim_don']} dönem<br>"
                        f"<b>Son Güncelleme:</b> {s['son_guncelleme']}"
                        f"</div>",
                        unsafe_allow_html=True
                    )
                    if s["ai_yorumu"]:
                        st.info(s["ai_yorumu"])


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — HAFIZA BANKASI
# ═══════════════════════════════════════════════════════════════════════════════
with tab4:
    st.markdown("### 📜 Hafıza Bankası")

    hisseler = tum_hafiza_listele()

    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        secili_h = st.selectbox(
            "Hisse:", options=sorted(hisseler) if hisseler else ["—"],
            key="hafiza_hisse"
        )
    with c2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("📊 Genel İstatistik", key="gen_ist"):
            ist = hafiza_istatistik()
            st.write(ist)
    with c3:
        st.markdown("<br>", unsafe_allow_html=True)
        kurum_sorgu = st.text_input("Kurum filtre:", placeholder="TERA", key="kurum_filtre")

    if secili_h and secili_h != "—":
        # Özet
        ozet_str = hafiza_ozet(secili_h)
        st.info(ozet_str)

        hafiza_veri = hafiza_oku(secili_h)

        # Kronoloji tablosu
        if hafiza_veri["tarihsel_senaryolar"]:
            df_gecmis = pd.DataFrame(hafiza_veri["tarihsel_senaryolar"])
            cols_goster = ["donem","senaryo","wyckoff_faz","guc_skoru",
                           "ana_kurum","net_alis","net_satis","fd_pct","mkk_trend","aciklama"]
            cols_var = [c for c in cols_goster if c in df_gecmis.columns]
            st.dataframe(df_gecmis[cols_var], use_container_width=True, hide_index=True)

        # Kurum bazlı geçmiş
        if kurum_sorgu:
            gecmis = hafiza_gecmis_kontrol(secili_h, kurum_sorgu.upper())
            if gecmis["kayit_sayisi"] > 0:
                st.markdown(f"**{kurum_sorgu.upper()}** bu hissede "
                            f"**{gecmis['kayit_sayisi']}** kez kayıtlı "
                            f"(ilk: {gecmis['ilk_gorulme']}, son: {gecmis['son_gorulme']})")
                st.dataframe(pd.DataFrame(gecmis["senaryolar"]),
                             use_container_width=True, hide_index=True)
            else:
                st.caption(f"{kurum_sorgu.upper()} bu hissede kayıt yok.")

# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.caption("🤖 AI Takas Dedektifi  •  Port 8503  •  Wyckoff + Takas + Hafıza")
