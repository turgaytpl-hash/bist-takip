"""
breadth_tab.py — BIST Piyasa Genişliği (Market Breadth) Paneli
Investing.com tarzı Advance-Decline Oscillatör + MA Oranları + Sinyal Motoru
"""

import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ── Dosya yolu ────────────────────────────────────────────────────────────────
EXCEL_PATH = Path(__file__).parent.parent / "bist_dashboard_final.xlsx"
TOPLAM_HISSE = 610

# ── Veri yükleme ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def _veri_yukle() -> pd.DataFrame:
    try:
        df = pd.read_excel(EXCEL_PATH, sheet_name="DATA")
        df.columns = df.columns.str.strip()
        df["Tarih"] = pd.to_datetime(df["Tarih"])
        df = df.sort_values("Tarih").reset_index(drop=True)
        df = df.dropna(subset=["BIST Kapanış", "Advance-Decline Farkı"])

        # MA oranları (%)
        for ma in ["20MA Üstü", "50MA Üstü", "200MA Üstü"]:
            if ma in df.columns:
                df[f"{ma}%"] = df[ma] / TOPLAM_HISSE * 100

        # Kümülatif AD Line
        df["AD_Kumul"] = df["Advance-Decline Farkı"].cumsum()

        # Haftalık ortalama (5 günlük rolling)
        df["20MA_Haftalik"] = df["20MA Üstü%"].rolling(5).mean()
        df["50MA_Haftalik"] = df["50MA Üstü%"].rolling(5).mean()
        df["200MA_Haftalik"] = df["200MA Üstü%"].rolling(5).mean()

        return df
    except FileNotFoundError:
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Veri yükleme hatası: {e}")
        return pd.DataFrame()


# ── Sinyal motoru ─────────────────────────────────────────────────────────────

def _sinyal_hesapla(df: pd.DataFrame) -> dict:
    if len(df) < 5:
        return {}

    son   = df.iloc[-1]
    once3 = df.iloc[-4:-1]  # son 3 gün (bugün hariç)
    once5 = df.iloc[-6:-1]  # son 5 gün

    ma20  = son.get("20MA Üstü%", None)
    ma50  = son.get("50MA Üstü%", None)
    ma200 = son.get("200MA Üstü%", None)
    bist  = son.get("BIST Kapanış", None)

    sinyaller = []

    # ── 🟢 Ralli sinyali ────────────────────────────────────────────────────
    ralli_kosullar = []
    if ma50 and ma50 > 65:
        ralli_kosullar.append("✅ 50MA% > %65")
    else:
        ralli_kosullar.append(f"❌ 50MA% < %65 (şu an %{ma50:.1f})" if ma50 else "❌ 50MA% verisi yok")

    if ma20 and len(once3) >= 2:
        ma20_trend = df["20MA Üstü%"].iloc[-3:].diff().mean()
        if ma20_trend > 0:
            ralli_kosullar.append("✅ 20MA% yukarı trend")
        else:
            ralli_kosullar.append("❌ 20MA% aşağı trend")
    
    if ma200 and ma200 > 55:
        ralli_kosullar.append("✅ 200MA% > %55 (uzun vade onayı)")
    else:
        ralli_kosullar.append(f"❌ 200MA% < %55 (şu an %{ma200:.1f})" if ma200 else "❌ 200MA% verisi yok")

    ad_son3 = df["Advance-Decline Farkı"].iloc[-3:].mean()
    if ad_son3 > 0:
        ralli_kosullar.append(f"✅ Son 3 gün breadth pozitif (ort: {ad_son3:+.0f})")
    else:
        ralli_kosullar.append(f"❌ Son 3 gün breadth negatif (ort: {ad_son3:+.0f})")

    ralli_sayi = sum(1 for k in ralli_kosullar if k.startswith("✅"))

    # ── 🔴 Dikkat sinyali ────────────────────────────────────────────────────
    dikkat_kosullar = []

    if ma20 and len(df) >= 3:
        ma20_2gun = df["20MA Üstü%"].iloc[-1] - df["20MA Üstü%"].iloc[-3]
        if ma20_2gun < -3:
            dikkat_kosullar.append(f"⚠️ 20MA% 2 günde {ma20_2gun:.1f}pp düştü (hızlı düşüş)")

    if ma50 and ma50 < 70 and bist:
        bist_1gun = df["BIST Kapanış"].iloc[-1] - df["BIST Kapanış"].iloc[-2] if len(df) >= 2 else 0
        if bist_1gun < 0:
            dikkat_kosullar.append(f"⚠️ 50MA% < %70 ({ma50:.1f}%) + BIST aşağı → Düzeltme riski")

    # ── ⚠️ Divergence tespiti ─────────────────────────────────────────────────
    divergence = False
    div_mesaj = ""
    if len(df) >= 10:
        bist_10 = df["BIST Kapanış"].iloc[-10:]
        ma50_10 = df["50MA Üstü%"].iloc[-10:]
        bist_zirve = bist_10.max() == bist_10.iloc[-1]   # bugün yeni zirve mi?
        ma50_zirve = ma50_10.max() == ma50_10.iloc[-1]   # 50MA% de yeni zirve mi?
        if bist_zirve and not ma50_zirve:
            divergence = True
            div_mesaj = f"🔴 BIST yeni zirve ({bist:.0f}) ama 50MA% yeni zirve değil ({ma50:.1f}%) — SATIŞ BASKISI OLABİLİR"

    # ── 📐 1000 Puan Kuralı ──────────────────────────────────────────────────
    kural_mesaj = ""
    if len(df) >= 2:
        bist_deg   = df["BIST Kapanış"].iloc[-1] - df["BIST Kapanış"].iloc[-2]
        ma50_deg   = df["50MA Üstü"].iloc[-1] - df["50MA Üstü"].iloc[-2] if "50MA Üstü" in df.columns else 0
        beklenen   = bist_deg / 1000 * 110  # 110 hisse / 1000 puan
        if abs(bist_deg) > 100:
            if bist_deg < 0:
                if abs(ma50_deg) < abs(beklenen):
                    kural_mesaj = f"📐 BIST {bist_deg:+.0f} puan | 50MA beklenen: {beklenen:+.0f} hisse | Gerçek: {ma50_deg:+.0f} → Düşüş sınırlı kalabilir"
                else:
                    kural_mesaj = f"📐 BIST {bist_deg:+.0f} puan | 50MA beklenen: {beklenen:+.0f} hisse | Gerçek: {ma50_deg:+.0f} → Geniş tabanlı düşüş"
            else:
                if ma50_deg >= beklenen * 0.8:
                    kural_mesaj = f"📐 BIST {bist_deg:+.0f} puan | 50MA beklenen: {beklenen:+.0f} hisse | Gerçek: {ma50_deg:+.0f} → Güçlü breadth onayı ✅"
                else:
                    kural_mesaj = f"📐 BIST {bist_deg:+.0f} puan | 50MA beklenen: {beklenen:+.0f} hisse | Gerçek: {ma50_deg:+.0f} → Dar tabanlı yükseliş ⚠️"

    return {
        "ma20": ma20, "ma50": ma50, "ma200": ma200,
        "ralli_kosullar": ralli_kosullar, "ralli_sayi": ralli_sayi,
        "dikkat_kosullar": dikkat_kosullar,
        "divergence": divergence, "div_mesaj": div_mesaj,
        "kural_mesaj": kural_mesaj,
        "ma20_haftalik": df["20MA_Haftalik"].iloc[-1] if "20MA_Haftalik" in df.columns else None,
        "ma50_haftalik": df["50MA_Haftalik"].iloc[-1] if "50MA_Haftalik" in df.columns else None,
        "ma200_haftalik": df["200MA_Haftalik"].iloc[-1] if "200MA_Haftalik" in df.columns else None,
    }


# ── AD Oscillatör grafiği ─────────────────────────────────────────────────────

def _ad_grafik(df: pd.DataFrame) -> go.Figure:
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.4, 0.6],
        vertical_spacing=0.06,
        subplot_titles=("Kümülatif A-D Line", "Günlük Advance-Decline Farkı")
    )

    # ── Üst: Kümülatif AD Line ────────────────────────────────────────────────
    fig.add_trace(go.Scatter(
        x=df["Tarih"],
        y=df["AD_Kumul"],
        name="Kümülatif AD",
        line=dict(color="#2196F3", width=2),
        fill="tozeroy",
        fillcolor="rgba(33,150,243,0.12)",
        hovertemplate="%{x|%d.%m.%Y}<br>Kümülatif: %{y:+,.0f}<extra></extra>"
    ), row=1, col=1)

    # Kümülatif 0 çizgisi
    fig.add_hline(y=0, line=dict(color="rgba(255,255,255,0.3)", width=1, dash="dot"), row=1, col=1)

    # ── Alt: Günlük bar ───────────────────────────────────────────────────────
    renkler = ["#26a69a" if v >= 0 else "#ef5350" for v in df["Advance-Decline Farkı"]]

    fig.add_trace(go.Bar(
        x=df["Tarih"],
        y=df["Advance-Decline Farkı"],
        name="A-D Farkı",
        marker_color=renkler,
        hovertemplate="%{x|%d.%m.%Y}<br>A-D Farkı: %{y:+,.0f}<extra></extra>"
    ), row=2, col=1)

    # 0 çizgisi
    fig.add_hline(y=0, line=dict(color="rgba(255,255,255,0.5)", width=1.5), row=2, col=1)

    # BIST kapanış — ikincil eksen olarak alt panele
    fig.add_trace(go.Scatter(
        x=df["Tarih"],
        y=df["BIST Kapanış"],
        name="BIST100",
        line=dict(color="#FFD700", width=1.5, dash="dot"),
        yaxis="y3",
        hovertemplate="%{x|%d.%m.%Y}<br>BIST: %{y:,.0f}<extra></extra>"
    ), row=2, col=1)

    fig.update_layout(
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117",
        font=dict(color="white", family="Arial"),
        height=520,
        margin=dict(l=10, r=60, t=40, b=10),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02,
            xanchor="right", x=1,
            bgcolor="rgba(0,0,0,0.3)"
        ),
        hovermode="x unified",
        yaxis3=dict(
            overlaying="y2",
            side="right",
            showgrid=False,
            tickformat=",",
            title=dict(text="BIST100", font=dict(color="#FFD700")),
            tickfont=dict(color="#FFD700"),
        )
    )

    fig.update_xaxes(
        gridcolor="rgba(255,255,255,0.07)",
        showgrid=True
    )
    fig.update_yaxes(
        gridcolor="rgba(255,255,255,0.07)",
        showgrid=True,
        zeroline=True,
        zerolinecolor="rgba(255,255,255,0.3)"
    )

    return fig


# ── MA Oranları grafiği ───────────────────────────────────────────────────────

def _ma_grafik(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()

    renk_map = {
        "20MA Üstü%":  ("#FF9800", "20MA%"),
        "50MA Üstü%":  ("#2196F3", "50MA%"),
        "200MA Üstü%": ("#4CAF50", "200MA%"),
    }

    for col, (renk, isim) in renk_map.items():
        if col in df.columns:
            fig.add_trace(go.Scatter(
                x=df["Tarih"],
                y=df[col],
                name=isim,
                line=dict(color=renk, width=2),
                hovertemplate=f"%{{x|%d.%m.%Y}}<br>{isim}: %{{y:.1f}}%<extra></extra>"
            ))

    # Referans çizgileri
    for seviye, renk, etiket in [
        (80, "rgba(76,175,80,0.4)",  "Güçlü"),
        (65, "rgba(33,150,243,0.4)", "Ralli"),
        (55, "rgba(255,152,0,0.4)",  "200MA Eşiği"),
        (50, "rgba(255,255,255,0.2)","Orta"),
    ]:
        fig.add_hline(
            y=seviye,
            line=dict(color=renk, width=1, dash="dash"),
            annotation_text=f"%{seviye} {etiket}",
            annotation_position="right",
            annotation_font_size=10,
        )

    fig.update_layout(
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117",
        font=dict(color="white", family="Arial"),
        height=320,
        margin=dict(l=10, r=80, t=20, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
        yaxis=dict(
            gridcolor="rgba(255,255,255,0.07)",
            ticksuffix="%",
            range=[0, 105]
        ),
        xaxis=dict(gridcolor="rgba(255,255,255,0.07)", showgrid=True)
    )

    return fig


# ── Ana panel fonksiyonu ──────────────────────────────────────────────────────

def breadth_panel():
    """Makro Kahini sekmesinde buton altında gösterilecek panel."""

    df = _veri_yukle()

    if df.empty:
        st.error(f"❌ `bist_dashboard_final.xlsx` bulunamadı. Beklenen yol: `{EXCEL_PATH}`")
        st.info("Dosya yolunu `breadth_tab.py` içindeki `EXCEL_PATH` değişkeninden düzenleyebilirsiniz.")
        return

    son = df.iloc[-1]
    s   = _sinyal_hesapla(df)

    st.divider()
    st.markdown("### 📊 Piyasa Genişliği (Market Breadth)")
    st.caption(f"Kaynak: bist_dashboard_final.xlsx  |  Son güncelleme: {son['Tarih'].strftime('%d.%m.%Y')}  |  Evren: {TOPLAM_HISSE} hisse")

    # ── 1. MA Oranları metrik kutular ─────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)

    def _trend_ok(df, col, gun=3):
        try:
            avg = df[col].iloc[-gun:].diff().mean()
            if avg > 0.5:  return "↑", "normal"
            if avg < -0.5: return "↓", "inverse"
            return "→", "off"
        except: return "→", "off"

    ok20,  dc20  = _trend_ok(df, "20MA Üstü%")
    ok50,  dc50  = _trend_ok(df, "50MA Üstü%")
    ok200, dc200 = _trend_ok(df, "200MA Üstü%")

    c1.metric(
        "20MA% (Kısa Vade)",
        f"%{s['ma20']:.1f} {ok20}" if s['ma20'] else "—",
        delta=f"Hft ort: %{s['ma20_haftalik']:.1f}" if s['ma20_haftalik'] else None,
        delta_color=dc20
    )
    c2.metric(
        "50MA% (Orta Vade)",
        f"%{s['ma50']:.1f} {ok50}" if s['ma50'] else "—",
        delta=f"Hft ort: %{s['ma50_haftalik']:.1f}" if s['ma50_haftalik'] else None,
        delta_color=dc50
    )
    c3.metric(
        "200MA% (Uzun Vade)",
        f"%{s['ma200']:.1f} {ok200}" if s['ma200'] else "—",
        delta=f"Hft ort: %{s['ma200_haftalik']:.1f}" if s['ma200_haftalik'] else None,
        delta_color=dc200
    )
    c4.metric(
        "BIST100",
        f"{int(son['BIST Kapanış']):,}",
        delta=f"{son['Advance-Decline Farkı']:+.0f} A-D" if son['Advance-Decline Farkı'] else None,
    )

    # ── 2. Sinyal kutuları ────────────────────────────────────────────────────
    ralli_sayi = s.get("ralli_sayi", 0)
    if ralli_sayi >= 4:
        st.success(f"🟢 RALLİ SİNYALİ — {ralli_sayi}/4 koşul sağlandı")
    elif ralli_sayi >= 2:
        st.warning(f"🟡 KARIŞIK — {ralli_sayi}/4 koşul sağlandı")
    else:
        st.error(f"🔴 DİKKAT — {ralli_sayi}/4 koşul sağlandı")

    if s.get("divergence"):
        st.error(f"⚠️ {s['div_mesaj']}")

    if s.get("kural_mesaj"):
        st.info(s["kural_mesaj"])

    if s.get("dikkat_kosullar"):
        for d in s["dikkat_kosullar"]:
            st.warning(d)

    # ── 3. Sinyal detayı ──────────────────────────────────────────────────────
    with st.expander("📋 Ralli Koşulları Detayı", expanded=False):
        for k in s.get("ralli_kosullar", []):
            st.markdown(f"- {k}")

    # ── 4. MA Oranları grafiği ────────────────────────────────────────────────
    st.markdown("#### 📈 MA Oranları Trendi")
    st.plotly_chart(_ma_grafik(df), use_container_width=True)

    # ── 5. AD Oscillatör ─────────────────────────────────────────────────────
    st.markdown("#### 📊 Advance-Decline Oscillatör")
    st.plotly_chart(_ad_grafik(df), use_container_width=True)
