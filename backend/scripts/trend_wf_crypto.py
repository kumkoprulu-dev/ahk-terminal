"""Kripto trend (EMA-cross) WALK-FORWARD basket — OOS'ta gerçekten Al&Tut'u geçiyor mu?
EMA fast/slow her fold'un eğitim diliminde optimize, test diliminde (OOS) sınanır."""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
from app.backtest import walkforward as wf  # noqa: E402
from app.backtest.grid_portfolio import UNIVERSE  # noqa: E402
from app.data import okx_provider  # noqa: E402
from app.storage.results_store import Recorder  # noqa: E402

ENTRY = "EMA({fast}) > EMA({slow})"
EXIT = "EMA({fast}) < EMA({slow})"
PARAMS = [{"name": "fast", "min": 10, "max": 50, "step": 5},
          {"name": "slow", "min": 60, "max": 200, "step": 20}]


def main():
    print(f"Kripto trend WALK-FORWARD ({len(UNIVERSE)} varlık, 1d) ...")
    print(f"  {'sembol':<16}{'OOS ret%':>10}{'Al&Tut%':>10}{'Sharpe':>8}{'MaxDD%':>9}{'kârlı fold':>12}")
    rec = Recorder("trend_wf_crypto", "walkforward", label=f"kripto trend EMA-cross WF ({len(UNIVERSE)} varlık)")
    oos, bh_all, shp = [], [], []
    for sym in UNIVERSE:
        df = okx_provider.get_ohlcv(sym, "1d", bars=1000)
        if df is None or len(df) < 460:
            continue
        try:
            r = wf.run_walk_forward(symbol=sym, entry_template=ENTRY, exit_template=EXIT,
                                    params=PARAMS, interval="1d", method="bayes",
                                    objective="sharpe", n_trials=25, train_bars=365,
                                    test_bars=90, fee_bps=8, direction="long", df=df)
            s = r["summary"]
            # Al&Tut (test bölgesi ~ tüm veri kabaca)
            bh = round((df['close'].iloc[-1] / df['close'].iloc[365] - 1) * 100, 1)
            oos.append(s["oos_total_return"]); bh_all.append(bh); shp.append(s["oos_sharpe"])
            print(f"  {sym.replace('-USDT-SWAP',''):<16}{s['oos_total_return']:>10}{bh:>10}"
                  f"{s['oos_sharpe']:>8}{s['oos_max_drawdown']:>9}"
                  f"{str(s['profitable_folds'])+'/'+str(s['valid_folds']):>12}")
            rec.add({"total_return": s["oos_total_return"], "buy_hold": bh, "sharpe": s["oos_sharpe"],
                     "max_drawdown": s["oos_max_drawdown"], "profitable_folds": s["profitable_folds"],
                     "valid_folds": s["valid_folds"]}, symbol=sym.replace("-USDT-SWAP", ""),
                    interval="1d", name=sym.replace("-USDT-SWAP", ""))
        except Exception as e:
            print(f"  {sym:<16} HATA: {str(e)[:40]}")
    rec.save()
    if oos:
        print(f"\n  === ORTALAMA (OOS, {len(oos)} varlık) ===")
        print(f"  Trend OOS getiri : {np.mean(oos):.1f}%")
        print(f"  Al&Tut getiri    : {np.mean(bh_all):.1f}%")
        print(f"  Ort. OOS Sharpe  : {np.mean(shp):.2f}")


if __name__ == "__main__":
    main()
