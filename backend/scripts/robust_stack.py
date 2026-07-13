"""Sağlam edge yığını — çok-lookback cross-sectional harmanı + Combo1, iki evrende.

Amaç: tek-lookback kırılganlığını gider (harman), iki evrende (15 major / 35 geniş) test et,
Combo1 ile birleşimin toplam Sharpe'ını dürüstçe ölç. İçgörü: Combo1↔major, xsec↔geniş.
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402
from app.backtest import edges as E  # noqa: E402
from app.data import okx_provider  # noqa: E402
from app.storage.results_store import Recorder  # noqa: E402

_REC = Recorder("robust_stack", "portfolio_stack", label="çok-lookback xsec HARMAN + Combo1")
_TAG = ""

MAJOR = ["BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "AVAX", "LINK", "DOT", "LTC",
         "BCH", "ATOM", "NEAR", "TRX", "BNB"]
WIDE = MAJOR + ["UNI", "FIL", "AAVE", "ETC", "APT", "ARB", "OP", "INJ", "SUI",
                "WLD", "PEPE", "BLUR", "LDO", "TIA", "SEI", "RUNE", "GRT",
                "ALGO", "XLM", "ICP", "SAND", "AXS", "EOS"]


def load(bases):
    dfs, px = {}, {}
    for b in bases:
        try:
            df = okx_provider.get_ohlcv(f"{b}-USDT-SWAP", "1d", bars=1000)
        except Exception:
            continue
        if df is None or len(df) < 500:
            continue
        dfs[b] = df; px[b] = df["close"]
    return dfs, pd.DataFrame(px).sort_index()


def line(name, s):
    t, sh, dd = E.stats(s)
    _, osh, _ = E.stats(s, 0.6)
    print(f"    {name:<28}{t:>9.1f}{sh:>8.2f}{osh:>8.2f}{dd:>8.1f}")
    _REC.add({"total_return": round(t, 2), "sharpe": round(sh, 3), "oos_sharpe": round(osh, 3),
              "max_drawdown": round(dd, 2)}, name=f"{_TAG} · {name.strip('> ').strip()}")


def run(tag, bases, k):
    global _TAG
    _TAG = tag
    dfs, prices = load(bases)
    print(f"\n=== {tag}: {len(dfs)} varlık, K={k} ===")
    # tek-lookback kırılganlık göstergesi
    sing = {lb: E.stats(E.xsec_returns(prices, lb, k), 0.6)[1] for lb in (20, 30, 60, 90)}
    print("    tek-lookback OOS Sharpe:", {lb: round(v, 2) for lb, v in sing.items()})
    xs = E.xsec_blend_returns(prices, k=k)          # HARMAN
    c1 = E.combo_portfolio_returns(dfs, E.COMBO1_ENTRY, E.COMBO1_EXIT)
    both = pd.concat([c1.rename("c1"), xs.rename("xs")], axis=1).dropna()
    corr = both["c1"].corr(both["xs"])
    comb = (both["c1"] + both["xs"]) / 2
    print(f"    {'kol':<28}{'TÜM%':>9}{'TÜM Shp':>8}{'OOSShp':>8}{'DD%':>8}")
    line("Combo1 portföy", both["c1"])
    line("Cross-sec HARMAN", both["xs"])
    line(">> 50/50 birleşim", comb)
    print(f"    korelasyon c1↔xsec = {corr:+.2f}")


def main():
    print("Sağlam yığın — çok-lookback HARMAN cross-sectional + Combo1")
    run("MAJOR (15, temiz)", MAJOR, 3)
    run("GENİŞ (37, dağılım)", WIDE, 5)
    _REC.save()


if __name__ == "__main__":
    main()
