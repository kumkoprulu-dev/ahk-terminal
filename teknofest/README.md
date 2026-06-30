# KatılımLens — TEKNOFEST 2026 / Senaryo 2

**Katılım Bankacılığı Finansal Metin Madenciliği, Bilgi Çıkarımı ve Akıllı Dashboard-Asistan Çözümü**

Katılım bankalarının web sitelerindeki kampanya ve ürün metinlerini otomatik
analiz eder; kâr payı oranı, vade, tutar, avantaj ve kampanya bilgilerini
**kaynak alıntısına bağlı** olarak çıkarır, yapılandırır, karşılaştırır ve bir
**dashboard + akıllı asistan** üzerinden sunar.

---

## Neden birinci? — 4 ayırt edici özellik

| # | Özellik | Yarışmaya katkısı |
|---|---------|-------------------|
| 1 | **Grounding / atıf** — her sayısal değer birebir kaynak cümleye bağlı; alıntısı metinde geçmeyen değer otomatik düşürülür | **Sıfır halüsinasyon** — eval'de FP=0 ile kanıtlı |
| 2 | **Domain doğruluğu** — "faiz" değil "kâr payı"; brüt/net ayrımı; faizsizlik dili | Katılım bankacılığı uzmanlığı, "milli" anlatı |
| 3 | **Agentic asistan** — niyet → araç çağrısı → **deterministik hesap** + LLM cilası | Sayılar koddan gelir, asla uydurulamaz |
| 4 | **Kendi eval harness'ımız** — gold-set'e karşı precision/recall/F1 | Raporda ölçülebilir başarı: **F1 = 1.00** |

## Hibrit LLM omurgası (provider soyutlaması)

Tek arayüz arkasında üç omurga — `TF_LLM_PROVIDER` ile seçilir:

- `mock` — LLM yok; kural+regex tabanlı çıkarım (çevrimdışı demo & CI, F1=1.00)
- `claude` — Anthropic Messages API (httpx ile doğrudan, SDK gerektirmez)
- `ollama` — Yerel/açık Türkçe model (llama3.1, Trendyol-LLM vb.)

Her durumda **grounding doğrulaması** uygulanır: LLM'in ürettiği kaynak alıntı
metinde gerçekten geçmiyorsa değer reddedilir.

## Canlı Kazıma (gerçek bankalar)

Sistem, 6 katılım bankasının gerçek ürün/kampanya sayfalarından **canlı**
veri çeker (`POST /api/ingest/live` veya dashboard'da "🌐 Canlı çek" butonu).
Kaynak URL'leri `ingest/live_sources.py` içinde doğrulanmış olarak tanımlıdır.

Doğrulanmış durum (httpx, server-render):

| Banka | Canlı | Not |
|-------|-------|-----|
| Kuveyt Türk | ✅ | Katılma + Dijital hesap; kâr payı %17,5 canlı çekildi |
| Vakıf Katılım | ✅ | Katılma hesabı; kâr payı %32,33 canlı çekildi |
| Albaraka Türk | ✅ | Katılma + kampanya sayfaları |
| Türkiye Finans | ✅ | ASP.NET (`<form>` korunur) |
| Ziraat Katılım | ✅ | Hesaplar sayfası |
| Emlak Katılım | ⚠️ | Saf JS-SPA → httpx içerik vermez; örnek-fallback (headless yol haritasında) |

**Oran-tablosu segmentasyonu (domain-doğru):** Katılım bankaları getiriyi çoğu
zaman sabit % oran değil, **kâr PAYLAŞIM oranı** (ör. "90-10" = %90 müşteri /
%10 banka) olarak yayınlar — faizsizlikte getiri garanti edilmez. Sistem HTML
oran/paylaşım tablolarını yapısal ayrıştırır (`extract/tables.py`), kademe×vade
ızgarasından paylaşım oranını ve asgari tutarı grounding'li çıkarır ve bu temiz
tabloyu LLM'e odaklı blok olarak verir. Örn. Kuveyt Türk canlı: paylaşım
"90-10 (Klasik)", asgari 250 TL — tablodan. Dashboard'da kâr payının altında
"📊 90-10" olarak gösterilir.

**Kural vs LLM:** Mock/kural omurgası TEMİZ metinde mükemmeldir
(gold F1=1,00) ve canlı sayfalarda kâr payı oranını doğru çeker. Ancak gerçek
sayfalar oranları çok-değerli tablolar/hesap araçları içinde sunar; bu tür
sayfalarda vade gibi alanlar için kural motoru çekimser kalır (yanlış tahmin
yerine boş — grounding ilkesi). Üretim kalitesinde canlı çıkarım için hibrit
omurga LLM'e geçirilir: `TF_LLM_PROVIDER=claude` (veya `ollama`). Bu, mimarinin
neden hibrit tasarlandığının somut gerekçesidir.

## Mimari

```
ingest/   → banka kaynakları + httpx/BS4 scraper + paketli örnek veri
extract/  → schema (grounded) · rules (TR regex) · prompts · extractor (LLM+kural+grounding)
compare/  → normalize · filtrele · sırala · en iyi oran · getiri hesabı
chat/     → tools (deterministik) · agent (niyet→araç→kaynaklı yanıt)
eval/     → gold set · harness (precision/recall/F1)
store.py  → SQLite (ürün JSON + ham kaynak metin / RAG)
api/      → FastAPI uçları    main.py → uygulama + statik frontend
```

## Çalıştırma

```bash
# bağımlılıklar mevcut venv'de: fastapi uvicorn httpx pydantic beautifulsoup4 lxml
uvicorn app.main:app --app-dir teknofest/backend --port 8090
# tarayıcı: http://localhost:8090
```

### On-Prem (kurum içi) garantisi — şartname 5.9 / 5.10

Sistem **varsayılan olarak tamamen kurum içi** çalışır: `TF_ONPREM=1` (varsayılan)
iken bulut sağlayıcıları (Groq/Gemini/Claude…) **mekanik olarak reddedilir** ve
yalnız yerel omurga kullanılır:
- **mock (kural motoru):** API anahtarı YOK, dış servis YOK, internet YOK — F1=1.00
- **ollama (opsiyonel):** yerel/açık-kaynak Türkçe model, yine kurum içi

`GET /api/health` bunu kanıtlar: `{"onprem": true, "harici_servis_kullaniliyor": false,
"veri_kurum_disina_cikmiyor": true}`. Dashboard'da **🔒 On-Prem** rozeti görünür.
Müşteri verisi kurum dışına çıkmaz; dış servise bağımlılık sıfırdır.

> Bulut sağlayıcılar yalnız geliştirme kolaylığı içindir ve **submission'da
> kullanılmaz**; açmak için bilinçli olarak `TF_ONPREM=0` verilmelidir.

### (Geliştirme) LLM omurgasını seçme

En kolay yol: `teknofest/backend/.env.example`'ı `.env` olarak kopyalayıp
ücretsiz bir anahtar girin. Sunucu açılışta otomatik okur.

| Servis | Anahtar (ücretsiz, kartsız) | .env |
|--------|------------------------------|------|
| **Groq** (önerilen) | https://console.groq.com/keys | `TF_LLM_PROVIDER=groq` + `TF_OPENAI_API_KEY=...` |
| **Google Gemini** | https://aistudio.google.com/apikey | `TF_LLM_PROVIDER=gemini` + `TF_OPENAI_API_KEY=...` |
| **OpenRouter** | https://openrouter.ai/keys | `TF_LLM_PROVIDER=openrouter` + `TF_OPENAI_API_KEY=...` |
| **Ollama** (yerel, anahtarsız) | https://ollama.com | `TF_LLM_PROVIDER=ollama` |
| **Claude** | Anthropic | `TF_LLM_PROVIDER=claude` + `ANTHROPIC_API_KEY=...` |

Hepsi OpenAI-uyumlu tek bir provider üzerinden konuşur (`app/llm/provider.py`).
Aktif provider'ı `GET /api/health` ile doğrulayın (`provider`, `provider_available`).

Ortam değişkeniyle de verilebilir:
```bash
TF_LLM_PROVIDER=groq TF_OPENAI_API_KEY=gsk_...  uvicorn app.main:app --app-dir teknofest/backend --port 8090
```

## Başlıca API uçları

| Uç | Açıklama |
|----|----------|
| `POST /api/ingest/samples` | Paketli örnek banka verilerini çıkar & kaydet |
| `POST /api/ingest/url` | Canlı banka URL'sinden çıkarım |
| `POST /api/ingest/text` | Serbest metinden çıkarım (hakem yapıştır-test) |
| `GET  /api/urunler` | Yapılandırılmış ürünler (düz) |
| `GET  /api/urunler/detay` | Grounding kanıtıyla tam kayıt |
| `GET  /api/karsilastir?urun_tipi=` | Karşılaştırma tablosu + en iyi/ortalama |
| `POST /api/chat` | Akıllı asistan (kaynaklı yanıt) |
| `GET  /api/eval` | Gold-set doğruluk (precision/recall/F1) |

## Test

```bash
python -m pytest teknofest/backend/tests -q   # 8 passed
```

## Yol haritası (yarışma süreci)

- Canlı kazıma: 6 katılım bankası için gerçek URL/sitemap + zamanlanmış tazeleme
- Açık Türkçe model ile yerel çıkarım kıyas raporu (claude vs ollama F1)
- Çıkarım için aktif öğrenme: düşük güvenli alanları insana sor
- Tablolu/PDF kampanya broşürlerinden çıkarım (multimodal)
