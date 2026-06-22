from app.fundamentals.score import fundamental_score


GOOD = {"pe": 8, "pb": 1.2, "ps": 1.0, "roe": 30, "roa": 16, "net_margin": 22,
        "revenue_growth": 28, "earnings_growth": 30, "debt_to_equity": 0.25, "current_ratio": 2.6}
BAD = {"pe": 80, "pb": 12, "ps": 15, "roe": -5, "roa": -2, "net_margin": -3,
       "revenue_growth": -10, "earnings_growth": -20, "debt_to_equity": 3, "current_ratio": 0.6}


def test_good_company_high_score():
    r = fundamental_score(GOOD)
    assert r["score"] > 80 and r["label"] in ("çok güçlü", "güçlü")
    assert set(r["buckets"]) == {"Değer", "Kârlılık", "Büyüme", "Sağlık"}


def test_bad_company_low_score():
    r = fundamental_score(BAD)
    assert r["score"] < 35 and r["label"] in ("zayıf", "çok zayıf")


def test_missing_data_returns_none():
    r = fundamental_score({"pe": None})
    assert r["score"] is None and r["label"] == "veri yok"


def test_partial_data_scores_from_available():
    r = fundamental_score({"roe": 30, "net_margin": 22})  # yalnız kârlılık
    assert r["score"] is not None and "Kârlılık" in r["buckets"]
