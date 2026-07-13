"""OOS-dayanıklı şampiyon komboya rejim FİLTRESİ ekleyip IS/OOS'ta test et.

Baz kombo (Fisher+ForceIndex+AwesomeOsc) trend-takip; choppy'de whipsaw yiyor.
Rejim kapısı (yalnız trend/verimli rejimde işlem aç) OOS edge'i güçlendiriyor mu?
Her filtre girişe AND'lenir; IS(%60)/OOS(%40) zamansal bölme ile karşılaştırılır.
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

BASE = ["Fisher", "ForceIndex", "AwesomeOsc"]   # OOS-dayanıklı üçlü şampiyon

# test edilecek rejim kapıları (yalnız trend/verimli rejimde işlem)
GATES = {
    "filtresiz":     None,
    "ADX>25":        "ADX(14) > 25",
    "ADX>20":        "ADX(14) > 20",
    "Chop<38":       "ChoppinessIndex(14) < 38",
    "Chop<45":       "ChoppinessIndex(14) < 45",
    "ER>0.3":        "EfficiencyRatio(10) > 0.3",
    "ER>0.4":        "EfficiencyRatio(10) > 0.4",
    "Hurst>0.5":     "HurstExponent(100) > 0.5",
    "ADX>20+Chop<45": "ADX(14) > 20 AND ChoppinessIndex(14) < 45",
}


def load_raw(interval="1d"):
    raw = {}
    for s in BIST:
        try:
            raw[s] = service.get_ohlcv(s, interval, "5y")
        except Exception:
            pass
    if okx_provider is not None:
        for s in CRYPTO:
            try:
                raw[s.replace("-USDT-SWAP", "")] = okx_provider.get_ohlcv(s, interval, bars=1000)
            except Exception:
                pass
    return {k: v for k, v in raw.items() if v is not None and len(v) > 2 * WARMUP + 80}


def split_basket(raw, frac=0.6):
    is_b, oos_b = {}, {}
    for sym, df in raw.items():
        split = int(len(df) * frac)
        is_b[sym] = df.iloc[:split]
        oos_b[sym] = df.iloc[max(0, split - WARMUP):]
    return is_b, oos_b


def main():
    raw = load_raw()
    is_b, oos_b = split_basket(raw)
    print(f"Sepet: {len(raw)} sembol · Baz kombo: {'+'.join(BASE)}\n")
    print(f"  {'rejim kapısı':<18}{'IS Shp':>8}{'OOS Shp':>9}{'OOSret%':>9}{'OOSdd%':>8}"
          f"{'OOSişl':>8}{'OOSkâr%':>8}{'OOS>BH':>8}")
    print("  " + "-" * 84)
    rec = Recorder("filter_combos", "combo_validation",
                   label=f"{'+'.join(BASE)} + rejim filtresi (sepet {len(raw)})")
    for label, gate in GATES.items():
        r_is = cs.score_combo(BASE, is_b, warmup=WARMUP, filt=gate)
        r_oos = cs.score_combo(BASE, oos_b, warmup=WARMUP, filt=gate)
        print(f"  {label:<18}{r_is['sharpe']:>8}{r_oos['sharpe']:>9}{r_oos['ret']:>9}"
              f"{r_oos['dd']:>8}{r_oos['trades']:>8}{r_oos['prof_pct']:>8}{r_oos['beat_bh']:>8}")
        rec.add({"is_sharpe": r_is["sharpe"], "sharpe": r_oos["sharpe"], "total_return": r_oos["ret"],
                 "max_drawdown": r_oos["dd"], "num_trades": r_oos["trades"],
                 "prof_pct": r_oos["prof_pct"], "beat_bh": r_oos["beat_bh"], "gate": label},
                name=f"{'+'.join(BASE)} · {label}")
    rec.save()


if __name__ == "__main__":
    main()
