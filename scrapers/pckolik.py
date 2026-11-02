# PCKolik — OEM paket listesi + detay sayfası çeker.
# Listing'deki görseller bileşen görselleri; gerçek sistem/kasa görseli
# detay sayfasında .case-img-crop img içinde bulunur.

import re
import asyncio
from scrapling import Fetcher
from .utils import (
    extract_specs_from_list,
    extract_specs_from_name,
    merge_specs,
    cacheable_specs,
    load_detail_cache,
    save_detail_cache,
)

STORE       = "pckolik"
BASE_URL    = "https://pckolik.com.tr/kategori/oem-paketler"
SITE_BASE   = "https://pckolik.com.tr"
PRODUCT_SEL = ".product-card"


def _parse_price(card) -> float:
    raw = ""
    for sel in (".price-new", ".price", ".current-price", ".product-price", ".price-box"):
        el = card.css(sel).first
        if el:
            raw = el.get_all_text().strip()
            if raw:
                break
    if not raw:
        match = re.search(r"(\d[\d.]*(?:,\d+)?)\s*(?:TL|₺)", card.get_all_text())
        if match:
            raw = match.group(1)
    if not raw:
        return 0.0
    clean = re.sub(r"[^\d,.]", "", raw)
    if "." in clean and "," in clean:
        clean = clean.replace(".", "").replace(",", ".")
    elif "," in clean:
        clean = clean.replace(",", ".")
    try:
        return float(clean)
    except ValueError:
        return 0.0


def _parse_page_products(page) -> list[dict]:
    products = []
    if not page:
        return products
    for card in page.css(PRODUCT_SEL):
        a_el = card.css("a.name").first or card.css("a").first
        href = a_el.attrib.get("href", "") if a_el else ""
        if not href or "javascript" in href.lower():
            continue
        if not href.startswith("http"):
            href = f"{SITE_BASE}{'/' if not href.startswith('/') else ''}{href}"

        name = "N/A"
        for sel in (".name", "a.name", "a.product-name", ".product-title", ".product-name", "h2", "h3"):
            name_el = card.css(sel).first
            if name_el:
                name = name_el.get_all_text().strip()
                if name and name != "N/A":
                    name = name.split("\n")[0].strip()
                    break

        price = _parse_price(card)

        image = None
        for img in card.css("img"):
            src = img.attrib.get("src") or ""
            if not src or src.startswith("/assets/") or src.endswith((".svg", ".gif")) or "icon" in src.lower():
                continue
            image = f"{SITE_BASE}{src}" if src.startswith("/") else src
            break

        features = [(li.get_all_text() if hasattr(li, "get_all_text") else li.text).strip()
                    for li in card.css("li")]
        specs = extract_specs_from_list(features)

        if name and name != "N/A":
            name_specs = extract_specs_from_name(f"{name} {href}")
            for k, v in specs.items():
                if v == "N/A" and name_specs.get(k) != "N/A":
                    specs[k] = name_specs[k]

        products.append({"name": name, "price": price, "image": image, "url": href, "store": STORE, "specs": specs})
    return products


def _parse_detail_image(page) -> str | None:
    if not page:
        return None
    for sel in (".case-img-crop img", ".case-img img", "img.case-img",
                ".product-gallery img", ".product-image img"):
        img = page.css(sel).first
        if img:
            src = img.attrib.get("src") or img.attrib.get("data-src") or ""
            if src and not src.endswith(".svg") and "icon" not in src.lower():
                return src
    return None


async def _fetch_product_details(product: dict, fetcher, cache=None) -> dict:
    url = product.get("url")
    if not url:
        return product
    if cache is not None and url in cache:
        cached = cache[url]
        if cached.get("image"):
            product["image"] = cached["image"]
        if cached.get("specs"):
            merge_specs(product["specs"], cached["specs"])
        return product

    def sync_fetch():
        try:
            return fetcher.get(url)
        except Exception:
            return None

    for attempt in range(3):
        page = await asyncio.to_thread(sync_fetch)
        if not page:
            await asyncio.sleep(1 + attempt)
            continue
        if getattr(page, "status_code", 200) == 429:
            await asyncio.sleep(4 + attempt * 4)
            continue
        image = _parse_detail_image(page)
        if image:
            if image.startswith("/"):
                image = f"{SITE_BASE}{image}"
            product["image"] = image
        if cache is not None:
            cache[url] = {"image": image, "specs": cacheable_specs(product["specs"])}
        break
    return product


async def scrape_all_pages_async() -> list[dict]:
    print(f"[PCKolik] Çekiliyor: {BASE_URL}", flush=True)
    fetcher = Fetcher()

    def fetch_sync(url):
        try:
            return fetcher.get(url)
        except Exception as e:
            print(f"[PCKolik] Hata: {e}", flush=True)
            return None

    first_page = await asyncio.to_thread(fetch_sync, BASE_URL)
    if not first_page:
        print("[PCKolik] İlk sayfa çekilemedi", flush=True)
        return []

    try:
        nums        = [int(a.text.strip()) for a in first_page.css(".pagination a, .page-link") if a.text.strip().isdigit()]
        total_pages = max(nums) if nums else 1
    except Exception:
        total_pages = 1

    print(f"[PCKolik] {total_pages} sayfa bulundu", flush=True)
    all_products = _parse_page_products(first_page)
    seen_urls    = {p["url"] for p in all_products if p.get("url")}
    print(f"[PCKolik] Sayfa 1: {len(all_products)} ürün", flush=True)

    if total_pages > 1:
        sem = asyncio.Semaphore(2)

        async def fetch_n(n):
            async with sem:
                for attempt in range(3):
                    try:
                        page     = await asyncio.to_thread(fetch_sync, f"{BASE_URL}?page={n}")
                        products = _parse_page_products(page)
                        if products:
                            print(f"[PCKolik] Sayfa {n}: {len(products)} ürün", flush=True)
                            return products
                    except Exception as e:
                        print(f"[PCKolik] Sayfa {n} hata (deneme {attempt+1}): {e}", flush=True)
                        await asyncio.sleep(2)
                return []

        results = await asyncio.gather(*[fetch_n(i) for i in range(2, total_pages + 1)], return_exceptions=True)
        for r in results:
            if isinstance(r, list):
                for p in r:
                    if p["url"] not in seen_urls:
                        seen_urls.add(p["url"])
                        all_products.append(p)

    print(f"[PCKolik] {len(all_products)} ürün için detay çekiliyor...", flush=True)
    cache  = load_detail_cache()
    cached = sum(1 for p in all_products if p.get("url") in cache)
    print(f"[PCKolik] {cached} ürün önbellekte", flush=True)

    sem = asyncio.Semaphore(8)

    async def fetch_detail_with_sem(prod):
        async with sem:
            was_cached = prod.get("url") in cache
            res = await _fetch_product_details(prod, fetcher, cache)
            if not was_cached:
                await asyncio.sleep(0.1)
            return res

    all_products = await asyncio.gather(*[fetch_detail_with_sem(p) for p in all_products])
    save_detail_cache(cache)
    print(f"[PCKolik] Tamamlandı — {len(all_products)} ürün", flush=True)
    return all_products


def scrape_all_pages() -> list[dict]:
    return asyncio.run(scrape_all_pages_async())


if __name__ == "__main__":
    import json
    products = scrape_all_pages()
    print(f"Toplam: {len(products)} ürün")
