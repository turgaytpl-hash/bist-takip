"""
mum_desen_tab.py — BIST Mum Deseni Tarayıcısı
TA-Lib ile seçili ~25 pattern, Investing.com tarzı:
  - Emerging (oluşuyor) + Completed (tamamlandı)
  - Boğa / Ayı yönü ayrımı
  - Güvenilirlik yıldızı
  - Kaç mum önce + Tarih
  - Periyot: 1D, 1W, 1M
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import date, datetime

try:
    import talib
    TALIB_OK = True
except ImportError:
    TALIB_OK = False

# ── Pattern kataloğu ──────────────────────────────────────────────────────────
# (fonksiyon_adı, türkçe_ad, yıldız_sayısı, yön)
# yön: "bull"=sadece boğa, "bear"=sadece ayı, "both"=her iki yön (TA-Lib değerine göre ayrılır)

PATTERNS = [
    # ── Boğa Dönüş ────────────────────────────────────────────────────────────
    ("CDLMORNINGSTAR",     "Sabah Yıldızı",       3, "bull"),
    ("CDLMORNINGDOJISTAR", "Sabah Doji Yıldızı",  3, "bull"),
    ("CDL3WHITESOLDIERS",  "3 Beyaz Asker",       3, "bull"),
    ("CDLHAMMER",          "Çekiç",               2, "bull"),
    ("CDLINVERTEDHAMMER",  "Ters Çekiç",          2, "bull"),

    # ── Ayı Dönüş ─────────────────────────────────────────────────────────────
    ("CDLEVENINGSTAR",     "Akşam Yıldızı",       3, "bear"),
    ("CDLEVENINGDOJISTAR", "Akşam Doji Yıldızı",  3, "bear"),
    ("CDL3BLACKCROWS",     "3 Siyah Karga",       3, "bear"),
    ("CDLSHOOTINGSTAR",    "Kayan Yıldız",        2, "bear"),
    ("CDLHANGINGMAN",      "Asılı Adam",          2, "bear"),

    # ── Her İki Yön (TA-Lib değerine göre ayrılır) ────────────────────────────
    ("CDLABANDONEDBABY",   "Terk Edilmiş Bebek",  3, "both"),
    ("CDLENGULFING",       "Yutan",               2, "both"),
]

YILDIZ    = {1: "⭐", 2: "⭐⭐", 3: "⭐⭐⭐"}
YON_EMOJI = {"bull": "🟢", "bear": "🔴"}
YON_TR    = {"bull": "Boğa", "bear": "Ayı"}


# ── Veri çekme ────────────────────────────────────────────────────────────────

@st.cache_data(ttl=1800)
def _veri_cek(hisse: str, interval: str, period: str) -> pd.DataFrame:
    ticker = hisse if hisse.endswith(".IS") else hisse + ".IS"
    try:
        df = yf.download(ticker, period=period, interval=interval,
                         progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if df.empty or len(df) < 5:
            return pd.DataFrame()
        return df
    except Exception:
        return pd.DataFrame()


# ── Pattern tespiti ───────────────────────────────────────────────────────────

def _pattern_tara_hisse(df: pd.DataFrame, secili_patternler: list) -> list:
    """Tek hisse için seçili patternleri tarar. Sonuç: list of dict."""
    if df.empty or len(df) < 5:
        return []

    op = df["Open"].values.astype(float)
    hi = df["High"].values.astype(float)
    lo = df["Low"].values.astype(float)
    cl = df["Close"].values.astype(float)
    idx = df.index

    sonuclar = []

    for fn_adi, tr_adi, yildiz, yon in secili_patternler:
        fn = getattr(talib, fn_adi, None)
        if fn is None:
            continue
        try:
            result = fn(op, hi, lo, cl)
        except Exception:
            continue

        # Son 20 mumu tara
        for i in range(len(result) - 1, max(len(result) - 21, -1), -1):
            val = result[i]
            if val == 0:
                continue

            # TA-Lib: +100 = boğa, -100 = ayı
            # Katalogda "bull" veya "bear" olanlar sabit yön,
            # "both" olanlar TA-Lib değerine göre ayrılır
            if yon == "bull":
                yon_gercek = "bull"
            elif yon == "bear":
                yon_gercek = "bear"
            else:
                yon_gercek = "bull" if val > 0 else "bear"
            candles_ago = len(result) - 1 - i

            # Oluşuyor mu? Son mum kapanmadıysa (şu an açık mum)
            emerging = (candles_ago == 0)

            tarih = idx[i]
            if hasattr(tarih, 'date'):
                tarih_str = str(tarih.date())
            else:
                tarih_str = str(tarih)

            sonuclar.append({
                "pattern_fn":  fn_adi,
                "pattern_tr":  tr_adi,
                "yildiz":      yildiz,
                "yon":         yon_gercek,
                "emerging":    emerging,
                "candles_ago": candles_ago,
                "tarih":       tarih_str,
            })
            break  # Her pattern için en son sinyali al

    return sonuclar


# ── Ana UI ────────────────────────────────────────────────────────────────────

def tab_mum_desen(bist_listesi_yukle_fn):
    st.subheader("🕯️ BIST Mum Deseni Tarayıcısı")
    st.caption("TA-Lib ile 60+ pattern — Emerging (oluşuyor) + Completed (tamamlandı) — Investing.com tarzı")

    if not TALIB_OK:
        st.error("TA-Lib kurulu değil. `pip install TA-Lib` komutunu çalıştırın.")
        return

    # ── Filtreler ─────────────────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns([2, 2, 2, 2])

    with col1:
        interval_sec = st.selectbox(
            "Periyot",
            ["1D", "1W", "1M"],
            key="mum_interval"
        )

    with col2:
        yon_sec = st.multiselect(
            "Yön",
            ["🟢 Boğa", "🔴 Ayı"],
            default=["🟢 Boğa", "🔴 Ayı"],
            key="mum_yon"
        )

    with col3:
        yildiz_sec = st.multiselect(
            "Min. Güvenilirlik",
            ["⭐", "⭐⭐", "⭐⭐⭐"],
            default=["⭐", "⭐⭐", "⭐⭐⭐"],
            key="mum_yildiz"
        )

    with col4:
        durum_sec = st.multiselect(
            "Durum",
            ["🟡 Oluşuyor", "✅ Tamamlandı"],
            default=["🟡 Oluşuyor", "✅ Tamamlandı"],
            key="mum_durum"
        )

    # Pattern seçimi — yön seçimine göre filtrele
    yon_map_on = {"🟢 Boğa": "bull", "🔴 Ayı": "bear"}
    izin_yon_on = {yon_map_on[y] for y in yon_sec}

    def _yon_uygun(yon):
        if yon == "both":
            return True  # both her zaman listede gösterilir, sonuçta ayrılır
        return yon in izin_yon_on

    with st.expander("🔧 Pattern Seçimi (yöne göre filtrelendi)", expanded=False):
        filtreli_patterns = [(fn, tr, y, yon) for fn, tr, y, yon in PATTERNS
                             if _yon_uygun(yon)]
        pattern_isimler = [f"{tr} ({fn})" for fn, tr, y, yon in filtreli_patterns]
        secili_idx = st.multiselect(
            "Patternler",
            options=pattern_isimler,
            default=pattern_isimler,
            key="mum_patterns"
        )

    max_ago = st.slider("Maks. kaç mum önce?", 1, 20, 5, key="mum_ago")

    tara_btn = st.button("🔍 Tara", type="primary", use_container_width=True, key="mum_tara")

    if not tara_btn:
        st.info("Filtreleri ayarlayıp **Tara** butonuna bas.")
        return

    # ── Seçili patternleri belirle ────────────────────────────────────────────
    secili_fn_set = set()
    for s in secili_idx:
        fn = s.split("(")[-1].rstrip(")")
        secili_fn_set.add(fn)

    secili_patternler = [(fn, tr, y, yon) for fn, tr, y, yon in PATTERNS
                         if fn in secili_fn_set]

    if not secili_patternler:
        st.warning("En az bir pattern seç.")
        return

    # ── Yön filtresi ──────────────────────────────────────────────────────────
    yon_map = {"🟢 Boğa": "bull", "🔴 Ayı": "bear"}
    izin_yon = {yon_map[y] for y in yon_sec}

    # ── Yıldız filtresi ───────────────────────────────────────────────────────
    yildiz_sayilari = set()
    if "⭐" in yildiz_sec:      yildiz_sayilari.add(1)
    if "⭐⭐" in yildiz_sec:    yildiz_sayilari.add(2)
    if "⭐⭐⭐" in yildiz_sec:  yildiz_sayilari.add(3)

    # ── Durum filtresi ────────────────────────────────────────────────────────
    izin_emerging   = "🟡 Oluşuyor"   in durum_sec
    izin_completed  = "✅ Tamamlandı" in durum_sec

    # ── Interval ayarla ───────────────────────────────────────────────────────
    iv_map = {"1D": ("1d", "6mo"), "1W": ("1wk", "2y"), "1M": ("1mo", "5y")}
    interval, period = iv_map[interval_sec]

    # ── Tarama ────────────────────────────────────────────────────────────────
    bist_liste = bist_listesi_yukle_fn()
    if not bist_liste:
        st.error("bist_fd.xlsx bulunamadı.")
        return

    prog = st.progress(0, text="Tarama başlıyor...")
    sonuclar = []

    for i, hisse in enumerate(bist_liste):
        prog.progress((i + 1) / len(bist_liste),
                      text=f"⏳ {hisse} ({i+1}/{len(bist_liste)})")

        df = _veri_cek(hisse, interval, period)
        if df.empty:
            continue

        hisse_sonuc = _pattern_tara_hisse(df, secili_patternler)

        for s in hisse_sonuc:
            # Filtrele
            if s["candles_ago"] > max_ago:
                continue
            if s["yon"] not in izin_yon:
                continue
            if s["yildiz"] not in yildiz_sayilari:
                continue
            if s["emerging"] and not izin_emerging:
                continue
            if not s["emerging"] and not izin_completed:
                continue

            durum = "🟡 Oluşuyor" if s["emerging"] else "✅ Tamamlandı"
            sonuclar.append({
                "Hisse":        hisse,
                "Pattern":      s["pattern_tr"],
                "Yön":          f"{YON_EMOJI[s['yon']]} {YON_TR[s['yon']]}",
                "Güvenilirlik": YILDIZ[s["yildiz"]],
                "Durum":        durum,
                "Mum Önce":     s["candles_ago"],
                "Tarih":        s["tarih"],
                "Periyot":      interval_sec,
            })

    prog.empty()

    if not sonuclar:
        st.warning("Seçilen kriterlere uygun sinyal bulunamadı.")
        return

    df_s = pd.DataFrame(sonuclar)

    # Sıralama: Oluşuyor önce, sonra mum önce
    df_s["_emer"] = df_s["Durum"].apply(lambda x: 0 if "Oluşuyor" in x else 1)
    df_s = df_s.sort_values(["_emer", "Mum Önce", "Hisse"]).drop(columns=["_emer"])

    # ── Metrikler ─────────────────────────────────────────────────────────────
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Toplam Sinyal", len(df_s))
    m2.metric("Hisse Sayısı", df_s["Hisse"].nunique())
    m3.metric("🟡 Oluşuyor", len(df_s[df_s["Durum"] == "🟡 Oluşuyor"]))
    m4.metric("🟢 Boğa", len(df_s[df_s["Yön"].str.contains("Boğa")]))
    m5.metric("🔴 Ayı", len(df_s[df_s["Yön"].str.contains("Ayı")]))

    st.divider()

    # ── Tablo ─────────────────────────────────────────────────────────────────
    st.dataframe(
        df_s.reset_index(drop=True),
        use_container_width=True,
        height=550,
        column_config={
            "Mum Önce": st.column_config.NumberColumn(format="%d"),
        }
    )

    # ── Excel ─────────────────────────────────────────────────────────────────
    buf = __import__("io").BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df_s.to_excel(w, index=False, sheet_name="MumDesenleri")
    st.download_button(
        "📥 Excel İndir", buf.getvalue(),
        file_name=f"mum_desen_{date.today()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
