"""Tarayıcı motoru: bir kuralı seçili universe'teki sembollere uygular."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from app.data import service
from app.data.universe import get_universe
from app.scanner.dsl import DSLError, evaluate, parse

# Sonuç satırında gösterilecek ek metrikler için hızlı hesaplar
from app.indicators import compute


def validate_rule(rule: str) -> None:
    """Kuralı parse eder; geçersizse DSLError fırlatır (taramadan önce kontrol)."""
    parse(rule)


def _scan_symbol(symbol: str, rule: str, interval: str, range_: str) -> dict | None:
    df = service.get_ohlcv(symbol, interval, range_)
    if df is None or len(df) < 30:
        return None
    try:
        signal = evaluate(df, rule)
    except DSLError:
        raise
    except Exception:
        return None
    if signal.empty:
        return None
    last = bool(signal.iloc[-1])
    if not last:
        return None
    close = float(df["close"].iloc[-1])
    prev = float(df["close"].iloc[-2]) if len(df) > 1 else close
    change = (close - prev) / prev * 100 if prev else 0.0
    try:
        rsi = float(compute("RSI", df)["RSI"].iloc[-1])
    except Exception:
        rsi = None
    return {
        "symbol": symbol,
        "price": round(close, 4),
        "change": round(change, 2),
        "rsi": round(rsi, 1) if rsi is not None and rsi == rsi else None,
        "volume": int(df["volume"].iloc[-1]) if df["volume"].iloc[-1] == df["volume"].iloc[-1] else 0,
    }


def scan(
    universe: str,
    rule: str,
    interval: str = "1d",
    range_: str = "1y",
    max_workers: int = 8,
) -> dict:
    """Universe içindeki sembolleri tarar, kuralı sağlayanları döndürür."""
    validate_rule(rule)  # erken hata
    symbols = [s.symbol for s in get_universe(universe)]
    if not symbols:
        return {"universe": universe, "rule": rule, "scanned": 0, "matches": []}

    matches: list[dict] = []
    errors = 0
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {
            ex.submit(_scan_symbol, sym, rule, interval, range_): sym
            for sym in symbols
        }
        for fut in as_completed(futures):
            try:
                row = fut.result()
            except DSLError:
                raise
            except Exception:
                errors += 1
                continue
            if row:
                matches.append(row)

    matches.sort(key=lambda r: r["change"], reverse=True)
    return {
        "universe": universe,
        "rule": rule,
        "scanned": len(symbols),
        "errors": errors,
        "match_count": len(matches),
        "matches": matches,
    }
