"""
Basamak Artış/Düşüş Tarama
---------------------------
0→10→20→30+ çıkanlar ve 30→20→10→0 düşenler.

Çalıştır: python altin_oran_tarama.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
from takas_depo import _oku

BASLANGIC = "2025_10"
BITIS     = "2026_05"

def tarama():
    df = _oku()
    if df.empty:
        print("❌ Veri yok.")
        return

    out = "basamak_rapor.xlsx"
    with pd.ExcelWriter(out, engine="openpyxl") as writer:

        for tip in ["aylik", "haftalik"]:
            df_tip = df[df["tip"] == tip].copy()
            if df_tip.empty:
                continue

            donemler = sorted([d for d in df_tip["donem"].astype(str).unique()
                               if BASLANGIC <= d <= BITIS])
            if len(donemler) < 2:
                continue

            alanlar  = []
            satanlar = []

            for (hisse, kurum), grp in df_tip.groupby(["hisse", "kurum"]):
                grp = grp[grp["donem"].isin(donemler)].sort_values("donem")
                if len(grp) < 2:
                    continue

                kron = {row["donem"]: round(row["oran2"], 2) for _, row in grp.iterrows()}
                vals = [kron.get(d, None) for d in donemler]
                vals_temiz = [v for v in vals if v is not None]

                if not vals_temiz:
                    continue

                ilk = vals_temiz[0]
                son = vals_temiz[-1]
                maks = max(vals_temiz)
                mins = min(vals_temiz)

                satir = {
                    "Hisse"  : hisse,
                    "Kurum"  : kurum,
                    "İlk%"   : ilk,
                    "Son%"   : son,
                    "Değişim": round(son - ilk, 2),
                }
                for d in donemler:
                    satir[d] = kron.get(d, None)

                # ALAN: ilkten sona anlamlı artış + basamak geçmiş
                if son > ilk and son - ilk >= 10:
                    # Hangi basamakları geçmiş
                    basamaklar = []
                    for esik in [10, 20, 30, 40, 50]:
                        if maks >= esik and ilk < esik:
                            gecis = next((d for d in donemler
                                         if kron.get(d, 0) >= esik), None)
                            if gecis:
                                basamaklar.append(f"%{esik}→{gecis}")
                    satir["Basamaklar"] = " | ".join(basamaklar)
                    alanlar.append(satir)

                # SATAN: ilkten sona anlamlı düşüş
                elif ilk > son and ilk - son >= 10:
                    basamaklar = []
                    for esik in [50, 40, 30, 20, 10]:
                        if mins <= esik and ilk > esik:
                            gecis = next((d for d in donemler
                                         if kron.get(d, 100) <= esik), None)
                            if gecis:
                                basamaklar.append(f"%{esik}↓{gecis}")
                    satir["Basamaklar"] = " | ".join(basamaklar)
                    satanlar.append(satir)

            # Alan sheet
            if alanlar:
                df_al = pd.DataFrame(alanlar).sort_values("Değişim", ascending=False)
                df_al.to_excel(writer, sheet_name=f"{tip.capitalize()}_Alan", index=False)
                print(f"✅ {tip} Alan: {len(df_al)} hisse-kurum")

            # Satan sheet
            if satanlar:
                df_sat = pd.DataFrame(satanlar).sort_values("Değişim", ascending=True)
                df_sat.to_excel(writer, sheet_name=f"{tip.capitalize()}_Satan", index=False)
                print(f"✅ {tip} Satan: {len(df_sat)} hisse-kurum")

    print(f"\n✅ {out} hazır — {BASLANGIC} → {BITIS}")

if __name__ == "__main__":
    tarama()
