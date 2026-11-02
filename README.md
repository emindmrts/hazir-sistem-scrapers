# Hazır Sistem Scraper'ları

![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)

Türkiye'deki hazır bilgisayar sistemlerini satan sitelerden ürün bilgilerini ve fiyatlarını otomatik olarak çeken bir Python projesi yaptım.

Vatan, Sinerji, GameGaraj, GamingGen gibi toplam 9 farklı siteyi destekliyor. Tek tek sitelere girip bilgisayar fiyatlarına bakmak yerine, hepsinin verisini tek yerden çekebiliyorsun.

---

## Desteklenen siteler

- Vatan Bilgisayar
- Sinerji
- GameGaraj
- GamingGen
- İnceHesap
- İtopya
- PCKolik
- Tebilon
- EnUcuzSistem (API)

---

## Kurulum

```bash
pip install -r requirements.txt
```

Playwright kullanan scraper'lar için Chromium da gerekiyor:

```bash
playwright install chromium
```

---

## Kullanım

Hepsini çalıştır (varsayılan olarak EnUcuzSistem API'sini kullanır, en hızlı yol):

```bash
python run_scrapers.py
```

Belirli siteleri çalıştır:

```bash
python run_scrapers.py vatan pckolik sinerji
```

Dosyaya kaydetmeden test et:

```bash
python run_scrapers.py --no-save
```

Tek bir scraper'ı direkt çalıştır:

```bash
python -m scrapers.vatan
```

Çıktı `output/products.json` dosyasına kaydedilir.

---

## Ne yapabilirsin?

Verinin kendisi JSON, specs parse edilmiş, store ayrı bir alan — yani direkt kullanıma hazır geliyor. Birkaç farklı kullanım:

**En ucuz sistemi bul**
Aynı CPU+GPU kombinasyonu 9 sitede farklı fiyatta satılıyor. `RTX 4060 + Ryzen 5 7500F` geçen tüm ürünleri filtrele, fiyata göre sırala. 3-5 bin TL fark görmek sürpriz olmaz.

**Fiyat alarmı kur**
Scraper'ı her gece çalıştır, fiyatları SQLite'a at. Takip ettiğin sistem belirli bir fiyatın altına düşünce Telegram/e-posta bildirimi gönder. Temel bir Python scripti ile çözülür.

**"Bütçeme göre en iyi GPU ne?" sorusunu otomatik yanıtla**
Specs alanları zaten parse edilmiş geliyor. 40 bin TL altındaki tüm sistemleri çek, GPU'ya göre grupla, her gruptan en ucuzunu al. Basit bir pandas one-liner.

**Piyasa analizi**
Hangi GPU modeli en çok hazır sistemde yer alıyor? RTX 4060 mı, RX 7600 mı? Ortalama fiyat son 30 günde ne kadar arttı? Birkaç satır kod ile grafik çıkarabilirsin.

**Stok takibi**
Bazen bir sistem sabah var, öğleden sonra yok. Scraper'ı saatlik çalıştır, bir ürün listeden düşünce kaydet. Hangi konfigürasyonlar hızlı tükeniyor görmek ilginç olabilir.

**Telegram/Discord bot**
Günlük en iyi 5 fiyat/performans sistemini otomatik paylaşan bir bot. Topluluklar için kullanışlı.

---

## Çekilen veri alanları

Her ürün için şu veriler geliyor:

| Alan | Tip | Açıklama |
|------|-----|----------|
| `name` | string | Ürün adı |
| `price` | float | Güncel fiyat (TL) |
| `image` | string | Ürün görseli URL'si |
| `url` | string | Ürün sayfası linki |
| `store` | string | Mağaza adı (vatan, sinerji, vs.) |
| `specs.CPU` | string | İşlemci modeli |
| `specs.GPU` | string | Ekran kartı |
| `specs.RAM` | string | Bellek kapasitesi + tipi |
| `specs.Storage` | string | Depolama (SSD/HDD) |
| `specs.Motherboard` | string | Anakart chipset'i |
| `specs.Case` | string | Kasa modeli |
| `specs.PSU` | string | Güç kaynağı (watt + verimlilik) |
| `specs.Cooler` | string | Soğutucu |

Bazı siteler Case/PSU/Cooler bilgisi vermez, bu alanlar `"N/A"` veya `"Pakette yok"` olarak gelir.

```json
{
  "name": "AMD Ryzen 5 7500F + RTX 4060 OEM Paket",
  "price": 29999.0,
  "store": "vatan",
  "specs": {
    "CPU": "AMD Ryzen 5 7500F",
    "GPU": "RTX 4060",
    "RAM": "16GB DDR5",
    "Storage": "500GB NVMe SSD",
    "Motherboard": "B650M",
    "Case": "N/A",
    "PSU": "650W 80+",
    "Cooler": "N/A"
  }
}
```

---

## EnUcuzSistem API'si

Bu bölümü ayrı açmak istedim çünkü ilk bakışta kafa karıştırıcı olabiliyor.

### Ne bu API?

`enucuzsistem.com` aslında bizimle aynı işi yapan bir site — Türkiye'deki hazır sistemleri toplayıp karşılaştırıyor. Bunu yaparken kendi içinde bir REST API kullanıyor:

```
GET https://enucuzsistem.com/api/products?page=1&category=hazir-sistem&pageSize=48
```

Bu endpoint düzgün JSON dönüyor. Yani Vatan, Sinerji, PCKolik gibi sitelere tek tek bağlanmak yerine bu tek API'yi çekince hepsinin verisini bir anda alabiliyorsun.

### Ne zaman API'yi kullanmalısın?

- **Hız önceliğin varsa** — ~2-3 dakikada ~2880 ürün. Bireysel scraper'lar çok daha uzun sürer.
- **Düzenli çalıştırıyorsan** — günlük cron job, zamanlayıcı vs. kuruyorsan bu modu kullan.
- **Bot korumasıyla uğraşmak istemiyorsan** — bazı siteler zaman zaman blok atıyor, API modunda bu sorun yok.
- **Hızlı prototip yapıyorsan** — verileri bir an önce görmek istiyorsan en kolay yol bu.

### Ne zaman bireysel scraper'ları kullanmalısın?

Bireysel scraper'lar esas olarak EnUcuzSistem API'si çöktüğünde veya değiştiğinde devreye girer. Scraping tabanlı projeler doğası gereği kırılgan — siteler yapı değişikliği yaptığında scraper'lar bozulur ama API çalıştığı sürece bireysel scraper'larla uğraşmana gerek yok. API'nin kapandığı durumda `USE_ENUCUZSISTEM_API=false` yapıp bireysel scraper'lara geçebilirsin.

Ayrıca EnUcuzSistem'in indexlemediği ürünler olabilir — doğrudan sitenin kendi verisini çekmek istiyorsan da bireysel scraper'lar daha güvenilir sonuç verir.

### Teknik detay

- Pagination `pageSize=48` ile yapılıyor, toplamda ~60 sayfa
- Sayfalar 5'li gruplar halinde paralel çekiliyor, her grup arasında 300ms bekleniyor (rate-limit koruması)
- `store` alanı "gaming-gen-hb", "tebilon-hb" gibi geldiğinde normalize ediliyor → `gaminggen`, `tebilon`
- Görsel URL'leri bazen `/api/cached-images?url=...` formatında geliyor, scraper decode edip gerçek URL'ye çeviriyor
- API'den eksik gelen spec alanları ürün ismi ve URL slug'ından `extract_specs_from_name` ile tamamlanıyor

### Önemli not

Bu bir üçüncü taraf sitesinin undocumented API'si, resmi dökümantasyonu yok. Şu an çalışıyor ama ileride endpoint değişebilir, rate-limit sıkılaşabilir ya da tamamen kapanabilir. Bireysel scraper'lar bu yüzden projede duruyor.

---

## Teknik detaylar

- **Scrapling** kütüphanesi kullanılıyor — bot koruması olan sitelerde daha stabil çalışıyor
- Detay sayfaları `.detail_cache.json` dosyasına önbellekleniyor; ikinci çalıştırmada çok daha hızlı oluyor
- Cache'i sıfırlamak için dosyayı sil ya da `SCRAPER_NO_CACHE=1` set et

---

## Ayarlar

| Değişken | Varsayılan | Ne yapar |
|----------|-----------|----------|
| `USE_ENUCUZSISTEM_API` | `true` | `false` yapınca her siteyi ayrı scrape eder |
| `SCRAPER_NO_CACHE` | `0` | `1` yapınca önbelleği devre dışı bırakır |

---

Sorularınız için: emindmrts@proton.me
