# AHK Terminal — Render'a Yayınlama

İnternetten (telefon datasıyla bile) erişilebilen kalıcı bir adres için. Render ücretsiz
katmanı yeterli; veri ve hesaplar PostgreSQL'de kalıcı tutulur.

## 1) Kodu GitHub'a yükle
Render bir Git deposundan dağıtır. Bir kez:
```bash
cd C:\Users\CASPER\Desktop\FinansalPlatform
git init                # zaten varsa atla
git add .
git commit -m "AHK Terminal"
# GitHub'da boş bir repo aç (örn. ahk-terminal), sonra:
git remote add origin https://github.com/KULLANICI/ahk-terminal.git
git branch -M main
git push -u origin main
```
> `.env`, `*.sqlite`, önbellek ve `venv` **gitignore'lı** — gizli anahtar repoya gitmez.

## 2) Render'da Blueprint ile dağıt
1. https://render.com → ücretsiz hesap (GitHub ile giriş).
2. **New → Blueprint** → GitHub reposunu seç. Render `render.yaml`'ı okur ve otomatik
   oluşturur: **web servisi** (Docker) + **ücretsiz PostgreSQL** (`DATABASE_URL` bağlanır).
3. Web servisinde **Environment → FINNHUB_API_KEY** değerini gir (Finnhub anahtarın).
4. **Apply / Deploy.** İlk derleme ~3-5 dk.

## 3) Adresin hazır
`https://ahk-terminal.onrender.com` (isim sana göre değişebilir). Telefondan da açılır;
mobil görünüm otomatik.

## Önemli notlar (ücretsiz katman)
- **Uyku:** 15 dk hareketsizlikte servis uyur; sonraki ilk istek ~30-60 sn (soğuk başlangıç).
  Sürekli açık istersen ücretli plan (~7$/ay) veya basit bir "ping" servisi.
- **Veri & hesaplar kalıcı:** OHLCV önbelleği + kullanıcı/portföy/strateji/alarm PostgreSQL'de
  (`STORAGE_BACKEND=postgres`). Yeniden dağıtımda **kaybolmaz**.
- **Render free Postgres** belirli süre sonra (Render politikası) silinebilir — kalıcı üretim
  için ücretli DB veya harici Postgres/TimescaleDB önerilir.
- **Veri kaynağı IP'si:** Yahoo/İş Yatırım bazı sunucu IP'lerini sınırlayabilir. Sınırlanırsa
  lisanslı veri veya proxy gerekir.
- **Güvenlik:** Genel internete açıldığı için şifreler güçlü olmalı; anahtarı Render env'inde
  tut (repoda değil). HTTPS Render tarafından otomatik sağlanır.

## Alternatif: Docker ile her yerde
```bash
docker build -t ahk-terminal .
docker run -p 8077:8077 -e FINNHUB_API_KEY=xxx ahk-terminal
# Postgres için: -e STORAGE_BACKEND=postgres -e DATABASE_URL=postgresql://...
```
