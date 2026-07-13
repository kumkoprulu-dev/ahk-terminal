"""3. bacak kategori karşılaştırması: trend+momentum tabanına HANGİ grup en çok katkı verir?

Kullanıcı sorusu: 6 grup var (trend/momentum/volatilite/hacim/kuant/istatistik). Yapısal
aramada 3. bacağı sadece REJİM filtresi yapmıştık. Ya HACİM / VOLATİLİTE yönlü teyit olarak
eklenirse? (OOS şampiyonu Fisher+ForceIndex+Awesome'da ForceIndex=hacimdi ve rejimden iyiydi.)

Her (güçlü trend+momentum tabanı) × (3. bacak seçeneği) IS/OOS'ta skorlanır. 3. bacak:
  - hacim (yönlü AND): MFI, CMF, ForceIndex, Klinger, VWAP, EOM, VolumeOsc
  - volatilite/MR (yönlü AND): Bollinger, Keltner, ZScore
  - rejim (filtre kapısı): ADX/Chop/ER/Hurst
  - — (filtresiz taban) referans
OOS Sharpe'a göre sıralanır + 3. bacak KATEGORİSİNİN ortalama OOS katkısı özetlenir.
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

# OOS'ta güçlü çıkan trend+momentum tabanları (structured_search top)
BASES = [["ZLEMA", "AwesomeOsc"], ["ZLEMA", "TRIX"], ["SMA", "Fisher"],
         ["ZLEMA", "PPO"], ["DEMA", "TRIX"]]

# 3. bacak seçenekleri: (etiket, kategori, directional_name veya None, filter_gate veya None)
THIRD = [
    ("—",         "referans", None, None),
    ("MFI",       "hacim", "MFI", None),
    ("CMF",       "hacim", "CMF", None),
    ("ForceIndex", "hacim", "ForceIndex", None),
    ("Klinger",   "hacim", "Klinger", None),
    ("VWAP",      "hacim", "VWAP", None),
    ("EOM",       "hacim", "EOM", None),
    ("VolumeOsc", "hacim", "VolumeOsc", None),
    ("Bollinger", "volat", "Bollinger", None),
    ("Keltner",   "volat", "Keltner", None),
    ("ZScore",    "volat", "ZScore", None),
    ("ADX>20",    "rejim", None, "ADX(14) > 20"),
    ("Chop<45",   "rejim", None, "ChoppinessIndex(14) < 45"),
    ("ER>0.3",    "rejim", None, "EfficiencyRatio(10) > 0.3"),
    ("Hurst>0.5", "rejim", None, "HurstExponent(100) > 0.5"),
]


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


def eval_combo(base, cat, dname, gate, basket):
    names = base + ([dname] if dname else [])
    return cs.score_combo(names, basket, interval=INTERVAL, warmup=WARMUP, filt=gate)


def main():
    raw = load_raw()
    is_b, oos_b = split(raw)
    print(f"Sepet {len(raw)} sembol · {len(BASES)} taban × {len(THIRD)} 3.bacak "
          f"= {len(BASES)*len(THIRD)} kombo\n")
    rows = []
    for base in BASES:
        for label, cat, dname, gate in THIRD:
            r_oos = eval_combo(base, cat, dname, gate, oos_b)
            r_is = eval_combo(base, cat, dname, gate, is_b)
            rows.append(("+".join(base), label, cat, r_is["sharpe"], r_oos["sharpe"],
                         r_oos["ret"], r_oos["dd"], r_oos["trades"], r_oos["beat_bh"]))
    rows.sort(key=lambda x: x[4], reverse=True)
    rec = Recorder("thirdleg_search", "combo_structured",
                   label=f"3.bacak kategori ({INTERVAL}, sepet {len(raw)})",
                   params={"interval": INTERVAL, "basket": sorted(raw)})
    for i, r in enumerate(rows, 1):
        rec.add({"is_sharpe": r[3], "sharpe": r[4], "total_return": r[5], "max_drawdown": r[6],
                 "num_trades": r[7], "beat_bh": r[8], "group": r[2]},
                interval=INTERVAL, name=f"{r[0]} + {r[1]} ({r[2]})", rank=i)
    rec.save()
    print(f"  {'#':>3} {'taban':<16}{'3.bacak':<11}{'grup':<9}{'IS':>7}{'OOS':>7}"
          f"{'ret%':>8}{'dd%':>7}{'işl':>6}{'>BH':>6}")
    print("  " + "-" * 80)
    for i, r in enumerate(rows[:25], 1):
        print(f"  {i:>3} {r[0]:<16}{r[1]:<11}{r[2]:<9}{r[3]:>7}{r[4]:>7}{r[5]:>8}"
              f"{r[6]:>7}{r[7]:>6}{r[8]:>6}")
    print("\n  --- 3. bacak GRUBU ortalama OOS Sharpe (tüm tabanlar üzerinde) ---")
    for cat in ["referans", "hacim", "volat", "rejim"]:
        vals = [r[4] for r in rows if r[2] == cat]
        if vals:
            print(f"    {cat:<10} ort OOS = {sum(vals)/len(vals):>6.3f}  (n={len(vals)})")


if __name__ == "__main__":
    main()
