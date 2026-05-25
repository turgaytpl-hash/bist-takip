"""
ai_yorum.py — BIST AI Takas Dedektifi — Yorum Motoru

Claude API ile:
  - Senaryo bazlı otomatik yorum
  - Hisse özet analizi
  - Hafıza destekli kronolojik yorum
  - Toplu tarama yorumu

Kullanım:
  from ai_yorum import hisse_yorumla, tarama_yorumla
  yorum = hisse_yorumla("RUBNS", senaryo_sonuc, hafiza)
"""

import json
import re
from typing import Optional
from takas_hafiza import hafiza_oku, hafiza_gecmis_kontrol

# ── Kurum Grupları ────────────────────────────────────────────────────────────
AKILLI_PARA = ["TERA", "MARBAS", "BULLS", "PUSULA", "ALNUS", "A1_CAPITAL"]
DAGITICI    = ["INFO", "IS_YATIRIM", "GARANTI", "YAPI_KREDI", "HALK_YATIRIM"]
BUYUK_YERLI = ["ZIRAAT_YATIRIM", "AK_YATIRIM", "DENIZ_YATIRIM", "VAKIF", "TEB"]
FON         = ["YAT_FONLARI", "EMEKLILIK"]
YABANCI     = ["YABANCI", "BANKOF", "CITIBANK", "HSBC"]

# ── Wyckoff Faz Açıklamaları ──────────────────────────────────────────────────
WYCKOFF_ACIKLAMA = {
    "Accumulation_A": "Satış dalgası durdu, ilk tepki alımları başlıyor",
    "Accumulation_B": "Birikim bölgesi — testler ve false breakdownlar",
    "Accumulation_C": "Son test / shakeout — en kritik faz, büyük fırsat",
    "Accumulation_D": "Güçlenme süreci — SOS (Sign of Strength) görülüyor",
    "Accumulation_E": "Kırılım ve markup başlangıcı",
    "Re_Accumulation": "Markup içinde konsolidasyon — birikim devam ediyor",
    "Distribution_A":  "Zirve bölgesi — buying climax yakın",
    "Distribution_B":  "Dağıtım bölgesi — kurumlar yavaş yavaş çıkıyor",
    "Distribution_C":  "Son sahte yükseliş (upthrust) — çıkış zamanı",
    "Distribution_D":  "Zayıflama süreci — düşüş yakın",
    "Distribution_E":  "Kırılım aşağı",
    "Belirsiz":        "Faz henüz netleşmedi",
}

# ═══════════════════════════════════════════════════════════════════════════════
# PROMPT ŞABLONLARI
# ═══════════════════════════════════════════════════════════════════════════════

SISTEM_PROMPT = """Sen BIST (Borsa İstanbul) uzmanı bir takas dedektifisin.
20 yıllık deneyimle Wyckoff metodolojisi ve kurumsal takas akışlarını analiz ediyorsun.

KURUM GRUPLARI VE ANLAMI:
- Akıllı Para (TERA, MARBAS, BULLS, PUSULA, ALNUS, A1_CAPITAL): Erken aşamada birikim yapan kurumlar
- Dağıtıcı (INFO, IS_YATIRIM, GARANTI, YAPI_KREDI, HALK_YATIRIM): Geç fazda dağıtım yapan kurumlar. INFO girişi = dağıtım başlangıcı
- Büyük Yerli (ZIRAAT_YATIRIM, AK_YATIRIM, DENIZ_YATIRIM, VAKIF, TEB): Pasif büyük oyuncular
- Fon (YAT_FONLARI, EMEKLILIK): Geç faz alıcıları
- Yabancı (YABANCI, BANKOF, CITIBANK, HSBC): MSCI/endeks operasyonları

WYCKOFF + BIST KURALLARI:
1. Akıllı Para alıyor + MKK bireysel azalıyor = EN GÜÇLÜ birikim sinyali
2. INFO girişi = Phase C/D — dağıtım başlamış olabilir, dikkat
3. FD artışı = bedelli/tahsisli şüphesi — tüm sinyaller geçersiz say
4. Mal devri: Yabancı/Büyük Yerli → Akıllı Para = pozitif; Akıllı Para → Fon/Dağıtıcı = negatif
5. Re-accumulation: Akıllı Para kar alıyor ama çıkmıyor = markup devam eder
6. Türk medyası/TV yoğun bahis = kurumların dağıtım aracı — çıkış sinyali
7. Blok işlem (tek günde %20+) = kurumsal anlaşma, gerçek alım

YORUM FORMATI (KESİNLİKLE UYUL):
- Max 2-3 cümle. Fazlası yasak.
- Her yorumda şu 3 bilgi: Kim alıyor/satıyor? FD durumu? Aksiyon ne?
- Güven 7+: "Giriş değerlendir" / Güven 5-7: "Takipte tut" / Güven 5-: "İzle"
- Kesinlikle Türkçe yaz
- Sayıları kullan: "TERA %12 aldı" gibi, muğlak yazma"""

def _hafiza_ozet_hazirla(hisse: str, ana_kurum: str = None) -> str:
    """Hafızadan kısa özet hazırla — prompt'a eklenecek."""
    h = hafiza_oku(hisse)
    if not h["tarihsel_senaryolar"]:
        return "Hafızada geçmiş kayıt yok."

    ist = h["istatistikler"]
    md  = h["mevcut_durum"]
    son_3 = h["tarihsel_senaryolar"][-3:]

    ozet = f"Hafıza ({ist['toplam_kayit']} kayıt): "
    ozet += f"Birikim:{ist['birikim_sayisi']} Dağıtım:{ist['dagitim_sayisi']} MalDevri:{ist['mal_devri_sayisi']}\n"
    ozet += f"Son dönemler: " + " → ".join([f"{s['donem']}:{s['senaryo']}" for s in son_3])

    if ana_kurum:
        gecmis = hafiza_gecmis_kontrol(hisse, ana_kurum)
        if gecmis["kayit_sayisi"] > 0:
            ozet += f"\n{ana_kurum} bu hissede {gecmis['kayit_sayisi']} kez alım yapmış (ilk: {gecmis['ilk_gorulme']})"

    return ozet


# ═══════════════════════════════════════════════════════════════════════════════
# ANA YORUM FONKSİYONLARI
# ═══════════════════════════════════════════════════════════════════════════════

async def hisse_yorumla_async(hisse: str, senaryo_sonuc: dict,
                               k1_kurumlar: dict = None) -> str:
    """
    Tek hisse için AI yorumu üret (async).
    Birikmiş Takip ve otomatik tarama için kullanılır.
    """
    try:
        import anthropic
        client = anthropic.Anthropic()
    except Exception:
        return _kural_tabanli_yorum(hisse, senaryo_sonuc, k1_kurumlar)

    # Veri hazırlığı
    ana_kurum = senaryo_sonuc.get("en_guclu_alan", "").split(" ")[0] if senaryo_sonuc.get("en_guclu_alan") else None
    hafiza_ozet = _hafiza_ozet_hazirla(hisse, ana_kurum)
    wyckoff_acik = WYCKOFF_ACIKLAMA.get(senaryo_sonuc.get("wyckoff_faz", "Belirsiz"), "")

    # Kurum detayları
    kurum_detay = ""
    if k1_kurumlar:
        alanlar = [(k, v) for k, v in k1_kurumlar.items() if v["net_degisim"] > 0]
        satanlar = [(k, v) for k, v in k1_kurumlar.items() if v["net_degisim"] < 0]
        alanlar = sorted(alanlar, key=lambda x: -x[1]["net_degisim"])[:3]
        satanlar = sorted(satanlar, key=lambda x: x[1]["net_degisim"])[:3]

        if alanlar:
            kurum_detay += "ALANLAR: " + ", ".join([f"{k}({v['grup']}) +{v['net_degisim']:.1f}%" for k, v in alanlar]) + "\n"
        if satanlar:
            kurum_detay += "SATANLAR: " + ", ".join([f"{k}({v['grup']}) {v['net_degisim']:.1f}%" for k, v in satanlar])

    kullanici_prompt = f"""HİSSE: {hisse}
SENARYO: {senaryo_sonuc.get('senaryo', '')}
WYCKOFF FAZ: {senaryo_sonuc.get('wyckoff_faz', '')} — {wyckoff_acik}
GÜVEN SKORU: {senaryo_sonuc.get('guven_skoru', 0)}/10
NET ALIŞ: +{senaryo_sonuc.get('net_alis', 0):.1f}% | NET SATIŞ: -{senaryo_sonuc.get('net_satis', 0):.1f}%
FD DEĞİŞİM: {senaryo_sonuc.get('fd_pct', 0):.1f}% {'⚠️ ŞÜPHELİ' if senaryo_sonuc.get('fd_supheli') else '✓ Sabit'}
MKK TRENDİ: {senaryo_sonuc.get('mkk_trend', 'bilinmiyor')}
{kurum_detay}
GEÇMİŞ: {hafiza_ozet}

Kısa, net, aksiyon odaklı yorum yaz (max 2-3 cümle):"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=200,
            system=SISTEM_PROMPT,
            messages=[{"role": "user", "content": kullanici_prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        return _kural_tabanli_yorum(hisse, senaryo_sonuc, k1_kurumlar)


def hisse_yorumla(hisse: str, senaryo_sonuc: dict,
                   k1_kurumlar: dict = None) -> str:
    """
    Tek hisse için AI yorumu üret (sync).
    """
    try:
        import anthropic
        client = anthropic.Anthropic()
    except Exception:
        return _kural_tabanli_yorum(hisse, senaryo_sonuc, k1_kurumlar)

    en_guclu_alan = senaryo_sonuc.get("en_guclu_alan", "") or ""
    ana_kurum = en_guclu_alan.split(" ")[0] if isinstance(en_guclu_alan, str) and en_guclu_alan else None






    hafiza_ozet_str = _hafiza_ozet_hazirla(hisse, ana_kurum)
    wyckoff_acik    = WYCKOFF_ACIKLAMA.get(senaryo_sonuc.get("wyckoff_faz", "Belirsiz"), "")

    kurum_detay = ""
    if k1_kurumlar:
        alanlar  = sorted([(k, v) for k, v in k1_kurumlar.items() if v["net_degisim"] > 0],
                           key=lambda x: -x[1]["net_degisim"])[:3]
        satanlar = sorted([(k, v) for k, v in k1_kurumlar.items() if v["net_degisim"] < 0],
                           key=lambda x: x[1]["net_degisim"])[:3]
        if alanlar:
            kurum_detay += "ALANLAR: " + ", ".join([f"{k}({v['grup']}) +{v['net_degisim']:.1f}%" for k, v in alanlar]) + "\n"
        if satanlar:
            kurum_detay += "SATANLAR: " + ", ".join([f"{k}({v['grup']}) {v['net_degisim']:.1f}%" for k, v in satanlar])

    kullanici_prompt = f"""HİSSE: {hisse}
SENARYO: {senaryo_sonuc.get('senaryo', '')}
WYCKOFF FAZ: {senaryo_sonuc.get('wyckoff_faz', '')} — {wyckoff_acik}
GÜVEN SKORU: {senaryo_sonuc.get('guven_skoru', 0)}/10
NET ALIŞ: +{senaryo_sonuc.get('net_alis', 0):.1f}% | NET SATIŞ: -{senaryo_sonuc.get('net_satis', 0):.1f}%
FD: {senaryo_sonuc.get('fd_pct', 0):.1f}% {'⚠️ ŞÜPHELİ' if senaryo_sonuc.get('fd_supheli') else '✓ Sabit'}
MKK: {senaryo_sonuc.get('mkk_trend', 'bilinmiyor')}
{kurum_detay}
GEÇMİŞ: {hafiza_ozet_str}

Kısa, net, aksiyon odaklı yorum (max 2-3 cümle):"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=200,
            system=SISTEM_PROMPT,
            messages=[{"role": "user", "content": kullanici_prompt}]
        )
        return response.content[0].text.strip()
    except Exception:
        return _kural_tabanli_yorum(hisse, senaryo_sonuc, k1_kurumlar)


def tarama_yorumla(senaryo_df, max_hisse: int = 10) -> dict:
    """
    Toplu tarama sonucunu yorumla.
    Sadece kritik/yüksek öncelikli hisseler için yorum üret.

    Returns: {hisse: yorum_str}
    """
    if senaryo_df is None or senaryo_df.empty:
        return {}

    # Sadece güven skoru 6+ olanları yorumla
    kritik = senaryo_df[senaryo_df["guven_skoru"] >= 6].head(max_hisse)
    yorumlar = {}

    for _, row in kritik.iterrows():
        hisse  = row["hisse"]
        sonuc  = row.to_dict()
        yorum  = hisse_yorumla(hisse, sonuc)
        yorumlar[hisse] = yorum

    return yorumlar


def hisse_sorgula(soru: str, df=None) -> str:
    """
    Kullanıcının serbest metin sorgusunu yanıtla.
    
    Desteklenen formatlar:
      "RUBNS"              → Son durum özeti
      "RUBNS detay"        → Tüm dönemler + Wyckoff
      "RUBNS 30"           → Son 30 gün
      "TERA"               → TERA'nın tüm aktif pozisyonları
      "TERA RUBNS"         → TERA'nın RUBNS hareketi
    """
    soru = soru.strip().upper()
    parcalar = soru.split()

    try:
        import anthropic
        client = anthropic.Anthropic()
        api_var = True
    except Exception:
        api_var = False
        client = None

    # ── Tek hisse sorgusu ──────────────────────────────────────────────────────
    if len(parcalar) == 1 or (len(parcalar) == 2 and parcalar[1] in ["DETAY", "30", "60", "90"]):
        hisse = parcalar[0]
        mod   = parcalar[1] if len(parcalar) > 1 else "OZET"
        hafiza = hafiza_oku(hisse)

        if not hafiza["tarihsel_senaryolar"]:
            return f"{hisse}: Hafızada kayıt yok. Dönem Tarama yapılmalı."

        if mod == "DETAY":
            prompt = f"""
{hisse} hissesinin tüm takas geçmişini analiz et:

{json.dumps(hafiza, ensure_ascii=False, indent=2)}

Tüm dönemleri kronolojik olarak özetle. 
Wyckoff fazını ve şu anki durumu değerlendir.
Aksiyon öner."""

        elif mod in ["30", "60", "90"]:
            prompt = f"""
{hisse} hissesinin son {mod} günlük takas özeti:

{json.dumps(hafiza['tarihsel_senaryolar'][-6:], ensure_ascii=False, indent=2)}

Son {mod} günde ne oldu? Trend değişti mi?"""

        else:
            md = hafiza["mevcut_durum"]
            ist = hafiza["istatistikler"]
            prompt = f"""
{hisse} hissesi için kısa özet:

Son Senaryo: {md['son_senaryo']}
Wyckoff: {md['wyckoff_faz']}
Ana Kurum: {md['en_guclu_kurum']} 
Güven: {md['guven_skoru']}/10
Ardışık Birikim: {md['toplam_birikim_donemi']} dönem
AI Yorumu: {md['ai_yorumu']}
İstatistik: {ist['toplam_kayit']} kayıt, {ist['birikim_sayisi']} birikim, {ist['dagitim_sayisi']} dağıtım

2-3 cümle ile özet ve aksiyon ver."""

    # ── Kurum sorgusu ──────────────────────────────────────────────────────────
    elif len(parcalar) == 1 and parcalar[0] in (AKILLI_PARA + DAGITICI + BUYUK_YERLI + FON + YABANCI):
        kurum = parcalar[0]
        prompt = f"{kurum} kurumunun aktif pozisyonlarını listele. Hafıza verisinden kontrol et."

    # ── Kurum + Hisse sorgusu ─────────────────────────────────────────────────
    elif len(parcalar) == 2:
        # "TERA RUBNS" → TERA'nın RUBNS'taki hareketi
        if parcalar[0] in (AKILLI_PARA + DAGITICI + BUYUK_YERLI + FON + YABANCI):
            kurum, hisse = parcalar[0], parcalar[1]
            gecmis = hafiza_gecmis_kontrol(hisse, kurum)
            prompt = f"""
{kurum} kurumunun {hisse} hissesindeki hareketi:
{json.dumps(gecmis, ensure_ascii=False, indent=2)}

Kısa yorum yap."""
        else:
            prompt = f"{soru} hakkında takas analizi yap."
    else:
        prompt = f"{soru} hakkında takas analizi yap."

    if not api_var:
        # API yoksa hafızadan kural tabanlı yorum
        hisse_kod = parcalar[-1] if parcalar else ""
        hafiza = hafiza_oku(hisse_kod)
        return hafiza_ozet(hisse_kod) if hafiza["tarihsel_senaryolar"] else f"{hisse_kod}: Hafızada kayıt yok."

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            system=SISTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        return f"Analiz yapılamadı: {str(e)}"


# ═══════════════════════════════════════════════════════════════════════════════
# KURAL TABANLI YORUM (API olmadan)
# ═══════════════════════════════════════════════════════════════════════════════

def _kural_tabanli_yorum(hisse: str, senaryo: dict, kurumlar: dict = None) -> str:
    """Claude API olmadan kural tabanlı basit yorum üret."""
    s      = senaryo.get("senaryo", "")
    wyckoff = senaryo.get("wyckoff_faz", "")
    guven  = senaryo.get("guven_skoru", 0)
    fd     = senaryo.get("fd_supheli", False)
    mkk    = senaryo.get("mkk_trend", "")
    alan   = senaryo.get("en_guclu_alan", "")
    satan  = senaryo.get("en_guclu_satan", "")

    if fd:
        return f"{hisse}: FD değişimi var, sinyaller şüpheli. Bedelli/tahsisli olabilir."

    wyckoff_ac = WYCKOFF_ACIKLAMA.get(wyckoff, "")
    mkk_yorum  = " Bireysel satıyor, kurum alıyor — güçlü sinyal." if mkk == "azalıyor" else ""

    if "Birikim" in s or "Toplama" in s:
        aksiyon = "Giriş değerlendir." if guven >= 7 else "Takipte tut."
        return f"{hisse}: {alan} alım yapıyor. {wyckoff_ac}.{mkk_yorum} Güven {guven}/10. {aksiyon}"

    elif "Mal Devri" in s:
        return f"{hisse}: {satan} → {alan} mal devri. FD sabit. Kimin aldığı önemli — grup takip et."

    elif "Dağıtım" in s:
        return f"{hisse}: Dağıtım sinyali. {satan} çıkıyor. {wyckoff_ac}. Dikkatli ol."

    elif "FD" in s:
        return f"{hisse}: Takas FD değişti. Bedelli/tahsisli şüphesi. Sinyal geçersiz sayılabilir."

    return f"{hisse}: {s}. Güven {guven}/10."


# ── Test ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    test_sonuc = {
        "senaryo":      "🟢 Birikim",
        "wyckoff_faz":  "Accumulation_C",
        "guven_skoru":  8.2,
        "net_alis":     12.4,
        "net_satis":    1.2,
        "fd_pct":       0.0,
        "fd_supheli":   False,
        "mkk_trend":    "azalıyor",
        "en_guclu_alan": "TERA +12.4%",
        "en_guclu_satan": "YABANCI -1.2%",
    }
    test_kurumlar = {
        "TERA":    {"net_degisim": 12.4, "grup": "Akıllı Para"},
        "YABANCI": {"net_degisim": -1.2, "grup": "Yabancı"},
    }

    print("Kural tabanlı yorum:")
    print(_kural_tabanli_yorum("RUBNS", test_sonuc, test_kurumlar))
    print()
    print("API yorumu (API yoksa kural tabanlı):")
    print(hisse_yorumla("RUBNS", test_sonuc, test_kurumlar))
