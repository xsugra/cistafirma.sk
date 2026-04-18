import logging
import re
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)


ORSR_SEARCH_URL = "https://www.orsr.sk/search_ico.asp"
ORSR_BASE_URL = "https://www.orsr.sk"


class OrsrScraperError(Exception):
    pass


@dataclass
class OrsrScrapeResult:
    ico: str
    source_url: str
    parsed: Dict


class OrsrHtmlParser:
    """Parser pre ORSR HTML výpisy, ktoré sú často renderované v tabuľkách."""

    DATE_PATTERN = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")
    ODDIEL_PATTERN = re.compile(
        r"Oddiel:\s*(?P<oddiel>.*?)\s+Vložka\s+číslo:\s*(?P<vlozka>[^\n\r]+)",
        re.IGNORECASE,
    )

    def parse(self, html: str, ico: str) -> Dict:
        soup = BeautifulSoup(html, "html.parser")
        full_text = soup.get_text("\n", strip=True)

        sections = self._extract_sections_from_tables(soup)
        oddiel, vlozka = self._extract_oddiel_and_vlozka(full_text)

        parsed = {
            "ico": self._normalize_ico(self._first_value(sections.get("IČO")) or ico),
            "oddiel": oddiel,
            "vlozka_cislo": vlozka,
            "obchodne_meno": self._first_value(sections.get("Obchodné meno"), default=""),
            "sidlo": "\n".join(sections.get("Sídlo", [])),
            "den_zapisu": self._parse_date(self._first_value(sections.get("Deň zápisu"))),
            "pravna_forma": self._first_value(sections.get("Právna forma"), default=""),
            "predmet_podnikania": sections.get("Predmet podnikania (činnosti)", []),
            "spolocnici": sections.get("Spoločníci", []),
            "vklady_spolocnikov": sections.get("Výška vkladu každého spoločníka", []),
            "statutarny_organ": sections.get("Štatutárny orgán", []),
            "konanie_menom_spolocnosti": "\n".join(sections.get("Konanie menom spoločnosti", [])),
            "vyska_zakladneho_imania": "\n".join(sections.get("Výška základného imania", [])),
            "orsr_aktualizacia_dat": self._parse_date(self._first_value(sections.get("Dátum aktualizácie údajov"))),
            "orsr_datum_vypisu": self._parse_date(self._first_value(sections.get("Dátum výpisu"))),
            "raw_sections": sections,
        }
        return parsed

    def _extract_sections_from_tables(self, soup: BeautifulSoup) -> Dict[str, List[str]]:
        sections: Dict[str, List[str]] = {}
        current_key: Optional[str] = None

        for row in soup.select("tr"):
            cells = row.find_all("td")
            if len(cells) < 2:
                continue

            key_raw = self._clean_text(cells[0].get_text(" ", strip=True))
            values = self._extract_value_lines(cells[1])

            if key_raw:
                current_key = key_raw.rstrip(":").strip()
                sections.setdefault(current_key, [])

            if not current_key or not values:
                continue

            sections[current_key].extend(values)

        # Remove duplicate neighbour lines but keep order
        for key, lines in sections.items():
            compacted: List[str] = []
            for line in lines:
                if compacted and compacted[-1] == line:
                    continue
                compacted.append(line)
            sections[key] = compacted

        return sections

    def _extract_oddiel_and_vlozka(self, text: str) -> (str, str):
        match = self.ODDIEL_PATTERN.search(text)
        if not match:
            return "", ""
        return self._clean_text(match.group("oddiel")), self._clean_text(match.group("vlozka"))

    def _extract_value_lines(self, cell) -> List[str]:
        text = cell.get_text("\n", strip=True)
        lines = []
        for line in text.splitlines():
            normalized = self._clean_text(line)
            if not normalized:
                continue
            # ORSR metadata line e.g. "(od: 13.11.2024)"
            if re.match(r"^\(od:\s*.*\)$", normalized):
                continue
            lines.append(normalized)
        return lines

    def _first_value(self, values: Optional[List[str]], default: str = "") -> str:
        if not values:
            return default
        return values[0]

    def _normalize_ico(self, ico: str) -> str:
        return re.sub(r"\D", "", ico or "").zfill(8)

    def _parse_date(self, value: str) -> Optional[date]:
        if not value:
            return None
        cleaned = self._clean_text(value)
        if not self.DATE_PATTERN.match(cleaned):
            return None
        day, month, year = cleaned.split(".")
        return date(int(year), int(month), int(day))

    def _clean_text(self, value: str) -> str:
        return re.sub(r"\s+", " ", (value or "")).strip()


class OrsrScraper:
    """Klient pre vyhľadanie ORSR výpisu podľa IČO."""

    def __init__(self, timeout: int = 25):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (compatible; CistaFirmaBot/1.0; +https://www.cistafirma.sk)",
                "Accept-Language": "sk-SK,sk;q=0.9,en;q=0.8",
            }
        )
        self.parser = OrsrHtmlParser()

    def fetch_by_ico(self, ico: str) -> OrsrScrapeResult:
        normalized_ico = re.sub(r"\D", "", ico or "").zfill(8)

        # ORSR historically používal rôzne názvy parametra, skúsime viac variantov.
        attempts = [
            {"ICO": normalized_ico},
            {"ico": normalized_ico},
            {"Ico": normalized_ico},
        ]

        last_html = ""
        last_url = ORSR_SEARCH_URL

        for params in attempts:
            response = self.session.get(ORSR_SEARCH_URL, params=params, timeout=self.timeout)
            response.raise_for_status()
            last_html = response.text
            last_url = response.url

            detail_url = self._extract_detail_url(last_html)
            if detail_url:
                detail_response = self.session.get(detail_url, timeout=self.timeout)
                detail_response.raise_for_status()
                last_html = detail_response.text
                last_url = detail_response.url

            if self._looks_like_company_extract(last_html):
                parsed = self.parser.parse(last_html, normalized_ico)
                return OrsrScrapeResult(ico=normalized_ico, source_url=last_url, parsed=parsed)

        raise OrsrScraperError(
            f"ORSR data pre IČO {normalized_ico} sa nepodarilo získať. Posledná URL: {last_url}"
        )

    def _extract_detail_url(self, html: str) -> Optional[str]:
        soup = BeautifulSoup(html, "html.parser")
        # Search results often link to detailed extract pages.
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if "vypis" in href.lower() or "vl" in href.lower() or "sid=" in href.lower():
                return requests.compat.urljoin(ORSR_BASE_URL, href)
        return None

    def _looks_like_company_extract(self, html: str) -> bool:
        probe = html.lower()
        return "obchodné meno" in probe and ("oddiel" in probe or "vložka" in probe)

