from app.sentiment import lexicon, engine


def test_positive_headline():
    s = lexicon.score_headline("Aselsan rekor karla zirveye uçtu, güçlü yükseliş")
    assert s > 0.3 and lexicon.label_for(s) == "pozitif"


def test_negative_headline():
    s = lexicon.score_headline("Tesla stock plunges on fraud probe and layoffs")
    assert s < -0.3 and lexicon.label_for(s) == "negatif"


def test_neutral_headline():
    s = lexicon.score_headline("Piyasalar bugün yatay seyretti, beklenti sürüyor")
    assert lexicon.label_for(s) == "nötr"


def test_bilingual():
    assert lexicon.score_headline("shares surge to record high") > 0
    assert lexicon.score_headline("hisselerde sert düşüş ve zarar") < 0


def test_lexicon_backend_always_available():
    assert "lexicon" in engine.available_backends()


def test_score_titles_fallback():
    # finbert kurulu değilse sözlüğe düşmeli
    scores, used = engine._score_titles(["strong profit beat"], "finbert")
    assert used == "lexicon" and scores[0] > 0
