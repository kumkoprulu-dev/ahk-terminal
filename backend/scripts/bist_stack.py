"""BIST edge testi — kripto'daki robust yığını (Combo1 portföy + cross-sectional harman)
BIST hisselerinde tekrarla. edges.py veri-kaynağı bağımsız; burada Yahoo (.IS) beslenir.

Sorular:
  1) Combo1 vs Combo2 portföy — BIST yapısal boğasında hangisi kazanıyor? Al&Tut'u geçen var mı?
  2) Cross-sectional momentum BIST'te çalışıyor mu? (long/short + BIST-uyumlu long-only-tilt)
  3) Combo1 + xsec birleşimi — kripto'daki gibi korelasyonsuz/robust mu?
  4) BIST edge'i kripto edge'iyle korelasyonsuz mu? (üçüncü bağımsız kol adayı)

Çalıştır (platform venv):  py -u scripts/bist_stack.py [evren]   evren=bist30|bist50
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from app.backtest import edges as E  # noqa: E402
from app.data import service  # noqa: E402
from app.data.universe import _BIST30, _BIST50, _BIST100  # noqa: E402
from app.storage.results_store import Recorder  # noqa: E402

_REC = Recorder("bist_stack", "portfolio_stack", label="BIST edge yığını")
_TAG = ""

INTERVAL = "1d"
RANGE = "5y"


def load(codes):
    """BIST kodları → (dfs dict, hizalı fiyat DataFrame). Yahoo .IS, günlük 5y."""
    dfs, px = {}, {}
    for c in codes:
        try:
            df = service.get_ohlcv(c + ".IS", INTERVAL, RANGE)
        except Exception:
            df = None
        if df is None or len(df) < 400:
            continue
        df = df[~df.index.duplicated(keep="last")].sort_index()
        dfs[c] = df
        px[c] = df["close"]
    prices = pd.DataFrame(px).sort_index()
    return dfs, prices


def buyhold_returns(prices: pd.DataFrame) -> pd.Series:
    """Eşit-ağırlık Al&Tut günlük getirisi (her varlık her gün long)."""
    return prices.pct_change().mean(axis=1).fillna(0.0)


def xsec_long_only(prices: pd.DataFrame, lookbacks=(20, 30, 60, 90), k: int = 3,
                   rebal: int = 5, fee: float = E.FEE) -> pd.Series:
    """BIST-uyumlu cross-sectional: sadece top-k LONG (short bacağı yok — BIST açığa satış
    kısıtlı). Kompozit sıra harmanı; en güçlü k varlığa eşit ağırlık, gerisi nakit."""
    rets = prices.pct_change()
    moms = {lb: prices.pct_change(lb) for lb in lookbacks}
    dates = prices.index
    W = pd.DataFrame(0.0, index=dates, columns=prices.columns)
    cur = pd.Series(0.0, index=prices.columns)
    max_lb = max(lookbacks)
    for i in range(len(dates)):
        if i < max_lb + 1:
            continue
        if i % rebal == 0:
            ranks = []
            for lb in lookbacks:
                m = moms[lb].iloc[i].dropna()
                if len(m) >= k:
                    ranks.append(m.rank())
            if ranks:
                comp = pd.concat(ranks, axis=1).mean(axis=1).dropna()
                if len(comp) >= k:
                    order = comp.sort_values()
                    cur = pd.Series(0.0, index=prices.columns)
                    cur[order.index[-k:]] = 1.0 / k
        W.iloc[i] = cur.values
    gross = (W.shift(1) * rets).sum(axis=1)
    turn = W.diff().abs().sum(axis=1)
    return (gross - turn * fee).fillna(0.0)


def line(name, s):
    t, sh, dd = E.stats(s)
    _, osh, odd = E.stats(s, 0.6)
    print(f"    {name:<26}{t:>9.1f}{sh:>8.2f}{osh:>8.2f}{dd:>8.1f}{odd:>8.1f}")
    _REC.add({"total_return": round(t, 2), "sharpe": round(sh, 3), "oos_sharpe": round(osh, 3),
              "max_drawdown": round(dd, 2), "oos_max_drawdown": round(odd, 2)},
             name=f"{_TAG} · {name.strip('> ').strip()}")


def crypto_corr(bist_series: dict[str, pd.Series]):
    """BIST edge'lerini kripto Combo1 portföyüyle korele et (bağımsızlık testi)."""
    try:
        from app.data import okx_provider
    except Exception:
        print("\n  (kripto korelasyon atlandı — okx_provider yok)")
        return
    MAJOR = ["BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "AVAX", "LINK", "DOT",
             "LTC", "BCH", "ATOM", "NEAR", "TRX", "BNB"]
    cdfs = {}
    for b in MAJOR:
        try:
            df = okx_provider.get_ohlcv(f"{b}-USDT-SWAP", "1d", bars=1000)
        except Exception:
            continue
        if df is not None and len(df) >= 500:
            cdfs[b] = df
    if not cdfs:
        print("\n  (kripto korelasyon atlandı — veri çekilemedi)")
        return
    cc1 = E.combo_portfolio_returns(cdfs, E.COMBO1_ENTRY, E.COMBO1_EXIT)
    cc1.index = pd.to_datetime(cc1.index).tz_localize(None).normalize()
    print("\n  === BIST edge'i ↔ Kripto Combo1 korelasyon (bağımsızlık) ===")
    for name, s in bist_series.items():
        bs = s.copy()
        bs.index = pd.to_datetime(bs.index).tz_localize(None).normalize()
        j = pd.concat([bs.rename("b"), cc1.rename("c")], axis=1).dropna()
        corr = j["b"].corr(j["c"]) if len(j) > 30 else float("nan")
        print(f"    {name:<26} corr={corr:+.2f}  (ortak {len(j)} gün)")


def run(tag, codes, k):
    global _TAG
    _TAG = tag
    dfs, prices = load(codes)
    print(f"\n{'='*66}\n=== {tag}: {len(dfs)}/{len(codes)} varlık yüklendi, K={k}, {INTERVAL} {RANGE} ===")
    if len(dfs) < 2 * k:
        print("    yetersiz varlık, atlanıyor.")
        return {}
    bh = buyhold_returns(prices)
    c1 = E.combo_portfolio_returns(dfs, E.COMBO1_ENTRY, E.COMBO1_EXIT)
    c2 = E.combo_portfolio_returns(dfs, E.COMBO2_ENTRY, E.COMBO2_EXIT)
    xs = E.xsec_blend_returns(prices, k=k)          # long/short harman
    xl = xsec_long_only(prices, k=k)                # BIST-uyumlu long-only tilt

    idx = c1.index.intersection(c2.index).intersection(xs.index).intersection(bh.index)
    c1, c2, xs, xl, bh = c1[idx], c2[idx], xs[idx], xl[idx], bh.reindex(idx).fillna(0.0)
    comb1x = (c1 + xs) / 2
    comb1l = (c1 + xl) / 2
    corr = pd.concat([c1.rename("a"), xs.rename("b")], axis=1).dropna().corr().iloc[0, 1]

    print(f"    {'kol':<26}{'TÜM%':>9}{'TÜMShp':>8}{'OOSShp':>8}{'DD%':>8}{'OOSDD':>8}")
    line("Al&Tut (eşit ağırlık)", bh)
    line("Combo1 portföy", c1)
    line("Combo2 portföy", c2)
    line("Cross-sec harman (L/S)", xs)
    line("Cross-sec long-only", xl)
    line(">> Combo1 + xsecLS 50/50", comb1x)
    line(">> Combo1 + xsecLong 50/50", comb1l)
    print(f"    korelasyon Combo1↔xsecLS = {corr:+.2f}")
    return {"Combo1-BIST": c1, "xsecLS-BIST": xs, "Combo1+xsec-BIST": comb1x}


def main():
    ev = sys.argv[1].lower() if len(sys.argv) > 1 else "bist30"
    codes, tag, k = {
        "bist100": (_BIST100, "BIST100 (geniş)", 8),
        "bist50": (_BIST50, "BIST50", 5),
        "bist30": (_BIST30, "BIST30 (likit major)", 3),
    }.get(ev, (_BIST30, "BIST30 (likit major)", 3))
    print("BIST edge yığını — Combo1/Combo2 portföy + cross-sectional harman (Yahoo .IS)")
    series = run(tag, codes, k)
    if series:
        crypto_corr(series)
    _REC.save()


if __name__ == "__main__":
    main()
