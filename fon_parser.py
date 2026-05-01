"""
fon_parser.py — Türk fon portföy PDF parser
İki format destekler:
  FORMAT A: Klasik (BHA, RKH, PHE, BMU...) — detaylı tablo, ISIN, alış tarihi
  FORMAT B: Basit  (CPT/Rota)               — KOD | ŞİRKET | NOMİNAL | RAYİÇ | %
"""

import re
import pdfplumber
from pathlib import Path


# ─────────────────────────────────────────────
# YARDIMCI FONKSİYONLAR
# ─────────────────────────────────────────────

def _to_float(s: str) -> float:
    """'1.234.567,89' veya '1,234,567.89' → float"""
    s = s.strip()
    if not s or s == '-':
        return 0.0
    # Nokta ondalık mı, binlik mi?
    if ',' in s and '.' in s:
        if s.rfind(',') > s.rfind('.'):   # Türk formatı: 1.234,56
            s = s.replace('.', '').replace(',', '.')
        else:                              # İngiliz formatı: 1,234.56
            s = s.replace(',', '')
    elif ',' in s:
        s = s.replace(',', '.')
    try:
        return float(s)
    except:
        return 0.0


def _extract_header(text: str) -> dict:
    """Fon adı, kurucu, NVD çıkar — her iki format için"""
    info = {'fon_adi': '', 'kurucu': '', 'nvd': 0.0, 'donem': 'Mart-2026'}

    # Fon adı
    m = re.search(r'(?:A[-.)]\s*FONUN ADI|Fonun Adı)\s*:?\s*(.+)', text, re.IGNORECASE)
    if m:
        info['fon_adi'] = m.group(1).strip()[:100]

    # CPT tarzı başlık
    if not info['fon_adi']:
        m = re.search(r'^([A-Z]{2,4})\s+MART\s+\d{4}\s+PORTFÖY', text, re.MULTILINE | re.IGNORECASE)
        if m:
            info['fon_adi'] = m.group(0).strip()

    # Kurucu
    m = re.search(r'(?:Kurucunun Ünvanı|KURUCUNUN ÜNVANI|B[-.)]\s*KURUCUNUN)\s*[:\s]+\n?([^\n]+)', text, re.IGNORECASE)
    if m:
        info['kurucu'] = m.group(1).strip()

    # NVD — farklı isimler
    for pat in [
        r'FON TOPLAM DEĞERİ\s+([\d.,]+)',
        r'TOPLAM DEĞER/NET VARLIK DEĞERİ\s*[:\s]+([\d.,]+)',
        r'Toplam Değer/Net Varlık Değeri\s*:\s*([\d.,]+)',
        r'E[-.)]\s*TOPLAM DEĞER.*?:\s*([\d.,]+)',
    ]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            info['nvd'] = _to_float(m.group(1))
            break

    # Dönem
    m = re.search(r'(Ocak|Şubat|Mart|Nisan|Mayıs|Haziran|Temmuz|Ağustos|Eylül|Ekim|Kasım|Aralık)[-\s]+(\d{4})', text, re.IGNORECASE)
    if m:
        info['donem'] = f"{m.group(1).capitalize()}-{m.group(2)}"

    return info


# ─────────────────────────────────────────────
# FORMAT A — Klasik (BHA, RKH, PHE, BMU...)
# KOD TL KISAAD ISIN NOMINAL PIYASA_FIY ALIS_TARIHI SOZLESME ALIS_FIY TOPLAM FPD% FTD% GRUP%
# ─────────────────────────────────────────────

_CLASSIC_RE = re.compile(
    r'^([A-Z][A-Z0-9]{2,5})\s+'           # hisse kodu
    r'TL\s+'                               # döviz cinsi
    r'\S.*?'                               # kısa şirket adı (lazy, tek satır)
    r'(TR[A-Z0-9]{9,})\s+'                # ISIN
    r'(-?[\d.]+,\d+)\s+'                  # nominal
    r'([\d.]+,\d+)\s+'                    # piyasa fiyatı (güncel)
    r'(\d{2}/\d{2}/\d{2})\s+'            # satın alış tarihi
    r'(\d{5,})\s+'                        # borsa sözleşme no
    r'([\d.]+,\d+)\s+'                    # birim alış fiyatı
    r'(-?[\d.]+,\d+)\s+'                  # toplam değer TL
    r'(-?[\d.,]+)\s+'                     # FPD %
    r'(-?[\d.,]+)\s+'                     # FTD %
    r'(-?[\d.,]+)',                        # GRUP %
    re.MULTILINE,
)


def _parse_classic(text: str) -> list:
    rows = {}
    for m in _CLASSIC_RE.finditer(text):
        kod      = m.group(1)
        nominal  = _to_float(m.group(3))
        if nominal <= 0:
            continue                       # negatif = kısa satış, atla
        piyasa   = _to_float(m.group(4))
        tarih    = m.group(5)
        alis_fiy = _to_float(m.group(7))
        toplam   = _to_float(m.group(8))
        fpd      = _to_float(m.group(9))

        if kod in rows:
            rows[kod]['nominal']     += nominal
            rows[kod]['toplam_deger'] += toplam
            rows[kod]['fpd_pct']     += fpd
        else:
            rows[kod] = {
                'hisse'      : kod,
                'piyasa_fiy' : piyasa,
                'alis_fiy'   : alis_fiy,
                'alis_tarihi': tarih,
                'nominal'    : nominal,
                'toplam_deger': toplam,
                'fpd_pct'    : fpd,
                'format'     : 'klasik',
            }
    return list(rows.values())


# ─────────────────────────────────────────────
# FORMAT B — Basit CPT/Rota
# KOD  ŞİRKET_ADI  NOMİNAL  RAYİÇ_DEĞER  %
# ─────────────────────────────────────────────

_SIMPLE_RE = re.compile(
    r'^([A-Z][A-Z0-9]{2,5})\s+'           # hisse kodu (BIST)
    r'(.+?)\s+'                            # şirket adı
    r'([\d,]+\.?\d*)\s+'                  # nominal
    r'([\d,]+\.?\d*)\s+'                  # rayiç değer
    r'([\d.]+)%',                          # oran %
    re.MULTILINE,
)

# HİSSE SENETLERİ bloğunu bul
_STOCK_BLOCK_RE = re.compile(
    r'A\)\s*HİSSE SENETLERİ(.+?)(?:B\)|TOPLAM:)',
    re.DOTALL | re.IGNORECASE,
)


def _parse_simple(text: str) -> list:
    rows = []
    # Sadece hisse bloğundan çek
    m_block = _STOCK_BLOCK_RE.search(text)
    block = m_block.group(1) if m_block else text

    for m in _SIMPLE_RE.finditer(block):
        kod    = m.group(1)
        # Yabancı ISIN kodlarını atla
        if re.match(r'^US|^NL|^GB|^DE', kod):
            continue
        nominal = _to_float(m.group(3))
        rayic   = _to_float(m.group(4))
        pct     = float(m.group(5))

        rows.append({
            'hisse'      : kod,
            'piyasa_fiy' : 0.0,       # format B'de yok
            'alis_fiy'   : 0.0,
            'alis_tarihi': '',
            'nominal'    : nominal,
            'toplam_deger': rayic,
            'fpd_pct'    : pct,
            'format'     : 'basit',
        })
    return rows


# ─────────────────────────────────────────────
# ANA PARSE FONKSİYONU
# ─────────────────────────────────────────────

def parse_fon_pdf(path: str) -> dict:
    """
    Tek bir fon PDF dosyasını parse et.
    Returns:
        {
            'fon_kodu': str,
            'fon_adi' : str,
            'kurucu'  : str,
            'nvd'     : float,
            'donem'   : str,
            'hisseler': [{'hisse', 'fpd_pct', 'nominal', 'toplam_deger', 'alis_tarihi', ...}]
        }
    """
    path = str(path)
    fon_kodu = Path(path).stem.split('_')[0].upper()

    with pdfplumber.open(path) as pdf:
        full_text = "\n".join(p.extract_text() or "" for p in pdf.pages)

    header = _extract_header(full_text)

    # Format tespiti: CPT/Rota basit format mı?
    if re.search(r'Rayiç Değeri\s*%', full_text) or \
       re.search(r'A\)\s*HİSSE SENETLERİ', full_text):
        hisseler = _parse_simple(full_text)
    else:
        hisseler = _parse_classic(full_text)

    # Sırala: ağırlık azalan
    hisseler.sort(key=lambda x: x['fpd_pct'], reverse=True)

    return {
        'fon_kodu': fon_kodu,
        'fon_adi' : header['fon_adi'] or fon_kodu,
        'kurucu'  : header['kurucu'],
        'nvd'     : header['nvd'],
        'donem'   : header['donem'],
        'hisseler': hisseler,
    }
