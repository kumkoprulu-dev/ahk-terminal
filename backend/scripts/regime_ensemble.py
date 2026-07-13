"""#3 REJİM-UYARLI ENSEMBLE — Combo2(boğa) / Combo1(her mevsim) / Grid(ayı-savunma) geçişi.

Üst-katman: piyasa genişliğini (breadth = evrenin % kaçı 100g MA üstünde) ölçer, rejime
göre o gün hangi stratejinin portföy getirisini kullanacağına karar verir (dünkü rejim
→ look-ahead yok):
  breadth > %60  → BOĞA   → Combo2 (agresif momentum)
  %40–60         → NÖTR   → Combo1 (her mevsim)
  breadth < %40  → AYI    → Grid (defans, exit_regime_break)
Ensemble equity vs her stratejinin tek-başına portföyü + Al&Tut. TÜM + OOS.
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from app.data import okx_provider  # noqa: E402
from app.scanner.dsl import evaluate  # noqa: E402
from app.backtest import grid  # noqa: E402
from app.backtest.grid_portfolio import UNIVERSE  # noqa: E402
from app.indicators import compute  # noqa: E402
from app.storage.results_store import Recorder  # noqa: E402

C1E = "Close > SMA(50) AND FisherTransform(9).Fisher > FisherTransform(9).Trigger AND Close > VWAP"
C1X = "Close < SMA(50) OR FisherTransform(9).Fisher < FisherTransform(9).Trigger OR Close < VWAP"
C2E = "FisherTransform(9).Fisher > FisherTransform(9).Trigger AND ForceIndex(13) > 0 AND AwesomeOsc(5,34) > 0"
C2X = "FisherTransform(9).Fisher < FisherTransform(9).Trigger OR ForceIndex(13) < 0 OR AwesomeOsc(5,34) < 0"
FEE = 10 / 1e4


def dsl_returns(df, entry, exit_):
    ent = evaluate(df, entry).fillna(False).to_numpy()
    ex = evaluate(df, exit_).fillna(False).to_numpy()
    n = len(df); pos = np.zeros(n); inp = False
    for i in range(n):
        if not inp and ent[i]:
            inp = True
        elif inp and ex[i]:
            inp = False
        pos[i] = 1.0 if inp else 0.0
    close = df["close"].to_numpy(float)
    r = np.zeros(n); r[1:] = close[1:] / close[:-1] - 1
    turn = np.zeros(n); turn[1:] = np.abs(np.diff(pos))
    net = np.concatenate([[0.0], pos[:-1] * r[1:]]) - turn * FEE
    return pd.Series(net, index=df.index)


def grid_returns(df):
    try:
        res = grid.simulate(df, interval="1d", buy_step_pct=4.0, sell_step_pct=4.0,
                            max_tiers=8, lot_quote=500.0, fee_bps=8.0, regime_ma=100,
                            exit_regime_break=True, warmup=0, light=False)
        eq = pd.Series([p["value"] for p in res["equity"]],
                       index=pd.to_datetime([p["time"] for p in res["equity"]], unit="s", utc=True))
        eq = eq.reindex(df.index).ffill()
        return eq.pct_change().fillna(0.0)
    except Exception:
        return pd.Series(0.0, index=df.index)


def stats(ret):
    ret = ret.dropna()
    if len(ret) < 30:
        return 0, 0, 0
    eq = (1 + ret).cumprod()
    return ((eq.iloc[-1] - 1) * 100,
            ret.mean() / ret.std() * np.sqrt(365) if ret.std() > 0 else 0,
            ((eq - eq.cummax()) / eq.cummax()).min() * 100)


def main():
    print(f"#3 Rejim-uyarlı ensemble — {len(UNIVERSE)} kripto (günlük)\n")
    c1, c2, gr, above = {}, {}, {}, {}
    for sym in UNIVERSE:
        df = okx_provider.get_ohlcv(sym, "1d", bars=1000)
        if df is None or len(df) < 300:
            continue
        k = sym.replace("-USDT-SWAP", "")
        c1[k] = dsl_returns(df, C1E, C1X)
        c2[k] = dsl_returns(df, C2E, C2X)
        gr[k] = grid_returns(df)
        sma100 = compute("SMA", df, {"length": 100})["SMA"]
        above[k] = (df["close"] > sma100).astype(float)
    C1 = pd.DataFrame(c1).sort_index(); C2 = pd.DataFrame(c2).sort_index()
    GR = pd.DataFrame(gr).sort_index(); AB = pd.DataFrame(above).sort_index()

    # portföy (eşit ağırlık) getirileri
    p1 = C1.mean(axis=1); p2 = C2.mean(axis=1); pg = GR.mean(axis=1)
    breadth = AB.mean(axis=1) * 100          # % kaç varlık 100g MA üstünde

    # ensemble: dünkü breadth → bugünkü strateji
    reg = breadth.shift(1)
    ens = pd.Series(index=p1.index, dtype=float)
    ens[reg > 60] = p2[reg > 60]             # boğa → Combo2
    ens[(reg <= 60) & (reg >= 40)] = p1[(reg <= 60) & (reg >= 40)]  # nötr → Combo1
    ens[reg < 40] = pg[reg < 40]             # ayı → Grid
    ens = ens.fillna(p1)                     # ilk barlar

    rec = Recorder("regime_ensemble", "portfolio_stack",
                   label=f"rejim-uyarlı ensemble ({len(UNIVERSE)} kripto)")

    def line(name, s, frac=0.0, tag=""):
        idx = s.index[int(len(s) * frac):]
        t, sh, dd = stats(s.loc[idx])
        print(f"    {name:<22}{t:>10.1f}{sh:>9.2f}{dd:>9.1f}")
        rec.add({"total_return": round(t, 2), "sharpe": round(sh, 3), "max_drawdown": round(dd, 2),
                 "period": tag}, interval="1d", name=f"{tag} · {name.strip('> ').strip()}")

    for tag, frac in [("TÜM DÖNEM", 0.0), ("OOS (son %40)", 0.6)]:
        print(f"=== {tag} ===")
        print(f"    {'strateji':<22}{'getiri%':>10}{'Sharpe':>9}{'MaxDD%':>9}")
        line("Combo1 (her mevsim)", p1, frac, tag)
        line("Combo2 (boğa)", p2, frac, tag)
        line("Grid (ayı-savunma)", pg, frac, tag)
        line(">> ENSEMBLE (rejim)", ens, frac, tag)
        print()
    rec.save()
    # rejim dağılımı
    r = breadth.shift(1).dropna()
    print(f"  Rejim dağılımı: boğa %{(r>60).mean()*100:.0f} · "
          f"nötr %{((r<=60)&(r>=40)).mean()*100:.0f} · ayı %{(r<40).mean()*100:.0f}")


if __name__ == "__main__":
    main()
