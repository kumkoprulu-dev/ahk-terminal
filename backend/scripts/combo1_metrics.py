"""Combo1 (SMA+Fisher+VWAP) TAM METRİK raporu — 'ne kazandırır?' sorusunun cevabı.
Backtest = tarihsel simülasyon (canlı paper daha işlem yapmadı, o yüzden panelde 0).
Tüm dönem + OOS (son %40, görülmemiş) ayrı; işlem sayısı/kazanma oranı/Sharpe/DD/PF."""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
from app.backtest import engine  # noqa: E402
from app.data import okx_provider  # noqa: E402
from app.storage.results_store import Recorder  # noqa: E402

ENTRY = "Close > SMA(50) AND FisherTransform(9).Fisher > FisherTransform(9).Trigger AND Close > VWAP"
EXIT = "Close < SMA(50) OR FisherTransform(9).Fisher < FisherTransform(9).Trigger OR Close < VWAP"
SYMS = ["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP", "BNB-USDT-SWAP",
        "XRP-USDT-SWAP", "LINK-USDT-SWAP", "ADA-USDT-SWAP", "DOGE-USDT-SWAP"]


def show(df, sym, warmup, tag):
    r = engine.simulate(df, symbol=sym, entry_rule=ENTRY, exit_rule=EXIT, interval="1d",
                        fee_bps=10, direction="long", warmup=warmup, light=True)
    m = r["metrics"]
    return {
        "sym": sym.replace("-USDT-SWAP", ""), "tag": tag,
        "ret": m["total_return"], "bh": m["buy_hold_return"], "shp": m["sharpe"],
        "dd": m["max_drawdown"], "n": m["num_trades"], "win": m.get("win_rate", 0),
        "pf": m.get("profit_factor", 0), "exp": m.get("exposure", 0),
        "open": m.get("open_position", False),
    }


def main():
    print("Combo1 = SMA(50) + Fisher(9) + VWAP  —  günlük OKX\n")
    rec = Recorder("combo1_metrics", "combo1", label="Combo1 tam metrik (8 kripto)")
    hdr = (f"  {'sembol':<7}{'dönem':<8}{'getiri%':>9}{'Al&Tut%':>9}{'işlem':>7}"
           f"{'kazanma%':>10}{'PF':>6}{'Sharpe':>8}{'MaxDD%':>8}{'poz.açık':>9}")
    for tag, frac in [("TÜM", 0.0), ("OOS", 0.6)]:
        print(f"=== {tag} DÖNEM ({'tüm tarih' if frac==0 else 'son %40, görülmemiş'}) ===")
        print(hdr)
        agg = {"ret": [], "bh": [], "shp": [], "n": [], "win": []}
        for sym in SYMS:
            df = okx_provider.get_ohlcv(sym, "1d", bars=1000)
            if df is None or len(df) < 300:
                continue
            wu = int(len(df) * frac) if frac > 0 else 60
            d = show(df, sym, wu, tag)
            agg["ret"].append(d["ret"]); agg["bh"].append(d["bh"]); agg["shp"].append(d["shp"])
            agg["n"].append(d["n"]); agg["win"].append(d["win"])
            print(f"  {d['sym']:<7}{tag:<8}{d['ret']:>9.1f}{d['bh']:>9.1f}{d['n']:>7}"
                  f"{d['win']:>10.1f}{d['pf']:>6.2f}{d['shp']:>8.2f}{d['dd']:>8.1f}"
                  f"{('AÇIK' if d['open'] else '—'):>9}")
            rec.add({"total_return": d["ret"], "buy_hold": d["bh"], "num_trades": d["n"],
                     "win_rate": d["win"], "profit_factor": d["pf"], "sharpe": d["shp"],
                     "max_drawdown": d["dd"], "period": tag}, symbol=d["sym"], interval="1d",
                    name=f"{d['sym']} · {tag}")
        print(f"  {'ORT':<7}{'':8}{np.mean(agg['ret']):>9.1f}{np.mean(agg['bh']):>9.1f}"
              f"{np.mean(agg['n']):>7.0f}{np.mean(agg['win']):>10.1f}{'':>6}"
              f"{np.mean(agg['shp']):>8.2f}\n")
        rec.add({"total_return": round(float(np.mean(agg["ret"])), 2),
                 "buy_hold": round(float(np.mean(agg["bh"])), 2),
                 "num_trades": round(float(np.mean(agg["n"])), 1),
                 "win_rate": round(float(np.mean(agg["win"])), 1),
                 "sharpe": round(float(np.mean(agg["shp"])), 3), "period": tag},
                interval="1d", name=f"ORTALAMA · {tag}")
    rec.save()


if __name__ == "__main__":
    main()
