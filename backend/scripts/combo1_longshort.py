"""Combo1 long-only vs LONG/SHORT — düşüşte de kazanır mı? (kullanıcı sorusu)

Sinyaller (DSL): boğa = 3 koşul YUKARI (long), ayı = 3 koşul AŞAĞI (short, ayna).
  L  (long-only): pos = +1 boğada, yoksa flat
  LS (long/short): pos = +1 boğada, −1 ayıda, karışıkta flat
Bar getirisi × önceki-bar pozisyonu (look-ahead yok) + değişimde komisyon.
UYARI: perp funding/borrow maliyeti MODELLENMEDİ; short kriptonun uzun-vade
yükseliş eğilimine karşı risklidir. Bu saf fiyat testi.
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
from app.data import okx_provider  # noqa: E402
from app.scanner.dsl import evaluate  # noqa: E402
from app.storage.results_store import Recorder  # noqa: E402

BULL = "Close > SMA(50) AND FisherTransform(9).Fisher > FisherTransform(9).Trigger AND Close > VWAP"
BEAR = "Close < SMA(50) AND FisherTransform(9).Fisher < FisherTransform(9).Trigger AND Close < VWAP"
SYMS = ["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP", "BNB-USDT-SWAP",
        "XRP-USDT-SWAP", "LINK-USDT-SWAP", "ADA-USDT-SWAP", "DOGE-USDT-SWAP"]
FEE = 10 / 1e4  # 10 bps / işlem yönü değişimi


def sim(close, pos, fee=FEE):
    """pos: her bar hedef pozisyon (-1/0/+1). Getiri = pos[t-1]*r[t] - değişim komisyonu."""
    r = np.diff(close) / close[:-1]
    p = pos[:-1]                       # önceki bar pozisyonu bu bar getirisine uygulanır
    gross = p * r
    turn = np.abs(np.diff(pos))        # pozisyon değişim büyüklüğü (komisyon tetikleyici)
    net = gross - turn * fee
    eq = np.cumprod(1 + net)
    total = (eq[-1] - 1) * 100 if len(eq) else 0.0
    # yıllıklandırılmış Sharpe (günlük)
    sd = net.std()
    shp = (net.mean() / sd * np.sqrt(365)) if sd > 0 else 0.0
    peak = np.maximum.accumulate(eq)
    dd = ((eq - peak) / peak).min() * 100 if len(eq) else 0.0
    return total, shp, dd


def build_pos(bull, bear, mode):
    n = len(bull)
    pos = np.zeros(n)
    for i in range(n):
        if mode == "L":
            pos[i] = 1.0 if bull[i] else 0.0
        else:  # LS
            pos[i] = 1.0 if bull[i] else (-1.0 if bear[i] else 0.0)
    return pos


def main():
    print("Combo1 long-only (L) vs long/short (LS) — günlük OKX\n")
    rec = Recorder("combo1_longshort", "combo1", label="Combo1 long-only vs long/short")
    for tag, frac in [("TÜM DÖNEM", 0.0), ("OOS (son %40)", 0.6)]:
        print(f"=== {tag} ===")
        print(f"  {'sembol':<7}{'Al&Tut%':>9}{'L getiri%':>11}{'LS getiri%':>12}"
              f"{'L Shp':>7}{'LS Shp':>8}{'L DD%':>8}{'LS DD%':>8}")
        A = {"bh": [], "l": [], "ls": [], "lshp": [], "lsshp": []}
        for sym in SYMS:
            df = okx_provider.get_ohlcv(sym, "1d", bars=1000)
            if df is None or len(df) < 300:
                continue
            s = int(len(df) * frac)
            bull = evaluate(df, BULL).fillna(False).to_numpy()
            bear = evaluate(df, BEAR).fillna(False).to_numpy()
            close = df["close"].to_numpy(float)
            bull, bear, close = bull[s:], bear[s:], close[s:]
            if len(close) < 40:
                continue
            bh = (close[-1] / close[0] - 1) * 100
            lt, lshp, ldd = sim(close, build_pos(bull, bear, "L"))
            lst, lsshp, lsdd = sim(close, build_pos(bull, bear, "LS"))
            A["bh"].append(bh); A["l"].append(lt); A["ls"].append(lst)
            A["lshp"].append(lshp); A["lsshp"].append(lsshp)
            print(f"  {sym.replace('-USDT-SWAP',''):<7}{bh:>9.1f}{lt:>11.1f}{lst:>12.1f}"
                  f"{lshp:>7.2f}{lsshp:>8.2f}{ldd:>8.1f}{lsdd:>8.1f}")
            rec.add({"buy_hold": round(bh, 2), "total_return": round(lt, 2), "sharpe": round(lshp, 3),
                     "max_drawdown": round(ldd, 2), "ls_return": round(lst, 2),
                     "ls_sharpe": round(lsshp, 3), "ls_max_drawdown": round(lsdd, 2), "period": tag},
                    symbol=sym.replace("-USDT-SWAP", ""), interval="1d",
                    name=f"{sym.replace('-USDT-SWAP','')} · {tag}")
        print(f"  {'ORT':<7}{np.mean(A['bh']):>9.1f}{np.mean(A['l']):>11.1f}"
              f"{np.mean(A['ls']):>12.1f}{np.mean(A['lshp']):>7.2f}{np.mean(A['lsshp']):>8.2f}\n")
    rec.save()


if __name__ == "__main__":
    main()
