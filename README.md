# Hazır Sistem Scraper'ları

Türk e-ticaret sitelerinden hazır (OEM) bilgisayar sistemlerini çeken Python scraper'ları.

## Desteklenen Siteler

| Site | Scraper |
|------|---------|
| Vatan Bilgisayar | `scrapers/vatan.py` |
| Sinerji | `scrapers/sinerji.py` |
| GameGaraj | `scrapers/gamegaraj.py` |
| GamingGen | `scrapers/gaminggen.py` |
| İnceHesap | `scrapers/incehesap.py` |
| İtopya | `scrapers/itopya.py` |
| PCKolik | `scrapers/pckolik.py` |
| Tebilon | `scrapers/tebilon.py` |
| EnUcuzSistem (API) | `scrapers/enucuzsistem.py` |

## Kurulum

```bash
pip install -r requirements.txt
```

Playwright için ek kurulum gerekebilir:
```bash
playwright install chromium
```

## Kullanım

### Tüm scraper'ları çalıştır
```bash
python run_scrapers.py
```

### Belirli siteleri çalıştır
```bash
python run_scrapers.py vatan pckolik sinerji
```

### Kaydetmeden test et
```bash
python run_scrapers.py --no-save
```

### Tek scraper çalıştır
```bash
python -m scrapers.vatan
python -m scrapers.sinerji
```

## Çıktı Formatı

Her scraper şu formatta liste döner:

```json
{
  "name": "Ürün adı",
  "price": 29999.0,
  "image": "https://...",
  "url": "https://...",
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

## Ortam Değişkenleri

| Değişken | Varsayılan | Açıklama |
|----------|-----------|----------|
| `USE_ENUCUZSISTEM_API` | `true` | `true` = EnUcuzSistem API'si (hızlı), `false` = her siteyi ayrı scrape et |
| `SCRAPER_NO_CACHE` | `0` | `1` = detay sayfası önbelleğini devre dışı bırak |

## Notlar

- `scrapling` kütüphanesi statik HTML için kullanılır (bot tespitine dayanıklı).
- Detay sayfaları hız için önbelleğe alınır (`.detail_cache.json`).
- `EnUcuzSistem` modu tüm sitelerin verilerini tek bir API üzerinden çeker (~2880 ürün).
