# app.py'ye Bebek Hisse Avcısı Ekleme

## 1. Import ekle (en üste):
```python
from bebek_hisse_tab import bebek_hisse_sekme
```

## 2. Tab listesine ekle:
```python
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "TAKAS ANALİZİ",
    "MKK PANEL",
    "...",
    "...",
    "🐣 BEBEK HİSSE AVCISI"  # ← YENİ
])
```

## 3. Tab içeriği:
```python
with tab5:
    bebek_hisse_sekme()
```

## 4. data/bebek_hisse/ klasörünü kopyala:
bist_app/data/bebek_hisse/ klasörüne 10 parquet dosyasını koy.
