"""DaviddTech/NNFX yuva araması uç noktaları (dashboard aracı).

StrategyFactory'nin '500+ strateji' kalıbını (Baseline+Confirmation+Volume+Noise) panelden
üretip OOS test etmeyi sağlar. Ağır arama (varsayılan 1536 kombo) arka-plan thread'inde
koşar; istemci job_id ile poll eder. Sonuçlar results.sqlite'a yazılır (kind=combo_nnfx),
böylece /api/results uçlarından da görünür. Combo3 gibi kombolar CANLIYA bağlanmaz — bu
yalnızca araştırma/triage aracıdır.
"""
from __future__ import annotations

import threading
import time
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.backtest import nnfx_service as nnfx

router = APIRouter(prefix="/api/nnfx", tags=["nnfx"])

# Basit süreç-içi iş kaydı (harici kuyruk yok; tek süreçlik dashboard için yeterli).
_JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()
_MAX_JOBS = 20


@router.get("/template")
def template():
    """NNFX yuva reçetesi: slotlar, noise kapıları, örnek kural, kombo sayıları."""
    return nnfx.slot_template()


@router.get("/results")
def latest_results(limit: int = 30):
    """En son kayıtlı NNFX araması (results.sqlite, kind=combo_nnfx) — panelde göster."""
    from app.storage.results_store import get_results_store
    store = get_results_store()
    for run in store.recent_runs(limit=50):
        if run.get("kind") == "combo_nnfx":
            return {"run": run, "results": store.run_results(run["run_id"], limit=limit)}
    return {"run": None, "results": []}


class SearchRequest(BaseModel):
    interval: str = "1d"
    use_confirm2: bool = False   # 4. yuva (2. confirmation) — daha ağır (7680 kombo)
    top: int = 30


def _run_job(job_id: str, req: SearchRequest) -> None:
    try:
        out = nnfx.run_search(interval=req.interval, use_confirm2=req.use_confirm2, top=req.top)
        with _LOCK:
            _JOBS[job_id].update(status="done" if out.get("ok") else "error",
                                 finished=time.time(), result=out,
                                 error=None if out.get("ok") else out.get("error"))
    except Exception as e:  # noqa: BLE001 — thread hatası job'a yansısın
        with _LOCK:
            _JOBS[job_id].update(status="error", finished=time.time(), error=str(e)[:200])


@router.post("/search")
def start_search(req: SearchRequest):
    """NNFX aramasını arka-plan thread'inde başlatır, job_id döner (GET /search/{id} ile poll)."""
    if req.interval not in ("1d", "4h", "1h", "1wk"):
        raise HTTPException(400, "Geçersiz interval (1d/4h/1h/1wk).")
    job_id = uuid.uuid4().hex[:12]
    with _LOCK:
        # eski bitmiş job'ları buda
        if len(_JOBS) >= _MAX_JOBS:
            done = sorted((j for j in _JOBS.items() if j[1]["status"] != "running"),
                          key=lambda kv: kv[1].get("finished", 0))
            for k, _ in done[:len(_JOBS) - _MAX_JOBS + 1]:
                _JOBS.pop(k, None)
        _JOBS[job_id] = {"status": "running", "started": time.time(),
                         "params": req.model_dump(), "result": None, "error": None}
    threading.Thread(target=_run_job, args=(job_id, req), daemon=True).start()
    return {"job_id": job_id, "status": "running", "params": req.model_dump()}


@router.get("/search/{job_id}")
def search_status(job_id: str):
    """Bir aramanın durumu; bittiğinde OOS-sıralı ilk sonuçları içerir."""
    with _LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            raise HTTPException(404, "job_id bulunamadı (süreç yeniden başladıysa kayıp).")
        job = dict(job)
    elapsed = round((job.get("finished") or time.time()) - job["started"], 1)
    return {"job_id": job_id, "status": job["status"], "elapsed_s": elapsed,
            "params": job["params"], "error": job["error"], "result": job["result"]}
