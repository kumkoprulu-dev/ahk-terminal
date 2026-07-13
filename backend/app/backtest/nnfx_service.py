"""DaviddTech/NNFX yuva araması — API + script ortak çekirdeği.

nnfx_search.py'ın basket yükleme + IS/OOS bölme + rank_nnfx mantığını tek yere toplar,
böylece `/api/nnfx` uçları ile komut satırı scripti AYNI kodu kullanır (parite). Ağır
arama (varsayılan 1536 kombo) route'ta arka-plan thread'inde koşturulur; burası saf
hesap + kalıcılaştırma (Recorder → results.sqlite).
"""
from __future__ import annotations

from app.backtest import combo_search as cs
from app.data import service
from app.storage.results_store import Recorder

try:
    from app.data import okx_provider
except Exception:  # pragma: no cover — kripto sağlayıcı opsiyonel
    okx_provider = None

DEFAULT_BIST = ["EREGL.IS", "KCHOL.IS", "SASA.IS", "TUPRS.IS", "SISE.IS", "FROTO.IS"]
DEFAULT_CRYPTO = ["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP", "BNB-USDT-SWAP"]
WARMUP = 120


def slot_template() -> dict:
    """UI'nin 'reçeteyi' gösterebilmesi için NNFX yuva tanımları + örnek kural."""
    example = next(cs.iter_nnfx(use_confirm2=True))
    entry, exit_ = cs.combo_rules(example)
    return {
        "slots": cs.NNFX_SLOTS,
        "noise": {k: (v or "—") for k, v in cs.NNFX_NOISE.items()},
        "n_combos_3slot": sum(1 for _ in cs.iter_nnfx(use_confirm2=False)) * len(cs.NNFX_NOISE),
        "n_combos_4slot": sum(1 for _ in cs.iter_nnfx(use_confirm2=True)) * len(cs.NNFX_NOISE),
        "example": {"names": example, "entry": entry, "exit": exit_},
        "note": ("DaviddTech/StrategyFactory '500+ strateji' = bu yuva kalıbının farklı "
                 "göstergelerle doldurulmuş hâli. Giriş = yuva long'ları AND (+noise kapısı); "
                 "çıkış = yuva exit'lerinin OR'u. Arama her komboyu IS/OOS böler, OOS Sharpe'a göre sıralar."),
    }


def load_basket(interval: str = "1d", bist: list[str] | None = None,
                crypto: list[str] | None = None) -> dict:
    """BIST (Yahoo) + kripto (OKX) OHLCV sepetini yükler (nnfx_search ile aynı)."""
    bist = bist or DEFAULT_BIST
    crypto = crypto or DEFAULT_CRYPTO
    bist_range = "5y" if interval in ("1d", "1wk") else "2y"
    crypto_bars = 1000 if interval == "1d" else 3000
    raw: dict = {}
    for s in bist:
        try:
            raw[s] = service.get_ohlcv(s, interval, bist_range)
        except Exception:
            pass
    if okx_provider is not None:
        for s in crypto:
            try:
                raw[s.replace("-USDT-SWAP", "")] = okx_provider.get_ohlcv(s, interval, bars=crypto_bars)
            except Exception:
                pass
    return {k: v for k, v in raw.items() if v is not None and len(v) > 2 * WARMUP + 80}


def _split(raw: dict, frac: float = 0.6):
    is_b, oos_b = {}, {}
    for sym, df in raw.items():
        sp = int(len(df) * frac)
        is_b[sym] = df.iloc[:sp]
        oos_b[sym] = df.iloc[max(0, sp - WARMUP):]
    return is_b, oos_b


def run_search(interval: str = "1d", use_confirm2: bool = False, top: int = 30,
               persist: bool = True) -> dict:
    """NNFX yuva araması: sepeti yükle → IS/OOS böl → OOS'ta skorla + IS'te ölç (overfit farkı).
    OOS Sharpe'a göre sıralı ilk `top` sonucu döner; persist ise results.sqlite'a yazar."""
    raw = load_basket(interval)
    if not raw:
        return {"ok": False, "error": "Sepet boş — veri yüklenemedi.", "results": []}
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
                       label=f"NNFX yuva araması ({interval}, sepet {len(raw)}, {slots})",
                       params={"interval": interval, "slots": slots, "basket": sorted(raw)})
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

    return {"ok": True, "run_id": run_id, "interval": interval, "slots": slots,
            "symbols": sorted(raw), "n_combos": len(oos), "noise_avg": noise_avg,
            "results": rows[:top]}
