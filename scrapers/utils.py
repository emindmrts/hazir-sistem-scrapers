# Spec extraction yardımcı fonksiyonları.
# extract_specs_from_list  → listing sayfasındaki bileşen metni listesinden spec çıkarır
# extract_specs_from_name  → ürün adı veya URL slug'ından regex ile spec çıkarır
# extract_specs_from_table → <th>Etiket</th><td>Değer</td> tablolarından spec çıkarır
# extract_specs_from_attributes → WooCommerce shop_attributes tablosundan spec çıkarır
# merge_specs              → base dict'teki N/A alanlarını extra dict'ten doldurur
# load/save_detail_cache   → detay sayfası spec'lerini URL bazlı önbellekler

import re
import os
import json

EMPTY_SPECS = {
    "CPU": "N/A",
    "Motherboard": "N/A",
    "GPU": "N/A",
    "RAM": "N/A",
    "Storage": "N/A",
    "Case": "N/A",
    "PSU": "N/A",
    "Cooler": "N/A",
}

_TR_MAP = str.maketrans({
    "ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u",
    "Ç": "c", "Ğ": "g", "İ": "i", "I": "i", "Ö": "o", "Ş": "s", "Ü": "u",
})


def _norm(s: str) -> str:
    # Türkçe karakterleri ASCII'ye fold eder; keyword eşleşmeleri için
    if not s:
        return ""
    return s.translate(_TR_MAP).lower()


# "arc", "aio" gibi kısa token'lar tam kelime olarak eşleşmeli; "arctic" gibi yanlış ateşlemesini önler
_EXACT = {"arc", "aio", "psu", "cpu", "case"}


def _has_word(text: str, kw: str) -> bool:
    # Normalize edilmiş metin üzerinde keyword eşleşmesi.
    # Türkçe ekler için trailing boundary gevşek tutulur (kasa → kasası eşleşir).
    # _EXACT listesindekiler her iki taraftan da sınır ister.
    tail = r"(?![a-z0-9])" if kw in _EXACT else r"(?![0-9])"
    return re.search(r"(?<![a-z0-9])" + re.escape(kw) + tail, text) is not None


def _has_any(text: str, kws) -> bool:
    return any(_has_word(text, kw) for kw in kws)


# Kurallar sırayla denenir; ilk eşleşen kategori kazanır.
# Sıra önemli: Cooler CPU'dan, Case PSU/Cooler'dan önce gelmeli.
_RULES = [
    ("GPU", ["ekran karti", "ekran kart", "geforce", "radeon", "grafik islemci", "arc"],
     [], r"(?<![a-z0-9])(rtx|gtx)\s?\d{3,4}|(?<![a-z0-9])rx\s?\d{3,4}"),
    ("Motherboard", ["anakart", "motherboard", "mainboard"], ["ekran"],
     r"(?<![a-z0-9])[abhxz]\d{3}[a-z]{0,2}(?![a-z0-9])"),
    # Case; PSU/Cooler'dan önce: bazı kasalar PSU veya "Cooler Master" içerir
    ("Case", ["kasa", "case", "tower", "kabin"], [], None),
    ("PSU", ["guc kaynagi", "power supply", "psu"], [],
     r"(?<![a-z0-9])(80\s?\+|80\s?plus)"),
    ("RAM", ["ram", "bellek"], ["anakart", "ekran", "ssd", "hdd", "kasa"],
     r"(?<![a-z0-9])ddr[45](?![a-z0-9])"),
    ("Storage", ["ssd", "hdd", "nvme", "m.2", "sata"], ["ekran", "anakart"],
     r"\d+\s?(gb|tb)\s?(ssd|hdd|nvme|m\.2)"),
    ("Cooler", ["sogutucu", "sogutma", "cooler", "sivi sogutma", "liquid cooling", "aio"],
     ["ram", "bellek"], None),
    ("CPU", ["islemci", "cpu", "ryzen", "intel", "core i", "core ultra", "processor"],
     ["sogutucu", "anakart"],
     r"(?<![a-z0-9])r[3579](?![a-z0-9])|(?<![a-z0-9])i[3579]-\d"),
]


def _classify(item: str) -> str | None:
    # Bir bileşen metninin hangi spec kategorisine girdiğini döner
    n = _norm(item)
    if not n:
        return None
    for category, pos, neg, rx in _RULES:
        if _has_any(n, neg):
            continue
        if _has_any(n, pos) or (rx and re.search(rx, n)):
            return category
    return None


def _psu_from_text(items: list[str]) -> str | None:
    # Kasayla gelen entegre PSU'yu yakalar ("650W 80+ ... Kasa" gibi)
    for it in items:
        n = _norm(it)
        rated = re.search(r"80\s?\+|80\s?plus", n)
        named = "guc kaynagi" in n or "power supply" in n
        if not (rated or named):
            continue
        watt = re.search(r"(\d{3,4})\s?w(?:att)?(?![a-z0-9])", n)
        parts = []
        if watt:
            parts.append(f"{watt.group(1)}W")
        if rated:
            parts.append("80+")
        if parts:
            return " ".join(parts)
    return None


def extract_specs_from_list(spec_items: list[str]) -> dict:
    # Bileşen metni listesinden spec çıkarır; her kategori ilk eşleşeni alır
    specs = dict(EMPTY_SPECS)
    if not spec_items:
        return specs

    for item in spec_items:
        item = (item or "").strip()
        if not item:
            continue
        category = _classify(item)
        if category and specs[category] == "N/A":
            specs[category] = " ".join(item.split())

    if specs["PSU"] == "N/A":
        psu = _psu_from_text(spec_items)
        if psu:
            specs["PSU"] = psu

    return specs


def extract_specs_from_attributes(attrs: dict) -> dict:
    # WooCommerce shop_attributes tablosunu spec alanlarına map eder
    specs = dict(EMPTY_SPECS)
    if not attrs:
        return specs

    norm = {_norm(k): (v or "").strip() for k, v in attrs.items()}

    def pick(*label_fragments):
        for label, val in norm.items():
            if not val:
                continue
            if any(frag in label for frag in label_fragments):
                return " ".join(val.split())
        return None
    cpu = pick("islemci modeli") or pick("islemci serisi")
    if cpu:
        specs["CPU"] = cpu
    mb = pick("cipset")
    if mb:
        specs["Motherboard"] = mb
    gpu = pick("grafik islemci modeli") or pick("grafik islemci serisi")
    if gpu:
        specs["GPU"] = gpu
    ram = pick("ram kapasitesi")
    if ram:
        ram_type = pick("ram tipi")
        ram_speed = pick("ram hizi")
        specs["RAM"] = " ".join(x for x in [ram, ram_type, ram_speed] if x)
    storage = pick("depolama kapasitesi")
    if storage:
        stype = pick("depolama tipi")
        specs["Storage"] = " ".join(x for x in [storage, stype] if x)
    case = pick("kasa")
    if case:
        specs["Case"] = case
    psu = pick("guc kaynagi")
    if psu:
        specs["PSU"] = psu
    cooler = pick("sogutma yontemi") or pick("sogutucu")
    if cooler:
        radiator = pick("radyator boyutu")
        specs["Cooler"] = " ".join(x for x in [cooler, radiator] if x)

    return specs


def merge_specs(base: dict, extra: dict) -> dict:
    # base'deki N/A alanlarını extra'dan doldurur (in-place)
    for k in EMPTY_SPECS:
        if base.get(k, "N/A") in (None, "", "N/A") and extra.get(k, "N/A") not in (None, "", "N/A"):
            base[k] = extra[k]
    return base


# Label fragments → spec category.  Order matters: more specific labels first
# (e.g. "ekran karti hafizasi" must not claim "Ekran Kartı" before the GPU row).
_LABEL_RULES = [
    ("CPU",       ["islemci modeli", "islemci serisi", "islemci", "processor", "cpu"]),
    ("Motherboard", ["anakart", "motherboard", "mainboard", "cipset", "chipset"]),
    ("GPU",       ["ekran karti modeli", "ekran karti serisi", "ekran karti", "grafik islemci", "gpu", "graphics"]),
    ("RAM",       ["ram kapasitesi", "ram tipi", "ram hizi", "ram", "bellek", "memory"]),
    ("Storage",   ["depolama kapasitesi", "depolama tipi", "ssd", "hdd", "depolama", "sabit disk", "storage"]),
    ("Cooler",    ["sogutma yontemi", "sogutucu", "cooler", "sogutma", "heatsink"]),
    ("Case",      ["kasa", "case", "kabin", "chassis"]),
    ("PSU",       ["guc kaynagi", "power supply", "psu"]),
]

_SUB_ATTR = ("hizi", "hiz", "hafizasi", "hafiza", "bellek tipi", "bellek arayuzu",
             "max. ram", "isletim sistemi", "serisi", "modeli", "powered by",
             "monitor", "monitorsuz", "ekran karti serisi", "islemci modeli",
             "ekran karti hafizasi")


def _label_to_category(label: str) -> str | None:
    # Türkçe/İngilizce spec tablosu etiketini spec kategorisine map eder
    n = _norm(label)
    if not n:
        return None
    for category, frags in _LABEL_RULES:
        for frag in frags:
            if frag in n:
                return category
    return None


def extract_specs_from_table(rows: list[tuple[str, str]]) -> dict:
    # <th>Etiket</th><td>Değer</td> tablosundan spec çıkarır.
    # "İşlemci Hızı", "Ekran Kartı Hafızası" gibi alt-attribute'lar atlanır.
    specs = dict(EMPTY_SPECS)
    if not rows:
        return specs

    filled = set()
    for label, value in rows:
        if not value or value.lower() in ("yok", "no", "-"):
            continue
        n_label = _norm(label)
        if any(sub in n_label for sub in _SUB_ATTR):
            continue
        cat = _label_to_category(label)
        if cat and cat not in filled:
            specs[cat] = " ".join(value.split())
            filled.add(cat)
    return specs


# Detay sayfası önbelleği.
# Tebilon/GamingGen gibi sitelerde detay sayfaları rate-limit'e takılır.
# Spec'ler URL başına kararlıdır; önbellekle ikinci çalıştırma çok daha hızlı olur.
# Sıfırlamak için dosyayı sil ya da SCRAPER_NO_CACHE=1 set et.

_CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", ".detail_cache.json")
_CACHE_DISABLED = os.environ.get("SCRAPER_NO_CACHE") == "1"


def load_detail_cache() -> dict:
    # Diske kaydedilmiş url → {spec: değer} önbelleğini döner
    if _CACHE_DISABLED:
        return {}
    try:
        with open(_CACHE_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_detail_cache(cache: dict) -> None:
    # Önbelleği diske yazar; aynı anda çalışan başka scraper'ın yazdıklarını korumak için merge eder
    if _CACHE_DISABLED or not cache:
        return
    merged = load_detail_cache()
    merged.update(cache)
    try:
        with open(_CACHE_PATH, "w", encoding="utf-8") as fh:
            json.dump(merged, fh, ensure_ascii=False)
    except OSError:
        pass


def cacheable_specs(specs: dict) -> dict:
    # Önbelleklemeye değer (N/A olmayan) alanları döner
    return {k: v for k, v in specs.items()
            if k in EMPTY_SPECS and v not in (None, "", "N/A")}


def _clean(s: str) -> str:
    return " ".join(s.split())


def extract_specs_from_name(name: str) -> dict:
    # Ürün adı veya URL slug'ından regex ile spec çıkarır.
    # Slug'lardaki tire/alt çizgi/eğik çizgi boşluğa normalize edilir.
    # Bulunamayan her alan "N/A" kalır.
    specs = dict(EMPTY_SPECS)
    if not name:
        return specs

    # Ayraçları boşluğa çevir
    text = re.sub(r"[-_/]+", " ", name)
    text = re.sub(r"\s+", " ", text).strip()
    # Birleşik slug pattern'leri ayır: "ddr4500gb" → "ddr4 500gb"
    text = re.sub(r"(ddr[45])(\d)", r"\1 \2", text, flags=re.IGNORECASE)
    text = re.sub(r"(\dgb)(\d)", r"\1 \2", text, flags=re.IGNORECASE)
    n = _norm(text)

    # GPU — RTX/GTX/RX/Arc/GT serisi
    gpu_m = re.search(
        r"\b((?:radeon\s+|geforce\s+)?(?:rtx|gtx|rx|arc\s+a|gt)\s*\d{3,4}\s*"
        r"(?:ti|xt|super)?(?:\s*\d+\s*gb?)?)",
        text, re.IGNORECASE)
    if gpu_m:
        specs["GPU"] = _clean(gpu_m.group(1))

    # CPU — Ryzen/Intel pattern'leri öncelik sırasıyla denenir
    cpu_patterns = [
        r"(?:amd\s+)?ryzen\s+(?:\d\s+)?\d{3,5}\w*",
        r"(?:amd\s+)?r[3579]\s+\d{3,5}\w*",
        r"intel\s+(?:core\s+)?ultra\s+\d\s+\d{3,5}\w*",
        r"intel\s+(?:core\s+)?[iu][3579]\s+\d{3,5}\w*",
        r"intel\s+(?:core\s+)?\d{3,5}\w*",
        r"amd\s+\d{3,5}\w*",
    ]
    for pat in cpu_patterns:
        cpu_m = re.search(pat, text, re.IGNORECASE)
        if cpu_m:
            specs["CPU"] = _clean(cpu_m.group(0))
            break

    # Motherboard — A620M, B650M, Z790 gibi chipset kodları
    for mb_m in re.finditer(r"\b([abhxz]\d{3}[a-z]{0,2})\b", text, re.IGNORECASE):
        start  = mb_m.start()
        before = _norm(text[max(0, start - 5):start])
        if "arc" in before:  # "Arc A750" GPU, chipset değil
            continue
        specs["Motherboard"] = mb_m.group(1)
        break

    # RAM — DDR/RAM/Bellek keyword'u şart; yoksa storage kapasitesi yanlış eşleşir
    ram_m = (re.search(r"(\d+\s*gb\s*(?:ddr[45]|ram|bellek))", text, re.IGNORECASE)
             or re.search(r"((?:ddr[45])\s*\d+\s*gb)", text, re.IGNORECASE))
    if ram_m:
        specs["RAM"] = _clean(ram_m.group(1))

    # Storage — GPU VRAM ve RAM aralıklarını hariç tutar;
    # storage keyword (ssd/nvme/m.2/hdd) varsa önceliklendirir
    _exclude = []
    if gpu_m:
        _exclude.append(gpu_m.span())
    if ram_m:
        _exclude.append(ram_m.span())

    storage_candidates = []
    gpu_end = gpu_m.end() if gpu_m else -1
    for sm in re.finditer(
        r"\d+\s*(?:gb|tb)(?:\s+(?:nvme|m\.?\s*2|ssd|hdd|sata))*",
        text, re.IGNORECASE):
        s, e = sm.span()
        if any(s < e2 and s2 < e for s2, e2 in _exclude):
            continue
        has_kw = bool(re.search(r"(?:nvme|m\.?\s*2|ssd|hdd|sata)", sm.group(0), re.IGNORECASE))
        # VRAM koruması: GPU'dan hemen sonra gelen ≤32GB birimsiz kapasite VRAM'dir
        if not has_kw and gpu_end >= 0 and gpu_end <= s <= gpu_end + 30:
            num = re.search(r"\d+", sm.group(0))
            if num and int(num.group(0)) <= 32:
                continue
        # Keyword'suz kapasitelerin ardından DDR/RAM geliyorsa bu RAM'dir, storage değil
        if not has_kw:
            tail = _norm(text[e:e + 12])
            if "ddr" in tail or "ram" in tail or "bellek" in tail:
                continue
        storage_candidates.append(sm)

    if storage_candidates:
        with_kw = [c for c in storage_candidates
                   if re.search(r"(?:nvme|m\.?\s*2|ssd|hdd|sata)", c.group(0), re.IGNORECASE)]
        if with_kw:
            chosen = with_kw[0]
        else:
            # Storage keyword yok — TB'yi GB'ye tercih et (RAM hiçbir zaman TB olmaz)
            tb = [c for c in storage_candidates
                  if re.search(r"\d+\s*tb", c.group(0), re.IGNORECASE)]
            chosen = tb[0] if tb else storage_candidates[0]
        specs["Storage"] = _clean(chosen.group(0))

    # Case
    for kw in ("kasa", "case", "tower", "kabin", "chassis"):
        idx = n.find(kw)
        if idx >= 0:
            start = max(0, idx - 20)
            end   = min(len(text), idx + len(kw) + 25)
            specs["Case"] = _clean(text[start:end])[:50]
            break

    # PSU
    psu_watt_m = re.search(r"(\d{3,4})\s*w(?:att)?(?![a-z])", text, re.IGNORECASE)
    if psu_watt_m:
        watt   = psu_watt_m.group(1)
        plus_m = re.search(
            r"(80\s*\+\s*(?:bronze|gold|silver|platinum|titanium)?"
            r"|80\s*plus\s*(?:bronze|gold|silver|platinum|titanium)?)",
            text, re.IGNORECASE)
        specs["PSU"] = f"{watt}W 80+" if plus_m else f"{watt}W"

    # Cooler — "BOX" işlemci kutulu gelir, stok soğutucu dahildir
    for kw in ("sogutucu", "sogutma", "sivi sogutma", "cooler", "aio", "liquid"):
        idx = n.find(kw)
        if idx >= 0:
            start = max(0, idx - 20)
            end   = min(len(text), idx + len(kw) + 25)
            specs["Cooler"] = _clean(text[start:end])[:50]
            break
    else:
        if re.search(r"(?<![a-z0-9])box(?![a-z0-9])", n):
            specs["Cooler"] = "Stok Soğutucu"

    return specs
