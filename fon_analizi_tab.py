"""
fon_analizi_tab.py — Fon Analizi Sekmesi
Akış: PDF yükle → parse → kaydet → göster
Yapı: Üst (fon kartları) | Orta (fon detay) | Alt (hisse analizi)
"""

import streamlit as st
import pandas as pd
import json
from pathlib import Path

try:
    from fon_parser import parse_fon_pdf
except ImportError:
    import sys
    sys.path.append(str(Path(__file__).parent))
    from fon_parser import parse_fon_pdf

# ── Veri dizini ────────────────────────────────────────────────────────────────
DATA_DIR  = Path(__file__).parent / "data" / "fon_portfoy"
DATA_DIR.mkdir(parents=True, exist_ok=True)
JSON_FILE = DATA_DIR / "_fonlar.json"


def _yukle() -> dict:
    if JSON_FILE.exists():
        return json.loads(JSON_FILE.read_text(encoding="utf-8"))
    return {}


def _kaydet(d: dict):
    JSON_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def _renk(v: float) -> tuple:
    if v >= 8:  return "#1a5e20", "white"
    if v >= 5:  return "#2e7d32", "white"
    if v >= 3:  return "#388e3c", "white"
    if v >= 1:  return "#81c784", "black"
    return "", "black"


# ── ANA FONKSİYON ─────────────────────────────────────────────────────────────
def tab_fon_analizi():

    st.markdown("## 📁 Fon Analizi")

    fonlar = _yukle()

    # ══════════════════════════════════════════════════════════════════════
    # PDF YÜKLEME
    # ══════════════════════════════════════════════════════════════════════
    with st.expander("📤 PDF Yükle / Güncelle", expanded=(len(fonlar) == 0)):

        donem_input = st.text_input("Dönem", value="Mart-2026",
                                    help="Örn: Mart-2026, Nisan-2026")

        uploaded = st.file_uploader(
            "Fon PDF dosyaları (birden fazla seçebilirsin)",
            type=["pdf"],
            accept_multiple_files=True,
            key="fon_uploader",
        )

        if st.button("🔄 Yükle ve İşle", type="primary", disabled=not uploaded):
            prog = st.progress(0, text="Hazırlanıyor...")
            basarili, hatali = [], []

            for i, f in enumerate(uploaded):
                prog.progress((i + 1) / len(uploaded), text=f"⏳ {f.name}")
                try:
                    tmp = DATA_DIR / f.name
                    tmp.write_bytes(f.read())
                    result = parse_fon_pdf(str(tmp))
                    tmp.unlink()
                    kod = result["fon_kodu"]
                    fonlar[kod] = {
                        "fon_adi" : result["fon_adi"],
                        "kurucu"  : result["kurucu"],
                        "nvd"     : result["nvd"],
                        "donem"   : donem_input,
                        "hisseler": result["hisseler"],
                    }
                    basarili.append(f"{kod} ({len(result['hisseler'])} hisse)")
                except Exception as e:
                    hatali.append(f"{f.name}: {e}")

            _kaydet(fonlar)
            prog.empty()
            if basarili:
                st.success(f"✅ {len(basarili)} fon: {', '.join(basarili)}")
            if hatali:
                st.error("❌ " + " | ".join(hatali))
            st.rerun()

        if fonlar:
            st.divider()
            sil = st.selectbox("Fon sil:", ["—"] + sorted(fonlar.keys()), key="sil_fon")
            if sil != "—" and st.button("🗑️ Sil", key="sil_btn"):
                del fonlar[sil]
                _kaydet(fonlar)
                st.rerun()

    if not fonlar:
        st.info("Henüz fon yüklenmedi. Yukarıdan PDF yükle.")
        return

    st.divider()

    # ══════════════════════════════════════════════════════════════════════
    # ÜST: FON KARTLARI — NVD büyüklüğüne göre sıralı
    # ══════════════════════════════════════════════════════════════════════
    st.markdown("### 🏦 Fonlar — Büyüklük Sırası")

    # 0 hisseli fonları filtrele
    sirali = sorted(
        [(k, v) for k, v in fonlar.items() if len(v.get("hisseler", [])) > 0],
        key=lambda x: x[1].get("nvd", 0), reverse=True
    )

    if not sirali:
        st.info("Hisse verisi olan fon yok. PDF yükle.")
        return

    for satir_bas in range(0, len(sirali), 5):
        satir = sirali[satir_bas: satir_bas + 5]
        cols  = st.columns(len(satir))
        for col, (kod, veri) in zip(cols, satir):
            nvd     = veri.get("nvd", 0)
            n_hisse = len(veri.get("hisseler", []))
            donem   = veri.get("donem", "")
            nvd_str = f"{nvd/1e9:.2f}B ₺" if nvd >= 1e9 else f"{nvd/1e6:.1f}M ₺"
            with col:
                st.metric(
                    label=f"**{kod}**",
                    value=nvd_str,
                    delta=f"{n_hisse} hisse · {donem}",
                )

    st.divider()

    # ══════════════════════════════════════════════════════════════════════
    # ORTA: FON DETAY
    # ══════════════════════════════════════════════════════════════════════
    st.markdown("### 🔍 Fon Detay")

    fon_secenekleri = [kod for kod, v in sirali]
    secili_kod = st.selectbox("Fon seç:", fon_secenekleri, key="fon_detay")
    secili     = fonlar[secili_kod]

    c1, c2, c3 = st.columns(3)
    nvd = secili.get("nvd", 0)
    c1.metric("NVD", f"{nvd/1e9:.3f}B ₺" if nvd >= 1e9 else f"{nvd/1e6:.1f}M ₺")
    c2.metric("Kurucu", secili.get("kurucu", "—")[:30])
    c3.metric("Dönem",  secili.get("donem", "—"))

    hisseler = secili.get("hisseler", [])

    if not hisseler:
        st.warning("Bu fon için hisse verisi yok.")
    else:
        rows = []
        for h in sorted(hisseler, key=lambda x: x.get("fpd_pct", 0), reverse=True):
            rows.append({
                "HİSSE"      : h.get("hisse", ""),
                "AĞIRLIK %"  : h.get("fpd_pct", 0),
                "NOMİNAL"    : h.get("nominal", 0),
                "DEĞER (₺)"  : h.get("toplam_deger", 0),
                "ALIŞ TARİHİ": h.get("alis_tarihi", ""),
                "ALIŞ FİY"   : h.get("alis_fiy", 0),
            })
        df = pd.DataFrame(rows)
        df.index = range(1, len(df) + 1)

        def _renk_satir(row):
            bg, fg = _renk(row["AĞIRLIK %"])
            stil   = f"background-color:{bg};color:{fg}" if bg else ""
            return [stil] * len(row)

        styled = (
            df.style
            .apply(_renk_satir, axis=1)
            .format({
                "AĞIRLIK %": "{:.2f}%",
                "NOMİNAL"  : "{:,.0f}",
                "DEĞER (₺)": "{:,.0f}",
                "ALIŞ FİY" : lambda x: f"{x:,.2f}" if x else "—",
            })
        )
        st.dataframe(styled, use_container_width=True,
                     height=min(600, 45 + len(df) * 35))

    st.divider()

    # ══════════════════════════════════════════════════════════════════════
    # ALT: HİSSE ANALİZİ — kaç fonda var
    # ══════════════════════════════════════════════════════════════════════
    st.markdown("### 📊 Hisse Analizi — Tüm Fonlarda")

    tum = []
    for kod, veri in fonlar.items():
        for h in veri.get("hisseler", []):
            tum.append({
                "FON"    : kod,
                "HİSSE"  : h.get("hisse", ""),
                "AĞIRLIK": h.get("fpd_pct", 0),
                "DEĞER"  : h.get("toplam_deger", 0),
            })

    if not tum:
        return

    df_tum = pd.DataFrame(tum)
    ozet = (
        df_tum.groupby("HİSSE")
        .agg(
            FON_SAYISI =("FON",     "nunique"),
            FONLAR     =("FON",     lambda x: ", ".join(sorted(x.unique()))),
            TOP_AGIRLIK=("AĞIRLIK", "sum"),
            TOP_DEGER  =("DEĞER",   "sum"),
        )
        .reset_index()
        .sort_values(["FON_SAYISI", "TOP_AGIRLIK"], ascending=[False, False])
        .reset_index(drop=True)
    )
    ozet.index = range(1, len(ozet) + 1)

    ara = st.text_input("Hisse ara:", placeholder="THYAO, ASELS...",
                        key="hisse_ara_alt").upper().strip()
    if ara:
        ozet = ozet[ozet["HİSSE"].str.contains(ara)]

    st.dataframe(
        ozet.style.format({
            "TOP_AGIRLIK": "{:.2f}%",
            "TOP_DEGER"  : "{:,.0f} ₺",
        }),
        use_container_width=True,
        height=500,
        column_config={
            "FON_SAYISI" : st.column_config.NumberColumn("# Fon",            format="%d"),
            "TOP_AGIRLIK": st.column_config.NumberColumn("Toplam Ağırlık %", format="%.2f%%"),
            "TOP_DEGER"  : st.column_config.NumberColumn("Toplam Değer (₺)", format="%,.0f"),
        },
    )
