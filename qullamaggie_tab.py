"""
qullamaggie_tab.py — Qullamaggie Tight Consolidation
teknik_app.py'a import edilir: from qullamaggie_tab import tab_qullamaggie
"""

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import time
import io
from datetime import datetime
from tarama_depo import sinyal_kaydet

TARAMA_ADI = "Qullamaggie"

# ─── CORE (senin orijinal kodun) ──────────────────────────────────────────────
def qullamaggie_tight_scan(hisse_listesi, flag_bant_esik=0.20,
                            flag_bar_min=10, flag_bar_max=40,
                            min_hacim=750_000, progress_cb=None):
    sonuclar = []
    toplam   = len(hisse_listesi)

    for i, hisse in enumerate(hisse_listesi):
        try:
            df = yf.download(f"{hisse}.IS", period="1y", interval="1d",
                             progress=False, auto_adjust=True)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            close = df["Close"].dropna()
            high  = df["High"].dropna()
            low   = df["Low"].dropna()
            vol   = df["Volume"].dropna()

            if len(close) < 60:
                continue

            son = float(close.iloc[-1])

            # Pole zirvesini bul — son 252 barda en yüksek
            lookback = min(252, len(high))
            pole_idx_rel = int(high.iloc[-lookback:].argmax())
            pole_pos = len(high) - lookback + pole_idx_rel

            # Flag süresi = zirveden bugüne
            flag_bar = len(close) - 1 - pole_pos
            if not (flag_bar_min <= flag_bar <= flag_bar_max):
                continue

            # Flag bölgesi bandı
            flag_h   = float(high.iloc[pole_pos:].max())
            flag_l   = float(low.iloc[pole_pos:].min())
            flag_bant = (flag_h - flag_l) / son
            if flag_bant >= flag_bant_esik:
                continue

            # Pole zirvesi — henüz kırılmamış mı?
            pole_zirve = float(high.iloc[pole_pos])
            if son >= pole_zirve * 0.99:
                continue

            # MA kontrolleri
            ma20 = float(close.rolling(20).mean().iloc[-1])
            if son < ma20 * 0.97:
                continue

            ma50  = float(close.rolling(50).mean().iloc[-1])  if len(close)>=50  else None
            ma150_s = close.rolling(150).mean().dropna()
            if len(ma150_s) > 20:
                ma150     = float(ma150_s.iloc[-1])
                ma150_yuk = ma150 > float(ma150_s.iloc[-21])
                ma150_uzak = (son/ma150-1)*100
            else:
                ma150 = None; ma150_yuk = True; ma150_uzak = None

            # Hacim
            ort_hcm = float(vol.iloc[-20:].mean())
            if ort_hcm < min_hacim:
                continue

            # Momentum
            m1 = (son/float(close.iloc[-22])-1)*100  if len(close)>=22  else None
            m3 = (son/float(close.iloc[-63])-1)*100  if len(close)>=63  else None
            m6 = (son/float(close.iloc[-126])-1)*100 if len(close)>=126 else None

            # Pole getirisi
            pole_bas = float(low.iloc[max(0,pole_pos-20):pole_pos+1].min()) if pole_pos>0 else float(close.iloc[0])
            pole_getiri = (pole_zirve/pole_bas-1)*100 if pole_bas>0 else 0

            sonuclar.append({
                "Hisse"        : hisse,
                "Fiyat"        : round(son, 2),
                "Pole_Zirve"   : round(pole_zirve, 2),
                "Pole_Getiri%" : round(pole_getiri, 1),
                "Flag_Bar"     : flag_bar,
                "Flag_Bant%"   : round(flag_bant*100, 1),
                "MA20_%"       : round((son/ma20-1)*100, 1),
                "MA50_%"       : round((son/ma50-1)*100, 1) if ma50 else "-",
                "MA150_%"      : round(ma150_uzak,1) if ma150_uzak is not None else "-",
                "MA150_Yukarı" : "✅" if ma150_yuk else "❌",
                "Mo_1ay%"      : round(m1,1) if m1 is not None else "-",
                "Mo_3ay%"      : round(m3,1) if m3 is not None else "-",
                "Mo_6ay%"      : round(m6,1) if m6 is not None else "-",
                "Hacim"        : int(ort_hcm),
            })
        except:
            continue

        if progress_cb:
            progress_cb(i+1, toplam, len(sonuclar))
        time.sleep(0.05)

    if not sonuclar:
        return pd.DataFrame()
    return pd.DataFrame(sonuclar).sort_values("Flag_Bant%").reset_index(drop=True)

def tab_qullamaggie(bist_listesi_yukle_fn, veri_cek_fn=None):
    st.markdown("### 🏹 Qullamaggie — Tight Consolidation")
    st.caption(
        "100 bar dar bant · Son 20 bar <%%15 · MA20 üzeri · "
        "MA150'den max %%4 aşağı · MA150 yukarı eğimli · "
        "40+ bardır banda değmemiş"
    )

    with st.expander("⚙️ Ayarlar", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            flag_bant_esik = st.slider("Flag Bant Eşiği %", 10, 35, 20) / 100
        with c2:
            flag_bar_min = st.slider("Flag Min Bar", 5, 20, 10)
            flag_bar_max = st.slider("Flag Max Bar", 20, 60, 40)
        with c3:
            min_hcm = st.number_input("Min Günlük Hacim", value=750_000, step=100_000)

    col_btn, col_info = st.columns([2, 5])
    with col_btn:
        tara = st.button("🔍 Tara", type="primary", use_container_width=True)
    with col_info:
        st.info("⏱️ ~3-4 dakika")

    if not tara:
        if "quall_df" in st.session_state and not st.session_state.quall_df.empty:
            _goster(st.session_state.quall_df, st.session_state.get("quall_tarih",""), min_hcm)
        return

    hisseler = bist_listesi_yukle_fn()
    if not hisseler:
        st.error("❌ bist_fd.xlsx bulunamadı!")
        return

    prog = st.progress(0, text="Başlıyor...")

    def progress_cb(i, toplam, bulunan):
        prog.progress(i/toplam, text=f"{i}/{toplam} — ✅{bulunan} geçti")

    df = qullamaggie_tight_scan(
        hisseler,
        flag_bant_esik=flag_bant_esik,
        flag_bar_min=flag_bar_min,
        flag_bar_max=flag_bar_max,
        min_hacim=min_hcm,
        progress_cb=progress_cb
    )
    if not df.empty:
        df = df.reset_index(drop=True)

    prog.empty()
    tarih = datetime.now().strftime("%d.%m.%Y %H:%M")
    st.session_state.quall_df    = df
    st.session_state.quall_tarih = tarih
    _goster(df, tarih, min_hcm)


def _goster(df, tarih, min_hcm=0):
    if df is None or df.empty:
        st.warning("⚠️ Kriterleri sağlayan hisse bulunamadı. Eşikleri gevşet.")
        return

    st.success(f"✅ **{len(df)} hisse** bulundu  |  🕐 {tarih}")

    c1, c2, c3 = st.columns(3)
    c1.metric("Toplam",          len(df))
    c2.metric("Flag Bant <10%",  len(df[df["Flag_Bant%"] < 10]))
    c3.metric("MA150 ✅",        len(df[df["MA150_Yukarı"] == "✅"]))

    def _rb(val):
        try:
            v = float(val)
            if v < 10: return "background-color:#1a472a;color:white"
            if v < 14: return "background-color:#2d6a4f;color:white"
            if v < 18: return "background-color:#52b788"
        except: pass
        return ""

    st.dataframe(
        df.style.map(_rb, subset=["Flag_Bant%"]),
        use_container_width=True, height=520
    )

    st.divider()
    col_kyd, col_xl = st.columns(2)

    with col_kyd:
        if st.button("💾 Performans Takip'e Kaydet", type="secondary"):
            liste = [{"hisse": r["Hisse"], "giris_fiyat": r["Fiyat"]}
                     for r in df.to_dict("records")]
            n = sinyal_kaydet(TARAMA_ADI, liste)
            st.success(f"✅ {n} sinyal kaydedildi.")

    with col_xl:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            df.to_excel(w, index=False)
        buf.seek(0)
        st.download_button(
            "📥 Excel İndir",
            data=buf.read(),
            file_name=f"qullamaggie_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
