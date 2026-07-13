"""Çeşitlendirilmiş kripto trend PORTFÖY (OOS) — 15 varlığın walk-forward equity'sini
eşit-ağırlık birleştir. Çeşitlendirme tek-varlık DD'sini (−56%) ne kadar düşürüyor?"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402
from app.backtest import walkforward as wf  # noqa: E402
from app.backtest.metrics import equity_metrics  # noqa: E402
from app.backtest.grid_portfolio import UNIVERSE  # noqa: E402
from app.data import okx_provider  # noqa: E402
from app.storage.results_store import get_results_store  # noqa: E402

ENTRY, EXIT = "EMA({fast}) > EMA({slow})", "EMA({fast}) < EMA({slow})"
PARAMS = [{"name": "fast", "min": 10, "max": 50, "step": 5},
          {"name": "slow", "min": 60, "max": 200, "step": 20}]


def main():
    print(f"Çeşitlendirilmiş kripto trend portföy (OOS walk-forward, {len(UNIVERSE)} varlık)...")
    curves = []
    for sym in UNIVERSE:
        df = okx_provider.get_ohlcv(sym, "1d", bars=1000)
        if df is None or len(df) < 460:
            continue
        try:
            r = wf.run_walk_forward(symbol=sym, entry_template=ENTRY, exit_template=EXIT,
                                    params=PARAMS, interval="1d", method="bayes",
                                    objective="sharpe", n_trials=25, train_bars=365,
                                    test_bars=90, fee_bps=8, direction="long", df=df)
            eq = r["equity"]
            if len(eq) > 10:
                times = [p["time"] for p in eq]
                idx = (pd.to_datetime(times, unit="s") if isinstance(times[0], (int, float))
                       else pd.to_datetime(times))
                s = pd.Series([p["value"] for p in eq], index=idx)
                curves.append((s / s.iloc[0]).rename(sym))  # 1.0'a normalize
        except Exception as e:
            print(f"  {sym}: {str(e)[:60]}")

    if not curves:
        print("Veri yok"); return
    mat = pd.concat(curves, axis=1).sort_index().ffill().dropna(how="all")
    port = mat.mean(axis=1)  # eşit-ağırlık portföy
    m = equity_metrics(port, "1d")

    # eşit-ağırlık Al&Tut (aynı OOS bölge)
    bh = []
    for sym in UNIVERSE:
        df = okx_provider.get_ohlcv(sym, "1d", bars=1000)
        if df is not None and len(df) > 460:
            c = df["close"].iloc[365:]
            bh.append(c.iloc[-1] / c.iloc[0] - 1)
    bh_ret = round(sum(bh) / len(bh) * 100, 1) if bh else 0

    print(f"\n  === ÇEŞİTLENDİRİLMİŞ TREND PORTFÖY (OOS, {len(curves)} varlık, eşit-ağırlık) ===")
    print(f"  Toplam getiri  : {m.get('total_return')}%   (eşit-ağırlık Al&Tut: {bh_ret}%)")
    print(f"  CAGR           : {m.get('cagr')}%")
    print(f"  Sharpe         : {m.get('sharpe')}   Sortino {m.get('sortino')}")
    print(f"  Max Drawdown   : {m.get('max_drawdown')}%   (tek-varlık ort ~−53%)")
    print(f"  Calmar         : {m.get('calmar')}   Volatilite {m.get('volatility')}%")

    run_id = get_results_store().record("trend_portfolio_crypto", "trend",
        [dict(m, _name=f"eşit-ağırlık portföy ({len(curves)} varlık)", _interval="1d", buy_hold=bh_ret)],
        label=f"çeşitlendirilmiş kripto trend portföy ({len(curves)} varlık, OOS)")
    print(f"\n  [DB] Sonuç kaydedildi → results.sqlite (run #{run_id})")


if __name__ == "__main__":
    main()
