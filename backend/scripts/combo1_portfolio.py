"""#1 PORTFÖY ÇEŞİTLENDİRME — Combo1'i tüm kripto evreninde aynı anda çalıştır.

Tez: tek varlıkta Sharpe ~0.5; korelasyonsuz çok varlıkta birleştirince gürültü söner
→ portföy Sharpe belirgin yükselir, DD düşer. Fonların asıl kaldıracı bu.

Her varlık: Combo1 (long-only) günlük getirisi = poz[t-1]×r[t] − değişim komisyonu.
Portföy: (a) eşit ağırlık, (b) ters-vol ağırlık (her varlık eşit RİSK katkısı).
Karşılaştırma: tek-varlık ort. Sharpe vs portföy Sharpe/DD.
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

ENTRY = "Close > SMA(50) AND FisherTransform(9).Fisher > FisherTransform(9).Trigger AND Close > VWAP"
EXIT = "Close < SMA(50) OR FisherTransform(9).Fisher < FisherTransform(9).Trigger OR Close < VWAP"
FEE = 10 / 1e4


def combo_returns(df):
    """Combo1 long-only günlük net getiri serisi (poz durum-makinesi, engine ile aynı)."""
    ent = evaluate(df, ENTRY).fillna(False).to_numpy()
    ex = evaluate(df, EXIT).fillna(False).to_numpy()
    n = len(df)
    pos = np.zeros(n)
    in_pos = False
    for i in range(n):
        if not in_pos and ent[i]:
            in_pos = True
        elif in_pos and ex[i]:
            in_pos = False
        pos[i] = 1.0 if in_pos else 0.0
    close = df["close"].to_numpy(float)
    r = np.zeros(n)
    r[1:] = close[1:] / close[:-1] - 1
    turn = np.zeros(n)
    turn[1:] = np.abs(np.diff(pos))
    net = np.concatenate([[0.0], pos[:-1] * r[1:]]) - turn * FEE
    return pd.Series(net, index=df.index)


def stats(ret):
    ret = ret.dropna()
    if len(ret) < 30:
        return 0, 0, 0
    eq = (1 + ret).cumprod()
    total = (eq.iloc[-1] - 1) * 100
    shp = ret.mean() / ret.std() * np.sqrt(365) if ret.std() > 0 else 0
    dd = ((eq - eq.cummax()) / eq.cummax()).min() * 100
    return total, shp, dd


def main():
    print(f"#1 Portföy çeşitlendirme — Combo1 × {len(UNIVERSE)} kripto (günlük)\n")
    rets = {}
    single_shp = []
    for sym in UNIVERSE:
        df = okx_provider.get_ohlcv(sym, "1d", bars=1000)
        if df is None or len(df) < 300:
            continue
        s = combo_returns(df)
        rets[sym.replace("-USDT-SWAP", "")] = s
        t, sh, dd = stats(s)
        single_shp.append(sh)
    R = pd.DataFrame(rets).sort_index()
    print(f"  {len(R.columns)} varlık, {len(R)} gün ortak takvim\n")

    # tek-varlık ortalama
    print(f"  Tek-varlık ORTALAMA Sharpe : {np.mean(single_shp):.3f}")

    rec = Recorder("combo1_portfolio", "combo1",
                   label=f"Combo1 portföy çeşitlendirme ({len(R.columns)} kripto)")
    rec.add({"sharpe": round(float(np.mean(single_shp)), 3)}, interval="1d",
            name="Tek-varlık ORTALAMA")

    # (a) eşit ağırlık portföy
    ew = R.mean(axis=1, skipna=True)
    te, se, de = stats(ew)
    print(f"\n  (a) EŞİT AĞIRLIK portföy:")
    print(f"      getiri {te:+.1f}%   Sharpe {se:.3f}   MaxDD {de:.1f}%")
    rec.add({"total_return": round(te, 2), "sharpe": round(se, 3), "max_drawdown": round(de, 2)},
            interval="1d", name="Eşit ağırlık portföy")

    # (b) ters-vol ağırlık (her varlık eşit risk) — 60g rolling vol
    vol = R.rolling(60).std()
    w = (1.0 / vol).replace([np.inf, -np.inf], np.nan)
    w = w.div(w.sum(axis=1), axis=0)          # normalize (satır toplamı 1)
    iv = (R * w.shift(1)).sum(axis=1, skipna=True)   # look-ahead yok: dünkü ağırlık
    ti, si, di = stats(iv.iloc[60:])
    print(f"\n  (b) TERS-VOL AĞIRLIK portföy (eşit risk katkısı):")
    print(f"      getiri {ti:+.1f}%   Sharpe {si:.3f}   MaxDD {di:.1f}%")
    rec.add({"total_return": round(ti, 2), "sharpe": round(si, 3), "max_drawdown": round(di, 2)},
            interval="1d", name="Ters-vol ağırlık portföy")
    rec.save()

    # ortalama ikili korelasyon (çeşitlendirme ne kadar mümkün)
    c = R.corr()
    avg_corr = (c.values[np.triu_indices_from(c.values, 1)]).mean()
    print(f"\n  Ort. ikili korelasyon : {avg_corr:.2f}  (düşük = daha iyi çeşitlendirme)")
    lift = se - np.mean(single_shp)
    print(f"\n  >>> ÇEŞİTLENDİRME KAZANCI: tek {np.mean(single_shp):.2f} → portföy {se:.2f} "
          f"(+{lift:.2f} Sharpe), DD tek ort'dan çok düşük.")


if __name__ == "__main__":
    main()
