"""
doji_alarm_tab.py — 6 Aylık & 12 Aylık Doji / Sabah Yıldızı Alarm Sekmesi

Pattern mantığı:
  [2+ yeşil mum → yükseliş bağlamı]
  [1-2 kırmızı mum → düzeltme]
  [doji → kararsızlık]

Sinyal tipleri:
  🟡 Oluşuyor  — açık mum doji şeklinde, bağlam uygun
  🟢 Tamamlandı — doji kapandı, yeşil onay bekleniyor
  🚀 Onaylı    — doji + ardından yeşil mum kapandı
"""

import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import date, datetime


# ── Veri çekme ────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def _aylik_veri_cek(hisse: str, period: str = "5y") -> pd.DataFrame:
    ticker = hisse if hisse.endswith(".IS") else hisse + ".IS"
    try:
        df = yf.download(ticker, period=period, interval="1mo",
                         progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df if not df.empty else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


# ── Mum yardımcıları ──────────────────────────────────────────────────────────

def _kirmizi(row) -> bool:
    try:
        return float(row["Close"]) < float(row["Open"])
    except Exception:
        return False

def _yesil(row) -> bool:
    try:
        return float(row["Close"]) >= float(row["Open"])
    except Exception:
        return False

def _body_oran(row) -> float:
    try:
        o = float(row["Open"]); c = float(row["Close"])
        h = float(row["High"]); l = float(row["Low"])
        rng = h - l
        return abs(c - o) / rng if rng > 0 else 1.0
    except Exception:
        return 1.0

def _doji(row, esik: float) -> bool:
    return _body_oran(row) < esik


# ── Pattern tespiti ───────────────────────────────────────────────────────────

def _pattern_tara(df: pd.DataFrame, periyot_bar: int, doji_esik: float) -> dict | None:
    """
    Aylık mumda pattern arar.

    Bağlam şartı: kırmızı seriden önce en az 2 ardışık yeşil mum olmalı.
    Pattern:
      1 veya 2 kırmızı mum → doji
    Sinyal:
      🚀 Onaylı    → doji sonrası yeşil kapandı
      🟢 Tamamlandı → doji kapandı, onay yok
      🟡 Oluşuyor  → açık mum doji şekliyor
    """
    if len(df) < 5:
        return None

    # Açık mum tespiti
    bugun = datetime.utcnow()
    son_idx = df.index[-1]
    acik_var = (son_idx.year == bugun.year and son_idx.month == bugun.month)

    kapali = df.iloc[:-1].tail(periyot_bar) if acik_var else df.tail(periyot_bar)
    acik   = df.iloc[-1] if acik_var else None

    if len(kapali) < 4:
        return None

    rows = list(kapali.itertuples())  # named tuples, hızlı erişim

    def get(row, col):
        return float(getattr(row, col))

    def kirmizi_t(row) -> bool:
        try: return get(row, "Close") < get(row, "Open")
        except: return False

    def yesil_t(row) -> bool:
        try: return get(row, "Close") >= get(row, "Open")
        except: return False

    def doji_t(row, esik=None) -> bool:
        e = esik if esik is not None else doji_esik
        try:
            o = get(row, "Open"); c = get(row, "Close")
            h = get(row, "High"); l = get(row, "Low")
            rng = h - l
            return abs(c - o) / rng < e if rng > 0 else False
        except: return False

    def tarih(row):
        try: return str(row.Index.date())
        except: return str(row.Index)

    def baglam_ok(idx_kirmizi_bas: int) -> bool:
        """idx_kirmizi_bas: rows listesinde kırmızı serinin başladığı index.
        Öncesinde en az 2 ardışık yeşil mum olmalı."""
        if idx_kirmizi_bas < 2:
            return False
        yesil_say = 0
        for j in range(idx_kirmizi_bas - 1, -1, -1):
            if yesil_t(rows[j]):
                yesil_say += 1
            else:
                break
        return yesil_say >= 2

    n = len(rows)

    # ── 🚀 ONAYLANMIŞ ──────────────────────────────────────────────────────────

    # Tek kırmızı: [...yeşil] [kırmızı] [doji] [yeşil]
    if n >= 4:
        if (kirmizi_t(rows[-3]) and doji_t(rows[-2]) and yesil_t(rows[-1])
                and baglam_ok(n - 3)):
            getiri = (get(rows[-1], "Close") / get(rows[-3], "Close") - 1) * 100
            return {
                "sinyal": "🚀 Onaylı",
                "detay": "Yükseliş → Kırmızı → Doji → Yeşil",
                "son_kapat": round(get(rows[-1], "Close"), 2),
                "getiri_pct": round(getiri, 1),
                "pattern_tarihi": tarih(rows[-2]),
            }

    # İki kırmızı: [...yeşil] [kırmızı] [kırmızı] [doji] [yeşil]
    if n >= 5:
        if (kirmizi_t(rows[-4]) and kirmizi_t(rows[-3]) and doji_t(rows[-2])
                and yesil_t(rows[-1]) and baglam_ok(n - 4)):
            getiri = (get(rows[-1], "Close") / get(rows[-4], "Close") - 1) * 100
            return {
                "sinyal": "🚀 Onaylı",
                "detay": "Yükseliş → 2×Kırmızı → Doji → Yeşil",
                "son_kapat": round(get(rows[-1], "Close"), 2),
                "getiri_pct": round(getiri, 1),
                "pattern_tarihi": tarih(rows[-2]),
            }

    # ── 🟢 TAMAMLANDI ──────────────────────────────────────────────────────────

    # Tek kırmızı
    if n >= 3:
        if (kirmizi_t(rows[-2]) and doji_t(rows[-1])
                and baglam_ok(n - 2)):
            return {
                "sinyal": "🟢 Tamamlandı",
                "detay": "Yükseliş → Kırmızı → Doji (onay bekleniyor)",
                "son_kapat": round(get(rows[-1], "Close"), 2),
                "getiri_pct": None,
                "pattern_tarihi": tarih(rows[-1]),
            }

    # İki kırmızı
    if n >= 4:
        if (kirmizi_t(rows[-3]) and kirmizi_t(rows[-2]) and doji_t(rows[-1])
                and baglam_ok(n - 3)):
            return {
                "sinyal": "🟢 Tamamlandı",
                "detay": "Yükseliş → 2×Kırmızı → Doji (onay bekleniyor)",
                "son_kapat": round(get(rows[-1], "Close"), 2),
                "getiri_pct": None,
                "pattern_tarihi": tarih(rows[-1]),
            }

    # ── 🟡 OLUŞUYOR ────────────────────────────────────────────────────────────

    if acik is not None and _doji(acik, doji_esik + 0.05):
        # Tek kırmızı kapandı
        if n >= 2 and kirmizi_t(rows[-1]) and baglam_ok(n - 1):
            return {
                "sinyal": "🟡 Oluşuyor",
                "detay": "Yükseliş → Kırmızı → [Doji oluşuyor]",
                "son_kapat": round(float(acik["Close"]), 2),
                "getiri_pct": None,
                "pattern_tarihi": str(acik.name.date()) if hasattr(acik.name, "date") else str(acik.name),
            }
        # İki kırmızı kapandı
        if n >= 3 and kirmizi_t(rows[-1]) and kirmizi_t(rows[-2]) and baglam_ok(n - 2):
            return {
                "sinyal": "🟡 Oluşuyor",
                "detay": "Yükseliş → 2×Kırmızı → [Doji oluşuyor]",
                "son_kapat": round(float(acik["Close"]), 2),
                "getiri_pct": None,
                "pattern_tarihi": str(acik.name.date()) if hasattr(acik.name, "date") else str(acik.name),
            }

    return None


# ── Streamlit UI ──────────────────────────────────────────────────────────────

def tab_doji_alarm(bist_listesi_yukle_fn):
    st.subheader("🕯️ Doji & Sabah Yıldızı Alarm Tarayıcısı")
    st.caption(
        "Yükseliş bağlamı (2+ yeşil mum) → kırmızı düzeltme (1-2 mum) → doji/kararsızlık. "
        "6 ve 12 aylık grafik."
    )

    col1, col2, col3, col4 = st.columns([2, 2, 2, 2])

    with col1:
        periyot_sec = st.multiselect(
            "Grafik Periyodu",
            ["6 Aylık", "12 Aylık"],
            default=["6 Aylık", "12 Aylık"],
            key="doji_periyot"
        )
    with col2:
        sinyal_sec = st.multiselect(
            "Sinyal Filtresi",
            ["🟡 Oluşuyor", "🟢 Tamamlandı", "🚀 Onaylı"],
            default=["🟡 Oluşuyor", "🟢 Tamamlandı", "🚀 Onaylı"],
            key="doji_sinyal"
        )
    with col3:
        doji_esik_pct = st.slider(
            "Doji Eşiği (body/range %)",
            min_value=10, max_value=40, value=25, step=5,
            key="doji_esik",
            help="25 önerilir. Düşük = daha sıkı doji."
        )
    with col4:
        tara_btn = st.button("🔍 Tara", type="primary",
                             use_container_width=True, key="doji_tara")

    if not tara_btn:
        st.info("Parametreleri seç ve **Tara** butonuna bas.")
        return
    if not periyot_sec:
        st.warning("En az bir periyot seç.")
        return

    bist_liste = bist_listesi_yukle_fn()
    if not bist_liste:
        st.error("bist_fd.xlsx bulunamadı.")
        return

    doji_esik  = doji_esik_pct / 100
    periyot_bar_map = {"6 Aylık": 6, "12 Aylık": 12}

    prog = st.progress(0, text="Tarama başlıyor...")
    sonuclar = []

    for i, hisse in enumerate(bist_liste):
        prog.progress((i + 1) / len(bist_liste),
                      text=f"⏳ {hisse} ({i+1}/{len(bist_liste)})")
        df_ay = _aylik_veri_cek(hisse)
        if df_ay.empty or len(df_ay) < 5:
            continue

        for p_adi in periyot_sec:
            sonuc = _pattern_tara(df_ay, periyot_bar_map[p_adi], doji_esik)
            if sonuc is None or sonuc["sinyal"] not in sinyal_sec:
                continue
            sonuclar.append({
                "Hisse":          hisse,
                "Periyot":        p_adi,
                "Sinyal":         sonuc["sinyal"],
                "Detay":          sonuc["detay"],
                "Son Fiyat":      sonuc["son_kapat"],
                "Getiri%":        sonuc.get("getiri_pct"),
                "Pattern Tarihi": sonuc["pattern_tarihi"],
            })

    prog.empty()

    if not sonuclar:
        st.warning("Seçilen kriterlere uygun hisse bulunamadı.")
        return

    df_s = pd.DataFrame(sonuclar)
    sira = {"🚀 Onaylı": 0, "🟢 Tamamlandı": 1, "🟡 Oluşuyor": 2}
    df_s["_s"] = df_s["Sinyal"].map(sira).fillna(9)
    df_s = df_s.sort_values(["_s", "Periyot", "Hisse"]).drop(columns=["_s"])

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Toplam",         len(df_s))
    m2.metric("🚀 Onaylı",     len(df_s[df_s["Sinyal"] == "🚀 Onaylı"]))
    m3.metric("🟢 Tamamlandı", len(df_s[df_s["Sinyal"] == "🟢 Tamamlandı"]))
    m4.metric("🟡 Oluşuyor",   len(df_s[df_s["Sinyal"] == "🟡 Oluşuyor"]))

    onaylı = df_s[df_s["Sinyal"] == "🚀 Onaylı"]["Getiri%"].dropna()
    if len(onaylı) > 0:
        st.markdown(
            f"**🚀 Onaylı ortalama getiri:** `%{onaylı.mean():.1f}` "
            f"| Pozitif: `{(onaylı > 0).sum()}/{len(onaylı)}`"
        )

    st.dataframe(
        df_s.reset_index(drop=True),
        use_container_width=True, height=500,
        column_config={
            "Son Fiyat": st.column_config.NumberColumn(format="%.2f"),
            "Getiri%":   st.column_config.NumberColumn(format="%.1f%%"),
        }
    )

    buf = __import__("io").BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df_s.to_excel(w, index=False, sheet_name="DojiAlarm")
    st.download_button(
        "📥 Excel İndir", buf.getvalue(),
        file_name=f"doji_alarm_{date.today()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
