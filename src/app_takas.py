"""
app_takas.py — TAKAS ANALİZİ Sekmesi
app.py'ye import edilir.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from takas_depo import (
    dosyalar_yukle, donemler_listele, kurumlar_listele,
    kurum_net_pozisyon, alarm_listesi, takas_analiz,
    hisse_kurum_detay, trend_analiz, donem_sil,
    BUYUK_YERLI, AKILLI_PARA, FON_YABANCI, KURUMLAR
)


def aylik_trend_analiz(df_csv: pd.DataFrame) -> dict:
    """6 aylık veriden sinyal tespiti."""
    if df_csv.empty:
        return {}
    df = df_csv[df_csv["tip"] == "aylik"].copy()
    if df.empty:
        return {}
    donemler = sorted(df["donem"].unique())
    if len(donemler) < 2:
        return {}

    sonuclar = {
        "sifirdan_giris": [], "buyuk_alim": [], "duzenli_artis": [],
        "sifira_cikis": [], "buyuk_satis": [], "duzenli_azalis": [],
    }

    for hisse in df["hisse"].unique():
        for kurum in df["kurum"].unique():
            k_df = df[(df["hisse"]==hisse) & (df["kurum"]==kurum)].sort_values("donem")
            if k_df.empty or len(k_df) < 2: continue
            oranlar = k_df["oran2"].tolist()
            d_list  = k_df["donem"].tolist()
            ilk = oranlar[0]; son = oranlar[-1]; fark = son - ilk
            kron = " → ".join([f"%{o:.1f}" for o in oranlar])

            if ilk < 0.1 and son >= 1.0:
                sonuclar["sifirdan_giris"].append({"Hisse":hisse,"Kurum":kurum,
                    "İlk":d_list[0],"Son":d_list[-1],"Son %":round(son,2),"Kronoloji":kron})

            for i in range(1, len(oranlar)):
                d_fark = oranlar[i] - oranlar[i-1]
                if d_fark >= 3.0:
                    sonuclar["buyuk_alim"].append({"Hisse":hisse,"Kurum":kurum,
                        "Dönem":d_list[i],"Önceki %":round(oranlar[i-1],2),
                        "Sonraki %":round(oranlar[i],2),"Artış":round(d_fark,2),"Kronoloji":kron})
                if d_fark <= -3.0:
                    sonuclar["buyuk_satis"].append({"Hisse":hisse,"Kurum":kurum,
                        "Dönem":d_list[i],"Önceki %":round(oranlar[i-1],2),
                        "Sonraki %":round(oranlar[i],2),"Düşüş":round(d_fark,2),"Kronoloji":kron})

            if len(oranlar) >= 3:
                son3 = oranlar[-3:]
                if all(son3[i]>son3[i-1] for i in range(1,len(son3))) and son3[-1]>=0.5:
                    sonuclar["duzenli_artis"].append({"Hisse":hisse,"Kurum":kurum,
                        "Son %":round(son,2),"Toplam":round(fark,2),"Kronoloji":kron})
                if all(son3[i]<son3[i-1] for i in range(1,len(son3))) and son3[0]>=0.5:
                    sonuclar["duzenli_azalis"].append({"Hisse":hisse,"Kurum":kurum,
                        "Son %":round(son,2),"Toplam":round(fark,2),"Kronoloji":kron})

            if ilk >= 1.0 and son < 0.1:
                sonuclar["sifira_cikis"].append({"Hisse":hisse,"Kurum":kurum,
                    "İlk %":round(ilk,2),"Kronoloji":kron})

    return {k: pd.DataFrame(v) for k, v in sonuclar.items()}


def _kart(hisse, kurum, renk, detay, kron):
    st.markdown(
        f"""<div style='border-left:4px solid {renk};padding:5px 10px;
        margin:3px 0;background:#FAFAFA;border-radius:0 4px 4px 0;'>
        <b>{hisse}</b> — <span style='color:{renk}'>{kurum}</span>
        <span style='float:right;font-weight:bold;color:{renk}'>{detay}</span><br>
        <small style='color:#666'>{kron}</small>
        </div>""", unsafe_allow_html=True
    )


def aylik_trend_goster():
    """Aylık trend — hisse bazlı, takip kurumları, %5+ filtresi."""
    from takas_depo import _oku, AKILLI_PARA, KURUMLAR

    df = _oku()
    if df.empty:
        st.info("Aylık veri yok.")
        return

    df_aylik = df[df["tip"] == "aylik"].copy()
    if df_aylik.empty:
        st.info("Aylık veri bulunamadı.")
        return

    donemler = sorted(df_aylik["donem"].unique())
    son_donem = donemler[-1]
    st.caption(f"📅 Mevcut aylar: {' | '.join(donemler)} | **Son: {son_donem}**")

    # ── Filtreler ─────────────────────────────────────────────────────────────
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        sec_ay = st.selectbox("Ay seç", donemler, index=len(donemler)-1, key="trend_ay")
    with col2:
        min_pct = st.number_input("Min pozisyon %", value=5.0, step=1.0, key="trend_min_pct")
    with col3:
        min_kurum = st.number_input("Min kurum sayısı", value=1, step=1, min_value=1, key="trend_min_kurum")

    # ── Seçili ay verisi ──────────────────────────────────────────────────────
    df_sec = df_aylik[df_aylik["donem"] == sec_ay].copy()

    # Sadece takip kurumları
    df_sec = df_sec[df_sec["kurum"].isin(KURUMLAR)]

    # Min %5 filtresi
    df_sec = df_sec[df_sec["oran2"] >= min_pct]

    if df_sec.empty:
        st.warning(f"'{sec_ay}' döneminde %{min_pct}+ pozisyonlu takip kurumu bulunamadı.")
        return

    # ── Önceki ay için trend hesapla ──────────────────────────────────────────
    onceki_ay = donemler[donemler.index(sec_ay)-1] if donemler.index(sec_ay) > 0 else None

    if onceki_ay:
        df_onc = df_aylik[df_aylik["donem"] == onceki_ay][["hisse","kurum","oran2"]].rename(
            columns={"oran2": "onceki_oran"}
        )
        df_sec = df_sec.merge(df_onc, on=["hisse","kurum"], how="left")
        df_sec["degisim"] = (df_sec["oran2"] - df_sec["onceki_oran"].fillna(0)).round(2)
        df_sec["yeni_giris"] = df_sec["onceki_oran"].isna() | (df_sec["onceki_oran"] < 1.0)
    else:
        df_sec["onceki_oran"] = 0
        df_sec["degisim"] = df_sec["oran2"]
        df_sec["yeni_giris"] = True

    # ── Hisse bazlı grupla ────────────────────────────────────────────────────
    rows = []
    for hisse, grp in df_sec.groupby("hisse"):
        grp = grp.sort_values("oran2", ascending=False)

        kurumlar_str = "  ".join([
            f"**{r['kurum']}** %{r['oran2']:.1f}" +
            (f" 🆕" if r["yeni_giris"] else
             f" ▲%{r['degisim']:.1f}" if r["degisim"] > 0.5 else
             f" ▼%{abs(r['degisim']):.1f}" if r["degisim"] < -0.5 else "")
            for _, r in grp.iterrows()
        ])

        toplam    = grp["oran2"].sum()
        kurum_say = len(grp)
        yeni_say  = grp["yeni_giris"].sum()
        artan_say = (grp["degisim"] > 0.5).sum()

        # Alarm seviyesi
        if kurum_say >= 3 and toplam >= 20:
            alarm = "🔴 KRİTİK"
        elif kurum_say >= 2 and toplam >= 10:
            alarm = "🟠 GÜÇLÜ"
        elif yeni_say > 0:
            alarm = "🟡 YENİ GİRİŞ"
        elif artan_say >= 1:
            alarm = "🟢 ARTIYOR"
        else:
            alarm = "⚪ İZLE"

        # Trend ikonu (son 3 ay)
        trend_str = ""
        if onceki_ay:
            trend_vals = []
            for d in donemler[-3:]:
                v = df_aylik[(df_aylik["hisse"]==hisse) & 
                             (df_aylik["donem"]==d) &
                             (df_aylik["kurum"].isin(KURUMLAR))]["oran2"].sum()
                trend_vals.append(v)
            if len(trend_vals) >= 2:
                if all(trend_vals[i] > trend_vals[i-1] for i in range(1, len(trend_vals))):
                    trend_str = "🚀 Sürekli Artış"
                elif trend_vals[-1] > trend_vals[-2]:
                    trend_str = "📈 Son Ay Arttı"
                elif trend_vals[-1] < trend_vals[-2]:
                    trend_str = "📉 Son Ay Azaldı"
                else:
                    trend_str = "➡️ Sabit"

        rows.append({
            "Hisse":        hisse,
            "Kurumlar":     kurumlar_str,
            "Toplam %":     round(toplam, 1),
            "Kurum Sayısı": kurum_say,
            "Trend":        trend_str,
            "Alarm":        alarm,
        })

    df_tablo = pd.DataFrame(rows)
    df_tablo = df_tablo[df_tablo["Kurum Sayısı"] >= int(min_kurum)]
    df_tablo = df_tablo.sort_values(["Alarm","Toplam %"], ascending=[True, False])

    if df_tablo.empty:
        st.warning("Filtre kriterlerine uyan hisse yok.")
        return

    # ── Özet metrikler ────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Toplam Hisse", len(df_tablo))
    c2.metric("🔴 Kritik",    len(df_tablo[df_tablo["Alarm"]=="🔴 KRİTİK"]))
    c3.metric("🟠 Güçlü",     len(df_tablo[df_tablo["Alarm"]=="🟠 GÜÇLÜ"]))
    c4.metric("🟡 Yeni Giriş",len(df_tablo[df_tablo["Alarm"]=="🟡 YENİ GİRİŞ"]))

    st.divider()

    # ── Alarm kartları ────────────────────────────────────────────────────────
    for _, r in df_tablo.iterrows():
        alarm = r["Alarm"]
        renk = {
            "🔴 KRİTİK":    "#C0392B",
            "🟠 GÜÇLÜ":     "#E67E22",
            "🟡 YENİ GİRİŞ":"#F39C12",
            "🟢 ARTIYOR":   "#1A7A3E",
            "⚪ İZLE":       "#717D7E",
        }.get(alarm, "#717D7E")

        st.markdown(
            f"""<div style='border-left:5px solid {renk};padding:8px 12px;
            margin:5px 0;background:#FAFAFA;border-radius:0 6px 6px 0;'>
            <span style='font-size:16px;font-weight:bold;'>{r['Hisse']}</span>
            <span style='color:{renk};margin-left:10px;font-weight:bold;'>{alarm}</span>
            <span style='float:right;color:#888;'>Toplam: <b>%{r['Toplam %']}</b> | {r['Kurum Sayısı']} kurum | {r['Trend']}</span><br>
            <small style='color:#555;'>{r['Kurumlar']}</small>
            </div>""",
            unsafe_allow_html=True
        )


def takas_sekmesi():
    """Ana takas analizi sekmesi."""

    tab1, tab2 = st.tabs(["📊 Takas Analizi", "🧠 Smart Money"])

    with tab1:
        _takas_analiz_tab()

    with tab2:
        _smart_money_tab()


def _smart_money_tab():
    """Smart Money Dashboard — kurum_takas.csv'den direkt hesaplar."""
    import os

    BUYUK_YERLI = ['IS_YATIRIM','HALK_YATIRIM','GARANTI','VAKIF',
                   'AK_YATIRIM','YAPI_KREDI','TEB','ZIRAAT_YATIRIM','DENIZ_YATIRIM']
    FONLAR      = ['YABANCI','YAT_FONLARI','EMEKLILIK','MIDAS']
    AKILLI      = ['MARBAS','BULLS','PUSULA','ALNUS','A1_CAPITAL']
    DAGITICI    = ['INFO','TERA']
    TUM_KURUMLAR = BUYUK_YERLI + FONLAR + AKILLI + DAGITICI

    SENARYOLAR = {
        "🏦 Büyük Yerli → Fon/Yabancı" : ("Büyük Yerli çıkıyor, Fon/Yabancı alıyor — AL sinyali", BUYUK_YERLI, FONLAR),
        "⚡ Dağıtıcı → Büyük Yerli"     : ("INFO/TERA satıyor, Büyük Yerli alıyor — AL sinyali",   DAGITICI,    BUYUK_YERLI),
        "🏦 Büyük Yerli → Akıllı Para"  : ("Büyük Yerli çıkıyor, Akıllı Para alıyor — AL sinyali", BUYUK_YERLI, AKILLI),
        "🔄 Akıllı Para → Dağıtıcı"    : ("MARBAS/BULLS satıyor, INFO/TERA alıyor — DİKKAT",       AKILLI,      DAGITICI),
    }

    MIN_POZISYON     = 1.5
    MIN_HANDOFF_GUCU = 2.0

    def ds(d):
        d = str(d).strip()
        try:
            if len(d)==8 and d.isdigit(): return int(d)
            elif len(d)==7 and '_' in d:
                y,m=d.split('_'); return int(y)*10000+int(m)*100+50
            elif len(d)==9 and '_' in d:
                ym,w=d.split('_'); return int(ym)*100+int(w)*10
        except: pass
        return 0

    @st.cache_data(ttl=1800)
    def handoff_hesapla():
        import os
        # Parquet varsa hızlı oku
        for path in ["src/data/takas/handoff_sonuclar.parquet",
                     "data/takas/handoff_sonuclar.parquet"]:
            if os.path.exists(path):
                return pd.read_parquet(path)
        return pd.DataFrame()

    # ── UI ────────────────────────────────────────────────────────
    st.markdown("### 🧠 Smart Money Dashboard")
    st.caption("kurum_takas.csv'den otomatik hesaplanır · 30dk önbellek")

    col_g, col_b = st.columns([2,5])
    with col_g:
        if st.button("🔄 Yenile", key="sm_yenile"):
            st.cache_data.clear()
            st.rerun()
    with col_b:
        st.info("Yeni takas yükledikten sonra 🔄 Yenile'ye bas.")

    with st.spinner("Handoff hesaplanıyor..."):
        hdf = handoff_hesapla()

    if hdf.empty:
        st.warning("⚠️ Handoff verisi bulunamadı. `bist_app/` klasöründe `python handoff_analiz.py` çalıştırın.")
        return

    st.success(f"✅ {len(hdf):,} handoff | {hdf['hisse'].nunique()} hisse | {hdf['donem'].nunique()} dönem")

    # ── Senaryo Özeti ─────────────────────────────────────────────
    st.markdown("#### 📊 Senaryo Özeti")
    ozet_rows = []
    for senaryo, (aciklama, sat_list, al_list) in SENARYOLAR.items():
        filtre = hdf['satan'].isin(sat_list) & hdf['alan'].isin(al_list)
        df_f   = hdf[filtre]
        son    = df_f[df_f['donem_sira'] >= 20260400]
        vals   = df_f['getiri_60g'].dropna()
        win_60 = round((vals > 0).mean() * 100, 0) if len(vals) >= 3 else None
        ort_60 = round(vals.mean(), 1) if len(vals) >= 3 else None
        ozet_rows.append({
            "Senaryo"         : senaryo,
            "Toplam"          : len(df_f),
            "Win 60g%"        : win_60,
            "Ort 60g%"        : ort_60,
            "Son Dönem Sinyal": len(son),
            "Son Dönem Hisse" : son['hisse'].nunique(),
        })

    ozet_df = pd.DataFrame(ozet_rows)

    def renk_win(val):
        try:
            v = float(val)
            if v >= 65: return "background-color:#1a472a;color:white"
            if v >= 55: return "background-color:#2d6a4f;color:white"
            if v >= 45: return "background-color:#52b788"
        except: pass
        return ""

    st.dataframe(
        ozet_df.style.map(renk_win, subset=["Win 60g%"]),
        use_container_width=True, hide_index=True
    )

    st.divider()

    # ── Aktif Sinyaller ───────────────────────────────────────────
    st.markdown("#### 🔥 Aktif Sinyaller (Son Dönem)")
    senaryo_sec = st.selectbox("Senaryo seç:",
        ["🔍 Tüm Senaryolar"] + list(SENARYOLAR.keys()),
        key="sm_senaryo_sec"
    )

    if senaryo_sec == "🔍 Tüm Senaryolar":
        aktif = hdf[hdf['donem_sira'] >= 20260400].sort_values(
            ['donem_sira','toplam_guc'], ascending=[False,False])
    else:
        sat_list = SENARYOLAR[senaryo_sec][1]
        al_list  = SENARYOLAR[senaryo_sec][2]
        aktif = hdf[
            hdf['satan'].isin(sat_list) &
            hdf['alan'].isin(al_list) &
            (hdf['donem_sira'] >= 20260400)
        ].sort_values(['donem_sira','toplam_guc'], ascending=[False,False])

    hisse_ozet = aktif.groupby('hisse').agg(
        sinyal        = ('hisse','count'),
        max_guc       = ('toplam_guc','max'),
        ilk_donem     = ('donem', 'last'),
        son_donem     = ('donem','first'),
        son_donem_sira= ('donem_sira','max'),
        ilk_donem_sira= ('donem_sira','min'),
        satan_kurumlar= ('satan', lambda x: ', '.join(x.unique()[:3])),
        alan_kurumlar = ('alan',  lambda x: ', '.join(x.unique()[:3])),
    ).reset_index().sort_values('max_guc', ascending=False)

    if hisse_ozet.empty:
        st.info("Bu senaryoda son dönemde sinyal yok.")
        return

    # Arama kutusu
    arama = st.text_input("🔍 Hisse Ara", placeholder="ONCSM, TATEN, ENSRI...",
                          key="sm_arama")
    if arama:
        hisse_ozet = hisse_ozet[
            hisse_ozet['hisse'].str.contains(arama.strip().upper())
        ].reset_index(drop=True)

    st.success(f"✅ **{len(hisse_ozet)} hisse** — {senaryo_sec}")

    # ── Sinyal Hafızası ───────────────────────────────────────────
    import json, os
    from datetime import date, datetime
    HAFIZA_PATH = "src/data/takas/sinyal_hafizasi.json"
    os.makedirs("src/data/takas", exist_ok=True)

    def hafiza_yukle():
        if os.path.exists(HAFIZA_PATH):
            with open(HAFIZA_PATH, encoding='utf-8') as f:
                return json.load(f)
        return {}

    def hafiza_kaydet(h):
        with open(HAFIZA_PATH, 'w', encoding='utf-8') as f:
            json.dump(h, f, ensure_ascii=False, indent=2)

    hafiza = hafiza_yukle()

    # ── Tile Görünümü ─────────────────────────────────────────────
    cols_per_row = 4
    for row_start in range(0, min(len(hisse_ozet), 24), cols_per_row):
        cols = st.columns(cols_per_row)
        for j, col in enumerate(cols):
            idx = row_start + j
            if idx >= len(hisse_ozet): break
            r = hisse_ozet.iloc[idx]
            hisse = r['hisse']
            h_kayit = hafiza.get(hisse, {})

            # Durum rengi
            if r['son_donem_sira'] >= 20260510:
                renk = "#1a472a"  # yeşil — aktif
            elif r['son_donem_sira'] >= 20260400:
                renk = "#7d4e00"  # sarı — zayıflıyor
            else:
                renk = "#4a1a1a"  # kırmızı — eski

            with col:
                if st.button(
                    f"🔍 {hisse}",
                    key=f"tile_{hisse}_{senaryo_sec[:5]}",
                    use_container_width=True
                ):
                    st.session_state['sm_secili_hisse'] = hisse

                st.markdown(
                    f"""<div style='background:{renk};border-radius:6px;
                    padding:8px;margin:-8px 0 8px 0;text-align:center;'>
                    <span style='color:#aaa;font-size:11px;'>Güç: {r['max_guc']:.1f} · {r['sinyal']} sinyal</span><br>
                    <span style='color:#6c9;font-size:10px;'>{r['satan_kurumlar']}</span><br>
                    <span style='color:#888;font-size:10px;'>{r['son_donem']}</span>
                    </div>""",
                    unsafe_allow_html=True
                )

    # ── Seçili Hisse Detayı ───────────────────────────────────────
    secili = st.session_state.get('sm_secili_hisse')
    if secili and secili in hisse_ozet['hisse'].values:
        st.divider()
        st.markdown(f"## 🟢 {secili} — Sinyal Detayı")

        r = hisse_ozet[hisse_ozet['hisse']==secili].iloc[0]

        # ── Dinamik tarih eşikleri ────────────────────────────────
        from datetime import date, timedelta
        bugun_sira = int(date.today().strftime('%Y%m%d'))
        bir_ay_once = int((date.today() - timedelta(days=30)).strftime('%Y%m%d'))
        iki_ay_once = int((date.today() - timedelta(days=60)).strftime('%Y%m%d'))

        # Durum hesapla — dinamik
        if r['son_donem_sira'] >= bir_ay_once:
            durum = "🟢 Aktif"
            durum_renk = "green"
        elif r['son_donem_sira'] >= iki_ay_once:
            durum = "🟡 Zayıflıyor"
            durum_renk = "orange"
        else:
            durum = "🔴 Eski Sinyal"
            durum_renk = "red"

        # ── Güncel fiyat çek ─────────────────────────────────────
        import yfinance as yf
        guncel_fiyat = None
        try:
            fiyat_df = yf.download(f"{secili}.IS", period="10d",
                                   progress=False, auto_adjust=True)
            if isinstance(fiyat_df.columns, pd.MultiIndex):
                fiyat_df.columns = fiyat_df.columns.get_level_values(0)
            if not fiyat_df.empty:
                guncel_fiyat = float(fiyat_df['Close'].dropna().iloc[-1])
        except:
            pass

        # ── Hafıza güncelle ───────────────────────────────────────
        if secili not in hafiza:
            hafiza[secili] = {}

        if 'ilk_sinyal' not in hafiza[secili]:
            hafiza[secili]['ilk_sinyal'] = r['ilk_donem']
        if 'kayit_tarihi' not in hafiza[secili]:
            hafiza[secili]['kayit_tarihi'] = str(date.today())
        if not hafiza[secili].get('giris_fiyat') and guncel_fiyat:
            hafiza[secili]['giris_fiyat'] = guncel_fiyat

        hafiza[secili]['son_guncelleme'] = str(date.today())
        hafiza[secili]['durum'] = durum
        hafiza[secili]['son_guc'] = float(r['max_guc'])
        hafiza[secili]['sinyal_sayisi'] = int(r['sinyal'])
        hafiza_kaydet(hafiza)

        giris_fiyat = hafiza[secili].get('giris_fiyat')
        kayit_tarihi = hafiza[secili].get('kayit_tarihi', str(date.today()))
        try:
            takipte_gun = (date.today() - date.fromisoformat(kayit_tarihi)).days
        except:
            takipte_gun = 0

        if guncel_fiyat and giris_fiyat and float(giris_fiyat) > 0:
            getiri = round((guncel_fiyat / float(giris_fiyat) - 1) * 100, 2)
        else:
            getiri = None

        # ── Metrik satır 1 ────────────────────────────────────────
        c1, c2, c3 = st.columns(3)
        c1.metric("📅 İlk Sinyal", r['ilk_donem'])
        c2.metric("🔢 Sinyal Adedi", r['sinyal'])
        c3.metric("💪 Max Güç", f"{r['max_guc']:.1f}")

        # ── Metrik satır 2 ────────────────────────────────────────
        c4, c5, c6, c7 = st.columns(4)
        c4.metric("💰 Giriş Fiyatı", f"{float(giris_fiyat):.2f} ₺" if giris_fiyat else "—")
        c5.metric("📈 Güncel Fiyat", f"{guncel_fiyat:.2f} ₺" if guncel_fiyat else "—")
        if getiri is not None:
            c6.metric("🎯 Getiri", f"%{getiri:+.1f}", delta=f"{getiri:+.1f}%")
        else:
            c6.metric("🎯 Getiri", "—")
        c7.metric("⏱️ Takipte", f"{takipte_gun} gün", delta=durum)

        # ── Satan / Alan ──────────────────────────────────────────
        c8, c9 = st.columns(2)
        c8.metric("📤 Satan", r['satan_kurumlar'])
        c9.metric("📥 Alan", r['alan_kurumlar'])

        # ── Not alanı — otomatik kayıt ────────────────────────────
        mevcut_not = hafiza[secili].get('not', '')
        yeni_not = st.text_area("📝 Not", value=mevcut_not,
                                key=f"not_{secili}", height=80,
                                placeholder="Örn: Fon alımı devam ediyor, ENSRI MSCI beklentisi...")
        if yeni_not != mevcut_not:
            hafiza[secili]['not'] = yeni_not
            hafiza_kaydet(hafiza)

        # ── Kronoloji ─────────────────────────────────────────────
        st.markdown("#### 📜 Handoff Kronolojisi")
        gecmis = hdf[hdf['hisse']==secili].sort_values('donem_sira', ascending=False)

        def renk_satir(row):
            alan  = str(row.get('alan',''))
            satan = str(row.get('satan',''))
            if any(k in alan  for k in ['YABANCI','YAT_FONLARI','EMEKLILIK','MIDAS']):
                return ['background-color:#d5f5e3;color:#1a5276']*len(row)
            if any(k in satan for k in ['INFO','TERA']):
                return ['background-color:#fadbd8;color:#922b21']*len(row)
            return ['']*len(row)

        cols_goster = ['donem','alarm_tipi','satan','satan_once%','satan_simdi%',
                       'alan','alan_once%','alan_simdi%']
        # Sadece mevcut kolonları göster
        cols_var = [c for c in cols_goster if c in gecmis.columns]
        if 'toplam_guc' not in cols_var:
            cols_var.append('toplam_guc')
        styled = gecmis[cols_var].head(20).style.apply(renk_satir, axis=1)
        st.dataframe(styled, use_container_width=True, hide_index=True)

        # ── Özet metrikler ────────────────────────────────────────
        cm1, cm2, cm3 = st.columns(3)
        cm1.metric("Toplam Handoff", len(gecmis))
        cm2.metric("Net Akış Gücü", f"{gecmis['toplam_guc'].sum():.1f}")
        cm3.metric("En Yüksek Güç", f"{gecmis['toplam_guc'].max():.1f}")

        # En aktif kurumlar
        ca1, ca2 = st.columns(2)
        ca1.metric("En Aktif Satan",
                   gecmis['satan'].value_counts().index[0] if len(gecmis) > 0 else "—")
        ca2.metric("En Aktif Alan",
                   gecmis['alan'].value_counts().index[0] if len(gecmis) > 0 else "—")

    # ── Tüm Açık Sinyaller Tablosu ────────────────────────────────
    with st.expander("📊 Tüm Açık Sinyaller (Hafıza)", expanded=False):
        hafiza = hafiza_yukle()
        if hafiza:
            satirlar = []
            for hisse, kayit in hafiza.items():
                satirlar.append({
                    'Hisse'       : hisse,
                    'İlk Sinyal'  : kayit.get('ilk_sinyal','—'),
                    'Kayıt'       : kayit.get('kayit_tarihi','—'),
                    'Güç'         : kayit.get('son_guc', 0),
                    'Sinyal'      : kayit.get('sinyal_sayisi', 0),
                    'Durum'       : kayit.get('durum','—'),
                    'Giriş ₺'     : kayit.get('giris_fiyat'),
                    'Not'         : kayit.get('not',''),
                })
            hafiza_df = pd.DataFrame(satirlar).sort_values('Güç', ascending=False)
            st.dataframe(hafiza_df, use_container_width=True, hide_index=True)
        else:
            st.info("Henüz takip edilen sinyal yok. Tile'a tıklayarak ekle.")

    st.divider()
    st.dataframe(hisse_ozet, use_container_width=True, hide_index=True)


# ── CACHE'Lİ HESAPLAMA ────────────────────────────────────────────────────────
@st.cache_data(ttl=600)
def _birikimli_hesapla(tip: str, son_x_donem: int, min_ardisik: int = 2) -> tuple:
    """
    Tüm geçmişten kümülatif net alım/satım hesaplar.
    tip: haftalik / aylik / gunluk
    son_x_donem: son kaç döneme bak
    Returns: (toplayanlar, satanlar, son_donem, donem_listesi)
    """
    from takas_depo import _oku, BUYUK_YERLI, AKILLI_PARA, FON_YABANCI
    df = _oku()
    if df.empty:
        return [], [], None, []

    df = df[df["tip"] == tip].copy()
    if df.empty:
        return [], [], None, []

    # Short kapama düzeltmesi
    if "short_kapama" in df.columns:
        df.loc[df["short_kapama"] == True, "dolasim_pct"] = \
            df.loc[df["short_kapama"] == True, "oran2"]

    donemler = sorted(df["donem"].astype(str).unique())
    if not donemler:
        return [], [], None, []

    son_donem    = donemler[-1]
    secili_donm  = donemler[-son_x_donem:]

    df_sec = df[df["donem"].isin(secili_donm)].copy()

    def grup(k):
        if k in BUYUK_YERLI: return "Büyük Yerli"
        if k in AKILLI_PARA: return "Akıllı Para"
        if k in FON_YABANCI: return "Fon/Yabancı"
        return "Diğer"

    toplayanlar, satanlar = [], []

    for (hisse, kurum), kdf in df_sec.sort_values("donem").groupby(["hisse", "kurum"]):
        if len(kdf) < min_ardisik:
            continue
        vals      = kdf["dolasim_pct"].tolist()
        son_n     = vals  # tüm seçili dönemler
        oran2     = float(kdf["oran2"].iloc[-1])
        trend_str = " → ".join([f"{v:+.1f}%" for v in son_n[-4:]])
        toplam    = round(sum(vals), 2)
        g         = grup(kurum)

        if sum(son_n) >= 3:
            surekli = all(v > 0 for v in son_n) and all(son_n[i] >= son_n[i-1] for i in range(1, len(son_n)))
            toplayanlar.append({
                "hisse": hisse, "kurum": kurum, "grup": g,
                "toplam": toplam, "son_pct": round(son_n[-1], 2),
                "oran2": round(oran2, 2), "donem_say": len(kdf),
                "surekli": surekli, "trend_str": trend_str,
            })
        elif sum(son_n) <= -3:
            surekli = all(v < 0 for v in son_n) and all(son_n[i] <= son_n[i-1] for i in range(1, len(son_n)))
            satanlar.append({
                "hisse": hisse, "kurum": kurum, "grup": g,
                "toplam": abs(toplam), "son_pct": abs(round(son_n[-1], 2)),
                "oran2": round(oran2, 2), "donem_say": len(kdf),
                "surekli": surekli, "trend_str": trend_str,
            })

    return toplayanlar, satanlar, son_donem, secili_donm


@st.cache_data(ttl=300)
def _fiyat_cek(hisse: str) -> tuple:
    """yfinance'dan son kapanış + % değişim. Returns (fiyat, degisim_pct)"""
    try:
        import yfinance as yf
        t = yf.Ticker(f"{hisse}.IS")
        h = t.history(period="5d")
        if len(h) >= 2:
            son   = float(h["Close"].iloc[-1])
            onceki= float(h["Close"].iloc[-2])
            return round(son, 2), round((son/onceki - 1)*100, 2)
        elif len(h) == 1:
            return round(float(h["Close"].iloc[-1]), 2), None
    except:
        pass
    return None, None


def _detay_panel_inline(hisse: str, secili_donm: list = None):
    """
    Seçili hissenin seçilen dönemdeki net alış/satış dağılımı.
    Matriks gibi: sol=alanlar, sağ=satanlar + tahta değişimi özeti.
    """
    from takas_depo import _oku
    df = _oku()
    if df.empty:
        return
    h_df = df[df["hisse"] == hisse].copy()
    if h_df.empty:
        return

    # Short kapama düzeltmesi
    if "short_kapama" in h_df.columns:
        h_df.loc[h_df["short_kapama"] == True, "dolasim_pct"] = \
            h_df.loc[h_df["short_kapama"] == True, "oran2"]

    # Dönem filtresi
    if secili_donm:
        h_df = h_df[h_df["donem"].isin(secili_donm)]

    if h_df.empty:
        st.caption("Seçilen dönemde veri yok.")
        return

    # ── Tahta (tks2) değişimi ─────────────────────────────────────────────────
    # İlk ve son dönem tks2 ortalamasından değişim hesapla
    tks2_ilk = h_df.groupby("donem")["tks2"].mean()
    if len(tks2_ilk) >= 2:
        tks2_bas  = float(tks2_ilk.iloc[0])
        tks2_son  = float(tks2_ilk.iloc[-1])
        tks2_fark = tks2_son - tks2_bas
        tks2_pct  = round((tks2_fark / tks2_bas * 100), 2) if tks2_bas > 0 else 0
    else:
        tks2_fark = 0
        tks2_pct  = 0

    # ── Kurum bazında kümülatif topla ─────────────────────────────────────────
    ozet = h_df.groupby("kurum").agg(
        net_pct  =("dolasim_pct", "sum"),
        net_adet =("adet_fark",   "sum"),
        t2_oran  =("oran2",       "last"),
    ).reset_index()
    ozet["net_pct"]  = ozet["net_pct"].round(2)
    ozet["net_adet"] = ozet["net_adet"].round(0).astype(int)

    alanlar  = ozet[ozet["net_pct"] > 0].sort_values("net_pct", ascending=False)
    satanlar = ozet[ozet["net_pct"] < 0].sort_values("net_pct", ascending=True)

    kurum_alan_top  = round(alanlar["net_pct"].sum(), 2)
    kurum_satan_top = round(satanlar["net_pct"].sum(), 2)
    kurum_net       = round(kurum_alan_top + kurum_satan_top, 2)

    # ── Tahta yorumu ──────────────────────────────────────────────────────────
    if tks2_pct < -1 and kurum_net > 0:
        tahta_yorum = "⚠️ Dağıtım — Kurumlar alıyor ama tahta küçülüyor"
        tahta_renk  = "#C0392B"
    elif tks2_pct > 1 and kurum_net > 0:
        tahta_yorum = "✅ Gerçek Birikim — Tahta büyüyor, kurumlar alıyor"
        tahta_renk  = "#1A7A3E"
    elif tks2_pct < -1 and kurum_net < 0:
        tahta_yorum = "📉 Çıkış — Hem tahta küçülüyor hem kurumlar satıyor"
        tahta_renk  = "#7B0000"
    elif tks2_pct > 1 and kurum_net < 0:
        tahta_yorum = "🔄 Mal Değişimi — Tahta büyüyor, kurumlar satıyor"
        tahta_renk  = "#E67E22"
    else:
        tahta_yorum = "➡️ Sabit"
        tahta_renk  = "#888"

    donem_str = f"{secili_donm[0]} → {secili_donm[-1]}" if secili_donm else "Tüm dönemler"

    # ── Başlık + Tahta özeti ──────────────────────────────────────────────────
    st.markdown(
        f"<div style='background:#EAF4FB;border-left:4px solid #1A5276;"
        f"border-radius:4px;padding:6px 12px;margin:4px 0;'>"
        f"<b>📊 {hisse}</b> "
        f"<span style='font-size:11px;color:#888;'>· {donem_str}</span>"
        f"</div>",
        unsafe_allow_html=True
    )

    # Tahta özet satırı
    tks2_renk = "#C0392B" if tks2_pct < 0 else "#1A7A3E"
    st.markdown(
        f"<div style='background:#F8F9FA;border-radius:4px;padding:6px 12px;"
        f"margin:4px 0;display:flex;justify-content:space-between;align-items:center;'>"
        f"<span style='font-size:12px;'>"
        f"📦 Tahta: <b style='color:{tks2_renk};'>{tks2_pct:+.2f}%</b>"
        f" &nbsp;|&nbsp; "
        f"🏦 Kurumlar net: <b style='color:{'#1A7A3E' if kurum_net>0 else '#C0392B'};'>"
        f"{kurum_net:+.2f}%</b>"
        f" &nbsp;|&nbsp; "
        f"<b style='color:{tahta_renk};'>{tahta_yorum}</b>"
        f"</span></div>",
        unsafe_allow_html=True
    )

    ca, cs = st.columns(2)

    with ca:
        st.markdown("**📈 Net Alanlar**")
        gorulu = alanlar[alanlar["net_pct"] >= 2]
        if gorulu.empty:
            st.caption("—")
        else:
            toplam_alan = gorulu["net_pct"].sum()
            for _, r in gorulu.iterrows():
                pay = round(r["net_pct"] / toplam_alan * 100, 0) if toplam_alan else 0
                st.markdown(
                    f"<div style='border-left:3px solid #1A5276;padding:3px 8px;"
                    f"margin:2px 0;background:#F8FBFF;'>"
                    f"<b style='color:#1A5276;font-size:12px;'>{r['kurum']}</b>"
                    f"<span style='float:right;color:#1A7A3E;font-weight:bold;font-size:12px;'>"
                    f"+{r['net_pct']:.2f}%</span><br>"
                    f"<span style='font-size:10px;color:#888;'>"
                    f"T2:%{r['t2_oran']:.2f} · "
                    f"{r['net_adet']:+,} adet · %{pay:.0f} pay</span>"
                    f"</div>",
                    unsafe_allow_html=True
                )

    with cs:
        st.markdown("**📉 Net Satanlar**")
        gorulu_sat = satanlar[satanlar["net_pct"] <= -2]
        if gorulu_sat.empty:
            st.caption("Eşiği geçen satış yok")
        else:
            toplam_satan = abs(gorulu_sat["net_pct"].sum())
            for _, r in gorulu_sat.iterrows():
                pay = round(abs(r["net_pct"]) / toplam_satan * 100, 0) if toplam_satan else 0
                st.markdown(
                    f"<div style='border-left:3px solid #C0392B;padding:3px 8px;"
                    f"margin:2px 0;background:#FFF8F8;'>"
                    f"<b style='color:#C0392B;font-size:12px;'>{r['kurum']}</b>"
                    f"<span style='float:right;color:#C0392B;font-weight:bold;font-size:12px;'>"
                    f"{r['net_pct']:.2f}%</span><br>"
                    f"<span style='font-size:10px;color:#888;'>"
                    f"T2:%{r['t2_oran']:.2f} · "
                    f"{r['net_adet']:+,} adet · %{pay:.0f} pay</span>"
                    f"</div>",
                    unsafe_allow_html=True
                )


@st.cache_data(ttl=600)
@st.cache_data(ttl=600)
def _altin_oran_hesapla(tip: str, son_x_donem: int,
                         min_kons: float = 0, min_net: float = 0) -> list:
    """
    Altın Oran hesaplama.
    - T2 konsantrasyonu: TÜM tiplerdeki en son snapshot'tan (tip bağımsız, sabit)
    - Net değişim: seçilen tip + son_x_donem'den
    - Kronoloji: seçilen tip'teki dönem bazlı hareketler (detay için)
    """
    from takas_depo import _oku, BUYUK_YERLI, AKILLI_PARA, FON_YABANCI
    df = _oku()
    if df.empty:
        return []

    if "short_kapama" in df.columns:
        df.loc[df["short_kapama"] == True, "dolasim_pct"] = \
            df.loc[df["short_kapama"] == True, "oran2"]

    def grup(k):
        if k in BUYUK_YERLI: return "Büyük Yerli"
        if k in AKILLI_PARA: return "Akıllı Para"
        if k in FON_YABANCI: return "Fon/Yabancı"
        return "Diğer"

    # ── T2 Snapshot: tüm veri içinde her hisse+kurum için EN SON oran2 ────────
    idx_son  = df.groupby(["hisse", "kurum"])["donem"].idxmax()
    snap_df  = df.loc[idx_son][["hisse", "kurum", "oran2"]].copy()
    snap_df  = snap_df[snap_df["oran2"] > 0]

    # ── Seçilen tip + dönem için net değişim ve kronoloji ─────────────────────
    df_tip   = df[df["tip"] == tip].copy()
    donemler = sorted(df_tip["donem"].astype(str).unique())
    if not donemler:
        return []

    son_donem   = donemler[-1]
    secili_donm = donemler[-son_x_donem:]

    # Net değişim (seçili dönemde kurum bazlı toplam)
    degisim_df = df_tip[df_tip["donem"].isin(secili_donm)].groupby(
        ["hisse", "kurum"]
    ).agg(net_degisim=("dolasim_pct", "sum")).reset_index()

    # Kronoloji: dönem × kurum pivot (detay paneli için)
    kronoloji_df = df_tip[df_tip["donem"].isin(secili_donm)][
        ["hisse", "kurum", "donem", "dolasim_pct", "oran2"]
    ].copy()

    sonuclar = []

    for hisse, h_snap in snap_df.groupby("hisse"):
        h_snap = h_snap.sort_values("oran2", ascending=False)
        toplam_t2 = h_snap["oran2"].sum()
        if toplam_t2 < 5:
            continue

        ilk3    = h_snap.head(3)["kurum"].tolist()
        ilk3_t2 = h_snap.head(3)["oran2"].sum()
        kons    = round(ilk3_t2 / toplam_t2 * 100, 1)

        h_deg     = degisim_df[degisim_df["hisse"] == hisse]
        ilk3_deg  = round(h_deg[h_deg["kurum"].isin(ilk3)]["net_degisim"].sum(), 2) \
                    if not h_deg.empty else 0.0
        diger_deg = round(h_deg[~h_deg["kurum"].isin(ilk3)]["net_degisim"].sum(), 2) \
                    if not h_deg.empty else 0.0

        # Filtre
        if min_kons > 0 and kons < min_kons:
            continue
        if min_net > 0 and ilk3_deg < min_net:
            continue

        skor = round(kons * 0.4 + max(ilk3_deg, 0) * 0.6, 1)

        # Kurum detayları (T2 snapshot + net değişim)
        kurum_detay = []
        for _, kr in h_snap.head(5).iterrows():
            k_deg = h_deg[h_deg["kurum"] == kr["kurum"]]["net_degisim"]
            nd    = round(float(k_deg.iloc[0]), 2) if not k_deg.empty else 0.0
            kurum_detay.append({
                "kurum": kr["kurum"],
                "oran2": round(float(kr["oran2"]), 2),
                "net_degisim": nd,
                "grup": grup(kr["kurum"]),
            })

        # Kronoloji verisi — dönem × (ilk3 kurumlar + diğer toplamı)
        h_kron = kronoloji_df[kronoloji_df["hisse"] == hisse]
        kron_rows = []
        for donem in secili_donm:
            d_df = h_kron[h_kron["donem"] == donem]
            if d_df.empty:
                continue
            row = {"donem": donem}
            for kurum in ilk3:
                k_row = d_df[d_df["kurum"] == kurum]
                row[kurum] = round(float(k_row["dolasim_pct"].iloc[0]), 2) \
                             if not k_row.empty else None
                # T2 pozisyon (oran2) da ekle
                row[f"{kurum}_t2"] = round(float(k_row["oran2"].iloc[0]), 2) \
                                     if not k_row.empty else None
            diger = d_df[~d_df["kurum"].isin(ilk3)]["dolasim_pct"].sum()
            row["Diğerleri"] = round(diger, 2)
            kron_rows.append(row)

        sonuclar.append({
            "hisse": hisse,
            "konsantrasyon": kons,
            "ilk3_t2": round(ilk3_t2, 1),
            "toplam_t2": round(toplam_t2, 1),
            "ilk3_deg": ilk3_deg,
            "diger_deg": diger_deg,
            "skor": skor,
            "kurumlar": kurum_detay,
            "ilk3": ilk3,
            "kronoloji": kron_rows,  # ← yeni
        })

    return sorted(sonuclar, key=lambda x: -x["skor"])


def _birikimli_tab():
    """📈 BİRİKMİŞ TAKİP — 3 kolonlu görünüm."""

    # ── Filtreler ─────────────────────────────────────────────────────────────
    f1, f2, f3, f4 = st.columns([2, 2, 3, 1])
    with f1:
        tip = st.selectbox("Veri Tipi:", ["haftalik", "aylik", "gunluk"],
                           key="bir_tip")
    with f2:
        son_x = st.select_slider("Son dönem:", options=[2, 4, 6, 8, 10, 12],
                                  value=6, key="bir_sonx")
    with f3:
        grup_f = st.multiselect("Grup:", ["Akıllı Para","Büyük Yerli","Fon/Yabancı","Diğer"],
                                 default=[], key="bir_grup",
                                 placeholder="Tümü göster")
    with f4:
        st.markdown("<br>", unsafe_allow_html=True)
        fiyat_goster = st.checkbox("💰 Fiyat", value=True, key="bir_fiyat")

    with st.spinner("Hesaplanıyor..."):
        toplayanlar, satanlar, son_donem, secili_donm = _birikimli_hesapla(tip, son_x)
        # min_kons ve min_net=0 ile tüm veriyi çek, filtreyi UI'da uygula
        altin_liste = _altin_oran_hesapla(tip, son_x, min_kons=0, min_net=0)

    if son_donem is None:
        st.info(f"{tip.upper()} veri bulunamadı.")
        return

    st.caption(
        f"📅 Son dönem: **{son_donem}** · {len(secili_donm)} dönem · "
        f"🟢 {len(toplayanlar)} alan · 🔴 {len(satanlar)} satan · "
        f"🥇 {len(altin_liste)} altın oran"
    )

    # Grup filtresi
    if grup_f:
        toplayanlar = [r for r in toplayanlar if r["grup"] in grup_f]
        satanlar    = [r for r in satanlar    if r["grup"] in grup_f]

    # ── Hisse bazında birleştir ───────────────────────────────────────────────
    def _hisse_ozet(liste):
        ozet = {}
        for r in liste:
            h = r["hisse"]
            if h not in ozet:
                ozet[h] = {
                    "hisse": h, "toplam": 0, "kurumlar": [],
                    "grup": r["grup"], "surekli": r["surekli"],
                    "donem_say": r["donem_say"], "oran2": r["oran2"],
                    "trend_str": r["trend_str"],
                }
            ozet[h]["toplam"] = round(ozet[h]["toplam"] + r["toplam"], 2)
            ozet[h]["kurumlar"].append({
                "kurum": r["kurum"], "toplam": r["toplam"],
                "oran2": r["oran2"], "surekli": r["surekli"]
            })
            if r["surekli"]:
                ozet[h]["surekli"] = True
        for h in ozet:
            ozet[h]["kurumlar"].sort(key=lambda x: -x["toplam"])
        return sorted(ozet.values(), key=lambda x: -x["toplam"])

    top_ozet = _hisse_ozet(toplayanlar)
    sat_ozet = _hisse_ozet(satanlar)

    GRUP_BG = {"Akıllı Para":"#D5F5E3","Büyük Yerli":"#D6EAF8",
               "Fon/Yabancı":"#F9EBEA","Diğer":"#F4F6F7"}
    GRUP_FG = {"Akıllı Para":"#1A5276","Büyük Yerli":"#1A5276",
               "Fon/Yabancı":"#922B21","Diğer":"#666"}

    # ── Standart kart ────────────────────────────────────────────────────────
    def _kart(r, pozitif, col_idx):
        hisse   = r["hisse"]
        surekli = r["surekli"]
        grup    = r["grup"]
        skey    = f"bir_sec_{'al' if pozitif else 'sat'}"
        secili  = st.session_state.get(skey) == hisse
        if pozitif:
            renk = "#0E4D92" if surekli else "#1A7A3E"
            ikon = "🚀" if surekli else "🟢"
            pct_str = f"+{r['toplam']:.1f}%"
        else:
            renk = "#7B0000" if surekli else "#C0392B"
            ikon = "📉" if surekli else "🔴"
            pct_str = f"-{r['toplam']:.1f}%"

        bg = "#DCF0FF" if secili else "#FAFAFA"

        fiyat_html = ""
        if fiyat_goster:
            fiyat, degisim = _fiyat_cek(hisse)
            if fiyat:
                d_renk = "#1A7A3E" if (degisim or 0) >= 0 else "#C0392B"
                d_str  = f"+{degisim:.1f}%" if (degisim or 0) >= 0 else f"{degisim:.1f}%"
                fiyat_html = (f"<span style='float:right;font-size:11px;"
                              f"color:{d_renk};font-weight:bold;'>"
                              f"{fiyat:.2f}₺ {d_str}</span>")

        kurum_html = " · ".join([
            f"<b>{k['kurum']}</b>({'🚀' if k['surekli'] else ''}%{k['oran2']:.1f})"
            for k in r["kurumlar"][:2]
        ])

        st.markdown(
            f"<div style='border-left:4px solid {renk};padding:6px 10px;"
            f"margin:3px 0;background:{bg};border-radius:0 6px 6px 0;'>"
            f"<div style='display:flex;justify-content:space-between;'>"
            f"<span><b style='font-size:13px;'>{hisse}</b> "
            f"<span style='font-size:10px;background:{GRUP_BG.get(grup,'#eee')};"
            f"color:{GRUP_FG.get(grup,'#666')};padding:1px 5px;border-radius:3px;'>{grup}</span>"
            f"</span><b style='color:{renk};font-size:14px;'>{ikon} {pct_str}</b></div>"
            f"<div style='font-size:11px;color:#555;margin-top:2px;'>{kurum_html}{fiyat_html}</div>"
            f"<div style='font-size:10px;color:#aaa;'>{r['donem_say']} dönem · {r['trend_str']}</div>"
            f"</div>",
            unsafe_allow_html=True
        )
        if st.button("▲ Kapat" if secili else f"🔍 {hisse}",
                     key=f"bir_btn_{'al' if pozitif else 'sat'}_{hisse}_{col_idx}",
                     use_container_width=True):
            st.session_state[skey] = None if secili else hisse
        if secili:
            _detay_panel_inline(hisse, secili_donm=list(secili_donm))

    # ── Altın Oran kartı ─────────────────────────────────────────────────────
    def _altin_kart(r, idx):
        hisse  = r["hisse"]
        skey   = "altin_sec"
        secili = st.session_state.get(skey) == hisse
        skor   = r["skor"]
        kons   = r["konsantrasyon"]

        if skor >= 50:
            renk = "#7D6608"; bg_header = "#FEF9E7"
        elif skor >= 35:
            renk = "#1A5276"; bg_header = "#EAF4FB"
        else:
            renk = "#1A7A3E"; bg_header = "#EAFAF1"

        bg = "#FFF8E1" if secili else "#FAFAFA"

        kurum_satirlar = ""
        for kr in r["kurumlar"][:3]:
            nd_renk = "#1A7A3E" if kr["net_degisim"] > 0 else "#C0392B"
            nd_str  = f"+{kr['net_degisim']:.1f}%" if kr["net_degisim"] > 0 \
                      else f"{kr['net_degisim']:.1f}%"
            kurum_satirlar += (
                f"<div style='font-size:11px;padding:1px 0;'>"
                f"<b style='color:#1A5276;'>{kr['kurum']}</b> "
                f"T2:<b>%{kr['oran2']:.1f}</b> "
                f"<span style='color:{nd_renk};font-weight:bold;'>{nd_str}</span></div>"
            )

        diger_renk = "#C0392B" if r["diger_deg"] <= 0 else "#E67E22"
        diger_str  = f"{r['diger_deg']:+.1f}%"

        fiyat_html = ""
        if fiyat_goster:
            fiyat, degisim = _fiyat_cek(hisse)
            if fiyat:
                d_renk = "#1A7A3E" if (degisim or 0) >= 0 else "#C0392B"
                d_str  = f"+{degisim:.1f}%" if (degisim or 0) >= 0 else f"{degisim:.1f}%"
                fiyat_html = (f"<span style='font-size:11px;color:{d_renk};"
                              f"font-weight:bold;float:right;'>{fiyat:.2f}₺ {d_str}</span>")

        st.markdown(
            f"<div style='border:2px solid {renk};border-radius:6px;"
            f"padding:8px 10px;margin:4px 0;background:{bg};'>"
            f"<div style='background:{bg_header};margin:-8px -10px 6px -10px;"
            f"padding:4px 10px;border-radius:4px 4px 0 0;"
            f"display:flex;justify-content:space-between;align-items:center;'>"
            f"<b style='font-size:14px;color:{renk};'>🥇 {hisse}</b>"
            f"<span style='font-size:12px;color:{renk};font-weight:bold;'>"
            f"Skor:{skor} · Kons:%{kons}</span></div>"
            f"{kurum_satirlar}"
            f"<div style='font-size:11px;margin-top:4px;border-top:1px solid #eee;padding-top:3px;'>"
            f"<span style='color:#888;'>Diğerleri: "
            f"<b style='color:{diger_renk};'>{diger_str}</b></span>"
            f"{fiyat_html}</div>"
            f"</div>",
            unsafe_allow_html=True
        )
        if st.button("▲ Kapat" if secili else f"🔍 {hisse}",
                     key=f"altin_btn_{hisse}_{idx}",
                     use_container_width=True):
            st.session_state[skey] = None if secili else hisse

        # ── Kronoloji detayı ─────────────────────────────────────────────────
        if secili:
            # Önce net alan/satan özeti
            _detay_panel_inline(hisse, secili_donm=list(secili_donm))
            st.markdown("---")
            kron = r.get("kronoloji", [])
            if not kron:
                st.caption("Kronoloji verisi yok.")
            else:
                ilk3 = r["ilk3"]
                # DataFrame oluştur
                kron_df = pd.DataFrame(kron)

                # Renklendirme fonksiyonu
                def _kron_renk(val):
                    if not isinstance(val, (int, float)) or pd.isna(val):
                        return "color:#aaa"
                    if val > 1:   return "background:#D5F5E3;color:#1A5276;font-weight:bold"
                    if val > 0:   return "color:#1A7A3E;font-weight:bold"
                    if val < -1:  return "background:#FADBD8;color:#C0392B;font-weight:bold"
                    if val < 0:   return "color:#C0392B"
                    return "color:#888"

                # Gösterilecek kolonlar: dönem + ilk3 kurumlar + Diğerleri
                # _t2 kolonlarını ayrı göster
                degisim_cols = [c for c in kron_df.columns
                                if c not in ["donem"] and not c.endswith("_t2")]
                t2_cols      = [c for c in kron_df.columns if c.endswith("_t2")]

                st.markdown(
                    f"<div style='font-size:11px;font-weight:bold;color:#1A5276;"
                    f"margin:6px 0 2px 0;'>📜 Dönem Kronolojisi — Net Değişim (%)</div>",
                    unsafe_allow_html=True
                )

                fmt = {c: "{:+.2f}" for c in degisim_cols if c != "donem"}
                styled = (
                    kron_df[["donem"] + degisim_cols]
                    .style
                    .map(_kron_renk, subset=degisim_cols)
                    .format(fmt, na_rep="—")
                )
                st.dataframe(styled, use_container_width=True,
                             hide_index=True, height=min(200, 38 + 35*len(kron_df)))

                # T2 pozisyon tablosu
                if t2_cols:
                    t2_display = kron_df[["donem"] + t2_cols].copy()
                    t2_display.columns = ["donem"] + [c.replace("_t2","") for c in t2_cols]
                    st.markdown(
                        "<div style='font-size:11px;font-weight:bold;color:#888;"
                        "margin:6px 0 2px 0;'>📊 T2 Pozisyon (%)</div>",
                        unsafe_allow_html=True
                    )
                    st.dataframe(
                        t2_display.style.format(
                            {c: "{:.2f}" for c in t2_display.columns if c != "donem"},
                            na_rep="—"
                        ),
                        use_container_width=True, hide_index=True,
                        height=min(200, 38 + 35*len(t2_display))
                    )

    # ── 3 Kolon ──────────────────────────────────────────────────────────────
    col_al, col_sat, col_altin = st.columns(3)

    with col_al:
        st.markdown(f"### 🟢 Birikmiş Alanlar ({len(top_ozet)})")
        if not top_ozet:
            st.caption("Bulunamadı.")
        else:
            for i, r in enumerate(top_ozet[:40]):
                _kart(r, pozitif=True, col_idx=i)

    with col_sat:
        st.markdown(f"### 🔴 Birikmiş Satanlar ({len(sat_ozet)})")
        if not sat_ozet:
            st.caption("Bulunamadı.")
        else:
            for i, r in enumerate(sat_ozet[:40]):
                _kart(r, pozitif=False, col_idx=i)

    with col_altin:
        st.markdown(f"### 🥇 Altın Oran ({len(altin_liste)})")

        fa1, fa2 = st.columns(2)
        with fa1:
            min_kons = st.slider("Min Kons%:", 0, 80, 0, 5, key="altin_kons")
        with fa2:
            min_net = st.slider("Min Net Alış%:", 0, 20, 0, 1, key="altin_net")

        # Filtreyi cache dışında, UI'da uygula
        gorulu = [
            r for r in altin_liste
            if r["konsantrasyon"] >= min_kons
            and r["ilk3_deg"] >= min_net
        ]

        st.caption(
            f"{'Filtre yok' if min_kons==0 and min_net==0 else f'Kons≥%{min_kons} · Net≥%{min_net}'}"
            f" → **{len(gorulu)}** hisse"
        )

        if not gorulu:
            st.info("Sinyal yok.")
        else:
            for i, r in enumerate(gorulu[:50]):
                _altin_kart(r, idx=i)


def _takas_analiz_tab():
    """Takas Analizi sekmesi."""

    # ── 4 Buton ──────────────────────────────────────────────────────────────
    b1, b2, b3, b4, _sp = st.columns([1, 1, 1, 1.2, 2.8])

    if "takas_mod" not in st.session_state:
        st.session_state["takas_mod"] = "haftalik"
    mod = st.session_state["takas_mod"]

    with b1:
        if st.button("📅 GÜNLÜK", use_container_width=True,
                     type="primary" if mod == "gunluk" else "secondary",
                     key="tb_gunluk"):
            st.session_state["takas_mod"] = "gunluk"
            st.rerun()
    with b2:
        if st.button("📆 HAFTALIK", use_container_width=True,
                     type="primary" if mod == "haftalik" else "secondary",
                     key="tb_haftalik"):
            st.session_state["takas_mod"] = "haftalik"
            st.rerun()
    with b3:
        if st.button("🗓️ AYLIK", use_container_width=True,
                     type="primary" if mod == "aylik" else "secondary",
                     key="tb_aylik"):
            st.session_state["takas_mod"] = "aylik"
            st.rerun()
    with b4:
        if st.button("📈 BİRİKMİŞ TAKİP", use_container_width=True,
                     type="primary" if mod == "birikimli" else "secondary",
                     key="tb_birikimli"):
            st.session_state["takas_mod"] = "birikimli"
            st.cache_data.clear()
            st.rerun()

    st.markdown("---")

    # ── BİRİKMİŞ TAKİP modu ──────────────────────────────────────────────────
    if mod == "birikimli":
        _birikimli_tab()
        return

    # ── GÜNLÜK / HAFTALIK / AYLIK ─────────────────────────────────────────────
    donemler = donemler_listele(mod)
    if not donemler:
        st.info(f"📂 {mod.upper()} veri yok. **Veri Yükle** sekmesinden ekleyin.")
        return

    c1, c2, c3 = st.columns([3, 1, 1])
    with c1:
        lbl = {"gunluk": "Günler:", "haftalik": "Haftalar:", "aylik": "Aylar:"}
        dfn = {"gunluk": 3, "haftalik": 4, "aylik": 3}
        secili_donemler = st.multiselect(
            lbl[mod], donemler, default=donemler[:dfn[mod]],
            key="takas_donem_sec"
        )
    with c2:
        min_pct = st.number_input("Min %:", value=0.5, step=0.1,
                                   min_value=0.0, max_value=10.0,
                                   key="takas_min_pct")
    with c3:
        st.markdown("<br>", unsafe_allow_html=True)
        ilk_giris = st.checkbox("🔵 İlk Giriş (%0→%3)", key="takas_ilk_giris")

    if not secili_donemler:
        st.warning("Dönem seçin.")
        return

    # ── %3+ Artış Yapan Kurumlar ──────────────────────────────────────────────
    from takas_depo import _oku as _t2
    t2_df = _t2()

    if not t2_df.empty:
        t2_sec = t2_df[t2_df["donem"].isin(secili_donemler)].copy()

        if "short_kapama" in t2_sec.columns:
            short_df     = t2_sec[t2_sec["short_kapama"] == True].copy()
            t2_sec_temiz = t2_sec[t2_sec["short_kapama"] != True].copy()
        else:
            short_df     = pd.DataFrame()
            t2_sec_temiz = t2_sec.copy()

        artis_df = t2_sec_temiz.groupby(["hisse","kurum"]).agg(
            dolasim_pct=("dolasim_pct","sum"),
            oran2=("oran2","last")
        ).reset_index()

        if not short_df.empty:
            s_ozet = short_df.groupby(["kurum","hisse"]).agg(
                oran2=("oran2","last"), dolasim_pct=("dolasim_pct","sum")
            ).reset_index()
            s_ozet = s_ozet[s_ozet["dolasim_pct"] >= max(3, min_pct)]
            if not s_ozet.empty:
                with st.expander("⚠️ Short Kapama Tespit Edildi", expanded=False):
                    for _, r in s_ozet.iterrows():
                        st.markdown(
                            f"<span style='font-size:12px;color:#E67E22;'>"
                            f"<b>{r['kurum']}</b> → <b>{r['hisse']}</b> "
                            f"T2:%{r['oran2']:.2f} Giriş:%{r['dolasim_pct']:.1f}</span>",
                            unsafe_allow_html=True
                        )

        if ilk_giris:
            df_onc = t2_df[~t2_df["donem"].isin(secili_donemler)].copy()
            onc    = df_onc.groupby(["hisse","kurum"])["oran2"].last().reset_index()
            onc.columns = ["hisse","kurum","onceki_oran"]
            tks2   = t2_sec.groupby("hisse")["tks2"].last().reset_index()
            artis_df = artis_df.merge(onc, on=["hisse","kurum"], how="left")
            artis_df = artis_df.merge(tks2, on="hisse", how="left")
            artis_df["onceki_oran"] = artis_df["onceki_oran"].fillna(0)
            artis_df["tks2"]        = artis_df["tks2"].fillna(0)
            artis_df["esik"] = artis_df["tks2"].apply(
                lambda x: 0.3 if x>=500_000_000 else (1.0 if x>=100_000_000 else 2.0)
            )
            artis_df = artis_df[
                (artis_df["onceki_oran"] < 0.5) &
                (artis_df["dolasim_pct"] >= artis_df["esik"]) &
                (artis_df["oran2"] <= 3)
            ].copy()
            baslik = "### 🔵 İlk Giriş Yapan Kurumlar (%0 → %3)"
        else:
            artis_df = artis_df[artis_df["dolasim_pct"] >= max(3, min_pct)].copy()
            baslik   = "### 📈 Seçilen Dönemde %3+ Artış Yapan Kurumlar"

        if not artis_df.empty:
            st.markdown(baslik)
            kl   = sorted(artis_df["kurum"].unique())
            cols = st.columns(min(len(kl), 4))
            for i, kurum in enumerate(kl):
                kdf  = artis_df[artis_df["kurum"]==kurum].sort_values(
                    "dolasim_pct", ascending=False).head(5)
                renk = "#1A5276" if kurum in AKILLI_PARA else "#1A7A3E"
                with cols[i % 4]:
                    st.markdown(
                        f"<div style='font-weight:bold;color:{renk};margin-bottom:4px;'>"
                        f"📈 {kurum}</div>", unsafe_allow_html=True
                    )
                    for _, r in kdf.iterrows():
                        st.markdown(
                            f"<div style='font-size:12px;padding:1px 0;'>"
                            f"<b>{r['hisse']}</b> "
                            f"<span style='color:{renk};font-weight:bold;'>"
                            f"+{r['dolasim_pct']:.1f}%</span></div>",
                            unsafe_allow_html=True
                        )

    st.markdown("---")

    # ── Toplama Alarm Listesi (3 kolonlu) ─────────────────────────────────────
    st.markdown("### 🚨 Toplama Alarm Listesi")
    alarm_df = alarm_listesi(secili_donemler, min_pct)

    if alarm_df.empty:
        st.caption("Bu dönemde alarm yok.")
    else:
        grp = {}
        sira = {"🔴 KRİTİK": 0, "🟠 GÜÇLÜ": 1}
        for _, r in alarm_df.iterrows():
            h = r["hisse"]
            if h not in grp:
                grp[h] = {"alarm": r["alarm"], "kurumlar": []}
            if sira.get(r["alarm"],9) < sira.get(grp[h]["alarm"],9):
                grp[h]["alarm"] = r["alarm"]
            grp[h]["kurumlar"].append(r)

        items = list(grp.items())[:36]
        cols3 = st.columns(3)
        for i, (hisse, data) in enumerate(items):
            alarm = data["alarm"]
            renk  = {"🔴 KRİTİK":"#C0392B","🟠 GÜÇLÜ":"#E67E22"}.get(alarm,"#95A5A6")
            k_html = "".join([
                f"<div style='font-size:11px;padding:1px 0 1px 6px;'>"
                f"<b style='color:{renk};'>{r['kurum']}</b> "
                f"T2:%{r['oran2']:.2f} · <b>+{r['dolasim_pct']:.2f}%</b></div>"
                for r in sorted(data["kurumlar"], key=lambda x: -x["dolasim_pct"])
            ])
            with cols3[i % 3]:
                st.markdown(
                    f"<div style='border-left:4px solid {renk};padding:6px 10px;"
                    f"margin:4px 0;background:#FAFAFA;border-radius:0 4px 4px 0;'>"
                    f"<b style='font-size:13px;'>{hisse}</b> "
                    f"<span style='color:{renk};font-size:11px;font-weight:bold;'>"
                    f"{alarm}</span>{k_html}</div>",
                    unsafe_allow_html=True
                )

    st.markdown("---")

    # ── Kurum Bazlı Detay Tablo ───────────────────────────────────────────────
    st.markdown("### 📋 Kurum Bazlı Detay Tablo")
    pivot_df = takas_analiz(secili_donemler, mod)

    if not pivot_df.empty:
        k_cols = [c for c in pivot_df.columns if c not in ["hisse","tks2"]]
        pivot_df["TOPLAM"] = pivot_df[k_cols].sum(axis=1).round(2)
        pivot_df = pivot_df[pivot_df["TOPLAM"].abs() >= min_pct]
        pivot_df = pivot_df.sort_values("TOPLAM", ascending=False)

        if pivot_df.empty:
            st.caption(f"Min %{min_pct} geçen hisse yok.")
        else:
            fmt = {c:"{:+.2f}" for c in k_cols + ["TOPLAM"]}
            fmt["tks2"] = "{:,.0f}"

            def _r(v):
                if not isinstance(v, float): return "color:#888"
                if v >= 1.0:  return "background-color:#D5F5E3;color:#1A5276;font-weight:bold"
                if v > 0:     return "color:#1A5276;font-weight:bold"
                if v <= -1.0: return "background-color:#FADBD8;color:#C0392B;font-weight:bold"
                if v < 0:     return "color:#C0392B"
                return "color:#888"

            st.dataframe(
                pivot_df.style.map(_r, subset=k_cols+["TOPLAM"]).format(fmt, na_rep="—"),
                use_container_width=True, height=500
            )
            st.download_button(
                "⬇️ Excel İndir",
                data=_takas_excel_indir(pivot_df, secili_donemler),
                file_name=f"takas_analiz_{mod}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="takas_excel_btn"
            )



def takas_veri_yukle_bolumu():
    """Veri Yükle sekmesindeki takas bölümü."""
    st.markdown("### 🏦 Kurum Takas Dosyaları")
    st.caption(
        "Dosya adı formatı: **KURUM_AY_DONEM.xlsx**  |  "
        "Aylık: `TERA__2026_01_03.xlsx`  |  "
        "Haftalık: `TERA_202604_01.xlsx`  |  "
        "Günlük: `TERA_20260420.xlsx`"
    )

    with st.form("takas_yukle_form"):
        yuklenen = st.file_uploader(
            "📂 Dosyaları Seçin (birden fazla seçilebilir):",
            type=["xlsx"],
            accept_multiple_files=True,
            key="takas_dosya_yukle"
        )
        yukle_btn = st.form_submit_button(
            "✅ Yükle", use_container_width=True
        )

    if yukle_btn:
        if not yuklenen:
            st.error("En az 1 dosya seçin!")
        else:
            dosya_listesi = [(f.name, f) for f in yuklenen]
            eklenen, hatalar = dosyalar_yukle(dosya_listesi)

            if eklenen:
                for msg in eklenen:
                    st.success(msg)
            if hatalar:
                for msg in hatalar:
                    st.warning(msg)

            if eklenen:
                st.rerun()

    # Kayıtlı dönemler
    st.markdown("---")
    st.markdown("**📂 Kayıtlı Veriler:**")

    col_g, col_h, col_a = st.columns(3)

    for col, tip, label in [
        (col_g, "gunluk", "📅 Günlük"),
        (col_h, "haftalik", "📆 Haftalık"),
        (col_a, "aylik", "🗓️ Aylık")
    ]:
        with col:
            st.markdown(f"**{label}:**")
            donemler = donemler_listele(tip)
            if donemler:
                kurumlar = kurumlar_listele()
                for d in donemler[:10]:
                    c1, c2 = st.columns([3, 1])
                    c1.markdown(f"`{d}`")
                    if c2.button("🗑️", key=f"takas_sil_{tip}_{d}"):
                        for k in kurumlar:
                            donem_sil(k, d)
                        st.rerun()
            else:
                st.caption("Henüz yok")


def _takas_excel_indir(df: pd.DataFrame, donemler: list):
    """Takas tablosunu Excel'e dönüştürür."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from io import BytesIO
    from datetime import datetime

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Takas Analiz"

    cols = list(df.columns)
    tarih = datetime.now().strftime("%d.%m.%Y")

    # Başlık
    ws.merge_cells(f"A1:{get_column_letter(len(cols))}1")
    c = ws["A1"]
    c.value = f"Takas Analizi | {', '.join(donemler)} | {tarih}"
    c.font = Font(bold=True, size=12, color="FFFFFF")
    c.fill = PatternFill("solid", start_color="1A252F")
    c.alignment = Alignment(horizontal="center")

    # Header
    for i, col in enumerate(cols, 1):
        cell = ws.cell(row=2, column=i, value=col)
        cell.font = Font(bold=True, color="FFFFFF", size=10)
        cell.fill = PatternFill("solid", start_color="1A3A5C")
        cell.alignment = Alignment(horizontal="center")

    # Veri
    for ri, (_, row) in enumerate(df.iterrows()):
        r = ri + 3
        for ci, col in enumerate(cols, 1):
            v = row[col]
            cell = ws.cell(row=r, column=ci, value=v)
            if isinstance(v, float):
                cell.number_format = "+0.00;-0.00;0.00"
                if v >= 1.0:
                    cell.font = Font(bold=True, color="1A5276")
                elif v > 0:
                    cell.font = Font(color="1A5276")
                elif v <= -1.0:
                    cell.font = Font(bold=True, color="C0392B")
                elif v < 0:
                    cell.font = Font(color="C0392B")

    # Kolon genişlikleri
    ws.column_dimensions["A"].width = 10
    for i in range(2, len(cols) + 1):
        ws.column_dimensions[get_column_letter(i)].width = 12

    ws.freeze_panes = "B3"

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
