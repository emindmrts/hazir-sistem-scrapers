# İtopya — ?pg=100 parametresiyle tüm OEM paketleri tek istekte çeker.
# Her ürün kartında .itopya-{bileşen} class'lı ikonlar spec alanlarına map edilir.
# "LITE" paketlerde RAM ve Storage pakete dahil değildir, bu alanlar işaretlenir.

import re
import asyncio
import sys
from scrapling import Fetcher
from .utils import extract_specs_from_list, extract_specs_from_name

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DOMAIN = "https://www.itopya.com"
BASE_URL    = f"{BASE_DOMAIN}/oem-paketler?pg=100"

ICON_MAP = {
    "islemci":    "CPU",
    "anakart":    "Motherboard",
    "ekran-karti":"GPU",
    "bellek":     "RAM",
    "ssd":        "Storage",
    "kasa":       "Case",
    "guc-kaynagi":"PSU",
    "sogutucu":   "Cooler",
}


async def scrape_all_pages_async() -> list[dict]:
    print(f"[İtopya] Tek istekle tüm ürünler çekiliyor...", flush=True)

    def fetch():
        fetcher = Fetcher()
        return fetcher.get(BASE_URL)

    page = None
    for attempt in range(2):
        try:
            page = await asyncio.to_thread(fetch)
            if page and (page.css(".product") or page.css(".product-card")):
                break
        except Exception as e:
            print(f"[İtopya] Hata: {e}", flush=True)
        await asyncio.sleep(2)

    if not page:
        print("[İtopya] Sayfa çekilemedi", flush=True)
        return []

    products = []
    cards    = page.css(".product") or page.css(".product-card")

    for el in cards:
        link_el = el.css(".product-block-top h1 a").first or el.css("a").first
        if not link_el:
            continue
        name = link_el.get_all_text().strip()
        href = link_el.attrib.get("href")
        if not href:
            continue
        link = href if href.startswith("http") else f"{BASE_DOMAIN}{href}"

        img_el = el.css("img").first
        image  = (img_el.attrib.get("data-src") or img_el.attrib.get("src")) if img_el else None
        if image and image.startswith("/"):
            image = f"{BASE_DOMAIN}{image}"

        price_el   = el.css(".product-price strong").first or el.css(".product-price").first
        price_text = price_el.get_all_text().strip() if price_el else "0"
        price_clean = re.sub(r"[^\d,]", "", price_text).replace(",", ".")
        try:
            price = float(price_clean)
        except Exception:
            price = 0.0

        specs      = {"CPU": "N/A", "Motherboard": "N/A", "GPU": "N/A", "RAM": "N/A",
                      "Storage": "N/A", "Case": "N/A", "PSU": "N/A", "Cooler": "N/A"}
        spec_items = []

        for feat in el.css(".product-block-feature li, .advice-system-feature p"):
            txt           = feat.get_all_text().strip()
            found_by_icon = False
            for icon_key, spec_key in ICON_MAP.items():
                if feat.css(f".itopya-{icon_key}").first:
                    specs[spec_key] = txt
                    found_by_icon   = True
                    break
            if not found_by_icon:
                spec_items.append(txt)

        extra = extract_specs_from_list(spec_items)
        for k, v in specs.items():
            if v == "N/A" and extra.get(k) != "N/A":
                specs[k] = extra[k]

        if name:
            name_specs = extract_specs_from_name(f"{name} {link}")
            for k, v in specs.items():
                if v == "N/A" and name_specs.get(k) != "N/A":
                    specs[k] = name_specs[k]

        # LITE paketlerde RAM/Storage pakete dahil değil; URL slug'dan yanlış çekilmesin
        slug     = (link or "").lower()
        is_lite  = "lite-paket" in slug or ("lite-" in slug and "lite" in name.lower())
        if is_lite:
            specs["RAM"]     = "Pakete dahil değil"
            specs["Storage"] = "Pakete dahil değil"

        products.append({"name": name, "price": price, "image": image, "url": link, "store": "itopya", "specs": specs})

    # Deduplikasyon
    seen:    set[str]   = set()
    unique:  list[dict] = []
    for p in products:
        if p["url"] not in seen:
            seen.add(p["url"])
            unique.append(p)

    print(f"[İtopya] Tamamlandı — {len(unique)} ürün", flush=True)
    return unique


def scrape_all_pages() -> list[dict]:
    return asyncio.run(scrape_all_pages_async())


if __name__ == "__main__":
    res = scrape_all_pages()
    print(f"Toplam: {len(res)} ürün")
