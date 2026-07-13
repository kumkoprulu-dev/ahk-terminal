"""DaviddTech / NNFX yuva şablonu araması — StrategyFactory'nin "500 stratejisi"nin
dürüst versiyonunu KENDİ verimizle üretir ve OOS'ta hangisinin tuttuğunu bulur.

Şablon (yuva/slot):  Baseline · Confirmation · [2. Confirmation] · Volume · Noise kapısı
Giriş = tüm yuva long'ları AND (+ noise kapısı) · Çıkış = yuva exit'lerinin OR'u.
StrategyFactory'nin sattığı şey bu kalıp + kombinasyon + backtest disiplinidir; burada
aynı kalıbı üretip her komboyu IS(%60)/OOS(%40) zamansal bölmede skorlar, OOS Sharpe'a
göre sıralarız (IS ile seçim overfit'e götürür — validate_combos/structured_search'te
görüldü). Hayatta kalan az sayıda kombo AYRICA walk-forward + Optuna'ya sokulmalı.

Kullanım:
  python scripts/nnfx_search.py                # 1d, baseline×confirm×volume (3 yuva)
  python scripts/nnfx_search.py 4h             # 4h
  python scripts/nnfx_search.py 1d confirm2    # 4 yuva (2. confirmation açık — daha ağır)
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.backtest import combo_search as cs  # noqa: E402
from app.data import service  # noqa: E402
from app.storage.results_store import Recorder  # noqa: E402

try:
    from app.data import okx_provider  # noqa: E402
except Exception:
    okx_provider = None

BIST = ["EREGL.IS", "KCHOL.IS", "SASA.IS", "TUPRS.IS", "SISE.IS", "FROTO.IS"]
CRYPTO = ["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP", "BNB-USDT-SWAP"]
WARMUP = 120
INTERVAL = sys.argv[1] if len(sys.argv) > 1 else "1d"
USE_C2 = "confirm2" in sys.argv[2:]


def load_raw():
    raw = {}
    bist_range = "5y" if INTERVAL in ("1d", "1wk") else "2y"
    crypto_bars = 1000 if INTERVAL == "1d" else 3000
    for s in BIST:
        try:
            raw[s] = service.get_ohlcv(s, INTERVAL, bist_range)
        except Exception:
            pass
    if okx_provider is not None:
        for s in CRYPTO:
            try:
                raw[s.replace("-USDT-SWAP", "")] = okx_provider.get_ohlcv(s, INTERVAL, bars=crypto_bars)
            except Exception:
                pass
    return {k: v for k, v in raw.items() if v is not None and len(v) > 2 * WARMUP + 80}


def split(raw, frac=0.6):
    is_b, oos_b = {}, {}
    for sym, df in raw.items():
        sp = int(len(df) * frac)
        is_b[sym] = df.iloc[:sp]
        oos_b[sym] = df.iloc[max(0, sp - WARMUP):]
    return is_b, oos_b


def main():
    raw = load_raw()
    if not raw:
        print("Sepet boş — veri yüklenemedi."); return
    is_b, oos_b = split(raw)
    n_combos = sum(1 for _ in cs.iter_nnfx(use_confirm2=USE_C2)) * len(cs.NNFX_NOISE)
    slots = "baseline×confirm×volume" + ("×confirm2" if USE_C2 else "")
    print(f"Sepet {len(raw)} sembol · NNFX yuvaları [{slots}] × {len(cs.NNFX_NOISE)} noise "
          f"= {n_combos} strateji (IS%60/OOS%40)\n")

    # OOS'ta skorla (asıl seçim ölçütü), aynı komboyu IS'te de ölç (overfit farkı için).
    oos = cs.rank_nnfx(oos_b, interval=INTERVAL, use_confirm2=USE_C2, warmup=WARMUP)
    is_lookup = {}
    for names in cs.iter_nnfx(use_confirm2=USE_C2):
        for nlabel, gate in cs.NNFX_NOISE.items():
            d = cs.score_combo(names, is_b, interval=INTERVAL, warmup=WARMUP, filt=gate)
            is_lookup[("+".join(names), nlabel)] = d["sharpe"]

    rec = Recorder("nnfx_search", "combo_nnfx",
                   label=f"DaviddTech/NNFX yuva şablonu ({INTERVAL}, sepet {len(raw)}, {slots})",
                   params={"interval": INTERVAL, "slots": slots, "basket": sorted(raw)})
    for i, d in enumerate(oos, 1):
        key = ("+".join(d["names"]), d["noise"])
        rec.add({**d, "is_sharpe": is_lookup.get(key)},
                interval=INTERVAL, name=f"{'+'.join(d['names'])} · {d['noise']}", rank=i)
    rec.save()

    print(f"  {'#':>3}  {'strateji (yuvalar)':<44}{'noise':<9}{'IS':>6}{'OOS':>6}"
          f"{'ret%':>8}{'dd%':>7}{'işl':>6}{'kâr%':>6}{'>BH':>6}")
    print("  " + "-" * 100)
    for i, d in enumerate(oos[:30], 1):
        key = ("+".join(d["names"]), d["noise"])
        name = "+".join(d["names"])
        print(f"  {i:>3}  {name:<44}{d['noise']:<9}{is_lookup.get(key, 0):>6}{d['sharpe']:>6}"
              f"{d['ret']:>8}{d['dd']:>7}{d['trades']:>6}{d['prof_pct']:>6}{d['beat_bh']:>6}")

    # noise kapısının ortalama katkısı (tüm kombolar üzerinde)
    print("\n  --- noise kapısı OOS Sharpe ortalaması ---")
    for nlabel in cs.NNFX_NOISE:
        vals = [d["sharpe"] for d in oos if d["noise"] == nlabel]
        if vals:
            print(f"    {nlabel:<10} ort OOS Sharpe = {sum(vals)/len(vals):.3f}  (n={len(vals)})")


if __name__ == "__main__":
    main()
