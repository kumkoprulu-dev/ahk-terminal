"""Yapısal kombo araması: 1 TREND × 1 MOMENTUM × 1 REJİM (planın FAZ 2 kanonik yapısı).

Giriş = trend_long AND momentum_long AND rejim_kapısı. Çıkış = trend/momentum exit'leri OR.
Her komboyu IS(%60)/OOS(%40) zamansal bölmede skorlar, OOS Sharpe'a göre sıralar
(IS ile seçim yanıltıyor — validate_combos'ta görüldü). "—" rejim = filtresiz referans.
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

# Kategori temsilcileri (tekli taramanın güçlüleri + çeşitlilik)
TREND = ["HMA", "ZLEMA", "DEMA", "SMA", "VWMA", "Kalman", "LSMA", "MOST"]
MOM = ["Fisher", "AwesomeOsc", "TRIX", "PPO", "RSI", "TSI", "CMO", "MACD"]
REGIME = {
    "—":         None,
    "ADX>20":    "ADX(14) > 20",
    "Chop<45":   "ChoppinessIndex(14) < 45",
    "ER>0.3":    "EfficiencyRatio(10) > 0.3",
    "Hurst>0.5": "HurstExponent(100) > 0.5",
}


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
    is_b, oos_b = split(raw)
    print(f"Sepet {len(raw)} sembol · {len(TREND)}×{len(MOM)}×{len(REGIME)} = "
          f"{len(TREND)*len(MOM)*len(REGIME)} yapısal kombo (trend×momentum×rejim)\n")
    rows = []
    for t in TREND:
        for m in MOM:
            for rlabel, gate in REGIME.items():
                r_oos = cs.score_combo([t, m], oos_b, interval=INTERVAL, warmup=WARMUP, filt=gate)
                r_is = cs.score_combo([t, m], is_b, interval=INTERVAL, warmup=WARMUP, filt=gate)
                rows.append((t, m, rlabel, r_is["sharpe"], r_oos["sharpe"], r_oos["ret"],
                             r_oos["dd"], r_oos["trades"], r_oos["prof_pct"], r_oos["beat_bh"]))
    rows.sort(key=lambda x: x[4], reverse=True)  # OOS Sharpe
    rec = Recorder("structured_search", "combo_structured",
                   label=f"trend×momentum×rejim ({INTERVAL}, sepet {len(raw)})",
                   params={"interval": INTERVAL, "basket": sorted(raw)})
    for i, r in enumerate(rows, 1):
        rec.add({"is_sharpe": r[3], "sharpe": r[4], "total_return": r[5], "max_drawdown": r[6],
                 "num_trades": r[7], "prof_pct": r[8], "beat_bh": r[9], "regime": r[2]},
                interval=INTERVAL, name=f"{r[0]}+{r[1]} · {r[2]}", rank=i)
    rec.save()
    print(f"  {'#':>3} {'trend':<8}{'momentum':<11}{'rejim':<10}{'IS':>7}{'OOS':>7}"
          f"{'ret%':>8}{'dd%':>7}{'işl':>6}{'kâr%':>6}{'>BH':>6}")
    print("  " + "-" * 82)
    for i, r in enumerate(rows[:30], 1):
        print(f"  {i:>3} {r[0]:<8}{r[1]:<11}{r[2]:<10}{r[3]:>7}{r[4]:>7}{r[5]:>8}"
              f"{r[6]:>7}{r[7]:>6}{r[8]:>6}{r[9]:>6}")
    # rejim kapısı ortalama katkısı
    print("\n  --- rejim kapısı OOS Sharpe ortalaması (tüm trend×momentum üzerinde) ---")
    for rlabel in REGIME:
        vals = [r[4] for r in rows if r[2] == rlabel]
        print(f"    {rlabel:<10} ort OOS Sharpe = {sum(vals)/len(vals):.3f}")


if __name__ == "__main__":
    main()
