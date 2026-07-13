"""Kombinatoryal gösterge arama motoru (indikatör-kombinasyon projesi FAZ 2-4).

Amaç: farklı kategorilerden göstergeleri tekli → ikili → üçlü kombinleyip sepet
(BIST+kripto) üzerinde backtest ederek HANGİ KOMBİNASYONUN en güçlü olduğunu bulmak,
zayıfları elemek, umut verenleri (sonra) optimize etmek.

Yaklaşım:
  1) TEMPLATES: her göstergeye kanonik boğa girişi (long) + çıkışı (exit) DSL kuralı.
  2) Üreteç: tekli, ikili (giriş=AND, çıkış=OR), üçlü.
  3) Sepet skorlayıcı: her sembolde engine.simulate, semboller arası ortalama.
  4) Sıralama + eleme: robust skor (ort. Sharpe, işlem tabanı, kârlı%).

NOT: tekli/ikili/üçlü TARAMA in-sample (triage) — binlerce kombo için walk-forward
çok pahalı. Amaç kaba eleme; hayatta kalan az sayıda kombo AYRICA walk-forward OOS'a
sokulur + Optuna ile optimize edilir ("umut verenlerde optimize"). Bkz plan FAZ 3.
"""
from __future__ import annotations

import itertools

import numpy as np

from app.backtest import engine

# ---------------------------------------------------------------------------
# FAZ 1 — Kanonik sinyal şablonları (varsayılan parametrelerle).
# cat: kombinatoryal çeşitlilik için kategori (trend/momentum/vol/hacim/mr).
# long: boğa girişi DSL kuralı · exit: ayı/ters çıkış DSL kuralı.
# ---------------------------------------------------------------------------
TEMPLATES: dict[str, dict] = {
    # --- Trend / hareketli ortalama: fiyat MA üstünde ---
    "EMA":        {"cat": "trend", "long": "close > EMA(20)",  "exit": "close < EMA(20)"},
    "SMA":        {"cat": "trend", "long": "close > SMA(50)",  "exit": "close < SMA(50)"},
    "WMA":        {"cat": "trend", "long": "close > WMA(20)",  "exit": "close < WMA(20)"},
    "HMA":        {"cat": "trend", "long": "close > HMA(20)",  "exit": "close < HMA(20)"},
    "DEMA":       {"cat": "trend", "long": "close > DEMA(20)", "exit": "close < DEMA(20)"},
    "TEMA":       {"cat": "trend", "long": "close > TEMA(20)", "exit": "close < TEMA(20)"},
    "Kalman":     {"cat": "trend", "long": "close > KalmanFilter", "exit": "close < KalmanFilter"},
    # --- Trend / yön-flip & özel ---
    "SuperTrend": {"cat": "trend", "long": "SuperTrend(10,3).Direction > 0", "exit": "SuperTrend(10,3).Direction < 0"},
    "PSAR":       {"cat": "trend", "long": "close > PSAR", "exit": "close < PSAR"},
    "Ichimoku":   {"cat": "trend", "long": "Ichimoku(9,26,52).Tenkan > Ichimoku(9,26,52).Kijun AND close > Ichimoku(9,26,52).SpanB",
                   "exit": "Ichimoku(9,26,52).Tenkan < Ichimoku(9,26,52).Kijun AND close < Ichimoku(9,26,52).SpanB"},
    "Donchian":   {"cat": "trend", "long": "close > Donchian(20).Middle", "exit": "close < Donchian(20).Middle"},
    "Aroon":      {"cat": "trend", "long": "Aroon(25).AroonUp > Aroon(25).AroonDown", "exit": "Aroon(25).AroonUp < Aroon(25).AroonDown"},
    "TrendScore": {"cat": "trend", "long": "TrendScore(10) > 5", "exit": "TrendScore(10) < -5"},
    "TechScore":  {"cat": "trend", "long": "TechScore > 60", "exit": "TechScore < 40"},
    # --- Momentum: eşik / midline / cross ---
    "RSI":        {"cat": "mom", "long": "RSI(14) > 50", "exit": "RSI(14) < 50"},
    "Stochastic": {"cat": "mom", "long": "Stochastic.K > Stochastic.D", "exit": "Stochastic.K < Stochastic.D"},
    "StochRSI":   {"cat": "mom", "long": "StochRSI.K > StochRSI.D", "exit": "StochRSI.K < StochRSI.D"},
    "CCI":        {"cat": "mom", "long": "CCI(20) > 0", "exit": "CCI(20) < 0"},
    "ROC":        {"cat": "mom", "long": "ROC(12) > 0", "exit": "ROC(12) < 0"},
    "Momentum":   {"cat": "mom", "long": "Momentum(10) > 0", "exit": "Momentum(10) < 0"},
    "WilliamsR":  {"cat": "mom", "long": "WilliamsR(14) > -50", "exit": "WilliamsR(14) < -50"},
    "MACD":       {"cat": "mom", "long": "macd > signal", "exit": "macd < signal"},
    "PPO":        {"cat": "mom", "long": "PPO(12,26) > 0", "exit": "PPO(12,26) < 0"},
    "TRIX":       {"cat": "mom", "long": "TRIX(15) > 0", "exit": "TRIX(15) < 0"},
    "TSI":        {"cat": "mom", "long": "TSI(25,13) > 0", "exit": "TSI(25,13) < 0"},
    # --- Volatilite: ortalamaya dönüş (dip al) ---
    "Bollinger":  {"cat": "mr", "long": "close < BollingerBands(20,2).Lower", "exit": "close > BollingerBands(20,2).Middle"},
    "Keltner":    {"cat": "mr", "long": "close < KeltnerChannel(20,2).Lower", "exit": "close > KeltnerChannel(20,2).Middle"},
    "ZScore":     {"cat": "mr", "long": "ZScore(20) < -1", "exit": "ZScore(20) > 0"},
    # --- Hacim / para akışı ---
    "MFI":        {"cat": "vol", "long": "MFI(14) > 50", "exit": "MFI(14) < 50"},
    "CMF":        {"cat": "vol", "long": "CMF(20) > 0", "exit": "CMF(20) < 0"},
    "VWAP":       {"cat": "vol", "long": "close > VWAP", "exit": "close < VWAP"},
    "VolumeOsc":  {"cat": "vol", "long": "VolumeOsc(5,20) > 0", "exit": "VolumeOsc(5,20) < 0"},

    # ===================== FAZ 0 — yeni yönlü göstergeler =====================
    # --- Trend ---
    "MOST":       {"cat": "trend", "long": "MOST(9,2).Direction > 0", "exit": "MOST(9,2).Direction < 0"},
    "VWMA":       {"cat": "trend", "long": "close > VWMA(20)", "exit": "close < VWMA(20)"},
    "KAMA":       {"cat": "trend", "long": "close > KAMA(10)", "exit": "close < KAMA(10)"},
    "ZLEMA":      {"cat": "trend", "long": "close > ZLEMA(20)", "exit": "close < ZLEMA(20)"},
    "Vortex":     {"cat": "trend", "long": "Vortex(14).VIPlus > Vortex(14).VIMinus", "exit": "Vortex(14).VIPlus < Vortex(14).VIMinus"},
    "LSMA":       {"cat": "trend", "long": "close > LSMA(25)", "exit": "close < LSMA(25)"},
    "Alligator":  {"cat": "trend", "long": "Alligator(13,8,5).Lips > Alligator(13,8,5).Teeth", "exit": "Alligator(13,8,5).Lips < Alligator(13,8,5).Teeth"},
    # --- Momentum ---
    "AwesomeOsc": {"cat": "mom", "long": "AwesomeOsc(5,34) > 0", "exit": "AwesomeOsc(5,34) < 0"},
    "AccelOsc":   {"cat": "mom", "long": "AcceleratorOsc > 0", "exit": "AcceleratorOsc < 0"},
    "UltimateOsc":{"cat": "mom", "long": "UltimateOsc(7,14,28) > 50", "exit": "UltimateOsc(7,14,28) < 50"},
    "CMO":        {"cat": "mom", "long": "CMO(14) > 0", "exit": "CMO(14) < 0"},
    "DPO":        {"cat": "mom", "long": "DPO(20) > 0", "exit": "DPO(20) < 0"},
    "KST":        {"cat": "mom", "long": "KST(10,15,20,30).KST > KST(10,15,20,30).Signal", "exit": "KST(10,15,20,30).KST < KST(10,15,20,30).Signal"},
    "RVI":        {"cat": "mom", "long": "RVI(10).RVI > RVI(10).Signal", "exit": "RVI(10).RVI < RVI(10).Signal"},
    "Fisher":     {"cat": "mom", "long": "FisherTransform(9).Fisher > FisherTransform(9).Trigger", "exit": "FisherTransform(9).Fisher < FisherTransform(9).Trigger"},
    "Coppock":    {"cat": "mom", "long": "CoppockCurve > 0", "exit": "CoppockCurve < 0"},
    "BOP":        {"cat": "mom", "long": "BOP(14) > 0", "exit": "BOP(14) < 0"},
    # --- Hacim ---
    "ForceIndex": {"cat": "vol", "long": "ForceIndex(13) > 0", "exit": "ForceIndex(13) < 0"},
    "EOM":        {"cat": "vol", "long": "EaseOfMovement(14) > 0", "exit": "EaseOfMovement(14) < 0"},
    "Klinger":    {"cat": "vol", "long": "KlingerOsc(34,55,13).KVO > KlingerOsc(34,55,13).Signal", "exit": "KlingerOsc(34,55,13).KVO < KlingerOsc(34,55,13).Signal"},
}

# Rejim/uygunluk FİLTRELERİ (yön vermez — üçlü kombonun 3. slotunda AND-kapısı olarak kullanılır).
FILTERS: dict[str, dict] = {
    "ADX>25":      {"cat": "filter", "gate": "ADX(14) > 25"},
    "Chop<38":     {"cat": "filter", "gate": "ChoppinessIndex(14) < 38"},   # trend rejimi
    "ER>0.3":      {"cat": "filter", "gate": "EfficiencyRatio(10) > 0.3"},  # verimli/trend
    "Hurst>0.5":   {"cat": "filter", "gate": "HurstExponent(100) > 0.5"},   # kalıcı trend
}


def _wrap(rule: str) -> str:
    return f"({rule})"


def combo_rules(names: list[str]) -> tuple[str, str]:
    """Kombo giriş/çıkış kuralı üretir: giriş = long'ların AND'i, çıkış = exit'lerin OR'u."""
    longs = [_wrap(TEMPLATES[n]["long"]) for n in names]
    exits = [_wrap(TEMPLATES[n]["exit"]) for n in names]
    entry = " AND ".join(longs)
    ex = " OR ".join(exits)
    return entry, ex


# ---------------------------------------------------------------------------
# Sepet skorlayıcı
# ---------------------------------------------------------------------------
def score_combo(names: list[str], basket: dict[str, "pd.DataFrame"], interval: str = "1d",
                fee_bps: float = 10.0, warmup: int = 120, min_trades: float = 2.0,
                filt: str | None = None) -> dict:
    """Bir komboyu sepetteki her sembolde çalıştırır, semboller arası özet döner.
    filt: opsiyonel rejim kapısı (DSL) — girişe AND'lenir (yalnız uygun rejimde işlem)."""
    entry, ex = combo_rules(names)
    if filt:
        entry = f"{entry} AND ({filt})"
    rets, shps, trs, dds, bhs = [], [], [], [], []
    for sym, df in basket.items():
        if df is None or len(df) < warmup + 40:
            continue
        try:
            r = engine.simulate(df, symbol=sym, entry_rule=entry, exit_rule=ex, interval=interval,
                                fee_bps=fee_bps, direction="long", warmup=warmup, light=True)
            m = r["metrics"]
            bh = (df["close"].iloc[-1] / df["close"].iloc[warmup] - 1) * 100
            rets.append(m["total_return"]); shps.append(m["sharpe"]); trs.append(m["num_trades"])
            dds.append(m["max_drawdown"]); bhs.append(bh)
        except Exception:
            continue
    if not rets:
        return {"names": names, "n": 0, "sharpe": -9, "ret": 0, "trades": 0, "dd": 0,
                "prof_pct": 0, "beat_bh": 0, "score": -9}
    sharpe = float(np.mean(shps)); ret = float(np.mean(rets)); trades = float(np.mean(trs))
    prof = sum(1 for x in rets if x > 0) / len(rets) * 100
    beat = sum(1 for r, b in zip(rets, bhs) if r > b) / len(rets) * 100
    # Robust skor: ort. Sharpe; çok az işlem yapan (fluke) cezalandırılır.
    penalty = 1.0 if trades >= min_trades else trades / min_trades
    score = sharpe * penalty
    return {"names": names, "n": len(rets), "sharpe": round(sharpe, 3), "ret": round(ret, 1),
            "trades": round(trades, 1), "dd": round(float(np.mean(dds)), 1),
            "prof_pct": round(prof), "beat_bh": round(beat), "score": round(score, 3)}


def rank_singles(basket, interval="1d", **kw) -> list[dict]:
    res = [score_combo([n], basket, interval, **kw) for n in TEMPLATES]
    return sorted(res, key=lambda d: d["score"], reverse=True)


def rank_pairs(names: list[str], basket, interval="1d", cross_cat_only=True, **kw) -> list[dict]:
    """İkili kombinasyonlar. cross_cat_only: yalnız farklı kategoriden çiftler (trend×momentum vb.)."""
    res = []
    for a, b in itertools.combinations(names, 2):
        if cross_cat_only and TEMPLATES[a]["cat"] == TEMPLATES[b]["cat"]:
            continue
        res.append(score_combo([a, b], basket, interval, **kw))
    return sorted(res, key=lambda d: d["score"], reverse=True)


def rank_triples(names: list[str], basket, interval="1d", distinct_cat=True, **kw) -> list[dict]:
    """Üçlü kombinasyonlar. distinct_cat: en az 2 farklı kategori (hepsi aynı olmasın)."""
    res = []
    for combo in itertools.combinations(names, 3):
        if distinct_cat and len({TEMPLATES[n]["cat"] for n in combo}) < 2:
            continue
        res.append(score_combo(list(combo), basket, interval, **kw))
    return sorted(res, key=lambda d: d["score"], reverse=True)


# ---------------------------------------------------------------------------
# DaviddTech / NNFX yuva şablonu — "Baseline + Confirmation(+2) + Volume + Noise".
#
# StrategyFactory'nin "500+ stratejisi" tek tek icat edilmiş algoritmalar DEĞİL; hepsi
# aynı yuva (slot) kalıbının farklı göstergelerle doldurulmuş hâli (NNFX metodolojisi):
#   Baseline (trend yönü) · Confirmation (momentum onayı) · [2. Confirmation] ·
#   Volume/para-akışı filtresi · Noise/rejim kapısı (yatay piyasada durdur).
# Giriş = tüm yuva long'ları AND + noise kapısı; çıkış = yuva exit'lerinin OR'u.
# Bu bizim score_combo(names, filt=noise) makinemize BİREBİR oturur — yeni DSL gerekmez;
# tek eklenen, yuva-kısıtlı üreteç. Amaç: bu 500 stratejinin dürüst versiyonunu KENDİ
# verimizle + walk-forward/OOS doğrulamamızla üretip hangisi gerçekten tutuyor görmek.
# Yuva havuzları TEMPLATES/FILTERS adlarına referanstır (tekli taramanın güçlüleri).
# ---------------------------------------------------------------------------
NNFX_SLOTS: dict[str, list[str]] = {
    "baseline": ["EMA", "HMA", "ZLEMA", "DEMA", "VWMA", "KAMA", "Kalman", "LSMA"],   # trend: fiyat vs MA
    "confirm":  ["MACD", "Fisher", "AwesomeOsc", "TSI", "PPO", "RSI", "CMO", "TRIX"],  # momentum onayı 1
    "confirm2": ["Vortex", "Aroon", "SuperTrend", "MOST", "Stochastic"],             # yön onayı 2 (cross)
    "volume":   ["MFI", "CMF", "VWAP", "ForceIndex", "EOM", "Klinger"],              # hacim/para akışı
}
# Noise/rejim kapıları (FILTERS ile aynı fikir) — girişe AND'lenir, yön VERMEZ.
NNFX_NOISE: dict[str, str | None] = {
    "—":         None,                              # filtresiz referans
    "ADX>25":    "ADX(14) > 25",                    # klasik NNFX gürültü filtresi
    "Chop<38":   "ChoppinessIndex(14) < 38",        # trend rejimi
    "ER>0.3":    "EfficiencyRatio(10) > 0.3",       # verimli hareket
}


def iter_nnfx(slots: dict[str, list[str]] = NNFX_SLOTS, use_confirm2: bool = True):
    """DaviddTech yuva şablonuna göre kombo adlarını üretir (baseline, confirm[, confirm2], volume).
    Aynı gösterge iki yuvada tekrarlanırsa (örn. havuzlar kesişirse) o kombo atlanır."""
    keys = ["baseline", "confirm"] + (["confirm2"] if use_confirm2 else []) + ["volume"]
    pools = [slots[k] for k in keys]
    for combo in itertools.product(*pools):
        if len(set(combo)) == len(combo):
            yield list(combo)


def rank_nnfx(basket, interval="1d", use_confirm2: bool = True,
              noise: dict[str, str | None] = NNFX_NOISE, **kw) -> list[dict]:
    """Tüm NNFX yuva kombolarını her noise kapısıyla skorlar, skora göre sıralı döner.
    Her sonuç sözlüğüne 'noise' etiketi eklenir. **kw → score_combo (warmup, fee_bps...)."""
    res = []
    for names in iter_nnfx(slots=NNFX_SLOTS, use_confirm2=use_confirm2):
        for nlabel, gate in noise.items():
            d = score_combo(names, basket, interval, filt=gate, **kw)
            d["noise"] = nlabel
            res.append(d)
    return sorted(res, key=lambda d: d["score"], reverse=True)
