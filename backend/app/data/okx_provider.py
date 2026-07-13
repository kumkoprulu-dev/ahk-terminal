"""OKX geçmiş mum (candle) sağlayıcı — backtest için.

Public REST (anahtar gerekmez). `/api/v5/market/history-candles` sayfalanarak
istenen sayıda bar geriye gidilir. Canlı işlem yapılacak enstrümanın (ör.
SOL-USDT-SWAP) GERÇEK mumlarıyla backtest yapmak için — Yahoo'nun türev-olmayan
BTC-USD'si yerine borsanın kendi verisi.

OKX bar kodları: 1m 3m 5m 15m 30m 1H 2H 4H 6H 12H 1D 1W 1M (H/D büyük harf).
Dönüş satırı: [ts_ms, o, h, l, c, vol, volCcy, volCcyQuote, confirm] — en yeni başta.
"""
from __future__ import annotations

import os
import time

import pandas as pd
import requests

BASE = "https://www.okx.com"
_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".cache", "okx")

# platform aralık kodu -> OKX bar kodu
_BAR = {
    "1m": "1m", "3m": "3m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "1H", "2h": "2H", "4h": "4H", "6h": "6H", "12h": "12H",
    "1d": "1D", "1wk": "1W", "1mo": "1M",
}


def get_ohlcv(inst: str = "SOL-USDT-SWAP", interval: str = "4h",
              bars: int = 3000, session: requests.Session | None = None,
              use_cache: bool = True, cache_ttl_h: float = 6.0) -> pd.DataFrame:
    """`bars` adet mumu geriye doğru sayfalayarak çeker (disk önbellekli).

    Döner: UTC DatetimeIndex + [open, high, low, close, volume] (artan sıralı float).
    use_cache: taze parquet önbelleği (cache_ttl_h saatten yeni) varsa ağ yerine onu kullan.
    """
    cache_path = os.path.join(_CACHE_DIR, f"{inst}_{interval}_{bars}.parquet")
    if use_cache and os.path.exists(cache_path):
        age_h = (time.time() - os.path.getmtime(cache_path)) / 3600.0
        if age_h <= cache_ttl_h:
            try:
                return pd.read_parquet(cache_path)
            except Exception:
                pass

    bar = _BAR.get(interval.lower(), interval)
    s = session or requests.Session()
    rows: list[list] = []
    after = ""  # boş = en güncel; sonra en eski ts ile geriye
    seen: set[int] = set()

    while len(rows) < bars:
        params = {"instId": inst, "bar": bar, "limit": "100"}
        if after:
            params["after"] = after
        r = s.get(f"{BASE}/api/v5/market/history-candles", params=params, timeout=15)
        r.raise_for_status()
        data = r.json().get("data", [])
        if not data:
            break
        new = [d for d in data if int(d[0]) not in seen]
        if not new:
            break
        for d in new:
            seen.add(int(d[0]))
        rows.extend(new)
        after = str(min(int(d[0]) for d in data))  # bir sonraki sayfa: bu ts'den eski
        time.sleep(0.12)  # OKX oran limiti (20 istek/2sn) — nazik ol

    if not rows:
        return pd.DataFrame()

    rows.sort(key=lambda d: int(d[0]))
    df = pd.DataFrame(
        [[int(d[0]), float(d[1]), float(d[2]), float(d[3]), float(d[4]), float(d[5])] for d in rows],
        columns=["ts", "open", "high", "low", "close", "volume"],
    )
    df.index = pd.to_datetime(df["ts"], unit="ms", utc=True)
    df.index.name = "date"
    out = df[["open", "high", "low", "close", "volume"]]
    if use_cache:
        try:
            os.makedirs(_CACHE_DIR, exist_ok=True)
            out.to_parquet(cache_path)
        except Exception:
            pass
    return out


if __name__ == "__main__":
    d = get_ohlcv("SOL-USDT-SWAP", "4h", bars=500)
    print(f"{len(d)} bar  {d.index[0]} → {d.index[-1]}")
    print(d.tail())
