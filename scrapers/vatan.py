# Vatan Bilgisayar — OEM paketler sayfasını çeker.
# Sayfa sayısı "286 adet ürün bulundu" ifadesinden hesaplanır.
# Tüm sayfalar paralel çekilir, eksik Case/PSU için detay sayfasına gidilir.

import re
import math
import sys
import asyncio
from scrapling import Fetcher
from .utils import extract_specs_from_list, extract_specs_from_name

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

STORE             = "vatan"
BASE_URL          = "https://www.vatanbilgisayar.com/oem-paketler/"
PRODUCTS_PER_PAGE = 24


def _parse_price(el) -> float:
    price_el = el.css(".product-list__price").first
    if not price_el:
        return 0.0
    raw   = price_el.get_all_text().strip()
    clean = re.sub(r"[^\d,.]", "", raw)
    if not clean:
        return 0.0
    if "," in clean and "." in clean:
        clean = clean.replace(".", "").replace(",", ".")
    elif "," in clean:
        clean = clean.replace(",", ".")
    elif "." in clean:
        parts = clean.split(".")
        if len(parts[-1]) == 3:
            clean = clean.replace(".", "")
    try:
        return float(clean)
    except ValueError:
        return 0.0


def _parse_page_products(page) -> list[dict]:
    products = []
    for el in page.css(".product-list"):
        link_el = el.css("a.product-list-link").first
        if not link_el:
            continue
        href        = link_el.attrib.get("href", "")
        url_product = href if href.startswith("http") else f"https://www.vatanbilgisayar.com{href}"

        name_el = el.css(".product-list__product-name").first or el.css("h3").first
        name    = name_el.get_all_text().strip() if name_el else "N/A"
        price   = _parse_price(el)

        img_el = el.css("img.lazyimg").first or el.css("img").first
        image  = (img_el.attrib.get("data-src") or img_el.attrib.get("src")) if img_el else None

        spec_items = [p.get_all_text().strip() for p in el.css(".productlist_spec ul li p")]
        specs      = extract_specs_from_list(spec_items)

        if name and name != "N/A":
            name_specs = extract_specs_from_name(f"{name} {url_product}")
            for k, v in specs.items():
                if v == "N/A" and name_specs.get(k) != "N/A":
                    specs[k] = name_specs[k]

        products.append({"name": name, "price": price, "image": image, "url": url_product, "store": STORE, "specs": specs})
    return products


async def _fetch_product_details(product: dict, fetcher_instance) -> dict:
    if product["specs"].get("Case") != "N/A" and product["specs"].get("PSU") != "N/A":
        return product

    url = product["url"]

    def sync_fetch():
        try:
            return fetcher_instance.get(url)
        except Exception:
            return None

    for attempt in range(2):
        try:
            page = await asyncio.to_thread(sync_fetch)
            if not page:
                continue
            spec_items = []
            for lbl in page.css("label.labl"):
                texts = [p.text.strip() for p in lbl.css("p") if p.text]
                if "SEÇİLDİ" in texts:
                    spec_items.append(texts[0])
            if spec_items:
                extra = extract_specs_from_list(spec_items)
                for k, v in extra.items():
                    if product["specs"].get(k, "N/A") == "N/A" and v != "N/A":
                        product["specs"][k] = v
            break
        except Exception:
            await asyncio.sleep(2)

    return product


async def scrape_all_pages_async() -> list[dict]:
    print(f"[Vatan] İlk sayfa çekiliyor...", flush=True)
    fetcher = Fetcher()

    def fetch_sync(url):
        return fetcher.get(url)

    first_page = await asyncio.to_thread(fetch_sync, BASE_URL)
    if not first_page:
        return []

    full_text   = first_page.get_all_text().lower()
    total_pages = 1
    m = re.search(r"(\d+)\s+adet\s+ürün\s+bulundu", full_text)
    if m:
        total_pages = math.ceil(int(m.group(1)) / PRODUCTS_PER_PAGE)
    else:
        count_el = first_page.css(".wrapper-product--count").first
        if count_el:
            m2 = re.search(r"(\d+)", count_el.get_all_text().replace(".", ""))
            if m2:
                total_pages = math.ceil(int(m2.group(1)) / PRODUCTS_PER_PAGE)

    print(f"[Vatan] {total_pages} sayfa bulundu", flush=True)
    all_products = _parse_page_products(first_page)

    if total_pages > 1:
        async def fetch_page_n(n):
            page = await asyncio.to_thread(fetch_sync, f"{BASE_URL}?page={n}")
            return _parse_page_products(page) if page else []

        results = await asyncio.gather(*[fetch_page_n(i) for i in range(2, total_pages + 1)])
        for r in results:
            all_products.extend(r)

    print(f"[Vatan] {len(all_products)} ürün için detay çekiliyor...", flush=True)
    sem = asyncio.Semaphore(15)

    async def fetch_with_sem(prod):
        async with sem:
            return await _fetch_product_details(prod, fetcher)

    all_products = await asyncio.gather(*[fetch_with_sem(p) for p in all_products])
    print(f"[Vatan] Tamamlandı — {len(all_products)} ürün", flush=True)
    return all_products


def scrape_all_pages() -> list[dict]:
    return asyncio.run(scrape_all_pages_async())


if __name__ == "__main__":
    products = scrape_all_pages()
    print(f"Toplam: {len(products)} ürün")
