"""#4 CROSS-SECTIONAL MOMENTUM — evreni sırala, top N long / bottom N short (piyasa-nötr).

Zaman-serisi değil KESİTSEL: her rebalans günü 15 varlığı momentuma (geçmiş L-gün getirisi)
göre sırala; en güçlü K'yı LONG, en zayıf K'yı SHORT, eşit ağırlık, dolar-nötr (net~0).
Piyasa yönünden bağımsız → Combo1 (long-biased) ile DÜŞÜK KORELASYON = gerçek yeni edge.

Birkaç lookback denenir; en iyinin Combo1 ile korelasyonu ölçülür (çeşitlendirme değeri).
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from app.data import okx_provider  # noqa: E402
from app.scanner.dsl import evaluate  # noqa: E402
from app.backtest.grid_portfolio import UNIVERSE  # noqa: E402
from app.storage.results_store import Recorder  # noqa: E402

C1E = "Close > SMA(50) AND FisherTransform(9).Fisher > FisherTransform(9).Trigger AND Close > VWAP"
C1X = "Close < SMA(50) OR FisherTransform(9).Fisher < FisherTransform(9).Trigger OR Close < VWAP"
FEE = 10 / 1e4
K = 3           # her bacakta varlık sayısı
REBAL = 5       # rebalans periyodu (gün) — haftalık


def combo1_port(prices, dfs):
    """Combo1 eşit-ağırlık portföy günlük getirisi (korelasyon için)."""
    cols = {}
    for k, df in dfs.items():
        ent = evaluate(df, C1E).fillna(False).to_numpy()
        ex = evaluate(df, C1X).fillna(False).to_numpy()
        n = len(df); pos = np.zeros(n); inp = False
        for i in range(n):
            if not inp and ent[i]:
                inp = True
            elif inp and ex[i]:
                inp = False
            pos[i] = 1.0 if inp else 0.0
        c = df["close"].to_numpy(float)
        r = np.zeros(n); r[1:] = c[1:] / c[:-1] - 1
        cols[k] = pd.Series(np.concatenate([[0.0], pos[:-1] * r[1:]]), index=df.index)
    return pd.DataFrame(cols).mean(axis=1)


def xsec(prices, lookback, k=K, rebal=REBAL):
    """Cross-sectional momentum getiri serisi (dolar-nötr, haftalık rebalans, işlem maliyetli)."""
    rets = prices.pct_change()
    mom = prices.pct_change(lookback)            # geçmiş L-gün getirisi = momentum
    dates = prices.index
    W = pd.DataFrame(0.0, index=dates, columns=prices.columns)
    cur = pd.Series(0.0, index=prices.columns)
    for i, dt in enumerate(dates):
        if i < lookback + 1:
            W.iloc[i] = 0.0; continue
        if i % rebal == 0:
            m = mom.iloc[i].dropna()
            if len(m) >= 2 * k:
                rank = m.sort_values()
                longs = rank.index[-k:]; shorts = rank.index[:k]
                cur = pd.Series(0.0, index=prices.columns)
                cur[longs] = 1.0 / k; cur[shorts] = -1.0 / k
        W.iloc[i] = cur.values
    gross = (W.shift(1) * rets).sum(axis=1)
    turn = W.diff().abs().sum(axis=1)            # rebalans devri
    net = gross - turn * FEE
    return net.fillna(0.0)


def stats(ret, frac=0.0):
    ret = ret.dropna(); ret = ret.iloc[int(len(ret) * frac):]
    if len(ret) < 30:
        return 0, 0, 0
    eq = (1 + ret).cumprod()
    return ((eq.iloc[-1] - 1) * 100,
            ret.mean() / ret.std() * np.sqrt(365) if ret.std() > 0 else 0,
            ((eq - eq.cummax()) / eq.cummax()).min() * 100)


def main():
    print(f"#4 Cross-sectional momentum — {len(UNIVERSE)} kripto, K={K} long/short, haftalık\n")
    dfs, px = {}, {}
    for sym in UNIVERSE:
        df = okx_provider.get_ohlcv(sym, "1d", bars=1000)
        if df is None or len(df) < 300:
            continue
        k = sym.replace("-USDT-SWAP", "")
        dfs[k] = df; px[k] = df["close"]
    prices = pd.DataFrame(px).sort_index().dropna(how="all")
    print(f"  {len(prices.columns)} varlık, {len(prices)} gün\n")

    rec = Recorder("cross_sectional", "portfolio_stack",
                   label=f"kesitsel momentum L/S ({len(prices.columns)} kripto, K={K})")
    print(f"  {'lookback':<10}{'TÜM ret%':>10}{'TÜM Shp':>9}{'OOS ret%':>10}{'OOS Shp':>9}{'OOS DD%':>9}")
    best = None
    for lb in [20, 30, 60, 90]:
        s = xsec(prices, lb)
        t, sh, _ = stats(s)
        ot, osh, odd = stats(s, 0.6)
        print(f"  {lb:<10}{t:>10.1f}{sh:>9.2f}{ot:>10.1f}{osh:>9.2f}{odd:>9.1f}")
        rec.add({"total_return": round(t, 2), "sharpe": round(sh, 3), "oos_ret": round(ot, 2),
                 "oos_sharpe": round(osh, 3), "oos_max_drawdown": round(odd, 2), "lookback": lb},
                interval="1d", name=f"xsec lookback={lb}")
        if best is None or osh > best[1]:
            best = (lb, osh, s)

    # en iyi lookback'in Combo1 ile korelasyonu
    lb, _, s = best
    c1 = combo1_port(prices, dfs)
    both = pd.concat([s.rename("xsec"), c1.rename("c1")], axis=1).dropna()
    corr = both["xsec"].corr(both["c1"])
    print(f"\n  En iyi lookback={lb}. Combo1 ile KORELASYON = {corr:+.2f}")
    print(f"  (düşük/negatif = gerçek bağımsız edge; birleştirince toplam Sharpe artar)")
    # 50/50 birleşim
    combo = (both["xsec"] + both["c1"]) / 2
    tc, shc, ddc = stats(combo)
    _, shc_o, _ = stats(combo, 0.6)
    print(f"  50/50 (xsec+Combo1) birleşim: TÜM Sharpe {shc:.2f} · OOS Sharpe {shc_o:.2f} · DD {ddc:.1f}%")
    rec.add({"total_return": round(tc, 2), "sharpe": round(shc, 3), "oos_sharpe": round(shc_o, 3),
             "max_drawdown": round(ddc, 2), "corr_combo1": round(corr, 3), "best_lookback": lb},
            interval="1d", name="50/50 xsec+Combo1 birleşim")
    rec.save()


if __name__ == "__main__":
    main()
