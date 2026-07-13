"""Kısa liste kombolarını zamansal IS/OOS bölmesiyle doğrula (seçim-overfit testi).

Her sembol verisi ikiye bölünür: IS (ilk %60) seçim/eğitim, OOS (son %40) görülmemiş.
Kombo IS'te seçildi (in-sample triage) → OOS'ta skoru KORUYOR mu? Çöküyorsa in-sample şans.
Parametre YOK (kombolar sabit); bu saf zamansal genelleme testi (FAZ 3 OOS kapısı).
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

# İn-sample taramadan çıkan kısa liste (tekli/ikili/üçlü şampiyonlar + düşük-DD adaylar)
SHORTLIST = [
    ["Fisher", "ForceIndex", "AwesomeOsc"],   # üçlü şampiyon
    ["Fisher", "SMA", "RSI"],
    ["HMA", "Fisher", "AwesomeOsc"],           # en düşük DD üçlü
    ["VWAP", "HMA", "ZLEMA"],
    ["VWAP", "HMA"],                            # ikili şampiyon
    ["Fisher", "ForceIndex"],                  # saf-yeni ikili
    ["HMA", "AwesomeOsc"],                     # düşük-DD ikili
    ["VWAP"],                                   # tekli şampiyon
]

WARMUP = 120


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
    """IS: baştan split'e kadar. OOS: split-WARMUP'tan sona (ısınma lideriyle)."""
    is_b, oos_b = {}, {}
    for sym, df in raw.items():
        split = int(len(df) * frac)
        is_b[sym] = df.iloc[:split]
        oos_b[sym] = df.iloc[max(0, split - WARMUP):]
    return is_b, oos_b


def main():
    raw = load_raw()
    print(f"Sepet: {len(raw)} sembol")
    is_b, oos_b = split_basket(raw)
    print(f"\n  {'kombo':<32}{'IS Shp':>8}{'OOS Shp':>9}{'ISret%':>8}{'OOSret%':>9}"
          f"{'OOSdd%':>8}{'OOSkâr%':>8}{'OOS>BH':>8}  verdict")
    print("  " + "-" * 96)
    rec = Recorder("validate_combos", "combo_validation",
                   label=f"kısa liste IS/OOS doğrulama (sepet {len(raw)})")
    for names in SHORTLIST:
        r_is = cs.score_combo(names, is_b, warmup=WARMUP)
        r_oos = cs.score_combo(names, oos_b, warmup=WARMUP)
        name = "+".join(names)
        # verdict: OOS Sharpe pozitif ve IS'in en az yarısı kadarsa "geçer"
        keep = r_oos["sharpe"] > 0.15 and r_oos["sharpe"] >= 0.5 * r_is["sharpe"]
        verdict = "GEÇER" if keep else ("zayıf" if r_oos["sharpe"] > 0 else "ÇÖKTÜ")
        print(f"  {name:<32}{r_is['sharpe']:>8}{r_oos['sharpe']:>9}{r_is['ret']:>8}"
              f"{r_oos['ret']:>9}{r_oos['dd']:>8}{r_oos['prof_pct']:>8}{r_oos['beat_bh']:>8}  {verdict}")
        rec.add({"is_sharpe": r_is["sharpe"], "sharpe": r_oos["sharpe"], "is_ret": r_is["ret"],
                 "total_return": r_oos["ret"], "max_drawdown": r_oos["dd"],
                 "prof_pct": r_oos["prof_pct"], "beat_bh": r_oos["beat_bh"], "verdict": verdict},
                name=name)
    rec.save()


if __name__ == "__main__":
    main()
