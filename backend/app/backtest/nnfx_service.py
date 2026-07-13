"""DaviddTech/NNFX yuva araması — API + script ortak çekirdeği.

nnfx_search.py'ın basket yükleme + IS/OOS bölme + rank_nnfx mantığını tek yere toplar,
böylece `/api/nnfx` uçları ile komut satırı scripti AYNI kodu kullanır (parite). Ağır
arama (varsayılan 1536 kombo) route'ta arka-plan thread'inde koşturulur; burası saf
hesap + kalıcılaştırma (Recorder → results.sqlite).
"""
from __future__ import annotations

from app.backtest import combo_search as cs
from app.data import service
from app.data.universe import get_universe
from app.storage.results_store import Recorder

try:
    from app.data import okx_provider
except Exception:  # pragma: no cover — kripto sağlayıcı opsiyonel
    okx_provider = None

# Karışık (BIST+kripto) varsayılan sepet — orijinal NNFX davranışı
DEFAULT_BIST = ["EREGL.IS", "KCHOL.IS", "SASA.IS", "TUPRS.IS", "SISE.IS", "FROTO.IS"]
DEFAULT_CRYPTO = ["BTC", "ETH", "SOL", "BNB"]
# Kripto evreni (Combo1/xsec'in doğrulandığı likit major, OKX perp)
CRYPTO_MAJOR = ["BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "AVAX", "LINK", "DOT",
                "LTC", "BCH", "ATOM", "NEAR", "TRX", "BNB"]
# UI'ın sunacağı evren seçenekleri (Edge Lab ile aynı + karışık)
UNIVERSES = ["karisik", "kripto", "bist30", "bist50", "bist100", "nasdaq", "emtia"]
WARMUP = 120


def slot_template() -> dict:
    """UI'nin 'reçeteyi' gösterebilmesi için NNFX yuva tanımları + örnek kural."""
    example = next(cs.iter_nnfx(use_confirm2=True))
    entry, exit_ = cs.combo_rules(example)
    return {
        "slots": cs.NNFX_SLOTS,
        "universes": UNIVERSES,
        "noise": {k: (v or "—") for k, v in cs.NNFX_NOISE.items()},
        "n_combos_3slot": sum(1 for _ in cs.iter_nnfx(use_confirm2=False)) * len(cs.NNFX_NOISE),
        "n_combos_4slot": sum(1 for _ in cs.iter_nnfx(use_confirm2=True)) * len(cs.NNFX_NOISE),
        "example": {"names": example, "entry": entry, "exit": exit_},
        "note": ("DaviddTech/StrategyFactory '500+ strateji' = bu yuva kalıbının farklı "
                 "göstergelerle doldurulmuş hâli. Giriş = yuva long'ları AND (+noise kapısı); "
                 "çıkış = yuva exit'lerinin OR'u. Arama her komboyu IS/OOS böler, OOS Sharpe'a göre sıralar."),
    }


def _load_crypto(bases: list[str], interval: str) -> dict:
    if okx_provider is None:
        return {}
    bars = 1000 if interval == "1d" else 3000
    out: dict = {}
    for b in bases:
        try:
            df = okx_provider.get_ohlcv(f"{b}-USDT-SWAP", interval, bars=bars)
            if df is not None:
                out[b] = df
        except Exception:
            pass
    return out


def _load_stock(symbols: list[str], interval: str) -> dict:
    rng = "5y" if interval in ("1d", "1wk") else "2y"
    out: dict = {}
    for s in symbols:
        try:
            df = service.get_ohlcv(s, interval, rng)
            if df is not None:
                out[s] = df[~df.index.duplicated(keep="last")].sort_index()
        except Exception:
            pass
    return out


def load_basket(interval: str = "1d", universe: str = "karisik", basket_size: int = 12) -> dict:
    """Seçilen evrenin OHLCV sepetini yükler. universe: karisik|kripto|bist30/50/100|nasdaq|emtia.
    basket_size: sepet üst sınırı (evrenin doğal sırasından ilk N — arama süresini kontrol eder;
    her kombo tüm sembollerde koşar, 100 sembol × 1536 kombo çok ağır olur)."""
    n = max(2, int(basket_size))
    if universe == "karisik":
        half = max(1, n // 2)
        raw = {**_load_stock(DEFAULT_BIST[:half], interval),
               **_load_crypto(DEFAULT_CRYPTO[:n - half], interval)}
    elif universe == "kripto":
        raw = _load_crypto(CRYPTO_MAJOR[:n], interval)
    else:
        syms = [s.symbol for s in get_universe(universe)][:n]
        raw = _load_stock(syms, interval)
    return {k: v for k, v in raw.items() if v is not None and len(v) > 2 * WARMUP + 80}


def _split(raw: dict, frac: float = 0.6):
    is_b, oos_b = {}, {}
    for sym, df in raw.items():
        sp = int(len(df) * frac)
        is_b[sym] = df.iloc[:sp]
        oos_b[sym] = df.iloc[max(0, sp - WARMUP):]
    return is_b, oos_b


def run_search(interval: str = "1d", use_confirm2: bool = False, top: int = 30,
               universe: str = "karisik", basket_size: int = 12,
               persist: bool = True) -> dict:
    """NNFX yuva araması: sepeti yükle → IS/OOS böl → OOS'ta skorla + IS'te ölç (overfit farkı).
    OOS Sharpe'a göre sıralı ilk `top` sonucu döner; persist ise results.sqlite'a yazar."""
    raw = load_basket(interval, universe=universe, basket_size=basket_size)
    if not raw:
        return {"ok": False, "error": f"Sepet boş — '{universe}' evreninden veri yüklenemedi.", "results": []}
    is_b, oos_b = _split(raw)
    slots = "baseline×confirm×volume" + ("×confirm2" if use_confirm2 else "")

    oos = cs.rank_nnfx(oos_b, interval=interval, use_confirm2=use_confirm2, warmup=WARMUP)
    # IS Sharpe yalnız DÖNEN ilk `top` kombo için hesaplanır (overfit farkını göstermek üzere);
    # 1536 kombonun tümü için IS ölçmek gereksiz — sadece gösterilenler lazım.
    is_lookup: dict[tuple, float] = {}
    for d in oos[:top]:
        gate = cs.NNFX_NOISE.get(d["noise"])
        s = cs.score_combo(d["names"], is_b, interval=interval, warmup=WARMUP, filt=gate)
        is_lookup[("+".join(d["names"]), d["noise"])] = s["sharpe"]

    rows = []
    for i, d in enumerate(oos, 1):
        key = ("+".join(d["names"]), d["noise"])
        rows.append({
            "rank": i, "name": "+".join(d["names"]), "noise": d["noise"],
            "is_sharpe": is_lookup.get(key), "oos_sharpe": d["sharpe"], "sharpe": d["sharpe"],
            "total_return": d["ret"], "max_drawdown": d["dd"], "num_trades": d["trades"],
            "prof_pct": d["prof_pct"], "beat_bh": d["beat_bh"], "score": d["score"],
        })

    run_id = None
    if persist:
        rec = Recorder("nnfx_service", "combo_nnfx",
                       label=f"NNFX yuva araması ({universe}, {interval}, sepet {len(raw)}, {slots})",
                       params={"interval": interval, "universe": universe, "slots": slots,
                               "basket": sorted(raw)})
        for r in rows:
            rec.add({k: v for k, v in r.items() if k != "rank"},
                    interval=interval, name=f"{r['name']} · {r['noise']}", rank=r["rank"])
        run_id = rec.save(quiet=True)

    # noise kapısı ortalama katkısı
    noise_avg = {}
    for nlabel in cs.NNFX_NOISE:
        vals = [d["sharpe"] for d in oos if d["noise"] == nlabel]
        if vals:
            noise_avg[nlabel] = round(sum(vals) / len(vals), 3)

    return {"ok": True, "run_id": run_id, "interval": interval, "universe": universe, "slots": slots,
            "symbols": sorted(raw), "n_combos": len(oos), "noise_avg": noise_avg,
            "results": rows[:top]}
