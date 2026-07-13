"""Edge ekseni — sistematik strateji (Combo1) sinyalini füzyona 4. eksen olarak sokar.

Teknik skor genel bir gösterge harmanıyken, edge skoru DOĞRULANMIŞ Combo1 kombosunun
(SMA50 + Fisher + VWAP) o anki bull koşullarının sağlanma oranıdır (0-100). 3/3 = Combo1
LONG sinyali aktif. Böylece füzyon, keşfettiğimiz edge'i de birleşik skora katar.
"""
from __future__ import annotations

from app.scanner.dsl import evaluate

# Combo1 (edges.COMBO1_ENTRY) bull koşulları — ayrı ayrı ölçülür ki kısmi güç görünsün
_COMBO1 = [
    ("Close > SMA(50)", "SMA50 üstü (trend)"),
    ("FisherTransform(9).Fisher > FisherTransform(9).Trigger", "Fisher yukarı (momentum)"),
    ("Close > VWAP", "VWAP üstü (hacim)"),
]


def edge_score(df) -> dict:
    """Combo1 bull koşullarının son bardaki sağlanma oranı → 0-100 edge skoru."""
    if df is None or len(df) < 60:
        return {"score": None, "label": "veri yok", "active": False, "conditions": [], "met": 0}
    conds, met = [], 0
    for rule, name in _COMBO1:
        try:
            v = bool(evaluate(df, rule).fillna(False).iloc[-1])
        except Exception:
            v = False
        conds.append({"name": name, "met": v})
        met += 1 if v else 0
    n = len(_COMBO1)
    score = round(met / n * 100, 1)
    active = met == n
    label = "Combo1 LONG ✓" if active else (f"{met}/{n} koşul" if met else "sinyal yok")
    return {"score": score, "label": label, "active": active, "conditions": conds, "met": met}
