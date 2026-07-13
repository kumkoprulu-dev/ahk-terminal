"""SMA+Fisher+VWAP komboyu WALK-FORWARD + Optuna ile optimize et (gerçek OOS testi).

Kombo parametreleri (SMA periyodu, Fisher periyodu) her fold'un EĞİTİM diliminde optimize,
bir sonraki TEST diliminde (OOS) sınanır. Tüm OOS foldlar zincirlenir. Bu, "parametreyi
optimize edince edge güçlenir mi yoksa in-sample illüzyonu mu?" sorusunu dürüst yanıtlar.

Sabit (in-sample triage'dan) SMA+Fisher+VWAP OOS 0.338'di; WF-optimize bunu geçer mi?
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
from app.backtest import walkforward as wf  # noqa: E402
from app.data import service  # noqa: E402

try:
    from app.data import okx_provider  # noqa: E402
except Exception:
    okx_provider = None

# {sma} ve {fisher} yer tutucuları — WF her fold'da optimize eder
ENTRY = ("Close > SMA({sma}) AND "
         "FisherTransform({fisher}).Fisher > FisherTransform({fisher}).Trigger AND "
         "Close > VWAP")
EXIT = ("Close < SMA({sma}) OR "
        "FisherTransform({fisher}).Fisher < FisherTransform({fisher}).Trigger OR "
        "Close < VWAP")
PARAMS = [{"name": "sma", "min": 20, "max": 100, "step": 10},
          {"name": "fisher", "min": 5, "max": 30, "step": 5}]

BIST = ["EREGL.IS", "KCHOL.IS", "SASA.IS", "TUPRS.IS", "SISE.IS", "FROTO.IS"]
CRYPTO = ["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP", "BNB-USDT-SWAP"]


def fetch(sym, market):
    if market == "crypto":
        return okx_provider.get_ohlcv(sym, "1d", bars=1000) if okx_provider else None
    return service.get_ohlcv(sym, "1d", "5y")


def main():
    from app.storage.results_store import Recorder
    print("SMA+Fisher+VWAP WALK-FORWARD optimize (1d, train 365 / test 90, grid) ...\n")
    print(f"  {'sembol':<10}{'OOS ret%':>10}{'Sharpe':>8}{'MaxDD%':>9}{'kârlı fold':>12}{'~params':>14}")
    rec = Recorder("wf_optimize_combo", "walkforward", label="SMA+Fisher+VWAP WF-optimize (1d)")
    oos_ret, shp = [], []
    universe = [(s, "bist") for s in BIST] + [(s, "crypto") for s in CRYPTO]
    for sym, market in universe:
        try:
            df = fetch(sym, market)
            if df is None or len(df) < 460:
                print(f"  {sym:<10} yetersiz veri"); continue
            r = wf.run_walk_forward(symbol=sym, entry_template=ENTRY, exit_template=EXIT,
                                    params=PARAMS, interval="1d", method="grid",
                                    objective="sharpe", n_trials=54, train_bars=365,
                                    test_bars=90, fee_bps=10, direction="long", df=df)
            s = r["summary"]
            # en sık seçilen parametreleri özetle
            ps = [f["params"] for f in r["folds"] if f.get("params")]
            if ps:
                sma_med = int(np.median([p["sma"] for p in ps]))
                fis_med = int(np.median([p["fisher"] for p in ps]))
                pstr = f"sma{sma_med}/fis{fis_med}"
            else:
                pstr = "-"
            oos_ret.append(s["oos_total_return"]); shp.append(s["oos_sharpe"])
            name = sym.replace("-USDT-SWAP", "")
            print(f"  {name:<10}{s['oos_total_return']:>10}{s['oos_sharpe']:>8}"
                  f"{s['oos_max_drawdown']:>9}"
                  f"{str(s['profitable_folds'])+'/'+str(s['valid_folds']):>12}{pstr:>14}")
            rec.add({"total_return": s["oos_total_return"], "sharpe": s["oos_sharpe"],
                     "max_drawdown": s["oos_max_drawdown"], "profitable_folds": s["profitable_folds"],
                     "valid_folds": s["valid_folds"], "params": pstr}, symbol=name, interval="1d", name=name)
        except Exception as e:
            print(f"  {sym:<10} HATA: {str(e)[:44]}")
    rec.save()
    if oos_ret:
        print(f"\n  === ORTALAMA (OOS, {len(oos_ret)} sembol) ===")
        print(f"  WF-optimize OOS getiri : {np.mean(oos_ret):.1f}%")
        print(f"  WF-optimize OOS Sharpe : {np.mean(shp):.3f}")
        print(f"  (sabit-param SMA+Fisher+VWAP OOS Sharpe 0.338 idi — karşılaştır)")


if __name__ == "__main__":
    main()
