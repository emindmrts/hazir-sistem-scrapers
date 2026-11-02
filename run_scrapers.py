"""
run_scrapers.py  —  Tüm scraper'ları çalıştır
Rich terminal UI · gerçek zamanlı durum takibi

Kullanım:
    python run_scrapers.py                → tüm scraper'lar (EnUcuzSistem API)
    python run_scrapers.py vatan pckolik  → sadece belirtilen(ler)
    python run_scrapers.py --no-save      → output/ klasörüne kaydetme
"""

import asyncio
import json
import os
import sys
import time
import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Optional, Callable

# ── Windows encoding fix ─────────────────────────────────────────────────────
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Scraper imports ──────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

from scrapers.sinerji      import scrape_all_pages_async    as scrape_sinerji
from scrapers.gamegaraj    import scrape_all_pages_async    as scrape_gamegaraj
from scrapers.itopya       import scrape_all_pages_async    as scrape_itopya
from scrapers.vatan        import scrape_all_pages_async    as scrape_vatan
from scrapers.incehesap    import scrape_all_pages_async    as scrape_incehesap
from scrapers.pckolik      import scrape_all_pages_async    as scrape_pckolik
from scrapers.gaminggen    import scrape_all_pages_async    as scrape_gaminggen
from scrapers.tebilon      import scrape_all_pages_async    as scrape_tebilon
from scrapers.enucuzsistem import scrape_all_pages_async    as scrape_enucuzsistem

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT        = Path(__file__).parent
OUTPUT_DIR  = ROOT / "output"
OUTPUT_JSON = OUTPUT_DIR / "products.json"

# ── Rich ─────────────────────────────────────────────────────────────────────
try:
    from rich.console import Console
    from rich.live    import Live
    from rich.table   import Table
    from rich.panel   import Panel
    from rich.text    import Text
    from rich.align   import Align
    from rich.layout  import Layout
    from rich         import box
    RICH = True
except ImportError:
    RICH = False
    print("[UYARI] 'rich' yükle:  pip install rich\n")

# ── Status ───────────────────────────────────────────────────────────────────
class Status(Enum):
    WAITING = "waiting"
    RUNNING = "running"
    DONE    = "done"
    ERROR   = "error"

_STATUS = {
    Status.WAITING: ("·",  "dim white",    "BEKLIYOR"),
    Status.RUNNING: ("►",  "bold yellow",  "CALISIYOR"),
    Status.DONE:    ("✓",  "bold green",   "TAMAM"),
    Status.ERROR:   ("✗",  "bold red",     "HATA"),
}

# ── State ────────────────────────────────────────────────────────────────────
@dataclass
class ScraperState:
    name:       str
    key:        str
    fn:         Callable
    status:     Status          = Status.WAITING
    count:      int             = 0
    elapsed:    float           = 0.0
    error:      str             = ""
    start_time: Optional[float] = None

    def live_elapsed(self) -> float:
        if self.status == Status.RUNNING and self.start_time:
            return time.time() - self.start_time
        return self.elapsed

ALL_SCRAPERS: list[ScraperState] = [
    ScraperState("Vatan",        "vatan",        scrape_vatan),
    ScraperState("InceHesap",    "incehesap",    scrape_incehesap),
    ScraperState("PCKolik",      "pckolik",      scrape_pckolik),
    ScraperState("GamingGen",    "gaminggen",    scrape_gaminggen),
    ScraperState("Tebilon",      "tebilon",      scrape_tebilon),
    ScraperState("Itopya",       "itopya",       scrape_itopya),
    ScraperState("Sinerji",      "sinerji",      scrape_sinerji),
    ScraperState("GameGaraj",    "gamegaraj",    scrape_gamegaraj),
    ScraperState("EnUcuzSistem", "enucuzsistem", scrape_enucuzsistem),
]

# ── Shared ───────────────────────────────────────────────────────────────────
_lock         = Lock()
_all_products: list[dict] = []

# ── Persistence ──────────────────────────────────────────────────────────────
def save_products(products: list[dict]) -> None:
    if not products:
        print("[WARN] Boş liste, kayıt atlandı.", flush=True)
        return
    OUTPUT_DIR.mkdir(exist_ok=True)
    payload = json.dumps(products, ensure_ascii=False, indent=2)
    OUTPUT_JSON.write_text(payload, encoding="utf-8")
    print(f"[Kayıt] {len(products)} ürün → {OUTPUT_JSON}", flush=True)

# ── Rich UI ──────────────────────────────────────────────────────────────────
def _header() -> "Panel":
    t = Text()
    t.append("HAZIR SISTEM  ", style="bold cyan")
    t.append("SCRAPER RUNNER", style="bold white")
    return Panel(Align.center(t), border_style="cyan", padding=(0, 2))


def _table(scrapers: list[ScraperState]) -> "Table":
    tbl = Table(
        box=box.ROUNDED, border_style="bright_black",
        header_style="bold cyan", padding=(0, 1), expand=True,
    )
    tbl.add_column("#",      style="dim white", width=3,  justify="right")
    tbl.add_column("",       width=2,           justify="center")
    tbl.add_column("Site",   style="bold white", min_width=14)
    tbl.add_column("Durum",  min_width=12)
    tbl.add_column("Ürün",   justify="right", width=7,  style="bold green")
    tbl.add_column("Süre",   justify="right", width=9,  style="cyan")
    tbl.add_column("Hata",   style="dim red",  min_width=30)

    for i, s in enumerate(scrapers, 1):
        icon, st, lbl = _STATUS[s.status]
        elapsed_str   = f"{s.live_elapsed():.1f}s" if s.start_time else "-"
        count_str     = str(s.count) if s.count else "-"
        row_bg        = "on grey11" if s.status == Status.RUNNING else ""
        tbl.add_row(
            str(i), Text(icon, style=st), s.name,
            Text(lbl, style=st), count_str, elapsed_str, s.error[:55],
            style=row_bg,
        )
    return tbl


def _footer(scrapers: list[ScraperState], t0: float) -> "Panel":
    done    = sum(1 for s in scrapers if s.status == Status.DONE)
    errors  = sum(1 for s in scrapers if s.status == Status.ERROR)
    running = sum(1 for s in scrapers if s.status == Status.RUNNING)
    total   = len(_all_products)
    elapsed = time.time() - t0
    line = Text()
    line.append(f" ✓ {done}  ", style="bold green")
    line.append(f" ► {running}  ", style="bold yellow")
    line.append(f" ✗ {errors}  ", style="bold red")
    line.append(f" {total} ürün  ", style="bold cyan")
    line.append(f" {elapsed:.1f}s ", style="bold white")
    return Panel(Align.center(line), border_style="bright_black", padding=(0, 1))


def _render(scrapers: list[ScraperState], t0: float):
    layout = Layout()
    layout.split_column(
        Layout(_header(),             size=3),
        Layout(_table(scrapers)),
        Layout(_footer(scrapers, t0), size=3),
    )
    return layout

# ── Runners ──────────────────────────────────────────────────────────────────
async def _run_async(state: ScraperState, save: bool) -> None:
    state.status     = Status.RUNNING
    state.start_time = time.time()
    try:
        result = await state.fn()
        state.elapsed = time.time() - state.start_time
        if not isinstance(result, list):
            raise TypeError("Scraper list döndürmedi")
        state.count = len(result)
        if save and result:
            with _lock:
                _all_products.extend(result)
                save_products(_all_products)
        state.status = Status.DONE
    except Exception as exc:
        state.elapsed = time.time() - state.start_time
        state.error   = str(exc)[:120]
        state.status  = Status.ERROR

# ── Main ─────────────────────────────────────────────────────────────────────
async def main(scrapers: list[ScraperState], save: bool) -> None:
    t0  = time.time()
    aws = [asyncio.create_task(_run_async(s, save)) for s in scrapers]

    if RICH:
        console = Console()

        async def _refresh(live: Live) -> None:
            while True:
                live.update(_render(scrapers, t0))
                await asyncio.sleep(0.2)

        with Live(_render(scrapers, t0), console=console, refresh_per_second=5) as live:
            refresh_task = asyncio.create_task(_refresh(live))
            await asyncio.gather(*aws, return_exceptions=True)
            refresh_task.cancel()
            live.update(_render(scrapers, t0))

        total_elapsed = time.time() - t0
        final = Table(
            box=box.DOUBLE_EDGE, border_style="cyan",
            header_style="bold cyan",
            title="[bold cyan]SCRAPING TAMAMLANDI[/bold cyan]",
            expand=False,
        )
        final.add_column("",      width=2,  justify="center")
        final.add_column("Site",  style="bold white", min_width=14)
        final.add_column("Durum", min_width=12)
        final.add_column("Ürün",  justify="right", style="bold green", width=7)
        final.add_column("Süre",  justify="right", style="cyan", width=9)
        final.add_column("Hata",  style="dim red", min_width=30)

        for s in scrapers:
            icon, st, lbl = _STATUS[s.status]
            final.add_row(
                Text(icon, style=st), s.name, Text(lbl, style=st),
                str(s.count) if s.count else "-", f"{s.elapsed:.1f}s", s.error[:50],
            )

        console.print()
        console.print(final)
        console.print()
        saved_line = (
            f"[dim]Kaydedildi → {OUTPUT_JSON}[/dim]"
            if save else
            "[dim yellow]Kaydetme devre dışı (--no-save)[/dim yellow]"
        )
        console.print(Panel(
            f"[bold green]✓  Toplam {len(_all_products)} ürün  ·  {total_elapsed:.1f}s[/bold green]\n"
            + saved_line,
            border_style="green",
            title="[bold green]ÖZET[/bold green]",
        ))
    else:
        await asyncio.gather(*aws, return_exceptions=True)
        print(f"\nToplam: {len(_all_products)} ürün")
        if save:
            print(f"Kaydedildi: {OUTPUT_JSON}")

# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Tüm scraper'ları çalıştır",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "sites", nargs="*", metavar="SITE",
        help="Çalıştırılacak siteler (boş = hepsi).\nGeçerli: "
             + ", ".join(s.key for s in ALL_SCRAPERS),
    )
    parser.add_argument("--no-save", action="store_true", help="output/ klasörüne kaydetme")
    args = parser.parse_args()

    use_api = True
    env_api = os.environ.get("USE_ENUCUZSISTEM_API")
    if env_api is not None:
        use_api = env_api.lower() in ("true", "1", "yes")
    elif not args.sites and sys.stdin.isatty():
        try:
            print("=" * 50)
            ans = input("EnUcuzSistem API kullanılsın mı? (E/h) [Varsayılan: E]: ").strip().lower()
            use_api = ans not in ("h", "n", "hayir", "no")
        except (KeyboardInterrupt, EOFError):
            use_api = True

    if args.sites:
        keys     = {k.lower() for k in args.sites}
        selected = [s for s in ALL_SCRAPERS if s.key in keys]
        if not selected:
            print(f"[HATA] Geçersiz site: {args.sites}")
            print("Geçerli:", ", ".join(s.key for s in ALL_SCRAPERS))
            sys.exit(1)
    else:
        if use_api:
            print("[INFO] EnUcuzSistem API kullanılıyor (~2880 ürün, hızlı).")
            selected = [s for s in ALL_SCRAPERS if s.key == "enucuzsistem"]
        else:
            print("[INFO] Bireysel mağaza scraper'ları çalıştırılıyor.")
            selected = [s for s in ALL_SCRAPERS if s.key != "enucuzsistem"]

    save = not args.no_save
    asyncio.run(main(selected, save))

    try:
        input("\n  Devam etmek için Enter'a basın...")
    except (EOFError, KeyboardInterrupt):
        pass
