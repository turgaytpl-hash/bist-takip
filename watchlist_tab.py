"""
watchlist_tab.py — Trader Not Defteri & Alarm Sistemi
"""

import streamlit as st
import pandas as pd
from datetime import date
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from watchlist_depo import (alarm_ekle, alarm_sil, alarm_guncelle,
                             alarm_tetiklendi_kaydet, liste_al,
                             alarm_sayisi, TEKNİK_ALARMLAR)

# ─── Alarm kontrol ───────────────────────────────────────────────────────────
def alarm_kontrol_tek(kayit: dict, r: dict, rw: dict = None) -> list:
    """Tek alarm satırı için koşulları kontrol et"""
    tetiklenenler = []
    fiyat  = r.get("fiyat", 0)
    seviye = kayit.get("seviye", 0)
    yon    = kayit.get("yon", "yukari")

    # Fiyat seviyesi kontrolü
    if seviye > 0:
        if yon == "yukari" and fiyat >= seviye:
            tetiklenenler.append(f"💰 Direnç Kırıldı: {fiyat:.2f} ≥ {seviye:.2f}")
        elif yon == "asagi" and fiyat <= seviye:
            tetiklenenler.append(f"💰 Destek Kırıldı: {fiyat:.2f} ≤ {seviye:.2f}")

    # Teknik alarmlar
    teknik = kayit.get("teknik_alarmlar", [])

    if "200MA Kırılımı" in teknik and r.get("sma200_kirildi"):
        tetiklenenler.append(f"📈 200MA Kırıldı! ({r.get('sma200',0):.2f} TL)")

    if "RS 200MA Kırılımı" in teknik and r.get("rs_200_kirildi"):
        tl = r.get("rs_sma200_tl", 0) or 0
        tetiklenenler.append(f"🔥 RS 200MA Kırıldı! (TL: {tl:.2f})")

    if "RS 200MA Yaklaşıyor (%5)" in teknik:
        uzak = r.get("rs_sma200_uzak")
        if uzak is not None and -5 <= uzak <= 0:
            tetiklenenler.append(f"🟡 RS 200MA'ya %{abs(uzak):.1f} kaldı!")

    if "20 Reverse" in teknik:
        try:
            from teknik_app import tara_20_reverse
            if tara_20_reverse(r):
                tetiklenenler.append("🔄 20 Reverse Sinyali!")
        except: pass

    if "150 Reverse" in teknik:
        try:
            from teknik_app import tara_150_reverse
            if tara_150_reverse(r):
                tetiklenenler.append("📊 150 Reverse Sinyali!")
        except: pass

    if "Altın Tavuk" in teknik:
        try:
            from teknik_app import tara_altin_tavuk
            if tara_altin_tavuk(r):
                tetiklenenler.append("🐔 Altın Tavuk Sinyali!")
        except: pass

    if "MACD Erken" in teknik:
        try:
            from teknik_app import tara_macd_erken
            if tara_macd_erken(r):
                tetiklenenler.append("📡 MACD Erken Uyarı!")
        except: pass

    if "Haftalık Dinlen" in teknik and rw:
        try:
            from teknik_app import tara_haftalik_dinlen
            if tara_haftalik_dinlen(rw):
                tetiklenenler.append("📊 Haftalık Dinlenme!")
        except: pass

    return tetiklenenler


def watchlist_sekme(veri_cek_fn, teknik_hesapla_fn,
                    teknik_haftalik_fn, bist100_cek_fn):

    st.subheader("🔔 Trader Not Defteri & Alarm Sistemi")

    liste = liste_al()

    # ── Bugün tetiklenen alarmlar banner ─────────────────────────────────────
    bugun_tetik = [a for a in liste
                   if (a.get("tetikleme_tarihi") or "").startswith(str(date.today()))
                   and a.get("durum") == "tetiklendi"]
    if bugun_tetik:
        for a in bugun_tetik:
            st.error(f"🚨 **{a['hisse']}** — {a['not'] or 'Alarm'} — "
                     f"Fiyat: {a.get('tetikleme_fiyat','?')} TL — {a['tetikleme_tarihi']}")

    # ── Ana layout ────────────────────────────────────────────────────────────
    col_liste, col_form = st.columns([3, 2])

    # ══ SAĞ: FORM ════════════════════════════════════════════════════════════
    with col_form:
        st.markdown("**➕ Yeni Alarm Ekle**")

        yeni_hisse  = st.text_input("Hisse Kodu", placeholder="DYOBY").upper().strip()
        
        col_sev, col_yon = st.columns(2)
        with col_sev:
            seviye = st.number_input("Seviye (TL)", min_value=0.0,
                                      value=0.0, step=0.01)
        with col_yon:
            yon = st.selectbox("Yön", 
                               ["yukari", "asagi"],
                               format_func=lambda x: "↑ Direnç Kırılımı" if x == "yukari" 
                                                     else "↓ Destek Retesti")

        sec_teknik = st.multiselect("Teknik Alarmlar", TEKNİK_ALARMLAR,
                                     key="wl_teknik")
        not_gir    = st.text_area("Not / Senaryo", 
                                   placeholder="RS 200MA = 17.50, Yatay direnç 17.90...",
                                   height=80)

        if st.button("💾 Alarm Ekle", use_container_width=True, type="primary"):
            if yeni_hisse:
                alarm_id = alarm_ekle(
                    hisse=yeni_hisse,
                    seviye=seviye if seviye > 0 else 0,
                    yon=yon,
                    teknik_alarmlar=sec_teknik,
                    not_=not_gir
                )
                st.success(f"✅ {yeni_hisse} alarmı eklendi! (ID: {alarm_id})")
                st.rerun()

        st.divider()

        # Mevcut alarmı sil/güncelle
        if liste:
            st.markdown("**🗑️ Alarm Sil**")
            alarm_secenekler = {
                f"{a['hisse']} — {a.get('not','')[:30] or a['id']}": a["id"]
                for a in liste
            }
            sec_sil = st.selectbox("Alarm seç", list(alarm_secenekler.keys()),
                                    key="wl_sil_sec")
            if st.button("🗑️ Sil", use_container_width=True):
                alarm_id_sil = alarm_secenekler[sec_sil]
                if alarm_sil(alarm_id_sil):
                    st.success("Silindi!")
                    st.rerun()

        st.divider()
        st.markdown("**⚡ Alarm Kontrol**")
        period_w    = st.selectbox("Periyot", ["1y","2y"], index=0, key="wl_period")
        kontrol_btn = st.button("🔄 Tümünü Kontrol Et",
                                 use_container_width=True, type="primary")

    # ══ SOL: LİSTE ═══════════════════════════════════════════════════════════
    with col_liste:
        if not liste:
            st.info("Takip listesi boş. Sağdan alarm ekle!")
        else:
            # Tablo
            rows = []
            for a in liste:
                durum_ikon = {
                    "bekliyor":   "⏳",
                    "tetiklendi": "🚨",
                    "gecti":      "✅"
                }.get(a.get("durum","bekliyor"), "⏳")

                rows.append({
                    "Durum":    durum_ikon,
                    "Hisse":    a["hisse"],
                    "Seviye":   a.get("seviye", "—"),
                    "Yön":      "↑ Direnç" if a.get("yon") == "yukari" else "↓ Destek",
                    "Teknik":   ", ".join(a.get("teknik_alarmlar", [])) or "—",
                    "Not":      a.get("not", "")[:50],
                    "Eklenme":  a.get("eklenme_tarihi",""),
                    "T.Tarihi": a.get("tetikleme_tarihi","—") or "—",
                    "T.Fiyat":  a.get("tetikleme_fiyat","—") or "—",
                })

            df_liste = pd.DataFrame(rows)
            st.dataframe(df_liste, use_container_width=True,
                         height=min(400, 60 + len(rows)*40),
                         hide_index=True,
                         column_config={
                             "Seviye": st.column_config.NumberColumn(format="%.2f"),
                         })

            # Kontrol sonuçları
            if kontrol_btn:
                bist100 = bist100_cek_fn(period_w)
                
                # Benzersiz hisseler
                hisseler = list({a["hisse"] for a in liste})
                prog = st.progress(0)
                veriler = {}
                for i, h in enumerate(hisseler):
                    prog.progress((i+1)/len(hisseler), text=f"⏳ {h}")
                    df   = veri_cek_fn(h, period_w)
                    if df.empty: continue
                    r    = teknik_hesapla_fn(df, bist100)
                    if not r: continue
                    df_w = veri_cek_fn(h, period_w, "1wk")
                    rw   = teknik_haftalik_fn(df_w) if not df_w.empty else {}
                    veriler[h] = (r, rw)
                prog.empty()

                # Her alarm için kontrol
                tetiklenen_var = False
                st.divider()
                st.markdown("**📊 Kontrol Sonuçları:**")

                for a in liste:
                    h = a["hisse"]
                    if h not in veriler: continue
                    r, rw = veriler[h]
                    
                    tetiklenenler = alarm_kontrol_tek(a, r, rw)
                    fiyat = r.get("fiyat", 0)
                    uzak200 = r.get("uzak200", 0) or 0
                    rs_durum = ""
                    if r.get("rs_200_kirildi"):
                        rs_durum = "🔥 RS YENİ KIRILIM"
                    elif r.get("rs_200_ustunde"):
                        rs_durum = f"🟢 RS Üstünde"
                    else:
                        uzak_rs = r.get("rs_sma200_uzak", 0) or 0
                        if -5 <= uzak_rs <= 0:
                            rs_durum = f"🟡 RS %{abs(uzak_rs):.1f} kaldı"
                        else:
                            rs_durum = f"🔴 RS %{uzak_rs:.1f}"

                    not_kisa = a.get("not","")[:40]
                    yon_ikon = "↑" if a.get("yon") == "yukari" else "↓"

                    if tetiklenenler:
                        tetiklenen_var = True
                        alarm_tetiklendi_kaydet(a["id"], fiyat)
                        st.error(f"""
**🚨 {h}** {yon_ikon} {a.get('seviye',0):.2f} TL | Fiyat: **{fiyat:.2f}**
{chr(10).join(tetiklenenler)}
_{not_kisa}_
""")
                    else:
                        # Normal durum göster
                        col1, col2, col3, col4 = st.columns([1,1,1,2])
                        col1.metric(h, f"{fiyat:.2f} TL")
                        col2.metric("200SMA", f"{uzak200:+.1f}%")
                        col3.metric("RS", rs_durum)
                        col4.write(f"_{not_kisa}_")

                if not tetiklenen_var:
                    st.success("✅ Tetiklenen alarm yok — piyasa bekleniyor")
