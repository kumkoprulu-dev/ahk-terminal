# AHK Terminal

İdeal / Matriks / TradingView karışımı bir finansal analiz terminali. BIST & küresel
piyasalar için tek panel: veri + 44 teknik/kuantitatif gösterge + tarama + backtest +
parametre optimizasyonu + walk-forward + kuantum-ilhamlı portföy + AI haber duyarlılığı,
**Panel (dashboard)** giriş ekranıyla.

## Özellikler (bu sürüm)
- **Veri:** Yahoo Finance (doğrudan, tarayıcı UA ile — rate-limit dirençli), yfinance yedek,
  Finnhub (arama + anlık quote). BIST (`.IS`), NASDAQ ve dünya borsaları.
- **44 gösterge** (registry tabanlı, kolay genişler):
  - Trend (12): SMA, EMA, WMA, HMA, DEMA, TEMA, SuperTrend, Ichimoku, PSAR, Donchian, Aroon, ADX
  - Momentum (11): RSI, Stochastic, StochRSI, MACD, CCI, ROC, Momentum, Williams %R, TSI, PPO, TRIX
  - Hacim (6): OBV, MFI, CMF, ADL, VWAP, VolumeOsc
  - Volatilite (5): ATR, Bollinger Bands, Keltner Channel, StdDev, HistVol
  - İstatistiksel (6): ZScore, Sharpe, Sortino, Calmar, Kurtosis, Skewness
  - Kuantitatif (4): KalmanFilter, HurstExponent, MeanReversionScore, FractalDim
- **Grafik:** TradingView Lightweight Charts (yerel, build adımı yok). Mum + hacim,
  overlay göstergeler (EMA/BB) ana grafikte, osilatörler (RSI/MACD) senkron alt-panelde.
- **Tarayıcı:** güvenli kural dili (DSL, `eval` yok). Örnek:
  `RSI(14) < 30 AND MACD > Signal`, `MACD Cross Up`, `Close < BollingerBands(20).Lower`.
- **Backtest + Strateji editörü:** DSL giriş/çıkış kurallı vektörel backtest. Stop-loss /
  take-profit, komisyon, long/short. Metrikler (Sharpe, Sortino, MaxDD, CAGR, Calmar,
  win-rate, profit factor), equity eğrisi ve işlem listesi; Al-Tut karşılaştırması.
- **Parametre optimizasyonu:** `{param}` şablonlu kurallar + aralıklar. Grid / Random /
  Bayesian (Optuna). Otomatik placeholder algılama, sonuç tablosu, en iyiyi Strateji'ye gönder.
- **Walk-Forward analizi:** ardışık eğitim/test pencereleri; eğitimde optimize, test
  penceresinde out-of-sample sınar (göstergeler warmup ile ısıtılır). Birleşik OOS equity,
  fold tablosu, IS-vs-OOS aşırı uyum uyarısı.
- **Portföy optimizasyonu:** Max Sharpe (Markowitz), Min Varyans, Risk Parity, Max Getiri,
  **Min CVaR (kuyruk riski, LP)**, **Black-Litterman (momentum görüşlü)**, Eşit Ağırlık +
  **Kuantum-İlhamlı (QUBO + Simulated Annealing)**. Etkin sınır grafiği, yöntem karşılaştırması,
  **Monte Carlo VaR/CVaR** stres testi, **füzyon tilt** (TechScore ile ağırlık eğme) ve
  **temel-skor ön-filtresi**. (Kuantum = klasik CPU'da kuantum-ilhamlı; gerçek donanım değil.)
- **Metinden formül (NL→DSL):** doğal Türkçe/İngilizce (diakritiksiz dahil) → DSL kuralı.
  Örn. "RSI 30 altında ve hacim ortalamanın üstünde" → `RSI(14) < 30 AND Volume > SMA(Volume, 20)`.
  Kalıp tabanlı (LLM gerektirmez), çıktı parser ile doğrulanır. Tarayıcı + Strateji'de 🪄 kutusu.
- **Alarmlar:** sembol + DSL/metin kuralı; kural son barda sağlanınca tetiklenir. Dashboard'da
  ekle/listele/sil, periyodik kontrol + tarayıcı bildirimi (Notification).
- **Canlı fiyat (WebSocket):** `/ws/prices` abone olunan sembollerin anlık fiyatını
  (~6 sn) iter; grafik başlığı canlı güncellenir, header'da "● CANLI" göstergesi. Tüm
  piyasalarda (BIST/ABD/kripto/emtia) çalışır. (Ücretsiz veri ~gecikmeli; gerçek tick için
  lisanslı/Finnhub WS gerekir.)
- **Hesaplar + kayıtlı öğeler:** kullanıcı kayıt/giriş (SQLite, pbkdf2 şifre, bearer token);
  Strateji ve Portföy'leri isimle **kaydet / yükle / sil**. Header'dan giriş, localStorage token.
- **Sembol grupları (tek merkez):** BIST 30 / BIST 50 / BIST 100 / NASDAQ / Emtia / Kripto
  — tarayıcıda, portföyde, sentiment'te ve aramada ortak kullanılır.
- **Mobil / responsive:** dar ekranda tüm yerleşimler tek kolona iner, sekmeler yatay
  kaydırılır, tablolar yatay kaydırmalı; yatay taşma yok (375px'de doğrulandı).
- **Temel analiz:** PE/PB/PS, ROE/ROA, marjlar, büyüme, borç/özsermaye, cari oran →
  değer/kârlılık/büyüme/sağlık kovaları ile **0-100 temel skor**. Kaynak: **BIST → İş Yatırım**
  (sanayi `XI_29` + banka `UFRS_K` mali tabloları, güncel fiyattan oran hesabı), ABD → Finnhub,
  diğer → yfinance. Sonuçlar diske önbelleklenir (`fundamentals.json`, 6 saat).
- **3'lü Füzyon:** Teknik skor + Haber skoru + Temel skor → ağırlıklı **birleşik sinyal**
  (GÜÇLÜ AL…GÜÇLÜ SAT) + özel kurallar (negatif haber + olumlu teknik = ⚠ uyarı; üç eksen
  uyumlu = 💪). Portföye **temel-skor ön-filtresi** olarak da bağlanır.
- **Füzyon backtest (TechScore):** teknik füzyon skoru `TechScore` adıyla bir göstergedir;
  Strateji/Optimize/Walk-Forward/Tarayıcı/grafikte kullanılır (örn. `TechScore > 62`).
  *Not: Haber (geçmiş arşiv yok) ve Temel (ücretsiz point-in-time veri yok) eksenleri
  look-ahead yanlılığı olmadan backtestlenemez; geçmiş test teknik ekseni kapsar.*
- **Haber duyarlılığı (AI/Sentiment):** Google News + Yahoo Finance'ten haber çekip skorlar.
  Varsayılan **TR+EN finans sözlüğü** (hızlı, bağımlılıksız); opsiyonel **FinBERT** derin
  model. Grup ısı haritası + sembol başına başlık-bazlı skor. (Q-BIST'ten uyarlandı.)

## Yayınlama (internetten erişim)
Render'a tek-tıkla dağıtım için **[DEPLOY.md](DEPLOY.md)** (Docker + ücretsiz PostgreSQL;
veri ve hesaplar kalıcı). Yerel için aşağıdaki kurulum yeterli.

## Kurulum
```powershell
cd backend
py -3.13 -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
# .env oluştur (örnek: .env.example) ve FINNHUB_API_KEY ekle (opsiyonel)
venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8077
```
Tarayıcıda: http://127.0.0.1:8077

## Testler
```powershell
cd backend
venv\Scripts\python.exe -m pytest -q
```

## API (özet)
| Uç | Açıklama |
|----|----------|
| `GET /health` | durum + gösterge sayısı |
| `GET /api/ohlcv?symbol=&interval=&range=` | mum verisi |
| `GET /api/symbols/search?q=` | sembol arama |
| `GET /api/indicators` | gösterge listesi + metadata |
| `POST /api/indicators/compute` | gösterge hesapla |
| `GET /api/universes` | tarama evrenleri (BIST, NASDAQ) |
| `POST /api/scan` | universe üzerinde kural tara |
| `POST /api/scan/validate` | kural doğrula |
| `POST /api/backtest` | strateji backtest (metrikler + equity + işlemler) |
| `POST /api/optimize` | parametre optimizasyonu (grid/random/bayes) |
| `POST /api/walkforward` | walk-forward out-of-sample analizi |
| `POST /api/portfolio/optimize` | portföy optimizasyonu (klasik + kuantum) + Monte Carlo |
| `GET /api/universes` | sembol grupları (BIST30/50/100, NASDAQ, Emtia, Kripto) |
| `GET /api/sentiment?symbol=` | sembol haber duyarlılığı + başlıklar |
| `POST /api/sentiment/group` | grup geneli duyarlılık ısı haritası |
| `GET /api/fundamentals?symbol=` | temel analiz metrikleri + 0-100 skor |
| `GET /api/fusion?symbol=` · `POST /api/fusion/group` | 3'lü füzyon sinyali |
| `GET /api/market/movers?group=` | dashboard piyasa nabzı |
| `POST /api/auth/register·login·logout` · `GET /api/auth/me` | hesap |
| `POST·GET·DELETE /api/saved` | kayıtlı strateji/portföy (auth) |
| `POST /api/formula` | metinden formül (NL→DSL) |
| `POST·GET·DELETE /api/alarms` · `GET /api/alarms/check` | alarmlar (auth) |
| `WS /ws/prices` | canlı fiyat akışı |

## Mimari notları
- `backend/app/storage/` — OHLCV deposu soyutlaması: `parquet` (varsayılan), `sqlite`
  (tek dosyalık DB) veya `postgres`/`timescale` (PostgreSQL/TimescaleDB, `DATABASE_URL` ile).
  Hepsi TimescaleDB-biçimli `ohlcv` zaman serisi tablosu kullanır. **PostgreSQL 17.2'ye karşı
  test edildi** (round-trip + zaman serisi tablosu + upsert); TimescaleDB'de `ohlcv` otomatik
  hypertable'a dönüşür.
- `backend/app/data/` — sağlayıcı soyutlaması; yeni kaynak = yeni `DataProvider`.
- `backend/app/indicators/registry.py` — `@indicator` ile kayıt. Yeni gösterge = bir fonksiyon.
- `backend/app/scanner/dsl.py` — güvenli tokenizer + recursive-descent parser + AST değerlendirici.
- Önbellek: Parquet (`backend/data/cache/`). İleride TimescaleDB ile değiştirilebilir.

## Yol haritası (sonraki fazlar)
~~Backtest~~ ✅ → ~~Optimizasyon~~ ✅ → ~~Walk-forward~~ ✅ → ~~Portföy (+kuantum)~~ ✅ →
~~Sentiment~~ ✅ → ~~Temel analiz + 3'lü füzyon~~ ✅ → ~~Füzyon backtest (TechScore)~~ ✅ →
~~CVaR / Black-Litterman / füzyon tilt~~ ✅ → ~~SQLite depo (Timescale-hazır)~~ ✅ →
~~BIST temel analizi (İş Yatırım, sanayi+banka)~~ ✅ → ~~Hesaplar + kayıtlı portföy/strateji~~ ✅ →
~~Canlı fiyat (WebSocket)~~ ✅ → ~~Metinden formül + alarmlar + dashboard canlı~~ ✅ →
~~Postgres/TimescaleDB backend (gerçek Postgres 17.2'de test edildi)~~ ✅ →
~~Mobil / responsive görünüm~~ ✅ →
**gerçek kuantum (QAOA/D-Wave)** → Finnhub WS (ABD gerçek tick) →
TimescaleDB hypertable + sürekli toplama → lisanslı veri.

## Notlar
- **Finnhub ücretsiz katmanı geçmiş mum (OHLCV) vermez** (yalnızca anlık quote). Geçmiş için
  Yahoo/yfinance birincildir. Lisanslı veri ileride eklenebilir.
- `.env` ve `backend/.env` **git'e girmez** (`.gitignore`). Paylaşılan API anahtarını
  canlıya çıkmadan yenileyin.
