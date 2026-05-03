# BIST Akıllı Para Takip — Eksikler & Yapılacaklar
Son güncelleme: 03.05.2026

---

## ✅ TAMAMLANANLAR
- Klasör temizliği (kök vs src çakışması giderildi)
- GitHub repo kuruldu
- Hisse Detay: MKK Aylık (4 ay) + Haftalık (4 hafta) grafikleri eklendi

---

## 🔴 KRİTİK — TAKAS DASHBOARD (src/app.py)

| # | Modül | Eksik/Hata | Notlar |
|---|-------|------------|--------|
| 1 | Hisse Detay | Kurum Takas Detayı dönem filtresi yok | Günlük/Haftalık/Aylık seçilebilir olmalı |
| 2 | Hisse Detay | dolasim_pct sıralaması yok | Büyükten küçüğe sıralanmalı |
| 3 | Bebek Hisse | DATA_DIR göreceli path sorunu | src/ içinden çalışınca yanlış klasör |
| 4 | Bebek Hisse | return col içinde fonksiyonu kesiyor | st.stop() veya else bloğu olmalı |

## 🟠 ORTA — BEBEK HİSSE (bebek_hisse_tab.py)

| # | Modül | Eksik/Hata | Notlar |
|---|-------|------------|--------|
| 5 | Bebek Hisse | asama_tespit sırasız veri hatası | iloc[-1] yerine max() olmalı |
| 6 | Bebek Hisse | kumul_panel gerçek kümülatif değil | Sadece son 2 dönem karşılaştırıyor |
| 7 | Bebek Hisse | satış takibi ilk5 seçimi yanlış | bas_pct değil delta'ya göre filtrele |
| 8 | Bebek Hisse | OSMANLΙ Yunan harfi sorunu | Türkçe İ ile eşleşmiyor |
| 9 | Bebek Hisse | yfinance bağımlılığı | BIST için güvenilir değil, Matriks'e geç |

---

## 🔴 KRİTİK — TEKNİK APP (teknik_app.py)

| # | Modül | Eksik/Hata | Notlar |
|---|-------|------------|--------|
| 10 | Performans Takip | Değişim% kolonu tabloda görünmüyor | Hesaplanıyor ama df_goster'de yok |
| 11 | Performans Takip | MAX fiyat + MAX tarih yok | Sinyal tarihinden bugüne en yüksek kapanış |
| 12 | Performans Takip | 1h/2h/1ay zaman bazlı getiri yok | Hedef tarihler kaydedilmeli |
| 13 | Performans Takip | Başarı oranı özeti yok | Her tarama için %10+ yapan / toplam |
| 14 | Takip & Alarm | Alarm bannerları temizlenmiyor | Tümünü Kontrol Et'te üst üste yığılıyor |
| 15 | Takip & Alarm | Sesli uyarı yok | Alarm tetiklenince ses çalmalı |
| 16 | Takip & Alarm | Gerçekleşen alarm arşivi yok | Yeşile dön + getiri% + arşive gönder |

---

## 🟡 YENİ MODÜLLER — EKLENECEK

| # | Modül | Açıklama | Öncelik |
|---|-------|----------|---------|
| 17 | Backtest | MKK sinyal (pp_fark >= %5) + fiyat getirisi | 🔴 Yüksek |
| 18 | BIST Yön Tayini | Breadth ratio, kurum/yabancı hacim, MA skorları | 🟠 Orta |
| 19 | Genel Akış | Tarama → Hisse Detay → Alarm/Trade Stratejisi ekle | 🟠 Orta |

---

## 💡 FİKİRLER — İLERİSİ İÇİN

- Trade Journal: giriş/çıkış/senaryo/sonuç kaydı
- Tarama → Hisse Detay tıklama entegrasyonu
- Sesli alarm sistemi (Windows toast veya tarayıcı sesi)
- Kurum Takas Detayı pivot tablo (tek satır/kurum, Günlük Δ, Haftalık Δ, Aylık Δ, Trend)

---

## 📋 SIRADAKI OTURUM ÖNCELİK SIRASI
1. #10 Değişim% kolonu göster (5 dk)
2. #1-2 Hisse Detay dönem filtresi + sıralama
3. #11-13 Performans Takip MAX fiyat + zaman bazlı getiri
4. #14 Alarm banner temizleme
5. #17 Backtest modülü
