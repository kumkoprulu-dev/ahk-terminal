# KatılımLens — Online Yayın (Deploy) Rehberi

Tek imaj (FastAPI + statik frontend). Sunucu `$PORT`'a bağlanır; ilk açılışta
örnek veriler otomatik çekilir. SQLite kalıcı disk gerektirmez (ücretsiz katman
için ideal) — veri ilk yüklemede yeniden üretilir.

## Seçenek A — Render (önerilen, ücretsiz, tek tık)

1. Repoyu GitHub'a push edin.
2. https://render.com → **New → Blueprint** → bu repo.
3. **Root Directory: `teknofest`** seçin (Blueprint `teknofest/render.yaml`'ı bulur).
4. Deploy → birkaç dakikada `https://katilimlens.onrender.com` yayında.

Healthcheck: `/api/health`. LLM omurgası varsayılan `mock` (anahtar gerekmez,
F1=1.00). Claude'a geçmek için Render panelinde:
`TF_LLM_PROVIDER=claude`, `ANTHROPIC_API_KEY=sk-...`.

## Seçenek B — Docker (herhangi bir bulut / VPS)

```bash
cd teknofest
docker build -t katilimlens .
docker run -p 8090:8090 katilimlens          # mock omurga
# Claude ile:
docker run -p 8090:8090 -e TF_LLM_PROVIDER=claude -e ANTHROPIC_API_KEY=sk-... katilimlens
```

## Seçenek C — Doğrudan (sunucu/VPS, Docker'sız)

```bash
pip install -r teknofest/requirements.txt
PORT=8090 uvicorn app.main:app --app-dir teknofest/backend --host 0.0.0.0 --port 8090
```

## Mobil

Arayüz responsive'dir: ≤640px'te karşılaştırma tablosu otomatik **kart
görünümüne** geçer, özet kartları 2 sütun olur, sohbet/eval panelleri tam
genişlik akar. Ayrı mobil uygulama gerekmez — telefon tarayıcısında çalışır
(PWA olarak ana ekrana eklenebilir).

## Doğrulama (deploy sonrası duman testi)

```bash
curl https://<host>/api/health
curl -X POST https://<host>/api/ingest/samples
curl https://<host>/api/eval        # F1=1.0, fp=0 beklenir
```
