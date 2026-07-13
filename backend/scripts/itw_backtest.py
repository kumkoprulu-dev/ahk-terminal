"""ITW = Ichimoku + TrendScore + Williams %R kombinasyonu (İdeal ITWAsil portu).

İdeal `ITWAsil.txt` mantığı platform DSL'ine taşındı ve ABLASYON yapıldı:
her bileşen tek başına (I, T, W), ikili (IT, IW, TW) ve üçlü (ITW) ayrı test edilir
→ "hangi kombinasyon en güçlü" (indikatör-kombinasyon projesinin amacı) doğrudan görülür.

İdeal ITWAsil parametreleri (birebir):
  Ichimoku   : tenkan=14, kijun=17, senkou_b=34  (shift=kijun=17)
  TrendScore : periyot=124, eşik a=62   (AL: TS>62 / SAT: TS<-62)
  WilliamsR  : periyot=50, AL eşiği -12 / SAT eşiği -83

Long-only backtest: entry = AL koşulu, exit = SAT koşulu. (İdeal'de stop-and-reverse.)
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
from app.backtest import engine  # noqa: E402
from app.data import service  # noqa: E402
from app.storage.results_store import Recorder  # noqa: E402

try:
    from app.data import okx_provider  # noqa: E402
except Exception:
    okx_provider = None

_REC = Recorder("itw_backtest", "ablation", label="ITW (Ichimoku+TrendScore+Williams) ablasyonu")

# --- İdeal ITWAsil bileşen koşulları (AL / SAT) ---
ICH = "Ichimoku(14,17,34)"
I_LONG = f"{ICH}.Tenkan > {ICH}.Kijun AND close > {ICH}.SpanB AND close > {ICH}.SpanA"
I_SHORT = f"{ICH}.Tenkan < {ICH}.Kijun AND close < {ICH}.SpanB AND close < {ICH}.SpanA"
# TrendScore İdeal DEFAULT değerleri: periyot 10, eşik ±5 (=periyot/2). (ITWAsil'de 124/62 elle-ayarlıydı.)
T_LONG, T_SHORT = "TrendScore(10) > 5", "TrendScore(10) < -5"
W_LONG, W_SHORT = "WilliamsR(50) > -12", "WilliamsR(50) < -83"


def _and(*parts):
    return " AND ".join(f"({p})" for p in parts)


# ablasyon: ad -> (giriş kuralı, çıkış kuralı)
STRATS = {
    "I  (Ichimoku)": (I_LONG, I_SHORT),
    "T  (TrendScore)": (T_LONG, T_SHORT),
    "W  (Williams)": (W_LONG, W_SHORT),
    "IT": (_and(I_LONG, T_LONG), _and(I_SHORT, T_SHORT)),
    "IW": (_and(I_LONG, W_LONG), _and(I_SHORT, W_SHORT)),
    "TW": (_and(T_LONG, W_LONG), _and(T_SHORT, W_SHORT)),
    "ITW (üçlü)": (_and(I_LONG, T_LONG, W_LONG), _and(I_SHORT, T_SHORT, W_SHORT)),
}

BIST = ["EREGL.IS", "KCHOL.IS", "SASA.IS", "TUPRS.IS", "SISE.IS", "FROTO.IS"]
CRYPTO = ["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP", "BNB-USDT-SWAP"]


def fetch(sym, market, interval):
    if market == "crypto" and okx_provider is not None:
        return okx_provider.get_ohlcv(sym, interval, bars=1000)
    return service.get_ohlcv(sym, interval, "5y" if interval == "1d" else "2y")


def run_market(name, symbols, market, interval="1d"):
    print(f"\n{'='*78}\n {name}  ({interval}, {len(symbols)} sembol) — İdeal ITWAsil ablasyonu\n{'='*78}")
    # her strateji için her sembolde getiri topla
    agg = {k: {"ret": [], "bh": [], "shp": [], "tr": []} for k in STRATS}
    for sym in symbols:
        try:
            df = fetch(sym, market, interval)
        except Exception as e:
            print(f"  {sym}: veri HATA {str(e)[:40]}"); continue
        if df is None or len(df) < 200:
            print(f"  {sym}: yetersiz veri ({0 if df is None else len(df)} bar)"); continue
        bh = round((df["close"].iloc[-1] / df["close"].iloc[130] - 1) * 100, 1)
        print(f"\n  {sym}  ({len(df)} bar, Al&Tut {bh:+.1f}%)")
        print(f"    {'strateji':<18}{'getiri%':>9}{'Sharpe':>8}{'MaxDD%':>8}{'işlem':>7}{'kâr%':>7}")
        for k, (e, x) in STRATS.items():
            try:
                r = engine.simulate(df, symbol=sym, entry_rule=e, exit_rule=x, interval=interval,
                                    fee_bps=10, direction="long", warmup=130, light=True)
                m = r["metrics"]
                agg[k]["ret"].append(m["total_return"]); agg[k]["bh"].append(bh)
                agg[k]["shp"].append(m["sharpe"]); agg[k]["tr"].append(m["num_trades"])
                print(f"    {k:<18}{m['total_return']:>9}{m['sharpe']:>8}"
                      f"{m['max_drawdown']:>8}{m['num_trades']:>7}{m.get('win_rate', 0):>7}")
            except Exception as ex:
                print(f"    {k:<18}  HATA: {str(ex)[:44]}")
    # özet: strateji ortalamaları
    print(f"\n  --- {name} ORTALAMA (semboller arası) ---")
    print(f"    {'strateji':<18}{'ort.get%':>9}{'ort.Shp':>9}{'ort.işlem':>10}{'>Al&Tut':>9}")
    for k in STRATS:
        d = agg[k]
        if not d["ret"]:
            continue
        beat = sum(1 for r, b in zip(d["ret"], d["bh"]) if r > b)
        beat_str = f"{beat}/{len(d['ret'])}"
        print(f"    {k:<18}{np.mean(d['ret']):>9.1f}{np.mean(d['shp']):>9.2f}"
              f"{np.mean(d['tr']):>10.1f}{beat_str:>9}")
        _REC.add({"total_return": round(float(np.mean(d["ret"])), 2),
                  "sharpe": round(float(np.mean(d["shp"])), 3),
                  "num_trades": round(float(np.mean(d["tr"])), 1),
                  "beat_buyhold": beat_str, "market": name},
                 interval=interval, name=f"{name} · {k.strip()}")


def main():
    market = sys.argv[1] if len(sys.argv) > 1 else "bist"
    if market in ("bist", "both"):
        run_market("BIST", BIST, "bist", "1d")
    if market in ("crypto", "both"):
        run_market("KRİPTO", CRYPTO, "crypto", "1d")
    _REC.save()


if __name__ == "__main__":
    main()
