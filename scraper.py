"""
Playwright-based scraper for https://edikte.justiz.gv.at
Supports all three search modes: Einfache Suche, Aktenzeichen, Erweiterte Suche.

Field mappings confirmed by live DOM inspection (Feb 2026):
  Einfach:      VKat (select-multiple), VOrt, VPLZ, BL (select-one)
                datum-submit-buttons for specific publication dates
  Aktenzeichen: Ger (select-one), GA (text), GZ (select-one), Zahl (id=AZ), Jahr (select-one)
  Erweitert:    FT (text), VKat, VWert (select-one), VVDat1/VVDat2 (text dates),
                VOrt, VPLZ, BL
  Submit:       input[name='sebut'] (regular) | input[name='datum'] (date-filtered)
"""

import asyncio
import logging
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

from playwright.async_api import async_playwright, Page, Browser, TimeoutError as PWTimeout

import config

logger = logging.getLogger(__name__)

SEARCH_MODES = {
    "einfach":      "https://edikte.justiz.gv.at/edikte/ex/exedi3.nsf/suche!OpenForm&subf=eex",
    "aktenzeichen": "https://edikte.justiz.gv.at/edikte/ex/exedi3.nsf/suche!OpenForm&subf=a",
    "erweitert":    "https://edikte.justiz.gv.at/edikte/ex/exedi3.nsf/suche!OpenForm&subf=vex",
}

# ── Value maps (UI label → site value) ─────────────────────────────────────
KATEGORIE_MAP: dict[str, str] = {
    "Eigenheim":        "EH",
    "Zweifamilienhaus": "ZH",
    "Mehrfamilienhaus": "MH",
    "Mietwohnhaus":     "MW",
    "Eigentumswohnung": "EW",
    "Gewerbeimmobilie": "GL",
    "Grundstück":       "UL",
    "Landwirtschaft":   "LF",
    "Sonstiges":        "SO",
    # extra aliases
    "Einfamilienhaus":  "EH",
    "Dachterrassenwohnung": "DTW",
    "Dachgeschoßwohnung":   "DGW",
    "Garconniere":      "GA",
    "Gartenwohnung":    "GW",
    "Reihenhaus":       "RH",
    "Superädifikat":    "SE",
    "Baurecht":         "BR",
}

BUNDESLAND_MAP: dict[str, str] = {
    "Wien":             "0",
    "Niederösterreich": "1",
    "Oberösterreich":   "3",
    "Steiermark":       "5",
    "Tirol":            "7",
    "Salzburg":         "4",
    "Kärnten":          "6",
    "Vorarlberg":       "8",
    "Burgenland":       "2",
}

# Maps the short UI labels to site court codes (from live Ger select options)
GERICHT_MAP: dict[str, str] = {
    "BG Döbling":       "015",
    "BG Favoriten":     "011",
    "BG Floridsdorf":   "016",
    "BG Graz-West":     "641",
    "BG Innsbruck":     "811",
    "BG Klagenfurt":    "721",
    "BG Linz":          "452",
    "BG Salzburg":      "565",
    "BG Innere Stadt":  "001",
    "BG Fünfhaus":      "013",
    "BG Hernals":       "014",
    "BG Hietzing":      "012",
    "BG Josefstadt":    "028",
    "BG Liesing":       "018",
    "BG Meidling":      "081",
    "BG Mödling":       "161",
}


class EdikteScraper:
    def __init__(self):
        self._playwright = None
        self._browser: Optional[Browser] = None

    async def __aenter__(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=config.HEADLESS,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        return self

    async def __aexit__(self, *_):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    # ── Public API ──────────────────────────────────────────────────────────

    async def search(self, params: dict) -> list[dict]:
        """
        Execute a search and return a list of result dicts.
        params keys:
          mode: "einfach" | "aktenzeichen" | "erweitert"
          -- einfach --
          kategorie, ort, plz, bundesland, seit (date string)
          -- aktenzeichen --
          aktenzeichen, gericht
          -- erweitert --
          kategorie, ort, plz, bundesland, seit, gericht, freitext
        """
        mode = params.get("mode", "einfach")
        url = SEARCH_MODES.get(mode, SEARCH_MODES["einfach"])

        ctx = await self._browser.new_context(
            accept_downloads=True,
            viewport={"width": 1400, "height": 900},
        )
        page = await ctx.new_page()
        page.set_default_timeout(config.SCRAPER_TIMEOUT)

        try:
            logger.info("Opening search page: %s", url)
            await page.goto(url, wait_until="networkidle")
            await self._fill_search_form(page, mode, params)
            results = await self._collect_results(page)
            logger.info("Found %d results – fetching detail pages …", len(results))
        finally:
            await ctx.close()

        # ── Fetch each detail page to get full metadata (Aktenzeichen, Gericht,
        #    Versteigerungstermin, Mindestgebot, Schätzwert, …) ──────────────
        enriched: list[dict] = []
        detail_ctx = await self._browser.new_context(
            accept_downloads=True,
            viewport={"width": 1400, "height": 900},
        )
        detail_page = await detail_ctx.new_page()
        detail_page.set_default_timeout(config.SCRAPER_TIMEOUT)
        try:
            for i, entry in enumerate(results):
                url_d = entry.get("detail_url", "")
                if not url_d:
                    enriched.append(entry)
                    continue
                try:
                    logger.info("[%d/%d] Fetching detail: %s", i + 1, len(results), url_d)
                    await detail_page.goto(url_d, wait_until="networkidle")
                    detail = await self._parse_detail(detail_page, url_d)
                    # Merge: detail values take priority over the basic search-row values
                    merged = {**entry, **{k: v for k, v in detail.items() if v}}
                    enriched.append(merged)
                except Exception as e:
                    logger.warning("Detail fetch failed for %s: %s", url_d, e)
                    enriched.append(entry)
        finally:
            await detail_ctx.close()

        logger.info("Detail fetch complete – %d entries enriched", len(enriched))
        return enriched

    async def fetch_detail(self, detail_url: str) -> dict:
        """Scrape a single Edikt detail page. Returns enriched metadata dict."""
        ctx = await self._browser.new_context(
            accept_downloads=True,
            viewport={"width": 1400, "height": 900},
        )
        page = await ctx.new_page()
        page.set_default_timeout(config.SCRAPER_TIMEOUT)
        try:
            await page.goto(detail_url, wait_until="networkidle")
            return await self._parse_detail(page, detail_url)
        finally:
            await ctx.close()

    async def download_gutachten(self, detail_url: str, edikt_id: int) -> Optional[Path]:
        """Download the Langgutachten PDF from a detail page. Returns local path."""
        config.DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
        ctx = await self._browser.new_context(
            accept_downloads=True,
            viewport={"width": 1400, "height": 900},
        )
        page = await ctx.new_page()
        page.set_default_timeout(config.SCRAPER_TIMEOUT)
        try:
            await page.goto(detail_url, wait_until="networkidle")
            pdf_path = await self._download_pdf(page, edikt_id)
            return pdf_path
        finally:
            await ctx.close()

    # ── Form filling ────────────────────────────────────────────────────────

    async def _fill_search_form(self, page: Page, mode: str, params: dict):
        if mode == "einfach":
            await self._fill_einfach(page, params)
        elif mode == "aktenzeichen":
            await self._fill_aktenzeichen(page, params)
        elif mode == "erweitert":
            await self._fill_erweitert(page, params)

        # ── Submit ──────────────────────────────────────────────────────────
        # For "Heute" / "Gestern" in einfach/erweitert, try to click the
        # matching publication-date button (input[name='datum']).
        # Otherwise click the regular Suchen button (input[name='sebut']).
        seit = params.get("seit", "")
        clicked = False
        if seit in ("Heute", "Gestern"):
            target_date = date.today() if seit == "Heute" else date.today() - timedelta(days=1)
            date_str = target_date.strftime("%d.%m.%Y")
            try:
                btn = await page.query_selector(f"input[name='datum'][value='{date_str}']")
                if btn:
                    await btn.click(timeout=5000)
                    clicked = True
                    logger.info("Clicked datum button: %s", date_str)
            except Exception as e:
                logger.debug("datum button click failed: %s", e)

        if not clicked:
            try:
                await page.click("input[name='sebut']", timeout=5000)
                clicked = True
            except PWTimeout:
                pass

        if not clicked:
            # Last resort fallback
            for sel in ["input[type='submit']", "button[type='submit']"]:
                try:
                    await page.click(sel, timeout=3000)
                    clicked = True
                    break
                except PWTimeout:
                    continue

        # Wait for results
        try:
            await page.wait_for_load_state("networkidle", timeout=30000)
        except PWTimeout:
            pass

    async def _fill_einfach(self, page: Page, params: dict):
        """Fill the simple search form using exact field IDs from DOM inspection."""
        # VKat – select-multiple, use value code
        kat_val = KATEGORIE_MAP.get(params.get("kategorie", ""), "")
        if kat_val:
            await self._try_select_by_value(page, "#VKat", kat_val)

        # VOrt, VPLZ – plain text inputs
        await self._try_fill(page, "#VOrt", params.get("ort", ""))
        await self._try_fill(page, "#VPLZ", params.get("plz", ""))

        # BL – select-one by numeric value
        bl_val = BUNDESLAND_MAP.get(params.get("bundesland", ""), "")
        if bl_val:
            await self._try_select_by_value(page, "#BL", bl_val)

    async def _fill_aktenzeichen(self, page: Page, params: dict):
        """Fill the Aktenzeichen search form using exact field IDs from DOM inspection.

        Accepts either:
          - structured dict keys: gericht, ga, gz, zahl, jahr
          - raw aktenzeichen string (e.g. "3 E 456/23w") that gets auto-parsed
        """
        # Gericht (Ger dropdown) – by value code
        ger_val = GERICHT_MAP.get(params.get("gericht", ""), "")
        if ger_val:
            await self._try_select_by_value(page, "#Ger", ger_val)

        # Try to use direct keys first, then parse the raw aktenzeichen string
        ga   = params.get("ga", "")
        gz   = params.get("gz", "")
        zahl = params.get("zahl", "")
        jahr = params.get("jahr", "")

        az_raw = params.get("aktenzeichen", "")
        if az_raw and not (ga or gz or zahl or jahr):
            # Parse "3 E 456/23w"  →  ga=3, gz=E, zahl=456, jahr=2023
            m = re.match(r'(\d+)\s+([A-Za-z]+)\s+(\d+)/(\d{2,4})', az_raw.strip())
            if m:
                ga, gz, zahl, yr = m.groups()
                year_int = int(yr)
                if year_int < 100:
                    year_int += 2000
                jahr = str(year_int)
            else:
                # Might be just a number – put it in Zahl
                zahl = az_raw.strip()

        if ga:
            await self._try_fill(page, "#GA", ga)
        if gz:
            await self._try_select_by_value(page, "#GZ", gz.upper())
        if zahl:
            await self._try_fill(page, "#AZ", zahl)   # id=AZ, name=Zahl
        if jahr:
            await self._try_select_by_value(page, "#Jahr", str(jahr))

    async def _fill_erweitert(self, page: Page, params: dict):
        """Fill the advanced search form using exact field IDs from DOM inspection."""
        # FT – Freitext / Suchtext
        await self._try_fill(page, "#FT", params.get("freitext", ""))

        # VKat, VOrt, VPLZ, BL – same as einfach
        await self._fill_einfach(page, params)

        # VWert – Schätzwert range (optional)
        vwert = params.get("schätzwert", params.get("wert", ""))
        if vwert:
            await self._try_select_by_value(page, "#VWert", vwert)

        # VVDat1 / VVDat2 – Versteigerungsdatum (optional), format DD.MM.YYYY
        await self._try_fill(page, "#VVDat1", params.get("datum_von", ""))
        await self._try_fill(page, "#VVDat2", params.get("datum_bis", ""))

    # ── Results collection ──────────────────────────────────────────────────

    async def _collect_results(self, page: Page) -> list[dict]:
        """Parse all result rows from the DataTables result table.

        The site renders results in a Bootstrap DataTable with id='DataTables_Table_0'.
        All results appear to be loaded on a single page (up to SearchMax=4999).
        """
        rows = await self._parse_result_rows(page)
        logger.info("Collected %d results", len(rows))
        return rows

    async def _parse_result_rows(self, page: Page) -> list[dict]:
        """Extract individual result entries from #DataTables_Table_0 tbody.

        Table columns (confirmed by live DOM inspection, Feb 2026):
          col0: Nr.
          col1: Edikt und Datum  – link text = titel, href = detail_url,
                                   data-sort = veroeffentlicht date (DD.MM.YYYY)
          col2: Adresse und Kategorie(n)  – first line = adresse, second = kategorie
          col3: Objektbezeichnung          – object description
        """
        try:
            # Wait briefly for the table to render
            await page.wait_for_selector("#DataTables_Table_0 tbody tr", timeout=10000)
        except PWTimeout:
            logger.warning("Result table #DataTables_Table_0 not found – trying generic fallback")
            return await self._parse_result_rows_fallback(page)

        raw_rows = await page.eval_on_selector_all(
            "#DataTables_Table_0 tbody tr",
            """els => els.map(r => {
                const cells = Array.from(r.querySelectorAll('td'));
                const col1  = cells[1] || {};
                const link  = col1.querySelector ? col1.querySelector('a[href]') : null;
                const col2txt = cells[2] ? cells[2].innerText.trim() : '';
                const col2parts = col2txt.split('\\n').map(s => s.trim()).filter(Boolean);
                return {
                    titel:          link ? link.innerText.trim() : '',
                    detail_url:     link ? link.href : '',
                    veroeffentlicht: col1.getAttribute ? (col1.getAttribute('data-sort') || '') : '',
                    adresse:        col2parts[0] || '',
                    kategorie_text: col2parts.slice(1).join(', '),
                    beschreibung:   cells[3] ? cells[3].innerText.trim() : '',
                };
            })"""
        )

        results = []
        for r in raw_rows:
            if not r.get("detail_url"):
                continue
            results.append({
                "detail_url":    r["detail_url"],
                "titel":         r["titel"],
                "veroeffentlicht": r["veroeffentlicht"],
                "adresse":       r["adresse"],
                "kategorien":    r["kategorie_text"],
                "beschreibung":  r["beschreibung"],
                # Fields filled in later via fetch_detail:
                "aktenzeichen":  "",
                "gericht":       "",
                "versteigerung": "",
                "mindestgebot":  "",
                "status":        "scraped",
            })

        # De-duplicate by URL
        seen: set[str] = set()
        unique = []
        for r in results:
            if r["detail_url"] not in seen:
                seen.add(r["detail_url"])
                unique.append(r)
        return unique

    async def _parse_result_rows_fallback(self, page: Page) -> list[dict]:
        """Generic row parser used when DataTables table is not found."""
        results = []
        rows = await page.query_selector_all("table tr")
        for row in rows:
            try:
                cells = await row.query_selector_all("td")
                if len(cells) < 2:
                    continue
                link_el = await row.query_selector("a[href]")
                if not link_el:
                    continue
                href = await link_el.get_attribute("href") or ""
                if href and not href.startswith("http"):
                    href = urljoin(config.EDIKTE_BASE_URL, href)
                if not href:
                    continue
                title = (await link_el.inner_text()).strip()
                texts = [(await c.inner_text()).strip() for c in cells]
                results.append({
                    "detail_url":    href,
                    "titel":         title or texts[0],
                    "adresse":       texts[2] if len(texts) > 2 else "",
                    "kategorien":    "",
                    "beschreibung":  texts[3] if len(texts) > 3 else "",
                    "veroeffentlicht": "",
                    "aktenzeichen":  "",
                    "gericht":       "",
                    "versteigerung": "",
                    "mindestgebot":  "",
                    "status":        "scraped",
                })
            except Exception as e:
                logger.debug("Fallback row parse error: %s", e)
        seen: set[str] = set()
        unique = []
        for r in results:
            if r["detail_url"] not in seen:
                seen.add(r["detail_url"])
                unique.append(r)
        return unique

    # ── Detail page ─────────────────────────────────────────────────────────

    async def _parse_detail(self, page: Page, url: str) -> dict:
        """Extract all relevant metadata from a detail page.

        The page body text has the format:
            Label:\n\nValue\n\nNextLabel:\n\nValue ...
        with the brief header block before the first label.
        """
        text = await page.eval_on_selector("body", "el => el.innerText")

        def field(pattern: str, default: str = "") -> str:
            m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if not m:
                return default
            # Grab first non-blank line from the group
            val = m.group(1).strip()
            return val.split("\n")[0].strip()

        # Title: the body starts with nav text + header block.
        # "BG Döbling, 015 26 E 27/24y\nVerschiebung - ...\nBerichtigte Fassung\n"
        # The actual Edikt title is on the second or third line of that block.
        title = ""
        title_m = re.search(
            r"Gerichtliche Versteigerungen\s+.+?\n(.+?)(?:\nBerichtigte Fassung)?(?:\nDienststelle)",
            text, re.DOTALL
        )
        if title_m:
            title_lines = [l.strip() for l in title_m.group(1).strip().splitlines() if l.strip()]
            title = " – ".join(title_lines[-2:]) if len(title_lines) >= 2 else (title_lines[0] if title_lines else "")

        versteigerung_termin = field(r"Neuer Versteigerungstermin:\s+\n+\s*(.+)")
        if not versteigerung_termin:
            versteigerung_termin = field(r"Versteigerungstermin:\s+\n+\s*(.+)")

        liegenschaft_adresse = field(r"Liegenschaftsadresse:\s+\n+\s*(.+)")
        plz_ort              = field(r"PLZ/Ort:\s+\n+\s*(.+)")
        adresse_full = f"{liegenschaft_adresse}, {plz_ort}".strip(", ") if (liegenschaft_adresse or plz_ort) else ""

        # Kundmachungsdatum: try several field labels used on different page variants
        kundmachung = field(r"Kundmachungsdatum:\s+\n+\s*(.+)")
        if not kundmachung:
            kundmachung = field(r"Erscheinungsdatum:\s+\n+\s*(.+)")
        if not kundmachung:
            kundmachung = field(r"Ver\xf6ffentlicht am:\s+\n+\s*(.+)")
        # Letzte Änderung am is the last-modified date, NOT the publication date –
        # stored separately so both are available without confusing them.
        letzte_aenderung = field(r"Letzte .nderung am:\s+\n+\s*(.+)")

        return {
            "detail_url":       url,
            "titel":            title,
            "aktenzeichen":     field(r"Aktenzeichen:\s+\n+\s*(.+)"),
            "gericht":          field(r"Dienststelle:\s+\n+\s*(.+)"),
            "veroeffentlicht":  kundmachung or letzte_aenderung,
            "letzte_aenderung": letzte_aenderung,
            "versteigerung":    versteigerung_termin,
            "adresse":       adresse_full,
            "kategorien":    field(r"Kategorie\(n\):\s+\n+\s*(.+)"),
            "mindestgebot":  field(r"Geringstes Gebot:\s+\n+\s*([\d\.,\s]+EUR)"),
            "schätzwert":    field(r"Schätzwert:\s+\n+\s*([\d\.,\s]+EUR)"),
            "objektgröße":   (
                field(r"Objektgr\xf6\xdfe:\s+\n+\s*(.+)")
                or field(r"Gesamtfl\xe4che:\s+\n+\s*([\d\.,\s]+m\xb2[^\n]*)")
                or field(r"Nutzfl\xe4che:\s+\n+\s*([\d\.,\s]+m\xb2[^\n]*)")
                or field(r"Wohnfl\xe4che:\s+\n+\s*([\d\.,\s]+m\xb2[^\n]*)")
                or field(r"Grundfl\xe4che:\s+\n+\s*([\d\.,\s]+m\xb2[^\n]*)")
                or field(r"Grundst\xfccksfl\xe4che:\s+\n+\s*([\d\.,\s]+m\xb2[^\n]*)")
            ),
            "beschreibung":  field(r"Beschreibung[^:]*:\s+\n+\s*(.{0,1000})", "")[:1000],
        }

    async def _download_pdf(self, page: Page, edikt_id: int) -> Optional[Path]:
        """Find and download the Langgutachten PDF via $file attachment links."""
        # Priority selectors – confirmed by live inspection:
        # PDF attachments are served as /$file/... links
        pdf_selectors = [
            "a[href*='$file'][href*='pdf']",
            "a[href*='$file'][href*='PDF']",
            "a:text-matches('Langgutachten.*pdf', 'i')",
            "a:has-text('Langgutachten')",
            "a[href*='$file']",            # any attachment as fallback
            "a[href*='.pdf']",
            "a[href*='Gutachten']",
            "a[href*='gutachten']",
            "a:has-text('Langtext')",
            "a:has-text('PDF')",
        ]

        for selector in pdf_selectors:
            try:
                els = await page.query_selector_all(selector)
                for el in els:
                    href = await el.get_attribute("href") or ""
                    if not href:
                        continue
                    if not href.startswith("http"):
                        href = urljoin(config.EDIKTE_BASE_URL, href)

                    dest = config.DOWNLOADS_DIR / f"gutachten_{edikt_id}.pdf"
                    try:
                        # Try Playwright download handler first
                        async with page.expect_download(timeout=30000) as dl_info:
                            await el.click()
                        download = await dl_info.value
                        await download.save_as(str(dest))
                        logger.info("Downloaded PDF to %s", dest)
                        return dest
                    except Exception:
                        # Fallback: direct HTTP fetch
                        if href.lower().endswith(".pdf") or "$file" in href:
                            import httpx
                            async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
                                r = await client.get(href)
                                if r.status_code == 200:
                                    dest.write_bytes(r.content)
                                    logger.info("Downloaded PDF via httpx to %s", dest)
                                    return dest
            except Exception as e:
                logger.debug("PDF selector %s failed: %s", selector, e)
                continue

        logger.warning("No PDF found for edikt_id=%s", edikt_id)
        return None

    # ── Helpers ─────────────────────────────────────────────────────────────

    async def _try_fill(self, page: Page, selector: str, value: str):
        if not value:
            return
        try:
            el = await page.query_selector(selector)
            if el:
                await el.fill(value)
        except Exception as e:
            logger.debug("_try_fill(%s) failed: %s", selector, e)

    async def _try_select_by_value(self, page: Page, selector: str, value: str):
        """Select a <select> option by its value attribute."""
        if not value:
            return
        try:
            el = await page.query_selector(selector)
            if el:
                await el.select_option(value=value)
        except Exception as e:
            logger.debug("_try_select_by_value(%s, %s) failed: %s", selector, value, e)

    async def _try_select_by_label(self, page: Page, selector: str, label: str):
        """Select a <select> option by its visible text (label)."""
        if not label:
            return
        try:
            el = await page.query_selector(selector)
            if el:
                await el.select_option(label=label)
        except Exception as e:
            logger.debug("_try_select_by_label(%s, %s) failed: %s", selector, label, e)
