"""#2 FUNDING CARRY (basis trade) — spot al + perp short, funding topla.

Delta-nötr: long spot + short perp aynı notional → yön riski ~0. Perp short olduğun
için funding_rate>0 iken funding SANA ödenir (kriptoda funding çoğunlukla pozitif:
long'lar short'lara öder). Getiri ≈ birikmiş funding − fees. Fonların düşük-riskli
kripto edge'i. GERÇEK OKX funding-rate-history ile ölçülür.

Funding periyodu 8 saat = günde 3, yılda 1095. Yıllık carry ≈ ort(fundingRate)×1095×100.
"""
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import requests  # noqa: E402
from app.storage.results_store import Recorder  # noqa: E402

BASE = "https://www.okx.com"
SYMS = ["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP", "BNB-USDT-SWAP",
        "XRP-USDT-SWAP", "DOGE-USDT-SWAP", "LINK-USDT-SWAP", "ADA-USDT-SWAP",
        "AVAX-USDT-SWAP", "LTC-USDT-SWAP"]
PERIODS_PER_YEAR = 1095  # 8h funding


def funding_history(inst, want=900, session=None):
    """funding-rate-history'yi sayfalayarak çeker (en yeni başta). Döner: fundingRate listesi."""
    s = session or requests.Session()
    rates, times = [], []
    after = ""
    seen = set()
    while len(rates) < want:
        params = {"instId": inst, "limit": "100"}
        if after:
            params["after"] = after
        r = s.get(f"{BASE}/api/v5/public/funding-rate-history", params=params, timeout=15)
        r.raise_for_status()
        data = r.json().get("data", [])
        if not data:
            break
        new = [d for d in data if d["fundingTime"] not in seen]
        if not new:
            break
        for d in new:
            seen.add(d["fundingTime"])
            rates.append(float(d["fundingRate"]))
            times.append(int(d["fundingTime"]))
        after = str(min(int(d["fundingTime"]) for d in data))
        time.sleep(0.1)
    return np.array(rates), np.array(times)


def main():
    print("#2 Funding carry (spot long + perp short) — GERÇEK OKX funding geçmişi\n")
    print(f"  {'sembol':<7}{'periyot':>8}{'gün':>6}{'ort.funding%':>13}{'poz%':>7}"
          f"{'YILLIK carry%':>14}{'birikmiş%':>11}")
    rec = Recorder("funding_carry", "carry", label="funding carry (spot long + perp short)")
    all_series = {}
    yields = []
    for sym in SYMS:
        try:
            rates, times = funding_history(sym, want=900)
        except Exception as e:
            print(f"  {sym:<7} HATA {str(e)[:40]}"); continue
        if len(rates) < 50:
            continue
        days = (times.max() - times.min()) / 86400000.0
        mean_rate = rates.mean()
        pos_pct = (rates > 0).mean() * 100
        ann = mean_rate * PERIODS_PER_YEAR * 100          # short perp = +funding topla
        cum = rates.sum() * 100                            # dönem boyu birikmiş
        yields.append(ann)
        all_series[sym.replace("-USDT-SWAP", "")] = rates
        print(f"  {sym.replace('-USDT-SWAP',''):<7}{len(rates):>8}{days:>6.0f}"
              f"{mean_rate*100:>13.4f}{pos_pct:>7.0f}{ann:>14.1f}{cum:>11.1f}")
        rec.add({"total_return": round(cum, 3), "annual_carry_pct": round(ann, 2),
                 "mean_funding_pct": round(mean_rate * 100, 5), "positive_pct": round(pos_pct, 1),
                 "periods": len(rates), "days": round(days)},
                symbol=sym.replace("-USDT-SWAP", ""), name=sym.replace("-USDT-SWAP", ""))

    print(f"\n  === PORTFÖY (eşit ağırlık {len(yields)} perp) ===")
    print(f"  Ortalama YILLIK carry : {np.mean(yields):.1f}%")
    if yields:
        rec.add({"annual_carry_pct": round(float(np.mean(yields)), 2), "n_perp": len(yields)},
                name=f"PORTFÖY (eşit ağırlık {len(yields)} perp)")
    rec.save()
    print(f"  (delta-nötr: yön riski ~0; ana risk = funding negatife dönmesi + execution)")
    # kaba fee etkisi: giriş+çıkış 2 bacak × ~5bps ≈ 20bps tek sefer (uzun tutunca amortize)
    print(f"  Fee notu: 2-bacak giriş/çıkış ~20bps tek sefer; aylarca tutunca ihmal edilebilir.")


if __name__ == "__main__":
    main()
