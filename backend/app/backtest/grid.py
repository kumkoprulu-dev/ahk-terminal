"""Sibirya grid-birikim (kademe/paçal) backtest simülatörü.

İdeal 'sibirya10_Beta' robotunun mantığının OHLCV üzerinde modeli. Mevcut tek-pozisyon
DSL motorundan (engine.simulate) FARKLIDIR: aynı anda birçok açık kademe tutar,
düşüşte kademe ekleyip ortalama maliyeti düşürür (paçal), her kademeyi kendi alış
fiyatının üstünde kârla kapatır (kademeli satış).

Kademe mantığı:
  • ALIŞ: fiyat, en düşük açık kademenin `buy_step_pct` altına inince yeni kademe al
    (flat iken ilk kademe bar kapanışında tohumlanır). Bar içi `low` ile dolum.
  • SATIŞ: her açık kademe, kendi alış fiyatının `sell_step_pct` üstüne çıkınca satılır
    (bar içi `high` ile). Realized kâr = o kademe.
  • Piramitleme (`pyramid`): daha derin kademelerde lot büyür (>1).
  • MA filtresi (`ma_period`): yalnızca fiyat MA'nın altındayken yeni kademe (zayıflıktan al).
  • Bant (`band_low/high`): sadece bu fiyat aralığında kademe aç (zirve/dip).
  • Rejim filtresi (`regime_ma`): uzun MA'nın altında (düşen trend) grid durur — endeks
    kill-switch'in kripto karşılığı; 0 = kapalı.

Metrikler mevcut metrics.py ile ortak (Sharpe/DD/CAGR + trade istatistikleri).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.backtest.metrics import equity_metrics, trade_metrics


def simulate(
    df: pd.DataFrame,
    *,
    symbol: str = "",
    interval: str = "4h",
    initial_cash: float = 10_000.0,
    lot_quote: float = 500.0,       # kademe başına yatırım (USDT)
    buy_step_pct: float = 3.0,      # kademe_arasi — % düşüşte yeni alım
    sell_step_pct: float = 3.0,     # kademe_arasi_satis — kademe alışının % üstünde sat
    max_tiers: int = 8,             # eşzamanlı açık kademe tavanı (sermaye sınırı)
    fee_bps: float = 8.0,           # OKX taker ~ 5bps, güvenli 8
    pyramid: float = 1.0,           # derin kademede lot ÇARPANI (1 = sabit; geometrik)
    pyramid_add: float = 0.0,       # derin kademede lot TOPLAMALI artış (Sibirya otomatik_lot): quote*(1+add*tier)
    ma_period: int = 0,             # >0 ise: yalnız close<=MA iken yeni kademe
    er_period: int = 0,             # >0 ise: Efficiency Ratio penceresi (range tespiti / varlık seçimi)
    er_max: float = 1.0,            # ER bu değerin ÜSTÜNDEyse (trending) yeni kademe AÇMA — grid yalnız choppy/yatayda
    heyecan_ma: int = 0,            # >0 ise sibirya3 HEYECAN: fiyat MA üstündeyken SATMA (trendi sür), MA altına düşünce kârlı kademeleri boşalt
    band_low: float = 0.0,          # dip fiyat (0 = kapalı)
    band_high: float = 0.0,         # zirve fiyat (0 = kapalı)
    regime_ma: int = 0,             # >0 ise: close<regime_MA iken grid durur (düşen trend)
    exit_regime_break: bool = False,  # regime_MA altına düşünce TÜM kademeleri boşalt (bear defansı)
    stop_dd_pct: float = 0.0,       # >0 ise: açık çuval zararı bu %'yi geçince hepsini boşalt
    warmup: int = 0,                # >0 ise ilk `warmup` bar yalnız ısınma; işlem/metrik sonrası bölgeden (walk-forward OOS)
    light: bool = False,
) -> dict:
    close = df["close"].to_numpy(float)
    high = df["high"].to_numpy(float)
    low = df["low"].to_numpy(float)
    idx = df.index
    n = len(df)
    fee = fee_bps / 10_000.0

    ma = (pd.Series(close).rolling(ma_period).mean().to_numpy() if ma_period > 0 else None)
    rma = (pd.Series(close).rolling(regime_ma).mean().to_numpy() if regime_ma > 0 else None)
    # Efficiency Ratio (Kaufman): |net değişim| / toplam yol. ~0=choppy(grid'e iyi), ~1=trend
    er = None
    if er_period > 0:
        c = pd.Series(close)
        net = c.diff(er_period).abs()
        path = c.diff().abs().rolling(er_period).sum()
        er = (net / path.replace(0, np.nan)).to_numpy()
    hma = (pd.Series(close).rolling(heyecan_ma).mean().to_numpy() if heyecan_ma > 0 else None)
    wu = max(ma_period, regime_ma, er_period, heyecan_ma, warmup)  # işleme başlamadan önce gereken bar

    cash = float(initial_cash)
    lots: list[dict] = []          # {buy_price, qty, tier, entry_i}
    trades: list[dict] = []
    equity = np.empty(n, float)
    max_concurrent = 0

    for i in range(n):
        px, hi, lo = close[i], high[i], low[i]

        # --- SATIŞ ---
        # HEYECAN (sibirya3): fiyat MA üstündeyken SATMA (trendi sür); MA altına düşünce
        #   kârlı kademeleri piyasadan (px) boşalt → +%0.6 yerine sürülen kazancı yakalar.
        # Aksi halde: klasik sabit hedef (+sell_step, bar içi high, limit fiyatından).
        heyecan_on = hma is not None and hma[i] == hma[i]
        still = []
        for lot in lots:
            if heyecan_on:
                sell_now = px <= hma[i] and px > lot["buy_price"]
                exit_price, reason = px, "heyecan"
            else:
                target = lot["buy_price"] * (1 + sell_step_pct / 100.0)
                sell_now, exit_price, reason = hi >= target, target, "target"
            if sell_now:
                proceeds = lot["qty"] * exit_price * (1 - fee)
                spent = lot["qty"] * lot["buy_price"]
                pnl = proceeds - spent * (1 + fee)  # alış ücreti de düş
                cash += proceeds
                trades.append({
                    "entry_date": _d(idx[lot["entry_i"]], interval),
                    "exit_date": _d(idx[i], interval),
                    "entry_price": round(lot["buy_price"], 6),
                    "exit_price": round(exit_price, 6),
                    "return_pct": round(pnl / spent * 100, 2) if spent else 0.0,
                    "pnl": round(pnl, 2),
                    "bars": int(i - lot["entry_i"]),
                    "reason": reason,
                })
            else:
                still.append(lot)
        lots = still

        # --- BEAR DEFANSI: trend kırıldı ya da çuval zararı sınırı aşıldı → hepsini boşalt ---
        if lots:
            regime_down = (exit_regime_break and rma is not None
                           and rma[i] == rma[i] and px < rma[i])
            dd = 0.0
            if stop_dd_pct > 0:
                cost = sum(l["qty"] * l["buy_price"] for l in lots)
                val = sum(l["qty"] * px for l in lots)
                dd = (val - cost) / cost * 100 if cost else 0.0
            if regime_down or (stop_dd_pct > 0 and dd <= -stop_dd_pct):
                reason = "regime_exit" if regime_down else "stop_dd"
                for lot in lots:
                    proceeds = lot["qty"] * px * (1 - fee)
                    spent = lot["qty"] * lot["buy_price"]
                    pnl = proceeds - spent * (1 + fee)
                    cash += proceeds
                    trades.append({
                        "entry_date": _d(idx[lot["entry_i"]], interval),
                        "exit_date": _d(idx[i], interval),
                        "entry_price": round(lot["buy_price"], 6),
                        "exit_price": round(px, 6),
                        "return_pct": round(pnl / spent * 100, 2) if spent else 0.0,
                        "pnl": round(pnl, 2),
                        "bars": int(i - lot["entry_i"]),
                        "reason": reason,
                    })
                lots = []

        # --- ALIŞ: bir sonraki kademe seviyesine inildi mi? (bar başına en çok 1) ---
        if i >= wu:
            regime_ok = rma is None or (rma[i] == rma[i] and px >= rma[i])
            ma_ok = ma is None or (ma[i] == ma[i] and px <= ma[i])
            band_ok = (band_low <= 0 or px >= band_low) and (band_high <= 0 or px <= band_high)
            # range kapısı: yalnız choppy/yatayda kademe aç (ER düşükse); trending'de dur
            er_ok = er is None or (er[i] == er[i] and er[i] <= er_max)

            if regime_ok and ma_ok and band_ok and er_ok and len(lots) < max_tiers:
                if not lots:
                    level, fill = px, px          # ilk kademe: bar kapanışında tohumla
                else:
                    lowest = min(l["buy_price"] for l in lots)
                    level = lowest * (1 - buy_step_pct / 100.0)
                    fill = level if lo <= level else None
                if fill is not None:
                    tier = len(lots)
                    quote = lot_quote * (pyramid ** tier) * (1 + pyramid_add * tier)
                    if cash >= quote * (1 + fee) and quote > 0:
                        qty = quote / fill
                        cash -= qty * fill * (1 + fee)
                        lots.append({"buy_price": fill, "qty": qty, "tier": tier, "entry_i": i})

        max_concurrent = max(max_concurrent, len(lots))
        equity[i] = cash + sum(l["qty"] * px for l in lots)

    # warmup bölgesini metrik/equity'den at (walk-forward OOS testi için)
    s = warmup if 0 < warmup < n else 0
    eq = equity[s:]
    idx_o = idx[s:]
    n_o = len(eq)
    equity_s = pd.Series(eq, index=idx_o)
    em = equity_metrics(equity_s, interval)
    tm = trade_metrics(trades)
    bh = close[-1] / close[s] - 1 if n_o else 0.0
    open_val = sum(l["qty"] * close[-1] for l in lots)
    open_cost = sum(l["qty"] * l["buy_price"] for l in lots)

    return {
        "symbol": symbol, "interval": interval,
        "params": {
            "initial_cash": initial_cash, "lot_quote": lot_quote,
            "buy_step_pct": buy_step_pct, "sell_step_pct": sell_step_pct,
            "max_tiers": max_tiers, "fee_bps": fee_bps, "pyramid": pyramid,
            "ma_period": ma_period, "regime_ma": regime_ma,
        },
        "metrics": {
            **em, **tm,
            "buy_hold_return": round(bh * 100, 2),
            "final_equity": round(float(eq[-1]), 2) if n_o else initial_cash,
            "max_concurrent_tiers": max_concurrent,
            "open_tiers_end": len(lots),
            "open_unrealized_pct": round((open_val - open_cost) / open_cost * 100, 2) if open_cost else 0.0,
            "bars": n_o, "period": f"{_d(idx_o[0], interval)} → {_d(idx_o[-1], interval)}" if n_o else "",
        },
        "equity": [] if light else [
            {"time": int(idx_o[i].timestamp()), "value": round(float(eq[i]), 2)}
            for i in range(n_o)
        ],
        "trades": trades,
    }


def run_okx(symbol: str = "SOL-USDT-SWAP", interval: str = "4h", bars: int = 3000, **kw) -> dict:
    """OKX'ten mum çekip grid backtest çalıştırır (canlı venue ile aynı enstrüman)."""
    from app.data import okx_provider
    df = okx_provider.get_ohlcv(symbol, interval, bars=bars)
    if df.empty or len(df) < 30:
        raise ValueError(f"Yetersiz OKX verisi: {symbol}")
    return simulate(df, symbol=symbol, interval=interval, **kw)


def _d(ts, interval: str) -> str:
    return ts.strftime("%Y-%m-%d") if interval in ("1d", "1wk", "1mo") else ts.strftime("%Y-%m-%d %H:%M")
