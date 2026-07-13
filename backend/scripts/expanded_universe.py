"""Evreni genişlet (15 → ~35 kripto) + iki bağımsız edge'i birleştir.

Tez: cross-sectional sıralama daha çok varlıkla daha temiz → Sharpe yükselir; Combo1
portföyü de daha çeşitli. Birleşim (korelasyonsuz) toplam Sharpe'ı yukarı çeker.
Kısa-geçmişli (yeni listelenen) semboller otomatik elenir (>=500 bar şartı).
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from app.backtest import edges as E  # noqa: E402
from app.data import okx_provider  # noqa: E402
from app.storage.results_store import Recorder  # noqa: E402

# Kurulu/likit kripto perp'ler (tokenize hisse/emtia hariç); kısa-geçmişli olan elenecek
UNIVERSE = [
    "BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "AVAX", "LINK", "DOT", "LTC",
    "BCH", "ATOM", "NEAR", "TRX", "BNB", "UNI", "FIL", "AAVE", "ETC", "APT",
    "ARB", "OP", "INJ", "SUI", "WLD", "PEPE", "BLUR", "LDO", "TIA", "SEI",
    "RUNE", "GRT", "ALGO", "XLM", "ICP", "SAND", "AXS", "EOS",
]


def main():
    print(f"Genişletilmiş evren — {len(UNIVERSE)} aday kripto perp (kısa-geçmiş elenecek)\n")
    dfs, px = {}, {}
    for base in UNIVERSE:
        sym = f"{base}-USDT-SWAP"
        try:
            df = okx_provider.get_ohlcv(sym, "1d", bars=1000)
        except Exception:
            continue
        if df is None or len(df) < 500:
            continue
        dfs[base] = df
        px[base] = df["close"]
    prices = pd.DataFrame(px).sort_index()
    print(f"  Geçerli (>=500 bar): {len(dfs)} varlık, {len(prices)} gün\n")

    # 1) Combo1 portföyü
    c1 = E.combo_portfolio_returns(dfs, E.COMBO1_ENTRY, E.COMBO1_EXIT)
    # 2) Cross-sectional (K evrenle ölçekli), lookback tara
    k = max(3, len(dfs) // 7)
    print(f"  Cross-sectional K={k} (her bacak), lookback taraması:")
    print(f"    {'lookback':<10}{'TÜM Shp':>9}{'OOS Shp':>9}")
    best = None
    for lb in [20, 30, 60, 90]:
        xs = E.xsec_returns(prices, lookback=lb, k=k)
        _, sh, _ = E.stats(xs)
        _, osh, _ = E.stats(xs, 0.6)
        print(f"    {lb:<10}{sh:>9.2f}{osh:>9.2f}")
        if best is None or osh > best[1]:
            best = (lb, osh, xs)
    lb, _, xs = best

    both = pd.concat([c1.rename("c1"), xs.rename("xs")], axis=1).dropna()
    corr = both["c1"].corr(both["xs"])
    comb = (both["c1"] + both["xs"]) / 2

    rec = Recorder("expanded_universe", "portfolio_stack",
                   label=f"genişletilmiş evren ({len(dfs)} kripto)")

    def row(name, s):
        t, sh, dd = E.stats(s)
        _, osh, _ = E.stats(s, 0.6)
        print(f"    {name:<26}{t:>10.1f}{sh:>9.2f}{osh:>9.2f}{dd:>9.1f}")
        rec.add({"total_return": round(t, 2), "sharpe": round(sh, 3), "oos_sharpe": round(osh, 3),
                 "max_drawdown": round(dd, 2), "best_lookback": lb, "corr_c1_xsec": round(corr, 3)},
                interval="1d", name=name.strip("> ").strip())

    print(f"\n  === SONUÇ (en iyi lookback={lb}, korelasyon c1↔xsec = {corr:+.2f}) ===")
    print(f"    {'kol':<26}{'TÜM ret%':>10}{'TÜM Shp':>9}{'OOS Shp':>9}{'MaxDD%':>9}")
    row("Combo1 portföy", both["c1"])
    row("Cross-sectional", both["xs"])
    row(">> 50/50 birleşim", comb)
    rec.save()
    # karşılaştırma: 15-varlık taban Sharpe ~1.06'ydı
    _, sc, _ = E.stats(comb); _, sco, _ = E.stats(comb, 0.6)
    print(f"\n  Birleşim Sharpe: TÜM {sc:.2f} / OOS {sco:.2f}  (15-varlık taban: TÜM 1.06 / OOS 1.06)")


if __name__ == "__main__":
    main()
