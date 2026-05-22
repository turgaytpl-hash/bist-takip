"""
kap_fon_indir.py — TEFAS'tan ilk 40 yerli hisse senedi fonunu çek,
KAP'tan PDF'lerini indir, fon_parser ile parse et, _fonlar.json'a kaydet.

Kullanım:
    python kap_fon_indir.py              # Bu ay
    python kap_fon_indir.py 2026 04      # Nisan 2026
"""

import sys
import json
import time
import requests
import re
from pathlib import Path
from datetime import date, datetime

# ─── Ayarlar ────────────────────────────────────────────────
DATA_DIR   = Path(__file__).parent / "FON"
DONEM_FILE = DATA_DIR / "_fonlar.json"
DATA_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.tefas.gov.tr/",
}

# ─── Yardımcı ───────────────────────────────────────────────

def donem_normalize(ay: int, yil: int) -> str:
    AYLAR = {1:'Ocak',2:'Şubat',3:'Mart',4:'Nisan',5:'Mayıs',6:'Haziran',
             7:'Temmuz',8:'Ağustos',9:'Eylül',10:'Ekim',11:'Kasım',12:'Aralık'}
    return f"{AYLAR[ay]}-{yil}"


def load_donemler() -> dict:
    if DONEM_FILE.exists():
        return json.loads(DONEM_FILE.read_text(encoding='utf-8'))
    return {}


def save_donemler(d: dict):
    DONEM_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding='utf-8')


# ─── TEFAS: İlk 40 yerli hisse senedi fonu ─────────────────

def tefas_ilk40(tarih: str) -> list:
    """
    pytefas ile hisse senedi fonlarını çek, büyüklüğe göre ilk 40'ı döndür.
    tarih: 'YYYY-MM-DD'
    """
    print(f"📡 TEFAS'tan {tarih} tarihi için veri çekiliyor...")
    try:
        import pytefas
        t = pytefas.Crawler()
        df = t.fetch(tarih, columns="info", kind="YAT")

        if df is None or df.empty:
            print("⚠️ TEFAS'tan veri gelmedi.")
            return []

        # Hisse senedi yoğun fonları filtrele (fon adında HS veya HİSSE geçenler)
        maske = df['fund_name'].str.contains('HİSSE|HISSE|HS YOĞUN|HS YOGUN', case=False, na=False)
        df_hs = df[maske].copy()

        if df_hs.empty:
            # Filtre çok dar ise tümünü al
            df_hs = df.copy()

        # Büyüklüğe göre sırala
        df_hs = df_hs.sort_values('portfolio_size', ascending=False).head(40)

        fon_kodlari = df_hs['fund_code'].tolist()
        print(f"✅ {len(fon_kodlari)} fon bulundu")
        for _, row in df_hs.head(5).iterrows():
            print(f"   {row['fund_code']:6} — {str(row['fund_name'])[:50]}")
        print("   ...")
        return fon_kodlari

    except ImportError:
        print("❌ pytefas yüklü değil: pip install pytefas")
        return []
    except Exception as e:
        print(f"❌ TEFAS hatası: {e}")
        return []


# ─── KAP: Fon koduna göre son portföy PDF'i bul ve indir ───


def kap_pdf_indir(fon_kodu: str, yil: int, ay: int, kayit_dir: Path) -> Path | None:
    """
    KAP bildirim sorgulama API'si ile fon portföy PDF'ini bul ve indir.
    """
    # 1. Bildirim listesini sorgula
    try:
        url = "https://kap.org.tr/tr/api/disclosureList"
        params = {
            "memberCode"    : fon_kodu,
            "disclosureType": "DG",
            "year"          : str(yil),
            "period"        : str(ay),
        }
        kap_headers = {
            **HEADERS,
            "Referer": f"https://kap.org.tr/tr/fon-bilgileri/bildirimler/{fon_kodu.lower()}",
        }
        r = requests.get(url, params=params, headers=kap_headers, timeout=15)
        r.raise_for_status()
        bildirimler = r.json()
    except Exception as e:
        # Alternatif endpoint dene
        try:
            url2 = f"https://kap.org.tr/tr/api/fund/{fon_kodu}/disclosures"
            r2 = requests.get(url2, headers=kap_headers, timeout=15)
            bildirimler = r2.json()
        except Exception:
            bildirimler = []

    # 2. Bildirimden PDF ekini bul
    pdf_url = None
    bildirim_id = None

    if isinstance(bildirimler, list):
        for b in bildirimler:
            tip = b.get("disclosureType") or b.get("bildiriTipi") or ""
            if "DG" in str(tip):
                bildirim_id = b.get("disclosureId") or b.get("bildirimId")
                if bildirim_id:
                    break

    # 3. Bildirim detayından PDF URL'si al
    if bildirim_id:
        try:
            det_url = f"https://kap.org.tr/tr/api/disclosure/{bildirim_id}"
            r3 = requests.get(det_url, headers=kap_headers, timeout=15)
            det = r3.json()
            ekler = det.get("attachments") or det.get("ekler") or []
            for ek in ekler:
                dosya_id = ek.get("attachmentId") or ek.get("ekId")
                if dosya_id:
                    pdf_url = f"https://kap.org.tr/tr/api/file/download/{dosya_id}"
                    break
        except Exception:
            pass

    # 4. Fallback: fon adı+dönem formatında dene
    if not pdf_url:
        # Formatlar: FON_YYYY.MM.pdf veya FON_YYYY_MM.pdf
        for fmt in [
            f"https://kap.org.tr/tr/api/file/download/{fon_kodu}_{yil}.{ay:02d}",
            f"https://kap.org.tr/tr/api/BildirimPdf/{fon_kodu}_{yil}_{ay:02d}",
        ]:
            try:
                r_test = requests.head(fmt, headers=HEADERS, timeout=10)
                if r_test.status_code == 200:
                    pdf_url = fmt
                    break
            except Exception:
                pass

    if not pdf_url:
        print(f"   ⚠️ {fon_kodu}: PDF URL bulunamadı")
        return None

    # 5. PDF'i indir
    try:
        r_pdf = requests.get(pdf_url, headers=HEADERS, timeout=30)
        r_pdf.raise_for_status()
        ct = r_pdf.headers.get("Content-Type", "")
        if "pdf" not in ct.lower() and len(r_pdf.content) < 1000:
            print(f"   ⚠️ {fon_kodu}: Geçersiz içerik ({ct})")
            return None

        dosya_yolu = kayit_dir / f"{fon_kodu}_{yil}_{ay:02d}.pdf"
        dosya_yolu.write_bytes(r_pdf.content)
        print(f"   ✅ {fon_kodu}: İndirildi ({len(r_pdf.content)//1024} KB)")
        return dosya_yolu

    except Exception as e:
        print(f"   ❌ {fon_kodu}: {e}")
        return None


# ─── ANA FONKSİYON ──────────────────────────────────────────

def main():
    # Argümanlardan yıl/ay al
    bugun = date.today()
    if len(sys.argv) == 3:
        yil, ay = int(sys.argv[1]), int(sys.argv[2])
    else:
        # Geçen ay (raporlar ~1 ay gecikmeyle yayınlanır)
        ay  = bugun.month - 1 if bugun.month > 1 else 12
        yil = bugun.year if bugun.month > 1 else bugun.year - 1

    donem     = donem_normalize(ay, yil)
    tarih_str = f"{yil}-{ay:02d}-{bugun.day:02d}"
    gecici_dir = DATA_DIR / "tmp_pdf"
    gecici_dir.mkdir(exist_ok=True)

    print(f"\n{'='*55}")
    print(f"  AMOS Fon İndirici — {donem}")
    print(f"{'='*55}\n")

    # 1. TEFAS'tan ilk 40 fon
    fon_kodlari = tefas_ilk40(tarih_str)
    if not fon_kodlari:
        print("Fon listesi alınamadı. Çıkılıyor.")
        return

    # 2. Mevcut veriyi yükle
    donemler = load_donemler()
    if donem not in donemler:
        donemler[donem] = {}

    # 3. Her fon için PDF indir ve parse et
    try:
        from fon_parser import parse_fon_pdf
    except ImportError:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).parent))
        from fon_parser import parse_fon_pdf

    basarili, hatali = [], []

    for i, fon_kodu in enumerate(fon_kodlari, 1):
        print(f"\n[{i:2}/{len(fon_kodlari)}] {fon_kodu}")

        # PDF indir
        pdf_yolu = kap_pdf_indir(fon_kodu, yil, ay, gecici_dir)
        if not pdf_yolu:
            hatali.append(fon_kodu)
            time.sleep(0.5)
            continue

        # Parse et
        try:
            sonuc = parse_fon_pdf(str(pdf_yolu))
            donemler[donem][sonuc['fon_kodu']] = {
                'fon_adi' : sonuc['fon_adi'],
                'kurucu'  : sonuc['kurucu'],
                'nvd'     : sonuc['nvd'],
                'hisseler': sonuc['hisseler'],
            }
            basarili.append(f"{fon_kodu} ({len(sonuc['hisseler'])} hisse)")
            pdf_yolu.unlink()  # Geçici dosyayı sil
        except Exception as e:
            print(f"   ❌ Parse hatası: {e}")
            hatali.append(fon_kodu)

        time.sleep(0.3)  # Rate limit için bekle

    # 4. Kaydet
    save_donemler(donemler)

    # 5. Özet
    print(f"\n{'='*55}")
    print(f"  {donem} TAMAMLANDI")
    print(f"{'='*55}")
    print(f"✅ Başarılı: {len(basarili)}")
    for b in basarili:
        print(f"   {b}")
    if hatali:
        print(f"\n❌ Hatalı: {len(hatali)}")
        for h in hatali:
            print(f"   {h}")
    print(f"\n💾 Kaydedildi: {DONEM_FILE}")


if __name__ == "__main__":
    main()
