# İnceHesap — OEM paket listesini çeker.
# Ürün bilgileri a[data-product] attribute'undaki JSON'dan alınır.
# Site Case/PSU/Cooler bilgisi vermez; bu alanlar "Pakette yok" olarak işaretlenir.

import re
import sys
import asyncio
import json
from scrapling import Fetcher
from .utils import extract_specs_from_name

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

STORE    = "incehesap"
BASE_URL = "https://www.incehesap.com/hazir-sistemler-fiyatlari/"


def _parse_page_products(page) -> list[dict]:
    if not page:
        return []
    products = []
    for el in page.css("a[data-product]"):
        href = el.attrib.get("href", "")
        if not href or "-oem-paket-fiyati-" not in href:
            continue
        href        = href.split("#")[0].split("?")[0]
        url_product = href if href.startswith("http") else f"https://www.incehesap.com{href}"

        img_el = el.css("img").first
        image  = (img_el.attrib.get("data-src") or img_el.attrib.get("src")) if img_el else None
        if image and image.startswith("/"):
            image = f"https://www.incehesap.com{image}"

        data = el.attrib.get("data-product")
        if not data:
            continue
        try:
            obj      = json.loads(data)
            category = obj.get("category", "")
            name     = obj.get("name", "N/A")
            if "OEM Paket" not in category and "OEM Paket" not in name:
                continue
            price = float(obj.get("price", 0))
        except Exception:
            continue

        specs = extract_specs_from_name(name)
        if specs.get("CPU") == "N/A" and specs.get("GPU") == "N/A":
            continue

        # Site bu alanları hiç paylaşmıyor; "N/A" yerine açıklayıcı etiket koy
        for k in ("Case", "PSU", "Cooler"):
            if specs.get(k, "N/A") == "N/A":
                specs[k] = "Pakette yok"

        products.append({"name": name, "price": price, "image": image, "url": url_product, "store": STORE, "specs": specs})
    return products


async def scrape_all_pages_async() -> list[dict]:
    print(f"[İnceHesap] Çekiliyor...", flush=True)
    fetcher = Fetcher()

    def fetch_sync(url):
        return fetcher.get(url)

    all_products: list[dict] = []
    seen_urls:    set[str]   = set()

    for page_num in range(1, 20):
        url  = BASE_URL if page_num == 1 else f"{BASE_URL}sayfa-{page_num}/"
        page = await asyncio.to_thread(fetch_sync, url)
        if not page:
            break
        batch = _parse_page_products(page)
        if not batch:
            break
        new_count = 0
        for p in batch:
            if p["url"] not in seen_urls:
                seen_urls.add(p["url"])
                all_products.append(p)
                new_count += 1
        print(f"[İnceHesap] Sayfa {page_num}: {new_count} ürün", flush=True)
        if new_count == 0:
            break

    print(f"[İnceHesap] Tamamlandı — {len(all_products)} ürün", flush=True)
    return all_products


def scrape_all_pages() -> list[dict]:
    return asyncio.run(scrape_all_pages_async())


if __name__ == "__main__":
    res = scrape_all_pages()
    with open("incehesap_output.json", "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
