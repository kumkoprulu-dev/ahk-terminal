"""Vektörel/olay-tabanlı backtest motoru.

Strateji = giriş kuralı (DSL) + opsiyonel çıkış kuralı (DSL) + opsiyonel stop/target.
Sinyaller bar kapanışında hesaplanır, dolum aynı barın kapanışında varsayılır
(göstergeler yalnızca o bara kadarki veriyi kullandığından look-ahead yoktur).
Stop-loss / take-profit bar içi (low/high) kontrol edilir ve seviye fiyatından çıkılır.

İleride VectorBT ile değiştirilebilir; API sözleşmesi (run) aynı kalır.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.backtest.metrics import equity_metrics, trade_metrics
from app.data import service
from app.scanner.dsl import DSLError, evaluate


def run(
    symbol: str,
    entry_rule: str,
    exit_rule: str | None = None,
    interval: str = "1d",
    range_: str = "2y",
    initial_cash: float = 10_000.0,
    fee_bps: float = 10.0,
    stop_loss: float | None = None,   # yüzde, örn. 5 => %5
    take_profit: float | None = None,  # yüzde
    direction: str = "long",           # long | short
) -> dict:
    """Veriyi çeker ve backtest'i çalıştırır."""
    df = service.get_ohlcv(symbol, interval, range_)
    if df is None or len(df) < 30:
        raise ValueError(f"Yetersiz veri: {symbol}")
    return simulate(
        df, symbol=symbol, entry_rule=entry_rule, exit_rule=exit_rule, interval=interval,
        range_=range_, initial_cash=initial_cash, fee_bps=fee_bps, stop_loss=stop_loss,
        take_profit=take_profit, direction=direction,
    )


def simulate(
    df,
    symbol: str = "",
    entry_rule: str = "",
    exit_rule: str | None = None,
    interval: str = "1d",
    range_: str = "2y",
    initial_cash: float = 10_000.0,
    fee_bps: float = 10.0,
    stop_loss: float | None = None,
    take_profit: float | None = None,
    direction: str = "long",
    light: bool = False,
    warmup: int = 0,
) -> dict:
    """Önceden çekilmiş OHLCV üzerinde backtest (optimizasyon bunu tekrar tekrar çağırır).
    light=True ise equity eğrisi serileştirilmez (yalnız metrikler — optimizasyon hızı).
    warmup>0 ise ilk `warmup` bar yalnız gösterge ısınması içindir; işlem/metikler
    warmup sonrası bölgeden hesaplanır (walk-forward out-of-sample testi için)."""
    entry_sig = evaluate(df, entry_rule).fillna(False).to_numpy()
    exit_sig = (
        evaluate(df, exit_rule).fillna(False).to_numpy()
        if exit_rule and exit_rule.strip()
        else None
    )

    close = df["close"].to_numpy(dtype=float)
    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    idx = df.index
    n = len(df)
    fee = fee_bps / 10_000.0
    sl = stop_loss / 100.0 if stop_loss else None
    tp = take_profit / 100.0 if take_profit else None
    is_long = direction != "short"

    cash = float(initial_cash)
    shares = 0.0
    entry_price = 0.0
    entry_idx = 0
    spent = 0.0
    trades: list[dict] = []
    equity = np.empty(n, dtype=float)

    for i in range(n):
        price = close[i]

        # --- pozisyonda ise çıkış kontrolü ---
        if shares != 0.0:
            exit_now = False
            exit_price = price
            reason = "signal"
            if is_long:
                if sl is not None and low[i] <= entry_price * (1 - sl):
                    exit_now, exit_price, reason = True, entry_price * (1 - sl), "stop"
                elif tp is not None and high[i] >= entry_price * (1 + tp):
                    exit_now, exit_price, reason = True, entry_price * (1 + tp), "target"
            else:
                if sl is not None and high[i] >= entry_price * (1 + sl):
                    exit_now, exit_price, reason = True, entry_price * (1 + sl), "stop"
                elif tp is not None and low[i] <= entry_price * (1 - tp):
                    exit_now, exit_price, reason = True, entry_price * (1 - tp), "target"
            if not exit_now and exit_sig is not None and exit_sig[i]:
                exit_now, reason = True, "signal"

            if exit_now:
                if is_long:
                    proceeds = shares * exit_price * (1 - fee)
                    pnl = proceeds - spent
                    cash += proceeds
                else:
                    pnl = shares * (entry_price - exit_price) - shares * exit_price * fee
                    cash = spent + pnl
                ret_pct = pnl / spent * 100 if spent else 0.0
                trades.append({
                    "entry_date": idx[entry_idx].strftime("%Y-%m-%d"),
                    "exit_date": idx[i].strftime("%Y-%m-%d"),
                    "entry_price": round(entry_price, 4),
                    "exit_price": round(float(exit_price), 4),
                    "return_pct": round(ret_pct, 2),
                    "pnl": round(float(pnl), 2),
                    "bars": int(i - entry_idx),
                    "reason": reason,
                })
                shares = 0.0

        # --- flat ise giriş kontrolü (warmup bölgesinde işlem açılmaz) ---
        if shares == 0.0 and entry_sig[i] and cash > 0 and i >= warmup:
            entry_price = price
            entry_idx = i
            spent = cash
            if is_long:
                shares = cash * (1 - fee) / price
                cash = 0.0
            else:
                shares = cash * (1 - fee) / price  # short edilen birim
                # nakit teminat olarak tutulur (cash = spent); P&L fiyat düşüşünden

        # --- bar sonu equity (mark-to-market) ---
        if shares == 0.0:
            equity[i] = cash
        elif is_long:
            equity[i] = cash + shares * price
        else:
            equity[i] = spent + shares * (entry_price - price)

    # warmup bölgesini at: metrikler/equity yalnız işlem yapılan bölgeden
    s = warmup if 0 < warmup < n else 0
    eq = equity[s:]
    idx_o = idx[s:]
    n_o = len(eq)
    equity_s = pd.Series(eq, index=idx_o)

    # Buy & hold karşılaştırması (test bölgesi)
    bh = close[-1] / close[s] - 1 if n_o else 0.0

    em = equity_metrics(equity_s, interval)
    tm = trade_metrics(trades)
    open_pos = shares != 0.0

    return {
        "symbol": symbol,
        "interval": interval,
        "range": range_,
        "entry_rule": entry_rule,
        "exit_rule": exit_rule,
        "params": {
            "initial_cash": initial_cash, "fee_bps": fee_bps,
            "stop_loss": stop_loss, "take_profit": take_profit, "direction": direction,
        },
        "metrics": {**em, **tm,
                    "buy_hold_return": round(float(bh) * 100, 2),
                    "final_equity": round(float(eq[-1]), 2) if n_o else initial_cash,
                    "exposure": round(sum(t["bars"] for t in trades) / n_o * 100, 1) if n_o else 0,
                    "open_position": open_pos},
        "equity": [] if light else [
            {"time": idx_o[i].strftime("%Y-%m-%d") if interval in ("1d", "1wk", "1mo") else int(idx_o[i].timestamp()),
             "value": round(float(eq[i]), 2)}
            for i in range(n_o)
        ],
        "trades": trades,
    }


def validate_rules(entry_rule: str, exit_rule: str | None) -> None:
    """Kuralları taramadan önce doğrular (DSLError fırlatır)."""
    from app.scanner.dsl import parse
    parse(entry_rule)
    if exit_rule and exit_rule.strip():
        parse(exit_rule)
