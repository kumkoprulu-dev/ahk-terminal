"""Combo1-kripto (HMA baseline) varyant testi — NNFX bulgusunu sağlam mı diye sına.

nnfx_search saf kriptoda HMA+Fisher+VWAP'ı (OOS 0.60) Combo1 (SMA+Fisher+VWAP, OOS 0.50)
üstünde buldu. Soru: bu GERÇEK bir iyileşme mi (birçok HMA periyodunda tutuyor mu = sağlam),
yoksa HMA(20)'nin şanslı tek-periyot aykırısı mı (xsec lookback dersinin tekrarı)? Ve HMA
varyantı mevcut SMA-Combo1'e ne kadar korelasyonlu (yüksek = güvenli baseline-swap; düşük =
farklı davranış, istifleme adayı)?

15-major kripto portföyünde (canlı sleeve evreni) her baseline varyantını Fisher9+VWAP ile
kur, TÜM/OOS Sharpe + DD + SMA-Combo1 korelasyonu ölç. Sonuç results.sqlite'a.

Çalıştır (platform venv):  py -u scripts/combo1_hma_test.py
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from app.backtest import edges as E  # noqa: E402
from app.data import okx_provider  # noqa: E402
from app.storage.results_store import Recorder  # noqa: E402

MAJOR = ["BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "AVAX", "LINK", "DOT",
         "LTC", "BCH", "ATOM", "NEAR", "TRX", "BNB"]

# Baseline varyantları (hepsi + Fisher9 + VWAP). "SMA50" = mevcut Combo1 referansı.
BASELINES = [
    ("SMA50 (mevcut Combo1)", "SMA(50)"),
    ("HMA20 (NNFX bulgusu)",  "HMA(20)"),
    ("HMA30",                 "HMA(30)"),
    ("HMA50",                 "HMA(50)"),
    ("HMA14",                 "HMA(14)"),
]


def rules(base_expr: str):
    entry = (f"Close > {base_expr} AND "
             "FisherTransform(9).Fisher > FisherTransform(9).Trigger AND Close > VWAP")
    exit_ = (f"Close < {base_expr} OR "
             "FisherTransform(9).Fisher < FisherTransform(9).Trigger OR Close < VWAP")
    return entry, exit_


def load_crypto():
    dfs = {}
    for b in MAJOR:
        try:
            df = okx_provider.get_ohlcv(f"{b}-USDT-SWAP", "1d", bars=1000)
        except Exception:
            continue
        if df is not None and len(df) >= 500:
            dfs[b] = df
    return dfs


def main():
    print("Combo1-kripto baseline varyant testi (15 major, Fisher9+VWAP sabit)\n")
    dfs = load_crypto()
    print(f"  {len(dfs)} kripto yüklendi\n")

    # her varyantın portföy getiri serisi
    series = {}
    for label, base in BASELINES:
        entry, exit_ = rules(base)
        series[label] = E.combo_portfolio_returns(dfs, entry, exit_)

    ref = series["SMA50 (mevcut Combo1)"]
    rec = Recorder("combo1_hma_test", "combo_variant",
                   label="Combo1-kripto baseline varyantları (SMA vs HMA)",
                   params={"universe": "kripto15", "baselines": [b for b, _ in BASELINES]})

    print(f"  {'baseline':<24}{'TÜM%':>9}{'TÜMShp':>8}{'OOSShp':>8}{'DD%':>8}{'OOSDD':>8}{'korel(SMA)':>12}")
    print("  " + "-" * 78)
    for label, _ in BASELINES:
        s = series[label]
        total, shp, dd = E.stats(s)
        _, oshp, odd = E.stats(s, 0.6)
        # SMA-Combo1 ile korelasyon (ortak günlerde)
        corr = pd.concat([s, ref], axis=1).dropna().corr().iloc[0, 1] if label != "SMA50 (mevcut Combo1)" else 1.0
        print(f"  {label:<24}{total:>9.1f}{shp:>8.2f}{oshp:>8.2f}{dd:>8.1f}{odd:>8.1f}{corr:>12.2f}")
        rec.add({"total_return": round(total, 2), "sharpe": round(shp, 3), "oos_sharpe": round(oshp, 3),
                 "max_drawdown": round(dd, 2), "oos_max_drawdown": round(odd, 2),
                 "corr_sma_combo1": round(float(corr), 3)}, name=label)

    # HMA20 varyantı + SMA-Combo1 50/50 istifi (bağımsızsa fayda katar mı?)
    hma = series["HMA20 (NNFX bulgusu)"]
    blend = pd.concat([ref, hma], axis=1).dropna().mean(axis=1)
    bt, bs, bdd = E.stats(blend); _, bosh, bodd = E.stats(blend, 0.6)
    print("  " + "-" * 78)
    print(f"  {'50/50 SMA+HMA istif':<24}{bt:>9.1f}{bs:>8.2f}{bosh:>8.2f}{bdd:>8.1f}{bodd:>8.1f}{'':>12}")
    rec.add({"total_return": round(bt, 2), "sharpe": round(bs, 3), "oos_sharpe": round(bosh, 3),
             "max_drawdown": round(bdd, 2), "oos_max_drawdown": round(bodd, 2)}, name="50/50 SMA+HMA istif")
    rec.save()

    print("\n  YORUM:")
    print("  - HMA'ların hepsi SMA'yı geçiyorsa = sağlam bulgu (tek periyot şansı değil).")
    print("  - korel(SMA) yüksek (>0.8) = aynı davranış, güvenli baseline-swap.")
    print("  - korel düşük + ikisi de güçlü = istifleme adayı (50/50 satırına bak).")


if __name__ == "__main__":
    main()
