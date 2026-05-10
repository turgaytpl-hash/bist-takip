"""
fon_parser.py — Türk fon portföy PDF parser
Üç format destekler:
  FORMAT A: Klasik (BHA, RKH, PHE, BMU...) — detaylı tablo, ISIN, alış tarihi
  FORMAT B: Basit  (CPT/Rota)               — KOD | ŞİRKET | NOMİNAL | RAYİÇ | %
  FORMAT C: ST1/Strateji                    — KOD | ŞİRKET | ISIN | NOMİNAL | TOPLAM | GRUP% | TOPLAM%
             (pdftotext -layout ile okunur; metin gömülü değilse OCR fallback)
"""

import re
import subprocess
import pdfplumber
from pathlib import Path


# ─────────────────────────────────────────────
# YARDIMCI FONKSİYONLAR
# ─────────────────────────────────────────────

def _to_float(s):
    s = str(s).strip()
    if not s or s == '-':
        return 0.0
    if ',' in s and '.' in s:
        if s.rfind(',') > s.rfind('.'):
            s = s.replace('.', '').replace(',', '.')
        else:
            s = s.replace(',', '')
    elif ',' in s:
        s = s.replace(',', '.')
    try:
        return float(s)
    except Exception:
        return 0.0


def _to_float_ocr(s):
    s = str(s).strip()
    s = re.sub(r'[oO©](?=\d)', '0', s)
    s = re.sub(r'(?<=\d)[oO©]', '0', s)
    s = s.replace(' ', '').replace('\u00a0', '')
    return _to_float(s)


_DONEM_MAP = {
    'ocak':'Ocak','subat':'Şubat','mart':'Mart','nisan':'Nisan',
    'mayis':'Mayıs','haziran':'Haziran','temmuz':'Temmuz',
    'agustos':'Ağustos','eylul':'Eylül','ekim':'Ekim',
    'kasim':'Kasım','aralik':'Aralık',
}


def _normalize_donem(raw):
    m = re.search(
        r'(ocak|şubat|subat|mart|nisan|mayıs|mayis|haziran|temmuz|ağustos|agustos'
        r'|eylül|eylul|ekim|kasım|kasim|aralık|aralik)'
        r'[-\s]+(\d{4})',
        raw, re.IGNORECASE,
    )
    if m:
        key = m.group(1).lower().replace('ş','s').replace('ğ','g').replace('ı','i').replace('ü','u').replace('ö','o')
        ay  = _DONEM_MAP.get(key, m.group(1).capitalize())
        return f"{ay}-{m.group(2)}"
    return raw


def _donem_from_date(text):
    MONTHS = {
        '01':'Ocak','02':'Şubat','03':'Mart','04':'Nisan',
        '05':'Mayıs','06':'Haziran','07':'Temmuz','08':'Ağustos',
        '09':'Eylül','10':'Ekim','11':'Kasım','12':'Aralık',
    }
    # Bitiş tarihi: son dd/MM/yyyy
    matches = re.findall(r'(\d{2})/(\d{2})/(\d{4})', text)
    if matches:
        dd, mm, yy = matches[-1]
        return f"{MONTHS.get(mm, mm)}-{yy}"
    return ''


def _extract_header(text):
    info = {'fon_adi':'', 'kurucu':'', 'nvd':0.0, 'donem':''}

    for pat in [
        r'(?:A[-.)]\s*FONUN ADI|A-FONUN ADI|Fonun Adı)\s*:?\s*(.+)',
    ]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            info['fon_adi'] = m.group(1).strip()[:100]
            break

    if not info['fon_adi']:
        m = re.search(r'^([A-Z]{2,4})\s+MART\s+\d{4}\s+PORTFÖY', text, re.MULTILINE|re.IGNORECASE)
        if m:
            info['fon_adi'] = m.group(0).strip()

    m = re.search(
        r'(?:Kurucunun Ünvanı|KURUCUNUN ÜNVANI|KURUCUNUN UNVANI|B[-.)]\s*KURUCUNUN)\s*[:\s]+\n?([^\n]+)',
        text, re.IGNORECASE,
    )
    if m:
        info['kurucu'] = m.group(1).strip()

    for pat in [
        r'FON TOPLAM DEĞERİ\s+([\d.,]+)',
        r'D-TOPLAM DEGER\s+([\d.,]+)',
        r'TOPLAM DEĞER/NET VARLIK DEĞERİ\s*[:\s]+([\d.,]+)',
        r'Toplam Değer/Net Varlık Değeri\s*:\s*([\d.,]+)',
        r'E[-.)]\s*TOPLAM DEĞER.*?:\s*([\d.,]+)',
    ]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            info['nvd'] = _to_float(m.group(1))
            break

    # Dönem: önce ay adı, sonra tarih aralığından
    m = re.search(
        r'(ocak|şubat|subat|mart|nisan|mayıs|mayis|haziran|temmuz|ağustos|agustos'
        r'|eylül|eylul|ekim|kasım|kasim|aralık|aralik)[-\s]+(\d{4})',
        text, re.IGNORECASE,
    )
    if m:
        info['donem'] = _normalize_donem(f"{m.group(1)}-{m.group(2)}")
    else:
        info['donem'] = _donem_from_date(text)

    return info


# ─────────────────────────────────────────────
# FORMAT A — Klasik
# ─────────────────────────────────────────────

_CLASSIC_RE = re.compile(
    r'^([A-Z][A-Z0-9]{2,5})\s+TL\s+\S.*?(TR[A-Z0-9]{9,})\s+'
    r'(-?[\d.]+,\d+)\s+([\d.]+,\d+)\s+(\d{2}/\d{2}/\d{2})\s+'
    r'(\d{5,})\s+([\d.]+,\d+)\s+(-?[\d.]+,\d+)\s+(-?[\d.,]+)\s+(-?[\d.,]+)\s+(-?[\d.,]+)',
    re.MULTILINE,
)


def _parse_classic(text):
    rows = {}
    for m in _CLASSIC_RE.finditer(text):
        kod     = m.group(1)
        nominal = _to_float(m.group(3))
        if nominal <= 0:
            continue
        piyasa   = _to_float(m.group(4))
        tarih    = m.group(5)
        alis_fiy = _to_float(m.group(7))
        toplam   = _to_float(m.group(8))
        fpd      = _to_float(m.group(9))
        if kod in rows:
            rows[kod]['nominal']      += nominal
            rows[kod]['toplam_deger'] += toplam
            rows[kod]['fpd_pct']      += fpd
        else:
            rows[kod] = {
                'hisse':kod, 'piyasa_fiy':piyasa, 'alis_fiy':alis_fiy,
                'alis_tarihi':tarih, 'nominal':nominal, 'toplam_deger':toplam,
                'fpd_pct':fpd, 'format':'klasik',
            }
    return list(rows.values())


# ─────────────────────────────────────────────
# FORMAT B — Basit CPT/Rota
# ─────────────────────────────────────────────

_SIMPLE_RE = re.compile(
    r'^([A-Z][A-Z0-9]{2,5})\s+(.+?)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+([\d.]+)%',
    re.MULTILINE,
)
_STOCK_BLOCK_RE = re.compile(
    r'A\)\s*HİSSE SENETLERİ(.+?)(?:B\)|TOPLAM:)',
    re.DOTALL | re.IGNORECASE,
)


def _parse_simple(text):
    rows = []
    m_block = _STOCK_BLOCK_RE.search(text)
    block = m_block.group(1) if m_block else text
    for m in _SIMPLE_RE.finditer(block):
        kod = m.group(1)
        if re.match(r'^US|^NL|^GB|^DE', kod):
            continue
        rows.append({
            'hisse':kod, 'piyasa_fiy':0.0, 'alis_fiy':0.0, 'alis_tarihi':'',
            'nominal':_to_float(m.group(3)), 'toplam_deger':_to_float(m.group(4)),
            'fpd_pct':float(m.group(5)), 'format':'basit',
        })
    return rows


# ─────────────────────────────────────────────
# FORMAT C — ST1/Strateji
# ─────────────────────────────────────────────

_BIST_RE  = re.compile(r'^([A-Z][A-Z0-9]{2,4})\s')
_NUM_TAIL = re.compile(
    r'([\d]{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?)\s+'
    r'([\d]{1,3}(?:[.,]\d{3})*(?:\.\d+)?)\s+'
    r'([\d.]+)\s+([\d.]+)\s*$'
)
_SKIP_WORDS = {'VIOP','REPO','TPP','GRUP','TOPLAM'}
_SKIP_RE    = re.compile(r'Toplam|Grup|Portföy|Fon|Türev|Diğer|TABLOSU', re.I)


def _extract_layout_text(path):
    r = subprocess.run(['pdftotext', '-layout', path, '-'], capture_output=True, text=True)
    return r.stdout or ''


def _is_text_pdf(path):
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ''
            if len(t.strip()) > 50:
                return True
    return False


def _ocr_pdf(path):
    try:
        import fitz
        import pytesseract
        from PIL import Image
        import io
    except ImportError as e:
        raise ImportError(f"OCR için: pip install pymupdf pytesseract pillow") from e

    doc = fitz.open(path)
    full = ''
    for page in doc:
        mat = fitz.Matrix(200/72, 200/72)
        pix = page.get_pixmap(matrix=mat)
        img = Image.open(io.BytesIO(pix.tobytes('png')))
        full += pytesseract.image_to_string(img, lang='tur', config='--psm 6') + '\n'
    return full


def _parse_st1_lines(lines, use_ocr=False):
    rows = {}
    float_fn = _to_float_ocr if use_ocr else _to_float

    def clean(line):
        if use_ocr:
            line = re.sub(r'\s+[oO©]\s+', ' ', line)
        return line.strip()

    i = 0
    while i < len(lines):
        line = clean(lines[i])
        m = _BIST_RE.match(line)
        if not m or m.group(1) in _SKIP_WORDS or _SKIP_RE.search(line):
            i += 1
            continue

        kod = m.group(1)
        nominal = toplam = grup_pct = toplam_pct = 0.0

        nm = _NUM_TAIL.search(line)
        if nm:
            nominal    = float_fn(nm.group(1))
            toplam     = float_fn(nm.group(2))
            try:
                grup_pct   = float(nm.group(3))
                toplam_pct = float(nm.group(4))
            except ValueError:
                pass
        else:
            combined = line
            for j in range(1, 5):
                if i + j >= len(lines):
                    break
                nxt = clean(lines[i + j])
                if not nxt:
                    break
                if _BIST_RE.match(nxt) and not _SKIP_RE.search(nxt):
                    break
                combined = combined + ' ' + nxt
                nm2 = _NUM_TAIL.search(combined)
                if nm2:
                    i += j
                    nominal    = float_fn(nm2.group(1))
                    toplam     = float_fn(nm2.group(2))
                    try:
                        grup_pct   = float(nm2.group(3))
                        toplam_pct = float(nm2.group(4))
                    except ValueError:
                        pass
                    break

        min_toplam = 100 if use_ocr else 0
        if toplam > min_toplam and grup_pct <= 15:
            if kod in rows:
                rows[kod]['nominal']      += nominal
                rows[kod]['toplam_deger'] += toplam
                rows[kod]['fpd_pct']      += grup_pct
            else:
                rows[kod] = {
                    'hisse':kod, 'nominal':nominal, 'toplam_deger':toplam,
                    'fpd_pct':grup_pct, 'toplam_pct':toplam_pct,
                    'piyasa_fiy':0.0, 'alis_fiy':0.0, 'alis_tarihi':'',
                    'format':'st1_ocr' if use_ocr else 'st1',
                }
        i += 1

    return rows


def _parse_st1(path):
    use_ocr = not _is_text_pdf(path)
    text    = _ocr_pdf(path) if use_ocr else _extract_layout_text(path)

    start_m = re.search(r"(?:III-FON|IN-FON|I{1,3}[-.]?FON)\s*PORTFOY|FON PORTFOY DEGER", text, re.IGNORECASE)
    end_m   = re.search(r'IV-FON TOPLAM',  text, re.IGNORECASE)

    if start_m and end_m:
        block = text[start_m.start(): end_m.start()]
    elif start_m:
        block = text[start_m.start():]
    else:
        block = text

    rows = _parse_st1_lines(block.split('\n'), use_ocr=use_ocr)
    return list(rows.values())


# ─────────────────────────────────────────────
# ANA PARSE FONKSİYONU
# ─────────────────────────────────────────────

def parse_fon_pdf(path):
    """
    Tek bir fon PDF dosyasını parse et.
    Returns:
        {
            'fon_kodu': str,
            'fon_adi' : str,
            'kurucu'  : str,
            'nvd'     : float,
            'donem'   : str,      # 'Mart-2026' normalize
            'hisseler': [{'hisse', 'fpd_pct', 'nominal', 'toplam_deger', ...}]
        }
    """
    path = str(path)
    fon_kodu = Path(path).stem.replace('_', ' ').split(' ')[0].upper()

    with pdfplumber.open(path) as pdf:
        full_text = '\n'.join(p.extract_text() or '' for p in pdf.pages)

    header = _extract_header(full_text)

    # Dönem dosya adından dene (hâlâ boşsa)
    if not header['donem']:
        stem = Path(path).stem.upper()
        AY_MAP = [
            ('OCAK','Ocak'),('SUBAT','Şubat'),('MART','Mart'),('NISAN','Nisan'),
            ('MAYIS','Mayıs'),('HAZIRAN','Haziran'),('TEMMUZ','Temmuz'),
            ('AGUSTOS','Ağustos'),('EYLUL','Eylül'),('EKIM','Ekim'),
            ('KASIM','Kasım'),('ARALIK','Aralık'),
        ]
        import datetime
        yil = datetime.date.today().year
        for tr, norm in AY_MAP:
            if tr in stem:
                header['donem'] = f"{norm}-{yil}"
                break

    # Görsel PDF (pdfplumber metin çıkaramıyorsa) — OCR ile tekrar oku
    is_visual = len(full_text.strip()) < 50
    if is_visual:
        ocr_text = _ocr_pdf(path)
        if not header['nvd'] or not header['donem']:
            ocr_header = _extract_header(ocr_text)
            if not header['nvd']:
                header['nvd'] = ocr_header['nvd']
            if not header['donem']:
                header['donem'] = ocr_header['donem']
            if not header['fon_adi']:
                header['fon_adi'] = ocr_header['fon_adi']
    else:
        ocr_text = None

    # Format tespiti
    if (re.search(r'III-FON PORTFOY DEGERI TABLOSU', full_text, re.IGNORECASE) or
            is_visual):
        # Format C — ST1/Strateji (görsel PDF otomatik OCR kullanır)
        hisseler = _parse_st1(path)
    elif (re.search(r'Rayiç Değeri\s*%', full_text) or
          re.search(r'A\)\s*HİSSE SENETLERİ', full_text)):
        hisseler = _parse_simple(full_text)
    else:
        hisseler = _parse_classic(full_text)

    hisseler.sort(key=lambda x: x['fpd_pct'], reverse=True)

    return {
        'fon_kodu': fon_kodu,
        'fon_adi':  header['fon_adi'] or fon_kodu,
        'kurucu':   header['kurucu'],
        'nvd':      header['nvd'],
        'donem':    header['donem'],
        'hisseler': hisseler,
    }
