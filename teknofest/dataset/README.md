# KatılımLens Veri Seti

Katılım bankacılığı ürün/kampanya metinleri ve bunlardan çıkarılan
yapılandırılmış veri. Kaynak: **BDDK Liste/77** (https://www.bddk.org.tr/Kurulus/Liste/77)
— Türkiye'deki **10 katılım bankasının** tamamı.

## Dosyalar

| Dosya | İçerik |
|-------|--------|
| `01_ham_metinler.json` | Bankaların ürün/kampanya ham metinleri (banka, kaynak_url, metin) |
| `02_yapilandirilmis_cikarim.json` | Grounding'li yapılandırılmış çıkarım: kâr payı oranı, vade, tahsis ücreti, masrafsızlık, kampanya türü, hedef kitle, ödül, indirim vb. — her değer kaynak alıntısıyla |

## Kapsanan bankalar (10)
Kuveyt Türk · Albaraka Türk · Türkiye Finans · Ziraat Katılım · Vakıf Katılım ·
Emlak Katılım · Hayat Finans (dijital) · TOM Katılım (dijital) · Dünya Katılım ·
Adil Katılım (dijital)

## Toplama yöntemi
- Server-render siteler: `httpx` + BeautifulSoup (tablo/başlık/gürültü ayrıştırma)
- JS-SPA/dijital bankalar: Playwright headless render
- httpx/erişim mümkün olmayan sayfalarda demo için domaine sadık örnek metin

## Notlar
- Örnek metinlerdeki oranlar temsilîdir; amaç bilgi-çıkarım doğruluğunu göstermektir.
- Çıkarım tekrar üretilebilir: `python -m app.ingest.probe` (canlı) veya
  `POST /api/ingest/live` (uygulama içi).
- Lisans: Apache License 2.0 (bkz. `../LICENSE`).
