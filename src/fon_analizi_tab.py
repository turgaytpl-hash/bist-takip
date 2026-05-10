"""
fon_analizi_tab.py — teknik_app.py içine eklenecek sekme
Kullanım: bu dosyayı import et, tab_fon_analizi() fonksiyonunu çağır.
"""

import streamlit as st
import pandas as pd
import json
import hashlib
from pathlib import Path
from datetime import datetime

# Lokal parser
try:
    from fon_parser import parse_fon_pdf
    from tefas_tab import tefas_bolumu
except ImportError:
    import sys
    sys.path.append(str(Path(__file__).parent))
    from fon_parser import parse_fon_pdf
    from tefas_tab import tefas_bolumu

# ─── Veri dizini ───────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent / "FON"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DONEM_FILE = DATA_DIR / "_fonlar.json"


# ─── Yardımcı: dönemler ────────────────────────────────────────────────────────

def _load_donemler() -> dict:
    """{'Mart-2026': {'BHA': {...}, 'RKH': {...}}, ...}"""
    if DONEM_FILE.exists():
        return json.loads(DONEM_FILE.read_text(encoding='utf-8'))
    return {}


def _save_donemler(d: dict):
    DONEM_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding='utf-8')


def _df_from_donem(donemler: dict, donem: str) -> pd.DataFrame:
    """Seçili dönemin tüm fonlarını tek DataFrame'e çevir"""
    rows = []
    for fon_kodu, fon_data in donemler.get(donem, {}).items():
        nvd = fon_data['nvd']
        kurucu = fon_data.get('kurucu', '')
        for h in fon_data['hisseler']:
            rows.append({
                'FON'        : fon_kodu,
                'KURUCU'     : kurucu,
                'NVD_TL'     : nvd,
                'HİSSE'      : h['hisse'],
                'AĞIRLIK_%'  : h['fpd_pct'],
                'NOMİNAL'    : h['nominal'],
                'DEĞER_TL'   : h['toplam_deger'],
                'ALIŞ_TARİHİ': h.get('alis_tarihi', ''),
                'ALIŞ_FİY'   : h.get('alis_fiy', 0),
            })
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df['DEĞER_TL'] = pd.to_numeric(df['DEĞER_TL'], errors='coerce').fillna(0)
    df['AĞIRLIK_%'] = pd.to_numeric(df['AĞIRLIK_%'], errors='coerce').fillna(0)
    return df


# ─── Renk fonksiyonları ────────────────────────────────────────────────────────

def _oran_renk(val):
    """Ağırlık % → CSS renk"""
    if val >= 8:   return 'background-color: #1a5e20; color: white'
    if val >= 5:   return 'background-color: #388e3c; color: white'
    if val >= 3:   return 'background-color: #66bb6a; color: black'
    if val >= 1:   return 'background-color: #a5d6a7; color: black'
    return ''


# ─── ANA FONKSİYON ─────────────────────────────────────────────────────────────

def tab_fon_analizi():
    """Streamlit Fon Analizi sekmesi — teknik_app.py içinden çağrılır"""

    st.markdown("## 📁 Fon Analizi")

    # ── TEFAS BÖLÜMÜ ──────────────────────────────────────────────────────────
    tefas_bolumu()
    st.divider()
    st.markdown("### 📋 Portföy Detayı (PDF)")
    st.markdown("*Her ay fon PDF'lerini yükle → otomatik parse → ağırlığa göre sırala*")

    donemler = _load_donemler()

    # ── SOL: Yükleme paneli ───────────────────────────────────────────────────
    with st.expander("📤 PDF Yükle", expanded=(len(donemler) == 0)):
        uploaded = st.file_uploader(
            "Fon PDF dosyaları (birden fazla seçebilirsin)",
            type=["pdf"],
            accept_multiple_files=True,
            key="fon_uploader",
        )

        st.caption("💡 Dönem PDF'den otomatik algılanır.")

        if st.button("🔄 PDF'leri İşle", type="primary", disabled=(not uploaded)):
            progress = st.progress(0, text="Hazırlanıyor...")
            basarili, hatali = [], []

            for i, f in enumerate(uploaded):
                progress.progress((i + 1) / len(uploaded), text=f"İşleniyor: {f.name}")
                try:
                    tmp = DATA_DIR / f.name
                    tmp.write_bytes(f.read())
                    result   = parse_fon_pdf(str(tmp))
                    fon_kodu = result['fon_kodu']
                    donem    = result['donem'] or 'Bilinmiyor-2026'

                    donemler.setdefault(donem, {})[fon_kodu] = {
                        'fon_adi' : result['fon_adi'],
                        'kurucu'  : result['kurucu'],
                        'nvd'     : result['nvd'],
                        'hisseler': result['hisseler'],
                    }
                    basarili.append(f"{fon_kodu}/{donem} ({len(result['hisseler'])} hisse)")
                    tmp.unlink()
                except Exception as e:
                    hatali.append(f"{f.name}: {e}")

            _save_donemler(donemler)
            progress.empty()

            if basarili:
                st.success(f"✅ {len(basarili)} fon yüklendi: {', '.join(basarili)}")
            if hatali:
                st.error(f"❌ Hatalar: {'; '.join(hatali)}")
            st.rerun()

    # Dönem silme
    if donemler:
        col_d, col_del = st.columns([3, 1])
        with col_d:
            pass
        with col_del:
            sil_donem = st.selectbox("Dönem sil:", ["—"] + list(donemler.keys()), key="sil_d")
            if sil_donem != "—" and st.button("🗑️ Sil", key="sil_btn"):
                del donemler[sil_donem]
                _save_donemler(donemler)
                st.rerun()

    if not donemler:
        st.info("Henüz fon verisi yok. Yukarıdan PDF yükle.")
        return

    # ── DÖNEM SEÇİMİ ──────────────────────────────────────────────────────────
    st.divider()
    donem_listesi = sorted(donemler.keys(), reverse=True)
    col_donem, col_info = st.columns([2, 3])
    with col_donem:
        secili_donem = st.selectbox(
            "📅 Dönem seç:",
            donem_listesi,
            key="fon_donem",
        )
    with col_info:
        fon_sayisi_d = len(donemler.get(secili_donem, {}))
        st.markdown(f"### 🗂️ {secili_donem}")
        st.caption(f"{fon_sayisi_d} fon yüklü")

    df = _df_from_donem(donemler, secili_donem)
    if df.empty:
        st.warning("Bu dönemde veri yok.")
        return

    fon_listesi = sorted(df['FON'].unique())

    # ── SEKMELER ──────────────────────────────────────────────────────────────
    t1, t2, t3, t4 = st.tabs([
        "📊 Tüm Fonlar — Ağırlık Sırası",
        "🔍 Hisse Ara",
        "🏦 Fon Detay",
        "⚡ Ortak Pozisyonlar",
    ])

    # ── T1: TÜM FONLAR ────────────────────────────────────────────────────────
    with t1:
        st.markdown(f"**{secili_donem}** — {len(fon_listesi)} fon, {df['HİSSE'].nunique()} farklı hisse")

        # Özet kart satırı
        cols = st.columns(min(len(fon_listesi), 5))
        for i, fon in enumerate(fon_listesi):
            nvd = donemler[secili_donem][fon]['nvd']
            n_hisse = len(df[df['FON'] == fon])
            with cols[i % 5]:
                st.metric(
                    label=fon,
                    value=f"{nvd/1e6:.1f}M ₺",
                    delta=f"{n_hisse} hisse",
                )

        st.divider()

        # Her fon ayrı tablo — ağırlığa göre sıralı
        fon_filter = st.multiselect(
            "Fon filtrele (boş = hepsi):",
            fon_listesi,
            default=[],
            key="fon_filter_t1",
        )
        goster_fonlar = fon_filter if fon_filter else fon_listesi

        for fon in goster_fonlar:
            fon_data = donemler[secili_donem][fon]
            nvd = fon_data['nvd']
            kurucu = fon_data.get('kurucu', '')

            st.markdown(f"### {fon} — {kurucu}")
            st.caption(f"NVD: **{nvd:,.0f} ₺** ({nvd/1e6:.1f}M)")

            sub = df[df['FON'] == fon].sort_values('AĞIRLIK_%', ascending=False).copy()
            sub = sub[['HİSSE', 'AĞIRLIK_%', 'NOMİNAL', 'DEĞER_TL', 'ALIŞ_TARİHİ', 'ALIŞ_FİY']].reset_index(drop=True)
            sub.index = sub.index + 1

            # Renk uygula
            def renk_satir(row):
                v = row['AĞIRLIK_%']
                if v >= 8:   bg = '#1a5e20'; fg = 'white'
                elif v >= 5: bg = '#2e7d32'; fg = 'white'
                elif v >= 3: bg = '#388e3c'; fg = 'white'
                elif v >= 1: bg = '#81c784'; fg = 'black'
                else:        bg = ''; fg = ''
                return [f'background-color:{bg};color:{fg}' if bg else ''] * len(row)

            styled = sub.style.apply(renk_satir, axis=1)
            styled = styled.format({
                'AĞIRLIK_%' : '{:.2f}%',
                'NOMİNAL'   : '{:,.0f}',
                'DEĞER_TL'  : '{:,.0f} ₺',
                'ALIŞ_FİY'  : lambda x: f'{x:,.2f}' if x else '—',
            })

            st.dataframe(styled, use_container_width=True, height=min(400, 40 + len(sub) * 35))
            st.divider()

    # ── T2: HİSSE ARA ─────────────────────────────────────────────────────────
    with t2:
        st.markdown("**Bir hisse kodunu yaz — hangi fonlarda var gör**")
        arama = st.text_input("Hisse kodu:", placeholder="THYAO, DAPGM...", key="hisse_ara").upper().strip()

        if arama:
            sub = df[df['HİSSE'] == arama].sort_values('AĞIRLIK_%', ascending=False)
            if sub.empty:
                st.warning(f"**{arama}** bu dönemde hiçbir fonda yok.")
            else:
                st.markdown(f"### {arama} — {len(sub)} fonda")
                # Küçük kart'lar
                cols = st.columns(len(sub))
                for i, (_, row) in enumerate(sub.iterrows()):
                    with cols[i]:
                        st.metric(
                            label=row['FON'],
                            value=f"%{row['AĞIRLIK_%']:.2f}",
                            delta=f"{row['NOMİNAL']:,.0f} adet",
                        )
                st.dataframe(
                    sub[['FON', 'KURUCU', 'AĞIRLIK_%', 'NOMİNAL', 'DEĞER_TL', 'ALIŞ_TARİHİ', 'ALIŞ_FİY']].reset_index(drop=True),
                    use_container_width=True,
                )
        else:
            # Genel hisse sıralaması — hangi hisse toplam kaç fonda var
            st.markdown("#### Dönem Özeti — En Fazla Fonda Olan Hisseler")
            ozet = df.groupby('HİSSE').agg(
                FON_SAYISI=('FON', 'nunique'),
                TOPLAM_DEGER=('DEĞER_TL', 'sum'),
                MAX_AGIRLIK=('AĞIRLIK_%', 'max'),
                FONLAR=('FON', lambda x: ', '.join(sorted(x.unique()))),
            ).reset_index().sort_values('FON_SAYISI', ascending=False)

            ozet = ozet[ozet['FON_SAYISI'] >= 1]
            st.dataframe(
                ozet.style.format({
                    'TOPLAM_DEGER': '{:,.0f} ₺',
                    'MAX_AGIRLIK' : '{:.2f}%',
                }),
                use_container_width=True,
                height=500,
            )

    # ── T3: FON DETAY + KARŞILAŞTIRMA ────────────────────────────────────────
    with t3:
        secili_fon = st.selectbox("Fon seç:", fon_listesi, key="fon_detay_sel")
        fon_data   = donemler[secili_donem][secili_fon]

        # Karşılaştırılacak dönem — seçili dönem dışındaki dönemler
        diger_donemler = [d for d in donem_listesi if d != secili_donem]

        if diger_donemler:
            kars_donem = st.selectbox(
                "Karşılaştır (baz dönem):",
                ["— Karşılaştırma yok"] + diger_donemler,
                key="fon_kars_donem",
            )
        else:
            kars_donem = "— Karşılaştırma yok"

        kars_data = donemler.get(kars_donem, {}).get(secili_fon) if kars_donem != "— Karşılaştırma yok" else None

        # Üst metrikler
        nvd_yeni = fon_data['nvd']
        nvd_eski = kars_data['nvd'] if kars_data else None
        col1, col2, col3 = st.columns(3)
        col1.metric(
            "NVD",
            f"{nvd_yeni/1e6:.1f}M ₺",
            delta=f"{(nvd_yeni-nvd_eski)/1e6:+.1f}M" if nvd_eski else None,
        )
        col2.metric("Kurucu", fon_data.get('kurucu', '—')[:25])
        col3.metric("Hisse Sayısı", len(fon_data['hisseler']),
                    delta=len(fon_data['hisseler']) - len(kars_data['hisseler']) if kars_data else None)

        st.divider()

        # ── Karşılaştırma tablosu ──────────────────────────────────────────
        if kars_data:
            eski_agirlik = {h['hisse']: h['fpd_pct']      for h in kars_data['hisseler']}
            eski_deger   = {h['hisse']: h['toplam_deger'] for h in kars_data['hisseler']}

            rows_k = []
            for h in fon_data['hisseler']:
                kod  = h['hisse']
                ag_y = h['fpd_pct']
                de_y = h['toplam_deger']
                ag_e = eski_agirlik.get(kod, 0.0)
                de_e = eski_deger.get(kod, 0.0)
                d_ag = ag_y - ag_e
                durum = ('🆕' if ag_e == 0 else '⬆️' if d_ag > 0.1 else '⬇️' if d_ag < -0.1 else '➡️')
                rows_k.append({
                    'DURUM'      : durum,
                    'HİSSE'      : kod,
                    f'%_{secili_donem}' : ag_y,
                    f'%_{kars_donem}'   : ag_e,
                    'Δ%'         : d_ag,
                    f'TL_{secili_donem}': de_y,
                    'ΔTL'        : de_y - de_e,
                })

            # Eski dönemde olup yenide olmayan (çıkışlar)
            yeni_hisseler = {h['hisse'] for h in fon_data['hisseler']}
            for kod, ag_e in eski_agirlik.items():
                if kod not in yeni_hisseler:
                    rows_k.append({
                        'DURUM'      : '🚪',
                        'HİSSE'      : kod,
                        f'%_{secili_donem}' : 0.0,
                        f'%_{kars_donem}'   : ag_e,
                        'Δ%'         : -ag_e,
                        f'TL_{secili_donem}': 0.0,
                        'ΔTL'        : -eski_deger.get(kod, 0),
                    })

            df_k = pd.DataFrame(rows_k).sort_values('Δ%', ascending=False).reset_index(drop=True)

            col_yeni, col_eski = st.columns(2)
            with col_yeni:
                st.markdown("#### ⬆️ Artan / 🆕 Yeni")
                df_artan = df_k[df_k['DURUM'].isin(['⬆️','🆕'])].copy()
                st.dataframe(
                    df_artan[['HİSSE','DURUM',f'%_{secili_donem}',f'%_{kars_donem}','Δ%']].style.format({
                        f'%_{secili_donem}': '{:.2f}%',
                        f'%_{kars_donem}'  : '{:.2f}%',
                        'Δ%'               : '{:+.2f}%',
                    }),
                    use_container_width=True, hide_index=True,
                )
            with col_eski:
                st.markdown("#### ⬇️ Azalan / 🚪 Çıkış")
                df_azalan = df_k[df_k['DURUM'].isin(['⬇️','🚪'])].sort_values('Δ%').copy()
                st.dataframe(
                    df_azalan[['HİSSE','DURUM',f'%_{secili_donem}',f'%_{kars_donem}','Δ%']].style.format({
                        f'%_{secili_donem}': '{:.2f}%',
                        f'%_{kars_donem}'  : '{:.2f}%',
                        'Δ%'               : '{:+.2f}%',
                    }),
                    use_container_width=True, hide_index=True,
                )

            st.markdown("#### 📋 Tüm Portföy")
            st.dataframe(
                df_k[['HİSSE','DURUM',f'%_{secili_donem}',f'%_{kars_donem}','Δ%',f'TL_{secili_donem}','ΔTL']].style.format({
                    f'%_{secili_donem}' : '{:.2f}%',
                    f'%_{kars_donem}'   : '{:.2f}%',
                    'Δ%'                : '{:+.2f}%',
                    f'TL_{secili_donem}': '{:,.0f} ₺',
                    'ΔTL'               : '{:+,.0f} ₺',
                }),
                use_container_width=True, hide_index=True,
            )

        else:
            # Karşılaştırma yok — sadece mevcut dönem tablosu
            sub = df[df['FON'] == secili_fon].sort_values('AĞIRLIK_%', ascending=False).copy()
            st.dataframe(
                sub[['HİSSE','AĞIRLIK_%','NOMİNAL','DEĞER_TL']].reset_index(drop=True).style.format({
                    'AĞIRLIK_%': '{:.2f}%',
                    'NOMİNAL'  : '{:,.0f}',
                    'DEĞER_TL' : '{:,.0f} ₺',
                }),
                use_container_width=True,
            )

    # ── T4: ORTAK POZİSYONLAR ─────────────────────────────────────────────────
    with t4:
        st.markdown("**Birden fazla fonda aynı anda olan hisseler**")
        if len(fon_listesi) < 2:
            st.info("Ortak pozisyon analizi için en az 2 fon gerekli. Daha fazla PDF yükle.")
        else:
            max_fon = min(5, len(fon_listesi))
            if max_fon <= 2:
                min_fon = 2
            else:
                min_fon = st.slider("En az kaç fonda olsun:", 2, max_fon, 2, key="min_fon")

            ozet = df.groupby('HİSSE').agg(
                FON_SAYISI=('FON', 'nunique'),
                TOPLAM_DEGER=('DEĞER_TL', 'sum'),
                FONLAR=('FON', lambda x: ', '.join(sorted(x.unique()))),
            ).reset_index()

            ozet_filtered = ozet[ozet['FON_SAYISI'] >= min_fon].sort_values(
                ['FON_SAYISI', 'TOPLAM_DEGER'], ascending=[False, False]
            )

            if ozet_filtered.empty:
                st.info(f"En az {min_fon} fonda ortak hisse yok.")
            else:
                st.markdown(f"**{len(ozet_filtered)} hisse** {min_fon}+ fonda bulunuyor")

                for _, row in ozet_filtered.iterrows():
                    emoji = "🔥" if row['FON_SAYISI'] >= 4 else "⚡" if row['FON_SAYISI'] >= 3 else "✅"
                    with st.container():
                        c1, c2, c3 = st.columns([1, 2, 2])
                        c1.markdown(f"### {emoji} {row['HİSSE']}")
                        c2.markdown(f"**{row['FON_SAYISI']} fon:** {row['FONLAR']}")
                        c3.markdown(f"Toplam: **{row['TOPLAM_DEGER']:,.0f} ₺**")
                        hisse_df = df[df['HİSSE'] == row['HİSSE']][['FON', 'AĞIRLIK_%', 'NOMİNAL', 'ALIŞ_TARİHİ']].sort_values('AĞIRLIK_%', ascending=False)
                        st.dataframe(hisse_df.reset_index(drop=True), use_container_width=True, hide_index=True)
                        st.divider()
