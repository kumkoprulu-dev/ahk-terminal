"""Uçtan uca pipeline testleri — çıkarım, grounding, karşılaştırma, eval, chat."""
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# İzole test DB'si + deterministik omurga.
# NOT: .env TF_LLM_PROVIDER=groq ayarlasa bile testler kural-tabanlı (mock)
# çalışmalı — bunu app importundan ÖNCE sabitliyoruz (dotenv mevcut env'i ezmez).
os.environ["TF_DB_PATH"] = str(Path(tempfile.gettempdir()) / "tf_test_katilim.db")
os.environ["TF_LLM_PROVIDER"] = "mock"

from app import compare, store  # noqa: E402
from app.chat import cevapla  # noqa: E402
from app.eval import degerlendir  # noqa: E402
from app.extract import extract_one, extract_sources  # noqa: E402
from app.ingest import get_sample_sources  # noqa: E402


@pytest.fixture(autouse=True)
def _db():
    store.init_db()
    store.clear()
    for s in get_sample_sources():
        store.save_kaynak(s.banka, s.url, s.sample_text)
    for u in extract_sources(get_sample_sources()).urunler:
        store.save_urun(u)
    yield
    store.clear()


def test_extraction_basics():
    src = get_sample_sources()[0]  # Kuveyt Türk
    u = extract_one(src.banka, src.sample_text, url=src.url)
    assert u.kar_payi_orani.value == 48.0
    assert u.vade_gun.value == 32
    assert u.para_birimi.value == "TRY"
    assert u.min_tutar.value == 1000.0


def test_grounding_present():
    """Her çıkarılan kâr payı değeri kaynak alıntı taşımalı."""
    for s in get_sample_sources():
        u = extract_one(s.banka, s.sample_text, url=s.url)
        if u.kar_payi_orani.value is not None:
            assert u.kar_payi_orani.source_quote, f"{s.banka}: alıntı yok"
            assert u.kar_payi_orani.source_quote in s.sample_text


def test_eval_no_hallucination():
    r = degerlendir("mock")
    assert r["fp"] == 0, "Halüsinasyon (FP) olmamalı"
    assert r["f1"] >= 0.95


def test_compare_best_rate():
    urunler = [type("U", (), {"to_flat": lambda self, p=p: p})() for p in []]
    from app.extract.schema import KatilimUrunu
    us = [KatilimUrunu.model_validate(p) for p in store.list_urunler()]
    best = compare.en_iyi_oran(us, urun_tipi="katilma_hesabi")
    assert best["banka"] == "Vakıf Katılım"
    assert best["kar_payi_orani"] == 50.0


def test_getiri_hesabi():
    h = compare.getiri_hesapla(100000, 50.0, 32)
    # 100000 * 0.50 * 32/365 ≈ 4383.56 brüt
    assert abs(h["brut_kar_payi"] - 4383.56) < 1.0
    assert h["net_kar_payi"] < h["brut_kar_payi"]


def test_chat_intent_en_iyi():
    r = cevapla("En yüksek kâr payı hangi bankada?", use_llm=False)
    assert "Vakıf" in r["cevap"]
    assert r["kaynaklar"], "Yanıt kaynak içermeli"


def test_chat_getiri():
    r = cevapla("100000 TL 32 gün ne kazandırır?", use_llm=False)
    assert r["arac"] == "getiri"
    assert r["veri"]["anapara"] == 100000


def test_chat_grounded_sources():
    r = cevapla("Dolar hesabı var mı?", use_llm=False)
    assert any("Türkiye Finans" in (k.get("banka") or "") for k in r["kaynaklar"])


def test_onprem_bulut_engellenir():
    """ON-PREM açıkken bulut sağlayıcı istense bile yerel omurgaya düşülür."""
    import importlib
    from app import config
    from app.llm import get_provider

    old = config.ONPREM
    config.ONPREM = True
    try:
        # Bulut isteği → Ollama yoksa mock'a düşmeli (asla claude/groq olmamalı)
        for cloud in ("groq", "claude", "gemini"):
            p = get_provider(cloud)
            assert p.name in ("mock", "ollama"), f"{cloud} on-prem'de sızdı: {p.name}"
    finally:
        config.ONPREM = old


def test_table_segmentation():
    """Kâr paylaşım oranı tablosundan yapısal çıkarım (87-13 vb.)."""
    from app.extract import tables as tbl
    from app.ingest.scraper import Table

    t = Table(
        caption="Kar Paylaşım Oranları (%)",
        headers=["Kademe", "Açılış Bakiyesi", "1 Aylık (30-31 Gün)", "6 Aylık (92-180 Gün)"],
        rows=[["Klasik", "250", "87-13", "90-10"], ["Altın", "100.000", "92-8", "95-5"]],
    )
    assert tbl.is_rate_table(t)
    res = tbl.extract_from_tables([t])
    assert res["paylasim_orani"].value.startswith("90-10")  # en uzun vade
    assert res["min_tutar"].value == 250.0
    assert "Paylaşım" in t.to_markdown() or "paylaşım" in t.to_markdown().lower()
