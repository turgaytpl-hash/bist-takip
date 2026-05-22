"""
takas_depo.py — 15 Kurum Takas Veri Deposu

Dosya adı formatları:
  Aylık:    TERA__2026_01_03.xlsx
  Haftalık: TERA_202604_01.xlsx
  Günlük:   TERA_20260420.xlsx

Kurum listesi:
  YAPI_KREDI, IS_YATIRIM, AK_YATIRIM, GARANTI, VAKIF, TEB
  TERA, INFO, MIDAS, BULLS, PUSULA, ALNUS
  YABANCI, YAT_FONLARI, EMEKLILIK
"""

import pandas as pd
import re
from pathlib import Path
from datetime import datetime
from io import BytesIO

BASE = Path(__file__).parent / "data" / "takas"
BASE.mkdir(parents=True, exist_ok=True)

TAKAS_CSV = BASE / "kurum_takas.csv"

# 15 kurum listesi
# BIST FD Hisse Listesi (590 hisse)
# BIST FD listesi — bist_fd.xlsx'ten dinamik yüklenir
def _bist_fd_yukle() -> set:
    try:
        adaylar = [
            Path(__file__).parent / "data" / "bist_fd.xlsx",
            Path(__file__).parent.parent / "data" / "bist_fd.xlsx",
            Path(__file__).parent.parent / "bist_fd.xlsx",
            Path(__file__).parent / "bist_fd.xlsx",
        ]
        xlsx = next((p for p in adaylar if p.exists()), None)
        if xlsx is None:
            return set()
        df = pd.read_excel(xlsx)
        kol = next((c for c in df.columns if str(c).upper().strip() in ["SEMBOL","KOD","HISSE","TICKER"]), df.columns[0])
        return set(df[kol].astype(str).str.strip().str.upper().tolist())
    except Exception:
        return set()

BIST_FD = _bist_fd_yukle()

KURUMLAR = [
    # Büyük Yerli
    "YAPI_KREDI", "IS_YATIRIM", "AK_YATIRIM", "GARANTI", "VAKIF", "TEB",
    # Akıllı Para
    "TERA", "INFO", "MIDAS", "BULLS", "PUSULA", "ALNUS",
    # Fon / Yabancı
    "YABANCI", "YAT_FONLARI", "EMEKLILIK",
    # Yeni Eklenen
    "HALK_YATIRIM", "ZIRAAT_YATIRIM", "A1_CAPITAL", "MARBAS", "DENIZ_YATIRIM"
]

# Kurum grupları
BUYUK_YERLI = ["YAPI_KREDI", "IS_YATIRIM", "AK_YATIRIM", "GARANTI", "VAKIF", "TEB",
               "HALK_YATIRIM", "ZIRAAT_YATIRIM", "DENIZ_YATIRIM"]
AKILLI_PARA = ["TERA", "INFO", "MIDAS", "BULLS", "PUSULA", "ALNUS", "A1_CAPITAL", "MARBAS"]
FON_YABANCI = ["YABANCI", "YAT_FONLARI", "EMEKLILIK"]


def _oku() -> pd.DataFrame:
    if TAKAS_CSV.exists():
        df = pd.read_csv(TAKAS_CSV)
        if "donem" in df.columns:
            df["donem"] = df["donem"].astype(str)
        return df
    return pd.DataFrame()


def _kaydet(df: pd.DataFrame):
    BASE.mkdir(parents=True, exist_ok=True)
    df.to_csv(TAKAS_CSV, index=False)


def _simdi():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def dosya_adi_parse(dosya_adi: str) -> tuple:
    """
    Dosya adından kurum ve dönem bilgisini çıkarır.
    
    TERA__2026_01_03.xlsx → ('TERA', '2026_01_03', 'aylik')
    TERA_202604_01.xlsx   → ('TERA', '202604_01',  'haftalik')
    TERA_20260420.xlsx    → ('TERA', '20260420',   'gunluk')
    """
    ad = Path(dosya_adi).stem  # uzantısız

    # Aylık: KURUM_2026_01 (tek alt çizgi, yıl_ay)
    m = re.match(r'^([A-Z0-9_]+)_(\d{4}_\d{2})$', ad)
    if m:
        return m.group(1), m.group(2), 'aylik'

    # Aylık eski format: KURUM__2026_01_03 (çift alt çizgi)
    m = re.match(r'^([A-Z0-9_]+)__(\d{4}_\d{2}_\d{2})$', ad)
    if m:
        return m.group(1), m.group(2), 'aylik'

    # Haftalık: KURUM_202604_01 (YYYYmm_w)
    m = re.match(r'^([A-Z0-9_]+)_(\d{6}_\d{2})$', ad)
    if m:
        return m.group(1), m.group(2), 'haftalik'

    # Günlük: KURUM_20260420 (YYYYmmdd)
    m = re.match(r'^([A-Z0-9_]+)_(\d{8})$', ad)
    if m:
        return m.group(1), m.group(2), 'gunluk'

    return None, None, None


def takas_oku_kurum(kaynak, dosya_adi: str = None) -> pd.DataFrame:
    """
    Kurum takas dosyasını okur ve normalize eder.
    Format: Hisse | 1.Adet | 2.Adet | Adet Fark | %(Piy) | Tks(2)
    """
    if hasattr(kaynak, "read"):
        data = BytesIO(kaynak.read())
        xl = pd.ExcelFile(data)
    else:
        xl = pd.ExcelFile(str(kaynak))

    df = pd.read_excel(xl, sheet_name=xl.sheet_names[0], header=0)

    # Kolon adları normalize
    df.columns = [str(c).strip() for c in df.columns]

    zorunlu = ["Hisse", "2.Adet", "Adet Fark", "Tks(2)"]
    eksik = [c for c in zorunlu if c not in df.columns]
    if eksik:
        raise ValueError(f"Eksik kolonlar: {eksik}")

    df = df[["Hisse", "1.Adet", "2.Adet", "Adet Fark", "%(Piy)", "Tks(2)"]].copy()
    df["Hisse"] = df["Hisse"].astype(str).str.strip().str.upper()

    for col in ["1.Adet", "2.Adet", "Adet Fark", "Tks(2)"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # %(Piy) virgüllü gelebilir: "11,28" → 11.28
    df["%(Piy)"] = pd.to_numeric(
        df["%(Piy)"].astype(str).str.replace(",", ".", regex=False),
        errors="coerce"
    )

    # Filtrele: BIST FD listesi + Tks(2) > 1M
    df = df[df["Hisse"].str.match(r"^[A-Z]{4,6}$")]
    df = df[df["Hisse"].isin(BIST_FD)]
    df = df[df["Tks(2)"].notna() & (df["Tks(2)"] > 1_000_000)]

    # PP hesapla
    df["Oran_1"] = (df["1.Adet"] / df["Tks(2)"] * 100).round(4)
    df["Oran_2"] = (df["2.Adet"] / df["Tks(2)"] * 100).round(4)
    df["PP_Fark"] = (df["Oran_2"] - df["Oran_1"]).round(4)

    # Short kapama tespiti: önceki dönem 1.Adet negatifse (short pozisyon vardı)
    # Bu durumda Adet Fark şişiyor — short kapama + yeni alım birleşiyor
    # dolasim_pct için gerçek yeni giriş = sadece 2.Adet baz alınır
    df["Short_Kapama"] = df["1.Adet"] < 0
    df["Dolasim_Pct"] = df.apply(
        lambda r: (r["2.Adet"] / r["Tks(2)"] * 100) if r["Short_Kapama"]
                  else (r["Adet Fark"] / r["Tks(2)"] * 100),
        axis=1
    ).round(4)

    return df.reset_index(drop=True)


def dosyalar_yukle(dosya_listesi: list) -> tuple:
    """
    Birden fazla dosyayı aynı anda yükler.
    dosya_listesi: [(dosya_adi, dosya_objesi), ...]
    """
    mevcut = _oku()
    eklenen = []
    hatalar = []

    for dosya_adi, dosya_obj in dosya_listesi:
        try:
            kurum, donem, tip = dosya_adi_parse(dosya_adi)
            if not kurum:
                hatalar.append(f"❌ {dosya_adi}: Format tanınamadı")
                continue

            # Oku
            df = takas_oku_kurum(dosya_obj, dosya_adi)

            # Kayıt için hazırla
            kayit = df[["Hisse", "2.Adet", "Adet Fark", "Tks(2)",
                        "Oran_2", "PP_Fark", "Dolasim_Pct", "Short_Kapama"]].copy()
            kayit.columns = ["hisse", "adet2", "adet_fark", "tks2",
                             "oran2", "pp_fark", "dolasim_pct", "short_kapama"]
            kayit["kurum"] = kurum
            kayit["donem"] = donem
            kayit["tip"] = tip
            kayit["yukleme"] = _simdi()

            # Mükerrer kontrol — bu kurum+dönem zaten kayıtlıysa
            # sadece eksik hisseleri ekle, mevcut kayıtlara dokunma
            if not mevcut.empty:
                var = mevcut[
                    (mevcut["kurum"] == kurum) &
                    (mevcut["donem"] == donem)
                ]
                if len(var) > 0:
                    kayitli_hisseler = set(var["hisse"].unique())
                    eksik = kayit[~kayit["hisse"].isin(kayitli_hisseler)]
                    if eksik.empty:
                        hatalar.append(f"⚠️ {dosya_adi}: Zaten kayıtlı (yeni hisse yok)")
                        continue
                    mevcut = pd.concat([mevcut, eksik], ignore_index=True)
                    eklenen.append(f"✅ {dosya_adi} (+{len(eksik)} yeni hisse eklendi)")
                    continue

            mevcut = pd.concat([mevcut, kayit], ignore_index=True)
            eklenen.append(f"✅ {dosya_adi} ({len(df)} hisse)")

        except Exception as e:
            hatalar.append(f"❌ {dosya_adi}: {str(e)}")

    if eklenen:
        _kaydet(mevcut)

    return eklenen, hatalar


def donemler_listele(tip: str = None) -> list:
    """Kayıtlı dönemleri listeler."""
    df = _oku()
    if df.empty:
        return []
    if tip:
        df = df[df["tip"] == tip]
    return sorted(df["donem"].astype(str).unique().tolist(), reverse=True)


def kurumlar_listele() -> list:
    """Kayıtlı kurumları listeler."""
    df = _oku()
    if df.empty:
        return []
    return sorted(df["kurum"].unique().tolist())


def donem_sil(kurum: str, donem: str):
    """Belirli bir dönem verisini siler."""
    df = _oku()
    if df.empty:
        return
    df = df[~((df["kurum"] == kurum) & (df["donem"] == donem))]
    _kaydet(df)


def takas_analiz(donemler: list = None, tip: str = None) -> pd.DataFrame:
    """
    Seçili dönemler için kurum × hisse bazlı analiz tablosu.
    
    Returns:
    hisse | TERA_pp | BULLS_pp | INFO_pp | ... | NET_ALARM
    """
    df = _oku()
    if df.empty:
        return pd.DataFrame()

    if tip:
        df = df[df["tip"] == tip]
    if donemler:
        df = df[df["donem"].isin(donemler)]

    if df.empty:
        return pd.DataFrame()

    # Her kurum için hisse bazlı PP fark pivot
    pivot = df.pivot_table(
        index="hisse",
        columns="kurum",
        values="dolasim_pct",
        aggfunc="sum"
    ).reset_index()
    pivot.columns.name = None

    # Tks2 ekle (son dönemden)
    son_donem = sorted(df["donem"].astype(str).unique())[-1]
    tks = df[df["donem"] == son_donem][["hisse", "tks2"]].drop_duplicates("hisse")
    pivot = pivot.merge(tks, on="hisse", how="left")

    return pivot


def alarm_listesi(donemler: list, min_pct: float = 0.5) -> pd.DataFrame:
    """
    Toplama alarmı: Seçili dönemde TEK KURUM bazlı ARTIŞ miktarına göre.
    🔴 KRİTİK → tek kurum ≥ %5 artış
    🟠 GÜÇLÜ  → tek kurum ≥ %3 artış
    Altı → gösterilmez
    """
    df = _oku()
    if df.empty:
        return pd.DataFrame()

    if donemler:
        df_sec = df[df["donem"].isin(donemler)].copy()
    else:
        df_sec = df.copy()

    # Her hisse+kurum için seçilen dönemde toplam artış
    net = df_sec.groupby(["hisse", "kurum"]).agg(
        dolasim_pct=("dolasim_pct", "sum"),
        oran2=("oran2", "last"),
        tks2=("tks2", "last")
    ).reset_index()

    # Sadece %3+ artış yapanlar
    alici = net[net["dolasim_pct"] >= 3].copy()
    if alici.empty:
        return pd.DataFrame()

    # Alarm seviyesi
    def alarm_seviye(row):
        if row["dolasim_pct"] >= 5:
            return "🔴 KRİTİK"
        elif row["dolasim_pct"] >= 3:
            return "🟠 GÜÇLÜ"
        return None

    alici["alarm"] = alici.apply(alarm_seviye, axis=1)
    alici = alici[alici["alarm"].notna()]
    alici["akilli_para"] = alici["kurum"].isin(AKILLI_PARA)

    # Sıralama
    alarm_sira = {"🔴 KRİTİK": 0, "🟠 GÜÇLÜ": 1}
    alici["alarm_sira"] = alici["alarm"].map(alarm_sira)
    alici = alici.sort_values(["alarm_sira", "dolasim_pct"], ascending=[True, False])

    return alici[["hisse", "kurum", "oran2", "dolasim_pct", "alarm", "akilli_para", "tks2"]]


def kurum_net_pozisyon(donemler: list = None) -> pd.DataFrame:
    """Her kurum için toplam net alış/satış."""
    df = _oku()
    if df.empty:
        return pd.DataFrame()

    if donemler:
        df = df[df["donem"].isin(donemler)]

    net = df.groupby("kurum").agg(
        net_adet=("adet_fark", "sum"),
        dolasim_pct=("dolasim_pct", "sum"),
        islem_sayisi=("hisse", "count")
    ).reset_index()

    net["yon"] = net["dolasim_pct"].apply(
        lambda x: "📈 NET ALIŞ" if x > 0 else "📉 NET SATIŞ"
    )

    # Grup bilgisi
    def grup(kurum):
        if kurum in BUYUK_YERLI:
            return "Büyük Yerli"
        if kurum in AKILLI_PARA:
            return "Akıllı Para"
        return "Fon/Yabancı"

    net["grup"] = net["kurum"].apply(grup)

    return net.sort_values("dolasim_pct", ascending=False)


def hisse_kurum_detay(hisse: str, donemler: list = None) -> pd.DataFrame:
    """Belirli bir hisse için kurum bazlı dönem detayı."""
    df = _oku()
    if df.empty:
        return pd.DataFrame()

    df = df[df["hisse"] == hisse]
    if donemler:
        df = df[df["donem"].isin(donemler)]

    return df[["kurum", "donem", "tip", "adet_fark", "oran2", 
               "dolasim_pct", "tks2"]].sort_values(["kurum", "donem"])


def kurum_elindeki_hisseler(kurum: str, tip: str = None, karsilastirma_donem: str = None) -> pd.DataFrame:
    """
    Belirli bir kurumun T2 son veriye göre elindeki hisseleri döndürür.

    T2 Adet (Son) → Her zaman EN SON mevcut veri (gunluk > haftalik > aylik öncelik)
    Karşılaştırma → tip bazında belirtilen dönem veya o tipin ilk dönemi
    Adet Fark     → Son - Karşılaştırma
    """
    df = _oku()
    if df.empty:
        return pd.DataFrame()

    df_kurum = df[df["kurum"] == kurum].copy()
    if df_kurum.empty:
        return pd.DataFrame()

    # ── En son dönem: günlük varsa önce onu al, yoksa haftalık, yoksa aylık ──
    for oncelik_tip in ["gunluk", "haftalik", "aylik"]:
        df_son_tip = df_kurum[df_kurum["tip"] == oncelik_tip].copy()
        if not df_son_tip.empty:
            break

    idx_son = df_son_tip.groupby("hisse")["donem"].idxmax()
    son = df_son_tip.loc[idx_son].copy()
    son = son[son["oran2"] > 0].copy()

    # ── Karşılaştırma dönemi ─────────────────────────────────────────────────
    df_kars = pd.DataFrame()
    if karsilastirma_donem:
        # Belirli dönem seçilmişse — hangi tipte olursa olsun, TÜM kurumlar için
        df_kars = df_kurum[df_kurum["donem"] == karsilastirma_donem].copy()
    elif tip:
        # Tip belirtilmişse o tipin en eski dönemini al
        df_kars_tip = df_kurum[df_kurum["tip"] == tip].copy()
        if not df_kars_tip.empty:
            en_eski = df_kars_tip["donem"].min()
            df_kars = df_kars_tip[df_kars_tip["donem"] == en_eski].copy()

    # ── Birleştir ve farkı hesapla ───────────────────────────────────────────
    if not df_kars.empty:
        kars_cols = df_kars[["hisse", "adet2", "oran2"]].copy()
        # Hisse bazında tek satır — birden fazla varsa max al
        kars_cols = kars_cols.groupby("hisse").agg(
            adet2_kars=("adet2", "last"),
            oran2_kars=("oran2", "last")
        ).reset_index()

        son = son.merge(kars_cols, on="hisse", how="left")
        # Karşılaştırma verisi olmayan hisseler için adet_fark=0
        son["adet_fark"] = (son["adet2"] - son["adet2_kars"].fillna(son["adet2"])).fillna(0)
        son["dolasim_pct"] = ((son["adet_fark"] / son["tks2"]) * 100).round(4)
        son["oran_degisim"] = (son["oran2"] - son["oran2_kars"].fillna(son["oran2"])).round(4)
    
    son = son.sort_values("oran2", ascending=False).reset_index(drop=True)

    cols = ["hisse", "donem", "tip", "adet2", "oran2", "adet_fark", "dolasim_pct", "tks2"]
    if "oran_degisim" in son.columns:
        cols.append("oran_degisim")

    return son[cols]


def kurum_donemler(kurum: str, tip: str = None) -> list:
    """Belirli bir kurumun kayıtlı dönemlerini listeler."""
    df = _oku()
    if df.empty:
        return []
    df_k = df[df["kurum"] == kurum]
    if tip:
        df_k = df_k[df_k["tip"] == tip]
    return sorted(df_k["donem"].astype(str).unique().tolist(), reverse=True)


def trend_analiz(min_hafta: int = 2) -> pd.DataFrame:
    """
    Haftalık veride trend analizi — ALAN tarafı (eski davranış korundu).
    min_hafta üst üste artış gösteren hisseler.
    """
    df = _oku()
    if df.empty:
        return pd.DataFrame()

    haftalik = df[df["tip"].isin(["haftalik", "gunluk"])]
    if haftalik.empty:
        return pd.DataFrame()

    sonuclar = []
    for hisse in haftalik["hisse"].unique():
        h_df = haftalik[haftalik["hisse"] == hisse]
        for kurum in h_df["kurum"].unique():
            k_df = h_df[h_df["kurum"] == kurum].sort_values("donem")
            if len(k_df) < min_hafta:
                continue
            vals = k_df["dolasim_pct"].tolist()
            son_n = vals[-min_hafta:]
            if all(v > 0 for v in son_n) and all(
                son_n[i] >= son_n[i-1] for i in range(1, len(son_n))
            ):
                sonuclar.append({
                    "hisse": hisse,
                    "kurum": kurum,
                    "hafta_sayisi": len(k_df),
                    "son_pct": vals[-1],
                    "toplam_pct": sum(vals),
                    "trend": "🚀 Sürekli Artış"
                })
            elif all(v > 0 for v in son_n):
                sonuclar.append({
                    "hisse": hisse,
                    "kurum": kurum,
                    "hafta_sayisi": len(k_df),
                    "son_pct": vals[-1],
                    "toplam_pct": sum(vals),
                    "trend": "🟢 Pozitif"
                })

    if not sonuclar:
        return pd.DataFrame()

    return pd.DataFrame(sonuclar).sort_values("toplam_pct", ascending=False)


def alan_satan_trend(donemler: list = None, min_donem: int = 2) -> dict:
    """
    Alan + Satan + Eşleşme analizi.

    Dönem bazlı dolasim_pct kullanır:
      - pozitif → o dönemde net ALIŞ
      - negatif → o dönemde net SATIŞ

    Short kapama şişmesi: short_kapama=True olan satırlar
    oran2 bazında değerlendirilir (dolasim_pct değil).

    Returns dict:
      {
        "alanlar":   DataFrame — hisse, kurum, son_pct, toplam_pct, donem_sayisi, trend, kurum_grup
        "satanlar":  DataFrame — hisse, kurum, son_pct, toplam_pct, donem_sayisi, trend, kurum_grup
        "eslesmeler": DataFrame — hisse, satan, alan, satan_grup, alan_grup, sinyal, satan_pct, alan_pct
      }
    """
    df = _oku()
    if df.empty:
        return {"alanlar": pd.DataFrame(), "satanlar": pd.DataFrame(), "eslesmeler": pd.DataFrame()}

    # Dönem filtresi
    if donemler:
        df = df[df["donem"].isin(donemler)]

    if df.empty:
        return {"alanlar": pd.DataFrame(), "satanlar": pd.DataFrame(), "eslesmeler": pd.DataFrame()}

    def _grup(kurum):
        if kurum in BUYUK_YERLI: return "Büyük Yerli"
        if kurum in AKILLI_PARA: return "Akıllı Para"
        if kurum in FON_YABANCI: return "Fon/Yabancı"
        return "Diğer"

    def _sinyal(satan_grup, alan_grup, alan):
        """MAL DEĞİŞİMİ sinyal tipi."""
        if alan in ["INFO"]:
            return "⚠️ Dağıtım"
        if satan_grup == "Büyük Yerli" and alan_grup == "Akıllı Para":
            return "🟢 Birikim"
        if satan_grup == "Büyük Yerli" and alan_grup == "Fon/Yabancı":
            return "🟢 Fon Girişi"
        if satan_grup == "Akıllı Para" and alan_grup == "Fon/Yabancı":
            return "🟢 Akıllı→Fon"
        if satan_grup == "Akıllı Para" and alan_grup == "Büyük Yerli":
            return "🔄 Devir"
        return "📊 Değişim"

    # Short kapama düzeltmesi: short_kapama=True → dolasim_pct yerine oran2 kullan
    if "short_kapama" in df.columns:
        df = df.copy()
        mask = df["short_kapama"] == True
        df.loc[mask, "dolasim_pct"] = df.loc[mask, "oran2"]

    # Her hisse+kurum için dönem bazlı dolasim_pct topla
    ozet = df.groupby(["hisse", "kurum"]).agg(
        toplam_pct  = ("dolasim_pct", "sum"),
        son_pct     = ("dolasim_pct", "last"),
        donem_sayisi= ("donem", "nunique"),
        son_oran2   = ("oran2", "last"),
    ).reset_index()

    ozet["kurum_grup"] = ozet["kurum"].apply(_grup)

    # Tüm dönemlerde pozitif mi? (sürekli artış)
    def _trend_etiket(row):
        h_df = df[(df["hisse"] == row["hisse"]) & (df["kurum"] == row["kurum"])].sort_values("donem")
        vals = h_df["dolasim_pct"].tolist()
        if len(vals) < min_donem:
            return "—"
        son = vals[-min_donem:]
        if all(v > 0 for v in son) and all(son[i] >= son[i-1] for i in range(1, len(son))):
            return "🚀 Sürekli Artış"
        if all(v > 0 for v in son):
            return "🟢 Pozitif"
        if all(v < 0 for v in son) and all(son[i] <= son[i-1] for i in range(1, len(son))):
            return "📉 Sürekli Azalış"
        if all(v < 0 for v in son):
            return "🔴 Negatif"
        return "↔️ Karışık"

    ozet["trend"] = ozet.apply(_trend_etiket, axis=1)

    # ALANLAR — toplam_pct > 0
    alanlar = ozet[ozet["toplam_pct"] > 0].copy()
    alanlar = alanlar.sort_values("toplam_pct", ascending=False).reset_index(drop=True)

    # SATANLAR — toplam_pct < 0
    satanlar = ozet[ozet["toplam_pct"] < 0].copy()
    satanlar["toplam_pct"] = satanlar["toplam_pct"].abs()
    satanlar["son_pct"] = satanlar["son_pct"].abs()
    satanlar = satanlar.sort_values("toplam_pct", ascending=False).reset_index(drop=True)

    # EŞLEŞMELER — aynı hissede hem alan hem satan var
    alan_hisseler  = set(alanlar["hisse"].unique())
    satan_hisseler = set(satanlar["hisse"].unique())
    ortak = alan_hisseler & satan_hisseler

    eslesmeler = []
    for hisse in ortak:
        h_alanlar  = alanlar[alanlar["hisse"] == hisse]
        h_satanlar = satanlar[satanlar["hisse"] == hisse]

        for _, s_row in h_satanlar.iterrows():
            for _, a_row in h_alanlar.iterrows():
                if s_row["kurum"] == a_row["kurum"]:
                    continue
                sinyal = _sinyal(s_row["kurum_grup"], a_row["kurum_grup"], a_row["kurum"])
                eslesmeler.append({
                    "hisse"     : hisse,
                    "satan"     : s_row["kurum"],
                    "satan_grup": s_row["kurum_grup"],
                    "satan_pct" : round(s_row["toplam_pct"], 2),
                    "alan"      : a_row["kurum"],
                    "alan_grup" : a_row["kurum_grup"],
                    "alan_pct"  : round(a_row["toplam_pct"], 2),
                    "sinyal"    : sinyal,
                    "son_oran2" : round(a_row["son_oran2"], 2),
                })

    eslesme_df = pd.DataFrame(eslesmeler) if eslesmeler else pd.DataFrame()

    # Sinyal öncelik sıralaması
    if not eslesme_df.empty:
        sinyal_sira = {
            "⚠️ Dağıtım": 0,
            "🟢 Fon Girişi": 1,
            "🟢 Akıllı→Fon": 2,
            "🟢 Birikim": 3,
            "🔄 Devir": 4,
            "📊 Değişim": 5,
        }
        eslesme_df["sinyal_sira"] = eslesme_df["sinyal"].map(sinyal_sira).fillna(9)
        eslesme_df = eslesme_df.sort_values(
            ["sinyal_sira", "satan_pct"], ascending=[True, False]
        ).drop(columns="sinyal_sira").reset_index(drop=True)

    return {
        "alanlar"   : alanlar,
        "satanlar"  : satanlar,
        "eslesmeler": eslesme_df,
    }
