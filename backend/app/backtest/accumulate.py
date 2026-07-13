"""Sibirya Beta — SADIK model (kullanıcının GERÇEK talimat kuralları, kaynaktan).

⚠️ SINIR: Gerçek strateji TICK + DERİNLİK(spread) tabanlıdır (0.4/0.6 anlık scalp,
spread-korumalı falling-knife = sibirya9 'if x<alis_satis_fark continue'). Tarihsel
tick/order-book verisi olmadığından bar (1h/1m) üzerinde ancak YAPI taklit edilir; günde
~10 tur ve spread koruması olduğundan AZ görünür. Canlı kâr asıl kanıttır.

Kurallar (kullanıcı + sibirya5/9 kaynağı):
  • ZARARA SATIŞ YOK. Kârda değilse tut. Maliyet = zaman, para değil.
  • ZİRVE TAVANI (temel analiz değeri): yalnız tavan altında al.
  • KADEME: %0.4 düşüşte al, %0.6 üstünde sat (NORMAL mod, per-kademe scalp).
  • PİRAMİT (sibirya5): toplamalı lot = base + tier*inc (2,4,6...). 125 kademeye / −%50'ye kadar.
  • KESKİN DÜŞÜŞ KORUMASI (sibirya9): tek barda ani büyük düşüşte ALMA (spread-açılma proxy'si).
  • TOPLU SAT: hisse tepeden >%25 düşmüşse per-kademe satışı DURDUR, tüm yığını ort.maliyet+%5'te sat.
  • Getiri = kullanılan sermaye üzerinden (return on max deployed), döngüler hep kârlı.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def simulate(
    df: pd.DataFrame,
    *,
    symbol: str = "",
    interval: str = "1h",
    unit_quote: float = 1000.0,     # 'base 2 lot' birimi (TL). Piramit bunu tier'a göre ölçekler
    ceiling: float | None = None,   # mutlak zirve tavanı (temel değer). None → tavan yok (test)
    ceiling_frac: float = 0.0,      # >0 ise tavan = ceiling_frac × trailing tepe (mutlak yoksa proxy)
    ceiling_window: int = 240,
    buy_step_pct: float = 0.4,
    sell_step_pct: float = 0.6,
    base_lot: int = 2,
    lot_inc: int = 2,               # piramit artışı (2,4,6...)
    max_tiers: int = 125,
    max_drop_pct: float = 50.0,     # en derin kademe entryden bu kadar aşağıda
    deep_dd_pct: float = 25.0,      # tepeden bu % düşünce TOPLU-SAT moduna geç
    bulk_target_pct: float = 5.0,   # toplu sat: ort.maliyet + bu %
    sharp_drop_pct: float = 3.0,    # tek barda bundan sert düşüşte ALMA (falling-knife proxy)
    fee_bps: float = 5.0,
    warmup: int = 0,
    light: bool = False,
) -> dict:
    close = df["close"].to_numpy(float)
    high = df["high"].to_numpy(float)
    low = df["low"].to_numpy(float)
    idx = df.index
    n = len(df)
    fee = fee_bps / 10_000.0
    roll_high = pd.Series(close).rolling(ceiling_window, min_periods=1).max().to_numpy()
    peak = pd.Series(close).cummax().to_numpy()   # şimdiye kadarki tepe (deep-DD için)
    wu = max(ceiling_window if ceiling_frac > 0 else 0, warmup, 1)

    INIT = 1e9                       # bol sermaye; asıl metrik = kullanılan sermaye
    cash = INIT
    lots: list[dict] = []            # {price, qty, entry_i}
    trades: list[dict] = []
    equity = np.empty(n, float)
    max_deployed = 0.0
    max_paper_dd = 0.0
    max_time = 0
    cycle_start_i = None
    entry_price = None               # ilk kademe (max_drop referansı)

    for i in range(n):
        px, hi, lo = close[i], high[i], low[i]
        deep = lots and (peak[i] > 0 and px <= peak[i] * (1 - deep_dd_pct / 100.0))

        # --- SATIŞ (asla zarara değil) ---
        if lots:
            qty = sum(l["qty"] for l in lots)
            cost = sum(l["qty"] * l["price"] for l in lots)
            avg = cost / qty
            if deep:
                # DERİN mod: per-kademe satış DURDU; tüm yığını ort+%5'te topluca sat
                target = avg * (1 + bulk_target_pct / 100.0)
                if hi >= target:
                    _close_all(lots, target, fee, cash_ref := [cash], trades, idx, interval, cycle_start_i, i, "toplu_sat_derin")
                    cash = cash_ref[0]; lots = []; cycle_start_i = None; entry_price = None
            else:
                # NORMAL mod: her kademe kendi +%0.6'sında satılır (hep kârlı)
                still = []
                for lot in lots:
                    tgt = lot["price"] * (1 + sell_step_pct / 100.0)
                    if hi >= tgt:
                        proceeds = lot["qty"] * tgt * (1 - fee)
                        pnl = proceeds - lot["qty"] * lot["price"] * (1 + fee)
                        cash += proceeds
                        trades.append(_trade(idx, lot["entry_i"], i, lot["price"], tgt,
                                             lot["qty"], pnl, interval, "kademe_sat"))
                    else:
                        still.append(lot)
                lots = still
                if not lots:
                    cycle_start_i = None; entry_price = None

        # --- ALIŞ ---
        if i >= wu and len(lots) < max_tiers:
            cap = ceiling if ceiling is not None else (ceiling_frac * roll_high[i] if ceiling_frac > 0 else np.inf)
            below_ceiling = px <= cap
            # keskin düşüş koruması: tek barda sert düşüşte alma (spread-açılma proxy)
            prev = close[i - 1] if i > 0 else px
            sharp = prev > 0 and (prev - lo) / prev * 100.0 > sharp_drop_pct
            drop_ok = entry_price is None or px >= entry_price * (1 - max_drop_pct / 100.0)

            if below_ceiling and not sharp and drop_ok:
                if not lots:
                    level, fill = px, px
                else:
                    lowest = min(l["price"] for l in lots)
                    level = lowest * (1 - buy_step_pct / 100.0)
                    fill = level if lo <= level else None
                if fill is not None:
                    tier = len(lots)
                    lot_units = base_lot + lot_inc * tier          # 2,4,6...
                    quote = unit_quote * (lot_units / base_lot)     # birime göre ölçek
                    qty = quote / fill
                    cash -= qty * fill * (1 + fee)
                    lots.append({"price": fill, "qty": qty, "entry_i": i})
                    if cycle_start_i is None:
                        cycle_start_i = i; entry_price = fill

        # --- izleme ---
        pos_val = sum(l["qty"] * px for l in lots)
        equity[i] = cash + pos_val
        deployed = INIT - cash
        max_deployed = max(max_deployed, deployed)
        if lots:
            cost = sum(l["qty"] * l["price"] for l in lots)
            max_paper_dd = min(max_paper_dd, (pos_val - cost) / cost * 100 if cost else 0)
            max_time = max(max_time, i - cycle_start_i)

    realized = sum(t["pnl"] for t in trades)
    open_qty = sum(l["qty"] for l in lots)
    open_cost = sum(l["qty"] * l["price"] for l in lots)
    open_val = open_qty * close[-1] if open_qty else 0.0
    ror = realized / max_deployed * 100 if max_deployed else 0.0
    yrs = n / (252 * (7 if interval == "1h" else 1)) if interval in ("1h",) else n / 252

    return {
        "symbol": symbol, "interval": interval,
        "metrics": {
            "realized_pnl": round(realized, 2),
            "return_on_capital": round(ror, 2),          # kullanılan sermaye üstünden getiri
            "max_deployed": round(max_deployed, 2),
            "num_trades": len(trades),
            "win_rate": 100.0 if trades else 0.0,        # zarara satış yok
            "max_time_bars": max_time,                   # asıl maliyet = zaman
            "max_paper_drawdown": round(max_paper_dd, 2),
            "open_tiers_end": len(lots),
            "open_unrealized_pct": round((open_val - open_cost) / open_cost * 100, 2) if open_cost else 0.0,
            "bars": n, "approx_years": round(yrs, 2),
        },
        "equity": [] if light else [
            {"time": _d(idx[i], interval), "value": round(float(equity[i]), 2)} for i in range(n)
        ],
        "trades": trades,
    }


def _trade(idx, ei, xi, entry, exit_, qty, pnl, interval, reason):
    cost = qty * entry
    return {"entry_date": _d(idx[ei], interval), "exit_date": _d(idx[xi], interval),
            "entry_price": round(entry, 4), "exit_price": round(exit_, 4), "qty": round(qty, 4),
            "return_pct": round(pnl / cost * 100, 2) if cost else 0, "pnl": round(pnl, 2),
            "bars": int(xi - ei), "reason": reason}


def _close_all(lots, price, fee, cash_ref, trades, idx, interval, start_i, i, reason):
    for lot in lots:
        proceeds = lot["qty"] * price * (1 - fee)
        pnl = proceeds - lot["qty"] * lot["price"] * (1 + fee)
        cash_ref[0] += proceeds
        trades.append(_trade(idx, lot["entry_i"], i, lot["price"], price, lot["qty"], pnl, interval, reason))


def _d(ts, interval: str) -> str:
    return ts.strftime("%Y-%m-%d") if interval in ("1d", "1wk", "1mo") else ts.strftime("%Y-%m-%d %H:%M")
