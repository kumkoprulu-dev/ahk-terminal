"""FastAPI uç noktaları — Senaryo 2 (Katılım Bankacılığı Bilgi Çıkarımı)."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from .. import compare, store
from ..chat import cevapla
from ..extract import extract_one, extract_sources
from ..extract.schema import KatilimUrunu
from ..ingest import fetch_clean, get_sample_sources
from ..llm import get_provider

router = APIRouter()


def _load() -> list[KatilimUrunu]:
    return [KatilimUrunu.model_validate(p) for p in store.list_urunler()]


@router.get("/health")
def health():
    prov = get_provider()
    return {"ok": True, "provider": prov.name, "provider_available": prov.available,
            "urun_sayisi": store.count()}


@router.post("/ingest/samples")
def ingest_samples():
    """Paketlenmiş örnek banka verilerinden çıkarım yap ve kaydet."""
    sources = get_sample_sources()
    res = extract_sources(sources)
    for s in sources:
        store.save_kaynak(s.banka, s.url, s.sample_text)
    for u in res.urunler:
        store.save_urun(u)
    return {"provider": res.provider, "eklenen": len(res.urunler),
            "warnings": res.warnings, "ozet": compare.ozet(res.urunler)}


@router.post("/ingest/live")
def ingest_live_route():
    """Gerçek katılım bankası sitelerinden CANLI kazıma + çıkarım + kayıt."""
    from ..ingest.live import ingest_live
    return ingest_live()


@router.get("/sources/probe")
def sources_probe():
    """Kayıtlı canlı kaynakların erişilebilirlik durumunu raporla."""
    from ..ingest.live_sources import get_live_sources
    from ..ingest.scraper import fetch_page
    out = []
    for s in get_live_sources():
        pg = fetch_page(s.url)
        out.append({"banka": s.banka, "urun": s.urun_adi, "url": s.url,
                    "status": pg.status, "len": len(pg.text),
                    "render_required": s.render_required,
                    "usable": pg.ok and len(pg.text) >= 300})
    return {"kaynaklar": out}


class IngestURL(BaseModel):
    banka: str
    url: str


@router.post("/ingest/url")
def ingest_url(body: IngestURL):
    """Canlı URL'den metin çek, çıkarım yap, kaydet."""
    text = fetch_clean(body.url)
    if not text:
        return {"ok": False, "hata": "Sayfa çekilemedi veya boş."}
    u = extract_one(body.banka, text, url=body.url)
    store.save_kaynak(body.banka, body.url, text)
    store.save_urun(u)
    return {"ok": True, "urun": u.to_flat()}


class IngestText(BaseModel):
    banka: str
    metin: str
    url: str | None = None


@router.post("/ingest/text")
def ingest_text(body: IngestText):
    """Serbest metinden çıkarım (hakem demosu / yapıştır-test)."""
    u = extract_one(body.banka, body.metin, url=body.url)
    store.save_kaynak(body.banka, body.url, body.metin)
    store.save_urun(u)
    return {"ok": True, "urun": u.model_dump(mode="json")}


@router.get("/urunler")
def urunler():
    return {"urunler": store.list_flat()}


@router.get("/urunler/detay")
def urunler_detay():
    return {"urunler": store.list_urunler()}


@router.get("/ozet")
def ozet():
    return compare.ozet(_load())


@router.get("/karsilastir")
def karsilastir(urun_tipi: str | None = None):
    return compare.karsilastir(_load(), urun_tipi=urun_tipi)


class ChatBody(BaseModel):
    soru: str
    use_llm: bool = True


@router.post("/chat")
def chat(body: ChatBody):
    return cevapla(body.soru, use_llm=body.use_llm)


@router.get("/eval")
def eval_run(provider: str | None = None):
    """Çıkarım doğruluğunu gold sete karşı ölç (precision/recall/F1)."""
    from ..eval import degerlendir
    return degerlendir(provider)


@router.post("/reset")
def reset():
    store.clear()
    return {"ok": True}
