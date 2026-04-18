import logging
import re
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

from registers.http_client import build_retry_session


logger = logging.getLogger(__name__)


ORSR_SEARCH_URL = "https://www.orsr.sk/search_ico.asp"
ORSR_RESULTS_URL = "https://www.orsr.sk/hladaj_ico.asp"
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
        oddiel_type = self._extract_oddiel_type(oddiel)  # Extrahovať typ

        parsed = {
            "ico": self._normalize_ico(self._first_value(sections.get("IČO")) or ico),
            "oddiel": oddiel,
            "oddiel_type": oddiel_type,  # Pridať typ
            "vlozka_cislo": vlozka,
            "obchodne_meno": self._first_value(sections.get("Obchodné meno"), default=""),
            "sidlo": "\n".join(sections.get("Sídlo", [])),
            "den_zapisu": self._parse_date(self._first_value(sections.get("Deň zápisu"))),
            "pravna_forma": self._first_value(sections.get("Právna forma"), default=""),
            "predmet_podnikania": sections.get("Predmet podnikania (činnosti)", []),
            "spolocnici": self._clean_persons(sections.get("Spoločníci", [])),
            "vklady_spolocnikov": sections.get("Výška vkladu každého spoločníka", []),
            "statutarny_organ": self._clean_persons(sections.get("Štatutárny orgán", [])),
            "prokura": self._clean_persons(sections.get("Prokúra", [])),
            "konanie": self._first_value(sections.get("Konanie menom spoločnosti"), default=""),  # Pre Sr/Sro
            "konanie_menom_spolocnosti": "\n".join(sections.get("Konanie menom spoločnosti", [])),
            "vyska_zakladneho_imania": "\n".join(sections.get("Výška základného imania", [])),
            "predstavenstvo": self._clean_persons(sections.get("Predstavenstvo", [])),  # Pre Dr
            "kontrolna_komisia": self._clean_persons(sections.get("Kontrolná komisia", [])),  # Pre Dr
            "zakladny_clensky_vklad": self._first_value(sections.get("Základný členský vklad"), default=""),  # Pre Dr
            "zapisovane_zakladne_imanie": self._first_value(sections.get("Zapisované základné imanie"), default=""),  # Pre Dr
            "dalske_pravne_skutocnosti": "\n".join(sections.get("Ďalšie právne skutočnosti", [])),  # Pre Dr
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
            if len(cells) < 1:
                continue

            first_cell = self._clean_text(cells[0].get_text(" ", strip=True))

            if first_cell.endswith(":"):
                current_key = first_cell.rstrip(":").strip()
                key = current_key
                sections.setdefault(key, [])
                values = self._extract_value_lines_from_cells(cells[1:])
            else:
                # Pokračovanie predchádzajúcej sekcie - ORSR často rozseká hodnoty do ďalších riadkov.
                if not current_key:
                    continue
                values = self._extract_value_lines_from_cells(cells)

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

    def _extract_oddiel_and_vlozka(self, text: str) -> Tuple[str, str]:
        match = self.ODDIEL_PATTERN.search(text)
        if not match:
            return "", ""
        return self._clean_text(match.group("oddiel")), self._clean_text(match.group("vlozka"))

    def _extract_oddiel_type(self, oddiel_text: str) -> str:
        """Extrahovať typ ORSR z textu oddiel (Sr, Sro, Dr, VS, KS, atď.)"""
        if not oddiel_text:
            return ""
        text = oddiel_text.strip().lower()
        # Najprv skúšame presné zhody
        for variant in ['sro', 'sr', 'dr', 'vs', 'ks', 'as']:
            if text == variant:
                return variant
            # Alebo začína s variant
            if text.startswith(variant) and (len(text) == len(variant) or text[len(variant)].isspace()):
                return variant
        # Ako záloha vráť prvé slovo
        return text.split()[0] if text else ""

    def _extract_value_lines_from_cells(self, cells) -> List[str]:
        text = "\n".join(cell.get_text("\n", strip=True) for cell in cells)
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

    def _clean_persons(self, persons: List[str]) -> List[str]:
        """
        Extrahuje iba mená osôb bez adries, rolí a metadát.

        ORSR bloky sú často „ploché“:
        - `konateľ`
        - `Martin`
        - `Močko`
        - `Nálepkova`
        - `7847/32A`
        - `Piešťany 921 01`
        - `Vznik funkcie: 23.04.2015`

        Z každého bloku chceme uložiť iba meno + priezvisko a bloky deduplikovať.
        """
        if not persons:
            return []

        cleaned: List[str] = []
        seen_names = set()
        current_name_parts: List[str] = []
        in_address_block = False

        def flush_current_name() -> None:
            if len(current_name_parts) < 2:
                current_name_parts.clear()
                return
            token_limit = 3 if self._starts_with_title(current_name_parts) else 2
            if len(current_name_parts) < token_limit:
                current_name_parts.clear()
                return
            name = " ".join(current_name_parts[:token_limit])
            current_name_parts.clear()
            if name not in seen_names:
                cleaned.append(name)
                seen_names.add(name)

        for raw_line in persons:
            line = self._clean_text(raw_line)
            if not line:
                continue

            if self._is_metadata_line(line) or self._is_metadata_start(line):
                flush_current_name()
                in_address_block = False
                continue

            if line.lower() in {"konateľ", "spoločník", "prokurista", "prokúra", "člen"}:
                continue

            if in_address_block:
                continue

            if self._is_address_component(line):
                flush_current_name()
                in_address_block = True
                continue

            clean_line = self._remove_position_and_metadata(line).strip()
            if not clean_line or self._is_address_component(clean_line):
                continue

            if not self._looks_like_name_token(clean_line):
                continue

            # Ak je meno už v jednom riadku (napr. "Lukáš Jurica"),
            # ulož ho hneď a prepneme sa do režimu preskakovania adresy.
            if len(clean_line.split()) >= 2:
                if self._is_incomplete_titled_name(clean_line):
                    # Napr. "Ing. Martin" -> priezvisko často nasleduje na ďalšom riadku.
                    current_name_parts = clean_line.split()
                    in_address_block = False
                    continue
                if clean_line not in seen_names:
                    cleaned.append(clean_line)
                    seen_names.add(clean_line)
                current_name_parts.clear()
                in_address_block = True
                continue

            current_name_parts.append(clean_line)

            # ORSR v týchto blokoch prakticky používa meno + priezvisko.
            # Pri tituloch čakáme na 3 tokeny (Ing. Martin Backo), inak 2 tokeny.
            required_tokens = 3 if self._starts_with_title(current_name_parts) else 2
            if len(current_name_parts) == required_tokens:
                flush_current_name()
                in_address_block = True

        flush_current_name()
        return cleaned

    def _starts_with_title(self, tokens: List[str]) -> bool:
        if not tokens:
            return False
        first = tokens[0].lower().rstrip('.')
        return first in {
            'ing', 'mgr', 'bc', 'mudr', 'judr', 'phdr', 'rndr',
            'mvdr', 'doc', 'prof', 'arch', 'paeddr', 'thdr', 'pharmdr'
        }

    def _is_incomplete_titled_name(self, text: str) -> bool:
        tokens = text.split()
        return len(tokens) == 2 and self._starts_with_title(tokens)

    def _looks_like_name_token(self, text: str) -> bool:
        if not text:
            return False
        if any(ch.isdigit() for ch in text):
            return False
        if text.lower() in {"konateľ", "spoločník", "prokurista", "prokúra", "vznik", "funkcie"}:
            return False
        return text[0].isalpha() and text[0].isupper()
    
    def _is_metadata_start(self, line: str) -> bool:
        """Detekuje začiatok metadátového riadku"""
        line_lower = line.lower()
        return any(marker in line_lower for marker in [
            'vznik', 'zaniknute', 'funkcie', 'od:', 'do:',
            'podľa', 'zápisu', 'osoba je', 'prokurista je',
            'je oprávnen', 'je stotožnen'
        ])

    def _is_metadata_line(self, line: str) -> bool:
        """Detekuje metadata riadky (pozície, dátumy)"""
        line_lower = line.lower()
        # Samostatné riadky s pozíciou (bez mena)
        if re.fullmatch(
            r"(konateľ|spoločník|prokurista|prokúra|predstavenstvo|kontrolná komisia|riaditeľ|prezident|chairman|director|člen)",
            line_lower.strip(),
        ):
            return True
        # Dátumy v zátvorke
        if re.search(r'\(od:|od:\s*\d{2}\.\d{2}\.\d{4}', line):
            return True
        return False

    def _is_address_component(self, line: str) -> bool:
        """Detekuje, či je to komponenta adresy (nie meno osôb)"""
        if re.search(r"\b\d{3}\s?\d{2}\b", line):
            return True
        # Číslo domu (7847/32A, č. 5, ul. 2, etc)
        if re.search(r'^\d+/\d+|^\d+\s*[a-zA-Z]?$|č\.|č\.p\.|č\.o\.', line):
            return True
        # Mestnosť (väčšinou veľké písmeno + položka bez čiary)
        if re.match(r'^[A-Z][a-ž]+$', line) and len(line.split()) == 1:
            # Skontroluj, či to nie je typické priezvisko
            if len(line) < 3 or line in ['Ul', 'Ulica']:
                return True
        return False

    def _remove_position_and_metadata(self, line: str) -> str:
        """Odstráni pozície a metadáta z riadku"""
        # Odstráni metadáta v zátvorke (od: dátum, do: dátum)
        line = re.sub(r"\s*\([^)]*\)\s*$", "", line).strip()

        # Odstráni pozície na začiatku
        # Pozície: konateľ, spoločník, generálny riaditeľ, atď.
        positions_pattern = (
            r"^(konateľ|spoločník|generálny\s+riaditeľ|riaditeľ|"
            r"prezident|výkonný|vedúci|vedúcej|chairman|director|člen|"
            r"member|členovia|zástupca|zástupcom)\s+"
        )
        line = re.sub(positions_pattern, "", line, flags=re.IGNORECASE).strip()

        # Odstráni trailing rolu za menom, napr.:
        # "Ing. Pavol Výboch - Člen predstavenstva" -> "Ing. Pavol Výboch"
        line = re.sub(
            r"\s*-\s*(predseda\s+predstavenstva|člen\s+predstavenstva|predseda|člen|konateľ|prokurista|riaditeľ).*$",
            "",
            line,
            flags=re.IGNORECASE,
        ).strip()

        return line


class OrsrScraper:
    """Klient pre vyhľadanie ORSR výpisu podľa IČO."""

    def __init__(self, timeout: int = 25):
        self.timeout = timeout
        self.session = build_retry_session(
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; CistaFirmaBot/1.0; +https://www.cistafirma.sk)",
                "Accept-Language": "sk-SK,sk;q=0.9,en;q=0.8",
            },
            total_retries=4,
            backoff_factor=0.6,
        )
        self.parser = OrsrHtmlParser()

    def fetch_by_ico(self, ico: str) -> OrsrScrapeResult:
        normalized_ico = re.sub(r"\D", "", ico or "").zfill(8)

        # ORSR search form (search_ico.asp) submituje GET na hladaj_ico.asp s parametrom ICO.
        attempts = [{"ICO": normalized_ico}, {"ico": normalized_ico}, {"Ico": normalized_ico}]

        last_html = ""
        last_url = ORSR_SEARCH_URL

        for params in attempts:
            try:
                response = self.session.get(ORSR_RESULTS_URL, params=params, timeout=self.timeout)
                response.raise_for_status()
                response.encoding = "cp1250"
                last_html = response.text
                last_url = response.url

                detail_url = self._extract_detail_url(last_html)
                if detail_url:
                    detail_response = self.session.get(detail_url, timeout=self.timeout)
                    detail_response.raise_for_status()
                    detail_response.encoding = "cp1250"
                    last_html = detail_response.text
                    last_url = detail_response.url

                if self._looks_like_company_extract(last_html):
                    parsed = self.parser.parse(last_html, normalized_ico)
                    return OrsrScrapeResult(ico=normalized_ico, source_url=last_url, parsed=parsed)
            except requests.exceptions.RequestException as exc:
                logger.warning("ORSR fetch attempt failed for ICO %s (%s): %s", normalized_ico, params, exc)
                continue

        raise OrsrScraperError(
            f"ORSR data pre IČO {normalized_ico} sa nepodarilo získať. Posledná URL: {last_url}"
        )

    def _extract_detail_url(self, html: str) -> Optional[str]:
        soup = BeautifulSoup(html, "html.parser")
        # Prefer explicit ORSR detail endpoints from search results.
        for link in soup.find_all("a", href=True):
            href = link["href"]
            href_l = href.lower()
            if "vypis.asp" in href_l or "zbl.asp" in href_l:
                return requests.compat.urljoin(ORSR_BASE_URL, href)
            if "sid=" in href_l and "id=" in href_l:
                return requests.compat.urljoin(ORSR_BASE_URL, href)
        return None

    def _looks_like_company_extract(self, html: str) -> bool:
        probe = html.lower()
        return (
            ("obchodn" in probe and "meno" in probe)
            and ("oddiel" in probe or "vložka" in probe or "vypis z obchodn" in probe)
        )
