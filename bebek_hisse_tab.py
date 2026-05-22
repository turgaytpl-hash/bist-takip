"""
bebek_hisse_tab.py — Bebek Hisse Avcısı
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path
from datetime import datetime

import yfinance as yf

BEBEK_HİSSELER = {
    "ARFYE": {"t2": 47_000_000,  "arz": "2026-01"},
    "EMPAE": {"t2": 38_000_000,  "arz": "2026-03"},
    "FRMPL": {"t2": 47_000_000,  "arz": "2026-01"},
    "UCAYM": {"t2": 60_000_000,  "arz": "2026-01"},
    "ZGYO":  {"t2": 84_600_000,  "arz": "2026-01"},
    "AKHAN": {"t2": 54_700_000,  "arz": "2026-02"},
    "NETCD": {"t2": 40_000_000,  "arz": "2026-02"},
    "MCARD": {"t2": 18_900_000,  "arz": "2026-02"},
    "KLYPV": {"t2": 46_300_000,  "arz": "2026-02"},
    "BESTE": {"t2": 54_600_000,  "arz": "2026-02"},
}

# Koordineli / izlenen kurumlar
BIRIKIM  = ["BANK-OF-AMERICA", "CITIBANK", "ALLBATROSS"]
GELISME  = ["TERA YATIRIM", "BULLS YATIRIM", "DESTEK YATIRIM", "A1 CAPITAL", "ALNUS YATIRIM"]
DAGITIM  = ["INFO YATIRIM"]
FONLAR   = ["YATIRIM FONLARI", "EMEKLILIK"]

DATA_DIR    = Path("data/bebek_hisse")
SİNYAL_LOG = Path("data/bebek_hisse/sinyal_log.csv")

# Bebek hisse için TÜM kurumlar izlenir — tahta küçük olduğu için hepsi önemli
KOORDİNELİ = []  # Boş = filtre yok, hepsi izlenir

SINYAL_KOLONLAR = [
    "hisse", "kurum", "ilk_tarih", "ilk_fiyat", "ilk_oran",
    "son_tarih", "son_fiyat", "son_oran", "durum"
]


def fiyat_cek(hisse: str, tarih: str) -> float:
    """Belirli bir tarihteki kapanış fiyatını yfinance'den çeker."""
    try:
        from datetime import datetime, timedelta
        dt = datetime.strptime(tarih, "%d.%m.%Y") if "." in tarih else datetime.strptime(tarih, "%Y-%m-%d")
        baslangic = (dt - timedelta(days=5)).strftime("%Y-%m-%d")
        bitis     = (dt + timedelta(days=2)).strftime("%Y-%m-%d")
        ticker = hisse if hisse.endswith(".IS") else hisse + ".IS"
        df = yf.download(ticker, start=baslangic, end=bitis,
                         progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if df.empty:
            return 0.0
        # Tarihe en yakın kapanışı al
        return round(float(df["Close"].iloc[-1]), 2)
    except:
        return 0.0


def sinyal_log_oku() -> pd.DataFrame:
    """Sinyal log dosyasını okur."""
    if not SİNYAL_LOG.exists():
        return pd.DataFrame(columns=SINYAL_KOLONLAR)
    try:
        return pd.read_csv(SİNYAL_LOG)
    except:
        return pd.DataFrame(columns=SINYAL_KOLONLAR)


def sinyal_log_kaydet(df: pd.DataFrame):
    """Sinyal log dosyasını kaydeder."""
    SİNYAL_LOG.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(SİNYAL_LOG, index=False)


def sinyal_guncelle_donem(hisse: str, df_donem: pd.DataFrame, t2_total: int, donem: str):
    """Belirli bir dönemin verisini tarayıp sinyal log'unu günceller."""
    if df_donem.empty or t2_total == 0:
        return

    log = sinyal_log_oku()
    guncellendi = False

    df_donem = df_donem.copy()
    df_donem["_oran"] = (df_donem["2.Adet"] / t2_total * 100).round(2)

    for _, r in df_donem.iterrows():
        kurum = str(r["Kurum"]).upper().strip()
        # KOORDİNELİ boşsa tüm kurumları izle
        if KOORDİNELİ and not any(k in kurum for k in KOORDİNELİ):
            continue

        oran = r["_oran"]
        if oran < 3.0:
            continue

        mask = (log["hisse"] == hisse) & (log["kurum"] == kurum)
        mevcut = log[mask]

        if mevcut.empty:
            fiyat = fiyat_cek(hisse, donem)
            yeni = {
                "hisse":     hisse,
                "kurum":     kurum,
                "ilk_tarih": donem,
                "ilk_fiyat": fiyat,
                "ilk_oran":  oran,
                "son_tarih": donem,
                "son_fiyat": fiyat,
                "son_oran":  oran,
                "durum":     "🎯 BİNGO!" if oran >= 5.0 else "📈 TAKİPTE"
            }
            log = pd.concat([log, pd.DataFrame([yeni])], ignore_index=True)
            guncellendi = True
        else:
            idx = mevcut.index[0]
            # Sadece daha yeni dönemse güncelle
            if str(donem) >= str(log.at[idx, "son_tarih"]):
                fiyat = fiyat_cek(hisse, donem)
                log.at[idx, "son_tarih"] = donem
                log.at[idx, "son_fiyat"] = fiyat
                log.at[idx, "son_oran"]  = oran
                log.at[idx, "durum"] = "🎯 BİNGO!" if oran >= 5.0 else "📈 TAKİPTE"
                guncellendi = True

    if guncellendi:
        sinyal_log_kaydet(log)


def sinyal_guncelle(hisse: str, df_takas: pd.DataFrame, t2_total: int):
    """
    Bir hissenin takas verisini tarayıp sinyal log'unu günceller.

    Kural:
    - Koordineli kurum ilk kez %3+ geçti → yeni kayıt + fiyat çek
    - Zaten kayıtlıysa → son oran/fiyat/tarih güncelle
    - %5 geçti → durum = BINGO
    - %3 altına düştü → durum = KAPANDI
    """
    if df_takas.empty or t2_total == 0:
        return

    log = sinyal_log_oku()
    donemler = sorted(df_takas["donem"].unique().tolist())
    son_donem = donemler[-1]
    df_son = df_takas[df_takas["donem"] == son_donem].copy()
    df_son["_oran"] = (df_son["2.Adet"] / t2_total * 100).round(2)

    guncellendi = False

    for _, r in df_son.iterrows():
        kurum = str(r["Kurum"]).upper().strip()
        # KOORDİNELİ boşsa tüm kurumları izle
        if KOORDİNELİ and not any(k in kurum for k in KOORDİNELİ):
            continue

        oran = r["_oran"]
        tarih = str(son_donem)

        # Bu hisse+kurum kombinasyonu logda var mı?
        mask = (log["hisse"] == hisse) & (log["kurum"] == kurum)
        mevcut = log[mask]

        if mevcut.empty:
            # Yeni kayıt — sadece %3+ ise
            if oran >= 3.0:
                fiyat = fiyat_cek(hisse, tarih)
                yeni = {
                    "hisse":      hisse,
                    "kurum":      kurum,
                    "ilk_tarih":  tarih,
                    "ilk_fiyat":  fiyat,
                    "ilk_oran":   oran,
                    "son_tarih":  tarih,
                    "son_fiyat":  fiyat,
                    "son_oran":   oran,
                    "durum":      "🎯 BİNGO!" if oran >= 5.0 else "📈 TAKİPTE"
                }
                log = pd.concat([log, pd.DataFrame([yeni])], ignore_index=True)
                guncellendi = True
        else:
            idx = mevcut.index[0]
            # Güncelle
            fiyat = fiyat_cek(hisse, tarih)
            log.at[idx, "son_tarih"] = tarih
            log.at[idx, "son_fiyat"] = fiyat
            log.at[idx, "son_oran"]  = oran

            if oran >= 5.0:
                log.at[idx, "durum"] = "🎯 BİNGO!"
            elif oran >= 3.0:
                log.at[idx, "durum"] = "📈 TAKİPTE"
            else:
                log.at[idx, "durum"] = "⚪ KAPANDI"
            guncellendi = True

    if guncellendi:
        sinyal_log_kaydet(log)

def yukle(hisse):
    p = DATA_DIR / f"{hisse}.parquet"
    if not p.exists():
        return pd.DataFrame()
    try:
        df = pd.read_parquet(p)
        # Kolon isimlerini normalize et
        yeniden_adlandir = {
            "Adet Fark": "Adet Fark",
            "GünlükF": "GunlukF",
            "HaftaF": "HaftaF",
            "AyF": "AyF",
            "ÜçAyF": "UcAyF",
        }
        df = df.rename(columns=yeniden_adlandir)
        # Eksik kolonları ekle
        for col in ["GunlukF","HaftaF","AyF","UcAyF","1.Pay","2.Pay","Adet Fark"]:
            if col not in df.columns:
                df[col] = 0.0
        return df
    except:
        return pd.DataFrame()

def asama_tespit(df, t2_total=None):
    """
    T2 bazlı aşama tespiti.
    Koordineli kurumların mevcut T2 oranına ve Adet Fark'a bakılır.
    Öncelik: Dağıtım > Kritik > Dikkat > Takipte > Yeni Giriş > Nötr
    """
    if df.empty: return "📂 Veri Yok"
    son = df[df["donem"] == df["donem"].iloc[-1]].copy()

    # T2 toplamı: parametre yoksa 2.Adet toplamını kullan (yaklaşık)
    t2 = t2_total if t2_total else son["2.Adet"].sum()
    if t2 == 0: return "📂 Veri Yok"

    son["_t2pct"] = son["2.Adet"] / t2 * 100

    # 2) Koordineli kurumların mevcut T2 oranı
    KOORD = ["BANK-OF-AMERICA","CITIBANK","ALLBATROSS",
             "TERA YATIRIM","BULLS YATIRIM","DESTEK YATIRIM","A1 CAPITAL","ALNUS YATIRIM",
             "YATIRIM FONLARI","EMEKLILIK"]

    max_oran = 0.0
    max_kurum = ""
    yeni_giris = False

    donemler_all = sorted(df["donem"].unique().tolist())
    onceki_donem = donemler_all[-2] if len(donemler_all) >= 2 else None

    for _, r in son.iterrows():
        k = str(r["Kurum"]).upper()
        if not any(kk in k for kk in KOORD):
            continue
        t2pct = r["_t2pct"]

        # Yeni giriş tespiti (önceki dönemde yoktu / 0'dı)
        if onceki_donem is not None:
            df_onc = df[df["donem"] == onceki_donem]
            onc_satir = df_onc[df_onc["Kurum"] == r["Kurum"]]
            onc_adet = onc_satir.iloc[0]["2.Adet"] if not onc_satir.empty else 0
            onc_pct = onc_adet / t2 * 100
            if onc_pct < 1.0 and t2pct >= 1.0:
                yeni_giris = True

        if t2pct > max_oran:
            max_oran = t2pct
            max_kurum = k

    if max_oran >= 5.0:  return "🟢 Oyuncu Var"
    if max_oran >= 3.0:  return "🟩 Takip Et"
    if max_oran >= 1.0:  return "🔵 Birikim"
    if yeni_giris:       return "🚨 Yeni Giriş"
    return "⚪ Nötr"

def kurum_kategori(kurum):
    k = kurum.upper()
    if any(b in k for b in ["BANK-OF-AMERICA","CITIBANK","ALLBATROSS"]): return "🟣"
    if any(b in k for b in ["TERA YATIRIM","BULLS YATIRIM","DESTEK YATIRIM","A1 CAPITAL","ALNUS YATIRIM"]): return "🟠"
    if "INFO YATIRIM" in k: return "🔴"
    if "YATIRIM FONLARI" in k or "EMEKLILIK" in k: return "🟢"
    if any(b in k for b in ["MIDAS","PUSULA","OSMANLΙ","TACIRLER"]): return "🔵"
    return ""

def bebek_hisse_sekme():
    st.header("🐣 Bebek Hisse Avcısı")
    st.caption("Yeni halka arz hisselerinde akıllı para takibi")

    # ── Kümülatif panel yardımcı fonksiyonu ──────────────────────────────────
    def kumul_panel(kod):
        df = yukle(kod)
        if df.empty: return pd.DataFrame()
        t2 = BEBEK_HİSSELER[kod]["t2"]
        donemler = sorted(df["donem"].unique().tolist())

        if len(donemler) < 2:
            return pd.DataFrame()

        # Sadece son 2 dönemi karşılaştır (dün → bugün)
        donem_ilk = donemler[-2]
        donem_son = donemler[-1]

        df_ilk = df[df["donem"] == donem_ilk][["Kurum","2.Adet"]].copy()
        df_ilk = df_ilk.rename(columns={"2.Adet": "baslangic_adet"})

        df_son = df[df["donem"] == donem_son][["Kurum","2.Adet"]].copy()
        df_son = df_son.rename(columns={"2.Adet": "guncel_adet"})

        df_merge = df_ilk.merge(df_son, on="Kurum", how="outer").fillna(0)
        df_merge["bas_pct"] = (df_merge["baslangic_adet"] / t2 * 100).round(2)
        df_merge["gun_pct"] = (df_merge["guncel_adet"]    / t2 * 100).round(2)
        df_merge["delta"]   = (df_merge["gun_pct"] - df_merge["bas_pct"]).round(2)
        return df_merge

    col_sol, col_orta, col_sag = st.columns([1, 1, 2.5])

    # ── SOL PANEL: Alış Takibi ────────────────────────────────────────────────
    with col_sol:
        st.markdown("**📈 Alış Takibi**")
        st.caption("Kümülatif T2 artışı")

        for kod in BEBEK_HİSSELER:
            df = yukle(kod)
            asama = asama_tespit(df, BEBEK_HİSSELER[kod]["t2"])
            veri = "✅" if not df.empty else "📂"
            if st.button(f"{veri} {kod}  {asama}", key=f"btn_{kod}", use_container_width=True):
                st.session_state["sec_hisse"] = kod

        st.divider()
        st.markdown("**📤 Takas Verisi Yükle**")

        from datetime import date
        secilen_tarih = st.date_input("Tarih", value=date.today(), key="y_tarih",
                                      format="DD.MM.YYYY",
                                      help="Yüklenen verinin tarihi")
        tarih = secilen_tarih.strftime("%d.%m.%Y")
        dosya = st.file_uploader("Excel (tüm hisseler)", type=["xlsx","xls"], key="y_dosya_gun")

        if dosya and tarih and st.button("💾 Tümünü Yükle", key="y_btn_gun", type="primary"):
            try:
                sheets = pd.read_excel(dosya, sheet_name=None, header=None)
                yuklenen = 0
                hatalar  = []

                for hisse_adi, df_raw in sheets.items():
                    hisse_kod = hisse_adi.upper().strip()
                    if hisse_kod not in BEBEK_HİSSELER:
                        continue

                    df_raw.columns = range(len(df_raw.columns))

                    # ── FORMAT ALGILAMA ──────────────────────────────────────
                    ilk_satir = [str(x) for x in df_raw.iloc[0].tolist()]

                    if any("POZISYON" in x.upper() for x in ilk_satir):
                        # Real Time format: Kurum|Takas|Pozisyon|%|Dün.Adet|Gün Adet|Maliyet
                        df_raw = df_raw.iloc[1:].copy()
                        df_raw = df_raw.rename(columns={
                            0:"Kurum", 1:"2.Adet", 2:"Pozisyon",
                            3:"2.Pay", 4:"1.Adet", 5:"GunlukF", 6:"Maliyet"
                        })
                        df_raw["Adet Fark"] = pd.to_numeric(df_raw.get("GunlukF", 0), errors="coerce").fillna(0)
                        df_raw["HaftaF"] = 0.0
                        df_raw["AyF"]    = 0.0
                        df_raw["UcAyF"]  = 0.0
                        df_raw["1.Pay"]  = 0.0

                    elif any("ADET FARK" in x.upper() for x in ilk_satir):
                        # Dönemlik format: Kurum|1.Adet|1.TL|1.Pay%|2.Adet|2.TL|2.Pay%|Adet Fark|TL Fark|Değişim%
                        df_raw = df_raw.iloc[1:].copy()
                        df_raw = df_raw.rename(columns={
                            0:"Kurum",   1:"1.Adet",   2:"1.TL",
                            3:"1.Pay",   4:"2.Adet",   5:"2.TL",
                            6:"2.Pay",   7:"Adet Fark", 8:"TL Fark",
                            9:"Degisim"
                        })
                        df_raw["GunlukF"] = df_raw["Adet Fark"]
                        df_raw["HaftaF"]  = 0.0
                        df_raw["AyF"]     = 0.0
                        df_raw["UcAyF"]   = 0.0

                    else:
                        # Hızlı Takas: Kurum|Takas(Son)|%|Takas(İlk)|%|Adet Fark|%|...|GünlükF|HaftaF|AyF|ÜçAyF
                        df_raw = df_raw.iloc[2:].copy()
                        df_raw = df_raw.rename(columns={
                            0:"Kurum",   1:"2.Adet",  2:"2.Pay",
                            3:"1.Adet",  4:"1.Pay",   5:"Adet Fark",
                            9:"GunlukF", 10:"HaftaF", 11:"AyF", 12:"UcAyF"
                        })

                    # ── NORMALİZE ────────────────────────────────────────────
                    df_raw = df_raw[df_raw["Kurum"].notna() &
                                    df_raw["Kurum"].astype(str).str.strip().ne("") &
                                    ~df_raw["Kurum"].astype(str).str.upper().str.contains("TOPLAM|KURUM", na=False)]

                    for c in ["2.Adet","1.Adet","Adet Fark","GunlukF","HaftaF","AyF","UcAyF"]:
                        if c in df_raw.columns:
                            df_raw[c] = pd.to_numeric(
                                df_raw[c].astype(str)
                                    .str.replace(".", "", regex=False)
                                    .str.replace(",", ".", regex=False),
                                errors="coerce"
                            ).fillna(0)

                    for c in ["2.Pay","1.Pay"]:
                        if c in df_raw.columns:
                            df_raw[c] = pd.to_numeric(
                                df_raw[c].astype(str)
                                    .str.replace(",", ".", regex=False)
                                    .str.replace("%", "", regex=False),
                                errors="coerce"
                            ).fillna(0)

                    df_raw["Kurum"] = df_raw["Kurum"].astype(str).str.strip().str.upper()

                    # Tüm object kolonları string'e zorla
                    for col in df_raw.columns:
                        if df_raw[col].dtype == object:
                            df_raw[col] = df_raw[col].astype(str)

                    # Tarihi standart formata çevir: DD.MM.YYYY → YYYYMMDD
                    from datetime import datetime as _dt
                    try:
                        if "." in tarih:
                            _d = _dt.strptime(tarih.strip(), "%d.%m.%Y")
                        elif "-" in tarih:
                            _d = _dt.strptime(tarih.strip(), "%Y-%m-%d")
                        else:
                            _d = _dt.strptime(tarih.strip(), "%Y%m%d")
                        donem_std = _d.strftime("%Y%m%d")
                    except:
                        donem_std = tarih.strip()
                    df_raw["hisse"]          = hisse_kod
                    df_raw["donem"]          = donem_std
                    df_raw["yukleme_tarihi"] = datetime.now().strftime("%Y-%m-%d")

                    # Standart kolonları garantile
                    STANDART_KOLONLAR = ["Kurum","2.Adet","2.Pay","1.Adet","1.Pay",
                                         "Adet Fark","GunlukF","HaftaF","AyF","UcAyF",
                                         "hisse","donem","yukleme_tarihi"]
                    for col in STANDART_KOLONLAR:
                        if col not in df_raw.columns:
                            df_raw[col] = 0.0 if col not in ["Kurum","hisse","donem","yukleme_tarihi"] else ""
                    df_raw = df_raw[STANDART_KOLONLAR]

                    DATA_DIR.mkdir(parents=True, exist_ok=True)
                    p = DATA_DIR / f"{hisse_kod}.parquet"
                    if p.exists():
                        mevcut  = pd.read_parquet(p)
                        # donem kolonunu string'e çevir, tip uyumsuzluğunu önle
                        mevcut["donem"] = mevcut["donem"].astype(str).str.strip()
                        mevcut  = mevcut[mevcut["donem"] != str(donem_std)]
                        df_raw["donem"] = str(donem_std)
                        df_yeni = pd.concat([mevcut, df_raw], ignore_index=True)
                    else:
                        df_yeni = df_raw
                    df_yeni.to_parquet(p, index=False)
                    yuklenen += 1

                if yuklenen > 0:
                    # Sinyal log güncelle
                    for hisse_kod in BEBEK_HİSSELER:
                        df_h = yukle(hisse_kod)
                        if not df_h.empty:
                            sinyal_guncelle(hisse_kod, df_h, BEBEK_HİSSELER[hisse_kod]["t2"])

                    st.success(f"✅ {yuklenen} hisse yüklendi — {tarih}")
                    st.rerun()
                else:
                    st.warning("Hiç hisse eşleşmedi. Sheet isimleri BEBEK_HİSSELER listesinde var mı?")
            except Exception as e:
                st.error(f"Hata: {e}")

    # ── ORTA PANEL: Satış Takibi ──────────────────────────────────────────────
    with col_orta:
        st.markdown("**📉 Satış Takibi**")
        st.caption("Kümülatif T2 düşüşü")

        for kod in BEBEK_HİSSELER:
            df_k = kumul_panel(kod)
            if df_k.empty:
                st.button(f"📂 {kod}", key=f"satis_btn_{kod}", use_container_width=True, disabled=True)
                continue

            # İlk dönemde en büyük 5 kurum — eşiksiz, sıra bazlı
            ilk5 = df_k.nlargest(5, "bas_pct")
            oyuncular = ilk5[ilk5["delta"] < -0.3].sort_values("delta")

            if oyuncular.empty:
                # %5+ oyuncu yok veya düşüş yok
                if st.button(f"✅ {kod}  ⚪ Sakin", key=f"satis_btn_{kod}", use_container_width=True):
                    st.session_state["sec_hisse"] = kod
                continue

            en_cok = oyuncular.iloc[0]
            dusus  = abs(en_cok["delta"])

            if dusus >= 2.0:
                etiket = "🔴 Boşalıyor"
            elif dusus >= 1.0:
                etiket = "🟠 Dikkat"
            else:
                etiket = "🟡 Azalıyor"

            if st.button(f"✅ {kod}  {etiket}", key=f"satis_btn_{kod}", use_container_width=True):
                st.session_state["sec_hisse"] = kod

    # ── SAĞ: Hisse detay ──────────────────────────────────────────────────────
    with col_sag:
        sec = st.session_state.get("sec_hisse", "ARFYE")
        bilgi = BEBEK_HİSSELER[sec]
        df_tum = yukle(sec)

        st.markdown(f"## {sec}")

        c1,c2,c3,c4 = st.columns(4)
        c1.metric("T2 Dolaşım", f"{bilgi['t2']/1_000_000:.1f}M")
        c2.metric("Halka Arz",  bilgi["arz"])
        c3.metric("Dönem",      df_tum["donem"].nunique() if not df_tum.empty else 0)
        c4.metric("Aşama",      asama_tespit(df_tum, bilgi["t2"]))

        if df_tum.empty:
            st.info("Henüz veri yok. Sol panelden Excel yükle.")
            return

        donemler = sorted(df_tum["donem"].unique().tolist())

        # ════════════════════════════════════════════════════════════════════
        # BÖLÜM 0 — ALIŞ / SATIŞ ÖZET PANELİ (Ana Ekran)
        # ════════════════════════════════════════════════════════════════════
        son_donem  = donemler[-1]
        df_son     = df_tum[df_tum["donem"] == son_donem].copy()
        t2_total   = bilgi["t2"]

        # ── Yardımcı fonksiyonlar ────────────────────────────────────────────
        def t2pct(adet):
            return round(adet / t2_total * 100, 2) if t2_total > 0 else 0.0

        def onceki_t2pct(kurum_adi):
            """Önceki dönemdeki T2 oranı. Yoksa None."""
            if len(donemler) < 2: return None
            df_onc = df_tum[df_tum["donem"] == donemler[-2]]
            satir  = df_onc[df_onc["Kurum"] == kurum_adi]
            if satir.empty: return None
            return t2pct(satir["2.Adet"].sum())  # sum ile duplikasyonu önle

        def alis_alarm(fark_pct, onc_pct, cur_pct):
            """Alış tarafı alarm — mevcut T2 oranı bazlı."""
            if onc_pct is not None and onc_pct < 1.0 and cur_pct >= 1.0:
                return "🚨 YENİ GİRİŞ"
            if cur_pct >= 5.0: return "🔴 KRİTİK"
            if cur_pct >= 3.0: return "🟠 DİKKAT"
            if cur_pct >= 1.0: return "🟡 TAKİPTE"
            return ""

        def satis_alarm(onc_pct, cur_pct):
            """
            Satış tarafı alarm — önceki dönemden düşüş miktarına göre.
            Eşikler: düşüş %2+ → 🔴 Boşaltım, %1-2 → 🟠 Dikkat, 0-1 → 🟡 Azalıyor
            """
            if onc_pct is None or onc_pct == 0: return ""
            dusus = onc_pct - cur_pct  # pozitif = düşüş
            if dusus <= 0: return ""
            if dusus >= 2.0: return "🔴 BOŞALTIM!"
            if dusus >= 1.0: return "🟠 DİKKAT"
            return "🟡 AZALIYOR"

        # ── T2 bazlı hesapla ─────────────────────────────────────────────────
        # Duplikasyon önle — aynı kurum birden fazla satırda olabilir
        df_son = df_son.groupby("Kurum", as_index=False).agg({
            "2.Adet": "sum", "2.Pay": "sum", "Adet Fark": "sum"
        })

        df_son["_cur_pct"]  = df_son["2.Adet"].apply(t2pct)
        df_son["_fark_pct"] = df_son["Adet Fark"].abs().apply(t2pct)

        alislar  = df_son[df_son["Adet Fark"] > 0].sort_values("Adet Fark", ascending=False)
        satislar = df_son[df_son["Adet Fark"] < 0].sort_values("Adet Fark", ascending=True)

        # ── Koordineli grup tanımları ─────────────────────────────────────────
        GRUP_BIRIKIM = ["BANK-OF-AMERICA","CITIBANK","ALLBATROSS"]
        GRUP_GELISME = ["TERA YATIRIM","BULLS YATIRIM","DESTEK YATIRIM","A1 CAPITAL","ALNUS YATIRIM"]
        GRUP_DAGITIM = ["INFO YATIRIM"]
        GRUP_FON     = ["YATIRIM FONLARI","EMEKLILIK"]
        TUM_KOORD    = GRUP_BIRIKIM + GRUP_GELISME + GRUP_DAGITIM + GRUP_FON

        def kurum_grup(kurum_adi):
            k = kurum_adi.upper()
            if any(g in k for g in GRUP_BIRIKIM): return "BİRİKİM"
            if any(g in k for g in GRUP_GELISME): return "GELİŞME"
            if any(g in k for g in GRUP_DAGITIM): return "DAĞITIM"
            if any(g in k for g in GRUP_FON):     return "FON"
            return "PERAKENDE"

        def en_buyuk_alisci(min_adet=50000):
            """Alış tarafındaki en büyük kurumu ve grubunu döndür."""
            if alislar.empty: return None, None
            r = alislar.iloc[0]
            if r["Adet Fark"] < min_adet: return None, None
            return r["Kurum"], kurum_grup(r["Kurum"])

        # ── ALIŞ TARAFI ──────────────────────────────────────────────────────
        col_alis, col_satis = st.columns(2)

        with col_alis:
            st.markdown("### 🟢 ALIŞ TARAFI")
            st.caption(f"📅 {son_donem} | T2 Bazlı Oran")

            if alislar.empty:
                st.info("Bu dönemde alış yok.")
            else:
                for _, r in alislar.head(8).iterrows():
                    cur_pct  = r["_cur_pct"]
                    onc_pct  = onceki_t2pct(r["Kurum"])
                    alarm    = alis_alarm(r["_fark_pct"], onc_pct, cur_pct)
                    kat      = kurum_kategori(r["Kurum"])

                    if onc_pct is None or onc_pct == 0:
                        trend = "🆕 YENİ"
                    else:
                        delta = cur_pct - onc_pct
                        trend = f"▲+{delta:.1f}%" if delta > 0 else f"▼{delta:.1f}%"

                    st.markdown(
                        f"{kat} **{r['Kurum'][:22]}**  \n"
                        f"`+{int(r['Adet Fark']):,}` &nbsp;|&nbsp; "
                        f"T2: **%{cur_pct:.2f}** &nbsp;|&nbsp; {trend} {alarm}"
                    )

        # ── SATIŞ TARAFI ─────────────────────────────────────────────────────
        with col_satis:
            st.markdown("### 🔴 SATIŞ TARAFI")
            st.caption(f"📅 {son_donem} | T2 Bazlı Oran")

            if satislar.empty:
                st.info("Bu dönemde satış yok.")
            else:
                for _, r in satislar.head(8).iterrows():
                    cur_pct = r["_cur_pct"]
                    onc_pct = onceki_t2pct(r["Kurum"])
                    alarm   = satis_alarm(onc_pct, cur_pct)
                    kat     = kurum_kategori(r["Kurum"])

                    if cur_pct == 0:
                        trend = "🚪 TAMAMEN ÇIKTI"
                    elif onc_pct is not None:
                        delta = cur_pct - onc_pct  # negatif olacak
                        trend = f"▼{delta:.1f}%"
                    else:
                        trend = "🚪 ÇIKTI"

                    # Boşaltım varsa alıcıyı göster
                    ekstra = ""
                    if alarm == "🔴 BOŞALTIM!":
                        buyuk_alisci, alisci_grup = en_buyuk_alisci()
                        if buyuk_alisci:
                            ekstra = f" → En büyük alıcı: **{buyuk_alisci[:18]}** ({alisci_grup})"

                    st.markdown(
                        f"{kat} **{r['Kurum'][:22]}**  \n"
                        f"`{int(r['Adet Fark']):,}` &nbsp;|&nbsp; "
                        f"T2: **%{cur_pct:.2f}** &nbsp;|&nbsp; {trend} {alarm}{ekstra}"
                    )

        # ── UYARI PANELİ — Boşaltım + Alıcı analizi ─────────────────────────
        st.divider()
        mesajlar = []

        if not alislar.empty and not satislar.empty:

            alan_list  = alislar["Kurum"].str.upper().tolist()
            satan_list = satislar["Kurum"].str.upper().tolist()

            def grup_var(k_list, grup):
                return any(any(g in k for g in grup) for k in k_list)

            # Boşaltım tespiti — satış tarafında koordineli + %2+ düşüş var mı?
            bosalanlar = []
            for _, r in satislar.iterrows():
                onc = onceki_t2pct(r["Kurum"])
                if onc and (onc - r["_cur_pct"]) >= 2.0:
                    g = kurum_grup(r["Kurum"])
                    if g in ["BİRİKİM","GELİŞME","DAĞITIM"]:
                        bosalanlar.append((r["Kurum"], g, onc, r["_cur_pct"]))

            for kurum_adi, grup, onc, cur in bosalanlar:
                buyuk_alisci, alisci_grup = en_buyuk_alisci()
                if buyuk_alisci is None:
                    mesajlar.append(("warning",
                        f"🔴 **BOŞALTIM** — {kurum_adi[:20]} satıyor (%{onc:.1f}→%{cur:.1f}). Alıcı belirsiz."))
                elif alisci_grup in ["BİRİKİM","GELİŞME"]:
                    # Koordineli → Koordineli = MAL DEĞİŞİMİ
                    mesajlar.append(("info",
                        f"🔄 **MAL DEĞİŞİMİ** — **{kurum_adi[:18]}** ({grup}) satıyor, "
                        f"**{buyuk_alisci[:18]}** ({alisci_grup}) alıyor. Koordineli devir!"))
                elif alisci_grup == "FON":
                    mesajlar.append(("success",
                        f"🟢 **KURUMSAL DEVİR** — {kurum_adi[:18]} çıkıyor, "
                        f"Yatırım Fonu devralıyor. Sağlıklı geçiş."))
                else:
                    # Koordineli satıyor + perakende alıyor = DAĞITIM
                    mesajlar.append(("warning",
                        f"⚠️ **DAĞITIM** — **{kurum_adi[:18]}** ({grup}) satıyor, "
                        f"alıcılar dağınık/perakende. Halka satış var!"))

            # Gelişme grubundan Birikim grubuna el değişimi (Adet Fark bazlı)
            if grup_var(satan_list, GRUP_BIRIKIM) and grup_var(alan_list, GRUP_GELISME):
                mesajlar.append(("info",
                    "🔄 **EL DEĞİŞİMİ** — BofA/Citi çıkıyor, Tera/Bulls devralıyor. Gelişme fazına geçiş!"))

        if mesajlar:
            st.markdown("#### 🚨 Uyarı Paneli")
            for tip, mesaj in mesajlar:
                if tip == "info":    st.info(mesaj)
                elif tip == "success": st.success(mesaj)
                elif tip == "warning": st.warning(mesaj)
                elif tip == "error":   st.error(mesaj)
        else:
            st.caption("✅ Özel uyarı yok.")

        st.divider()

        # ════════════════════════════════════════════════════════════════════
        # BÖLÜM 1 — AKTİF TAKAS PASTA GRAFİĞİ
        # ════════════════════════════════════════════════════════════════════
        st.divider()
        st.markdown("### 🥧 Aktif Takas Dağılımı")

        son_donem_data = df_tum[df_tum["donem"] == donemler[-1]].copy()
        son_donem_data = son_donem_data[son_donem_data["2.Adet"] > 0].copy()
        son_donem_data = son_donem_data.sort_values("2.Adet", ascending=False)

        if not son_donem_data.empty:
            # Top 6 + Diğer
            top6 = son_donem_data.head(6)
            diger = son_donem_data.iloc[6:]["2.Adet"].sum()

            labels = top6["Kurum"].str[:20].tolist()
            values = top6["2.Adet"].tolist()

            if diger > 0:
                labels.append("DİĞER")
                values.append(diger)

            fig_pie = go.Figure(go.Pie(
                labels=labels,
                values=values,
                hole=0.35,
                textinfo="label+percent",
                textfont=dict(size=11),
            ))
            fig_pie.update_layout(
                height=320,
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="white"),
                legend=dict(orientation="h", y=-0.2),
                margin=dict(l=0, r=0, t=20, b=0)
            )
            st.plotly_chart(fig_pie, use_container_width=True)

            # Tablo olarak da göster
            tablo = top6[["Kurum","2.Adet","2.Pay"]].copy()
            tablo["2.Adet"] = tablo["2.Adet"].apply(lambda x: f"{int(x):,}")
            tablo["2.Pay"]  = tablo["2.Pay"].apply(lambda x: f"%{x:.2f}")
            tablo["Kat"]    = tablo["Kurum"].apply(kurum_kategori)
            tablo["Kurum"]  = tablo["Kat"] + " " + tablo["Kurum"].str[:25]
            st.dataframe(
                tablo[["Kurum","2.Adet","2.Pay"]].rename(columns={"2.Adet":"Adet","2.Pay":"Pay%"}),
                use_container_width=True, hide_index=True, height=220
            )

        # ════════════════════════════════════════════════════════════════════
        # BÖLÜM 2 — DÖNEM DETAYI (Karşılaştırmalı)
        # ════════════════════════════════════════════════════════════════════
        st.divider()
        st.markdown("### 🔍 Dönem Detayı — Pozisyon Değişimi")

        if len(donemler) >= 2:
            son    = donemler[-1]
            onceki = donemler[-2]

            df_son    = df_tum[df_tum["donem"] == son].copy()
            df_onceki = df_tum[df_tum["donem"] == onceki].copy()

            # Duplikasyon önle — Kurum bazında grupla (aynı kurum birden fazla satırda olabilir)
            df_son    = df_son.groupby("Kurum", as_index=False).agg({"2.Adet": "sum", "2.Pay": "sum"})
            df_onceki = df_onceki.groupby("Kurum", as_index=False).agg({"2.Adet": "sum", "2.Pay": "sum"})

            # Sıralama ekle
            df_son["sira_son"]       = df_son["2.Adet"].rank(ascending=False, method="min").astype(int)
            df_onceki["sira_onceki"] = df_onceki["2.Adet"].rank(ascending=False, method="min").astype(int)

            # Birleştir
            df_merge = df_son[["Kurum","2.Adet","2.Pay","sira_son"]].merge(
                df_onceki[["Kurum","2.Adet","2.Pay","sira_onceki"]].rename(
                    columns={"2.Adet":"onceki_adet","2.Pay":"onceki_pay"}
                ),
                on="Kurum", how="outer"
            ).fillna(0)

            df_merge["degisim_adet"] = df_merge["2.Adet"] - df_merge["onceki_adet"]
            df_merge["degisim_pay"]  = df_merge["2.Pay"]  - df_merge["onceki_pay"]
            df_merge["sira_degisim"] = df_merge["sira_onceki"] - df_merge["sira_son"]

            # Sırala — en büyük değişim üstte
            df_merge = df_merge.sort_values("degisim_adet", ascending=False)

            # Görüntü hazırla
            rows = []
            for _, r in df_merge.iterrows():
                if r["2.Adet"] == 0 and r["onceki_adet"] == 0:
                    continue
                kat = kurum_kategori(r["Kurum"])

                # Sıra değişimi
                sira_d = int(r["sira_degisim"]) if r["sira_onceki"] > 0 else 0
                if sira_d > 3:
                    sira_str = f"🚀 +{sira_d} sıra"
                elif sira_d > 0:
                    sira_str = f"📈 +{sira_d}"
                elif sira_d < -3:
                    sira_str = f"⬇️ {sira_d} sıra"
                elif sira_d < 0:
                    sira_str = f"📉 {sira_d}"
                elif r["onceki_adet"] == 0:
                    sira_str = "🆕 YENİ"
                elif r["2.Adet"] == 0:
                    sira_str = "🚪 ÇIKTI"
                else:
                    sira_str = "—"

                # Yön
                if r["degisim_adet"] > 100000:
                    yon = "🟢 ALIYOR"
                elif r["degisim_adet"] > 0:
                    yon = "🟡 Az Alış"
                elif r["degisim_adet"] < -100000:
                    yon = "🔴 SATIYOR"
                elif r["degisim_adet"] < 0:
                    yon = "🟠 Az Satış"
                else:
                    yon = "⚪ Sabit"

                rows.append({
                    "Kurum":      f"{kat} {r['Kurum'][:22]}",
                    "Mevcut%":    f"%{r['2.Pay']:.2f}",
                    "Önceki%":    f"%{r['onceki_pay']:.2f}",
                    "Değişim":    f"{int(r['degisim_adet']):+,}",
                    "Pay Δ":      f"{r['degisim_pay']:+.2f}%",
                    "Sıra":       sira_str,
                    "Yön":        yon,
                })

            df_goster = pd.DataFrame(rows)
            st.caption(f"🏷️ {sec} | 📅 {onceki} → {son}")
            st.dataframe(df_goster, use_container_width=True,
                         hide_index=True, height=500)

        else:
            st.info("Karşılaştırma için en az 2 dönem gerekli. Bir gün daha veri yükle!")

            # Tek dönem varsa sadece mevcut göster
            sec_donem = donemler[-1]
            df_donem  = df_tum[df_tum["donem"] == sec_donem].copy()
            alan  = df_donem[df_donem["Adet Fark"] > 0].sort_values("Adet Fark", ascending=False)
            satan = df_donem[df_donem["Adet Fark"] < 0].sort_values("Adet Fark", ascending=True)

            col_a, col_s = st.columns(2)
            with col_a:
                st.markdown("**🟢 Alan Kurumlar**")
                for _, r in alan.iterrows():
                    kat = kurum_kategori(r["Kurum"])
                    st.markdown(f"{kat} **{r['Kurum'][:25]}** `+{int(r['Adet Fark']):,}` %{r['2.Pay']:.2f}")
            with col_s:
                st.markdown("**🔴 Satan Kurumlar**")
                for _, r in satan.iterrows():
                    kat = kurum_kategori(r["Kurum"])
                    st.markdown(f"{kat} **{r['Kurum'][:25]}** `{int(r['Adet Fark']):,}` %{r['2.Pay']:.2f}")

        # ════════════════════════════════════════════════════════════════════
        # BÖLÜM 3 — AŞAMA ANALİZİ
        # ════════════════════════════════════════════════════════════════════
        st.divider()
        st.markdown("### 🧠 Akıllı Para Aşama Analizi")

        # Son dönemde koordineli kurumlar
        koord_kurumlar = ["BANK-OF-AMERICA","CITIBANK","ALLBATROSS","TERA YATIRIM",
                          "BULLS YATIRIM","INFO YATIRIM","DESTEK YATIRIM","A1 CAPITAL"]

        rows = []
        for d in donemler:
            df_d = df_tum[df_tum["donem"]==d]
            for k in koord_kurumlar:
                satir = df_d[df_d["Kurum"].str.contains(k, na=False)]
                if not satir.empty:
                    r = satir.iloc[0]
                    rows.append({
                        "Dönem": d[:10],
                        "Kurum": k,
                        "1.Pay%": f"%{float(r['1.Pay']):.2f}",
                        "2.Pay%": f"%{float(r['2.Pay']):.2f}",
                        "Hareket": f"+{int(r['Adet Fark']):,}" if r['Adet Fark']>0 else f"{int(r['Adet Fark']):,}",
                        "Yön": "🟢 GİRİYOR" if r['Adet Fark']>0 else "🔴 ÇIKIYOR" if r['Adet Fark']<0 else "⚪ SABIT"
                    })

        if rows:
            df_koord = pd.DataFrame(rows)
            st.dataframe(df_koord, use_container_width=True, hide_index=True, height=300)
        else:
            st.info("Koordineli kurum hareketi tespit edilmedi.")

        # Aşama uyarısı
        asama = asama_tespit(df_tum, bilgi["t2"])
        if "Dağıtım" in asama:
            st.error(f"⚠️ **{asama}** — INFO Yatırım yeni girmiş! Dağıtım başlıyor olabilir.")
        elif "Birikim" in asama:
            st.info(f"**{asama}** — BofA/Citibank/Allbatross alıyor. Erken dönem.")
        elif "Fon" in asama:
            st.success(f"**{asama}** — Yatırım fonları büyütüyor. Momentum yaklaşıyor.")
        elif "Gelişme" in asama:
            st.warning(f"**{asama}** — TERA/Bulls/Destek devrede.")
        else:
            st.info(f"**{asama}**")
