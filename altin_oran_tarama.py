"""
Altın Oran Tarama
-----------------
Çalıştır: python altin_oran_tarama.py
Çıktı: altin_oran_rapor.xlsx
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
from takas_depo import _oku

KONS_ESIK = 50  # İlk 5 kurumun toplamı bu eşiği geçmeli

def tarama():
    df = _oku()
    if df.empty:
        print("❌ Veri yok.")
        return

    sonuclar = []

    for tip in ["haftalik", "aylik"]:
        df_tip = df[df["tip"] == tip].copy()
        if df_tip.empty:
            continue

        # Her hisse için son dönem
        son_donem = df_tip.groupby("hisse")["donem"].max().reset_index()
        son_donem.columns = ["hisse", "son_donem"]

        for _, row in son_donem.iterrows():
            hisse    = row["hisse"]
            donem    = row["son_donem"]

            d_df = df_tip[
                (df_tip["hisse"] == hisse) &
                (df_tip["donem"] == donem) &
                (df_tip["oran2"] > 0)
            ].drop_duplicates(subset=["kurum"]).copy()

            if d_df.empty:
                continue

            toplam = d_df["oran2"].sum()
            if toplam < 8:
                continue

            d_sorted    = d_df.sort_values("oran2", ascending=False)
            ilk5        = d_sorted.head(5)
            ilk5_toplam = ilk5["oran2"].sum()
            kons        = round(ilk5_toplam / toplam * 100, 1)

            if kons < KONS_ESIK:
                continue

            kurum_str = " | ".join([
                f"{r['kurum']} %{r['oran2']:.1f}"
                for _, r in ilk5.iterrows()
            ])

            sonuclar.append({
                "Tip"           : tip,
                "Hisse"         : hisse,
                "Son Dönem"     : donem,
                "Konsantrasyon%": kons,
                "Toplam T2%"    : round(toplam, 2),
                "İlk 5 Kurum"   : kurum_str,
            })

    if not sonuclar:
        print(f"❌ %{KONS_ESIK} eşiğini geçen hisse bulunamadı.")
        return

    result_df = pd.DataFrame(sonuclar).sort_values(
        ["Tip", "Konsantrasyon%"], ascending=[True, False]
    )

    out = "altin_oran_rapor.xlsx"
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        for tip in ["haftalik", "aylik"]:
            sheet = result_df[result_df["Tip"] == tip].drop(columns="Tip")
            if not sheet.empty:
                sheet.to_excel(writer, sheet_name=tip.capitalize(), index=False)

    print(f"✅ {out} oluşturuldu — {len(result_df)} hisse")
    print(f"   Haftalık: {len(result_df[result_df['Tip']=='haftalik'])} hisse")
    print(f"   Aylık:    {len(result_df[result_df['Tip']=='aylik'])} hisse")

if __name__ == "__main__":
    tarama()
