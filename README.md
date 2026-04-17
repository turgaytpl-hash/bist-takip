# BIST Akıllı Para Takip Sistemi 📊

MKK kurumsal oran + Yabancı/Fon/Emeklilik takas + TERA/BULLS/PUSULA takibini
tek bir dashboard'da birleştirir.

## 🚀 Streamlit Cloud'da Çalıştırma

1. Bu repoyu GitHub'a fork/push et
2. [share.streamlit.io](https://share.streamlit.io) → "New app" → repo seç
3. Main file: `app.py`
4. Deploy!

## 💻 Lokal Çalıştırma

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 📁 Klasör Yapısı

```
bist_app/
├── app.py                  ← Ana uygulama
├── requirements.txt
├── data/
│   ├── haftalik/           ← Haftalık CSV geçmişi (otomatik)
│   └── aylik/              ← Aylık CSV geçmişi (otomatik)
└── src/
    ├── depo.py             ← Veri yönetimi
    ├── parser.py           ← xlsx okuma
    └── excel_export.py     ← Excel indirme
```

## 📅 Haftalık Kullanım (Pazartesi)

Veri Yükle sekmesi → Haftalık:
- Dönem: `2025_17`
- Yabancılar xlsx → yükle
- MKK xlsx → yükle (1 gün geriden)
- TERA / BULLS / PUSULA → opsiyonel

## 📆 Aylık Kullanım (Ay Sonu)

Veri Yükle sekmesi → Aylık:
- Dönem: `2025_04`  
- Yabancılar + Fon + Emeklilik + MKK + Özel Fonlar

## 🔍 Ana Tablo Mantığı

| Hisse | W1 Yab↕ | W1 MKK pp | W2 Yab↕ | W2 MKK pp | Trend | Yab% | Fon% | TERA% |
|-------|---------|-----------|---------|-----------|-------|------|------|-------|

**Filtreler:**
- Min. yeşil dönem sayısı
- 🚀 Sadece sürekli artış (momentum)
- Min. MKK pp eşiği
- Özel fon filtresi (TERA/BULLS/PUSULA var mı)

## 📊 Metodoloji

1. **Toplam hisse adeti** = `Tks(2)` (FD dosyasına gerek yok)
2. **Dönemsel değişim** = `Adet Fark` + `% Değişim` + Momentum
3. **MKK değişimi** = `Kur_Oran_2 − Kur_Oran_1` (PP fark, patlama yok)
4. **Pozisyon oranı** = `2.Adet / Tks(2) × 100`
