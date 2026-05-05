import logging
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

from registers.http_client import build_retry_session


logger = logging.getLogger(__name__)


ORSR_SEARCH_URL = "https://www.orsr.sk/search_ico.asp"
ORSR_RESULTS_URL = "https://www.orsr.sk/hladaj_ico.asp"
ORSR_BASE_URL = "https://www.orsr.sk"


DATE_PATTERN = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")
OD_DATE_PATTERN = re.compile(r"\(\s*od:\s*(\d{2}\.\d{2}\.\d{4})\s*\)", re.IGNORECASE)
ODDIEL_PATTERN = re.compile(
    r"Oddiel:\s*(?P<oddiel>\S+)\s+Vložka\s+číslo:\s*(?P<vlozka>\S+(?:\s*/\s*\S+)?)",
    re.IGNORECASE,
)

FOOTER_DATES = {
    "aktualizacia": re.compile(r"Dátum aktualizácie údajov[:\s]*\n?\s*(\d{2}\.\d{2}\.\d{4})", re.IGNORECASE),
    "vypis": re.compile(r"Dátum výpisu[:\s]*\n?\s*(\d{2}\.\d{2}\.\d{4})", re.IGNORECASE),
}

PERSON_ROLE_TOKENS = {
    "konateľ", "konatelia", "spoločník", "spolocnik", "prokurista", "prokúra",
    "predstavenstvo", "kontrolná komisia", "dozorná rada", "člen predstavenstva",
    "predseda predstavenstva", "podpredseda predstavenstva",
    "člen dozornej rady", "predseda dozornej rady",
    "riaditeľ", "štatutárny orgán",
    # Družstvá: typ orgánu býva uvedený ako samostatné slovo v prvom podriadku
    "predseda", "podpredseda", "predseda družstva", "podpredseda družstva",
    "predseda a podpredseda",
}

# Tituly pred menom
TITLE_TOKENS = {
    "ing", "mgr", "bc", "mudr", "judr", "phdr", "rndr", "mvdr",
    "doc", "prof", "arch", "paeddr", "thdr", "pharmdr", "dr", "dipl",
}


class OrsrScraperError(Exception):
    pass


@dataclass
class OrsrEntry:
    """Jeden záznam v sekcii ORSR výpisu (napr. jedna osoba, jedna činnosť)."""

    lines: List[str] = field(default_factory=list)  # br-oddelene riadky
    od: str = ""  # (od: dd.mm.yyyy)
    link_name: str = ""  # meno extrahovane z <a class="lnm">

    @property
    def text(self) -> str:
        return " ".join(line for line in self.lines if line)


@dataclass
class OrsrScrapeResult:
    ico: str
    source_url: str
    parsed: Dict


class OrsrHtmlParser:
    """
    Parser pre ORSR HTML výpisy.

    ORSR stránka má konzistentnú štruktúru:
      - hlavný riadok (tr) sa identifikuje cez <span class="tl">Názov sekcie:</span>
      - druhý td obsahuje jednu alebo viac <table> elementov - každá tabuľka
        je práve jeden záznam (entry) danej sekcie
      - každý entry má pre obsah <span class="ra"> oddelené <br/>, datum "(od:)"
        je v samostatnom td
      - osoby majú <a class="lnm"> s menom zloženým z dvoch <span class="ra">
    """

    def parse(self, html: str, ico: str) -> Dict:
        soup = BeautifulSoup(html, "html.parser")
        sections = self._extract_sections(soup)
        footer_dates = self._extract_footer_dates(soup)

        oddiel, vlozka = self._extract_oddiel_and_vlozka(soup)
        oddiel_type = self._normalize_oddiel_type(oddiel)

        structured = self._build_structured(sections)

        return {
            "ico": self._normalize_ico(self._first_line(sections.get("IČO")) or ico),
            "oddiel": oddiel,
            "oddiel_type": oddiel_type,
            "vlozka_cislo": vlozka,
            "obchodne_meno": self._first_line(sections.get("Obchodné meno")),
            "sidlo": self._format_address(sections.get("Sídlo", [])),
            "den_zapisu": self._parse_date(self._first_line(sections.get("Deň zápisu"))),
            "pravna_forma": self._first_line(sections.get("Právna forma")),

            "predmet_podnikania": [e.text for e in sections.get("Predmet podnikania (činnosti)", []) if e.text],

            "spolocnici": [p["name"] for p in structured.get("spolocnici", []) if p.get("name")],
            "vklady_spolocnikov": [v["summary"] for v in structured.get("vklady_spolocnikov", []) if v.get("summary")],

            "statutarny_organ": [p["name"] for p in structured.get("statutarny_organ", []) if p.get("name")],
            "prokura": [p["name"] for p in structured.get("prokura", []) if p.get("name")],

            "predstavenstvo": [p["name"] for p in structured.get("predstavenstvo", []) if p.get("name")],
            "kontrolna_komisia": [p["name"] for p in structured.get("kontrolna_komisia", []) if p.get("name")],
            "dozorna_rada": [p["name"] for p in structured.get("dozorna_rada", []) if p.get("name")],
            "akcionari": [p["name"] for p in structured.get("akcionari", []) if p.get("name")],

            "konanie": self._join_section_text(sections.get("Konanie", [])),
            "konanie_menom_spolocnosti": self._join_section_text(sections.get("Konanie menom spoločnosti", [])),

            "vyska_zakladneho_imania": self._first_line(sections.get("Výška základného imania")),
            "zapisovane_zakladne_imanie": self._first_line(sections.get("Zapisované základné imanie")),
            "zakladny_clensky_vklad": self._join_section_text(sections.get("Základný členský vklad", [])),

            "akcie": [e.text for e in sections.get("Akcie", []) if e.text],

            "dalske_pravne_skutocnosti": self._join_section_text(sections.get("Ďalšie právne skutočnosti", [])),

            "orsr_aktualizacia_dat": self._parse_date(footer_dates.get("aktualizacia")),
            "orsr_datum_vypisu": self._parse_date(footer_dates.get("vypis")),

            "raw_sections": self._raw_sections(sections),
            "structured": structured,
        }

    # ---------------------------------------------------------------- extract

    def _extract_sections(self, soup: BeautifulSoup) -> Dict[str, List[OrsrEntry]]:
        """Zoberie každý vrchný TR, ktorý má v prvom TD <span class="tl">."""
        sections: Dict[str, List[OrsrEntry]] = {}

        for tr in soup.find_all("tr"):
            tds = tr.find_all("td", recursive=False)
            if len(tds) < 2:
                continue
            tl = tds[0].find("span", class_="tl")
            if not tl:
                continue
            key = tl.get_text(" ", strip=True).rstrip(":").strip()
            if not key:
                continue

            # inner content contains nested tables, každá = jeden entry
            nested = tds[1].find_all("table", recursive=False)
            entries: List[OrsrEntry] = []
            if nested:
                for inner in nested:
                    entry = self._parse_entry_table(inner)
                    if entry is not None:
                        entries.append(entry)
            else:
                # fallback: jeden entry priamo z td (nema nested)
                entry = self._parse_entry_from_element(tds[1])
                if entry is not None:
                    entries.append(entry)

            sections.setdefault(key, []).extend(entries)

        return sections

    def _parse_entry_table(self, table: Tag) -> Optional[OrsrEntry]:
        row = table.find("tr", recursive=False) or table.find("tr")
        if not row:
            return None
        tds = row.find_all("td", recursive=False)
        if not tds:
            return None
        content_td = tds[0]
        od_td = tds[1] if len(tds) >= 2 else None
        entry = self._parse_entry_from_element(content_td)
        if entry is None:
            return None
        if od_td is not None:
            od_text = od_td.get_text(" ", strip=True)
            match = OD_DATE_PATTERN.search(od_text)
            if match:
                entry.od = match.group(1)
        return entry

    def _parse_entry_from_element(self, element: Tag) -> Optional[OrsrEntry]:
        segments = self._split_by_br(element)
        lines: List[str] = []
        link_name = ""
        for seg in segments:
            text_parts: List[str] = []
            for piece in seg:
                if piece["is_link_name"]:
                    if not link_name:
                        link_name = piece["text"]
                if piece["text"]:
                    text_parts.append(piece["text"])
            line = self._normalize_whitespace(" ".join(text_parts))
            if line:
                lines.append(line)
        if not lines and not link_name:
            return None
        return OrsrEntry(lines=lines, link_name=link_name)

    def _split_by_br(self, element: Tag) -> List[List[Dict]]:
        """Rozdelí obsah elementu podľa <br/> značiek na logické riadky.

        Každý segment (riadok) je list dictov {text, is_link_name}.
        """
        segments: List[List[Dict]] = []
        current: List[Dict] = []

        def flush() -> None:
            nonlocal current
            if current:
                segments.append(current)
                current = []

        def handle(node) -> None:
            nonlocal current
            if isinstance(node, NavigableString):
                text = str(node).strip()
                if text:
                    current.append({"text": text, "is_link_name": False})
                return
            if not isinstance(node, Tag):
                return
            if node.name == "br":
                flush()
                return
            if node.name == "img":
                return
            if node.name == "a" and "lnm" in (node.get("class") or []):
                # Meno osoby: zober textu z vnutornych span.ra
                name_parts: List[str] = []
                for sp in node.find_all("span", class_="ra"):
                    part = sp.get_text(" ", strip=True)
                    if part:
                        name_parts.append(part)
                name = " ".join(name_parts) if name_parts else node.get_text(" ", strip=True)
                name = self._normalize_whitespace(name)
                if name:
                    current.append({"text": name, "is_link_name": True})
                return
            if node.name == "a":
                # priamy link (napr. icon wrapper), ignorujeme img a ine
                for child in node.children:
                    handle(child)
                return
            if node.name in ("span", "div", "font", "b", "i", "u", "strong", "em"):
                # rekurzívne
                for child in node.children:
                    handle(child)
                return
            # default fallback pre neznáme tagy - spracuj text
            text = node.get_text(" ", strip=True)
            if text:
                current.append({"text": text, "is_link_name": False})

        for child in element.children:
            handle(child)
        flush()
        return segments

    # ------------------------------------------------------------ structured

    def _build_structured(self, sections: Dict[str, List[OrsrEntry]]) -> Dict[str, List[Dict]]:
        """Prevedie sekcie na plne strukturovane zaznamy pre frontend."""
        result: Dict[str, List[Dict]] = {
            "statutarny_organ": [],
            "spolocnici": [],
            "vklady_spolocnikov": [],
            "prokura": [],
            "predstavenstvo": [],
            "kontrolna_komisia": [],
            "dozorna_rada": [],
            "akcionari": [],
            "predmet_podnikania": [],
            "dalsie_pravne_skutocnosti": [],
            "akcie": [],
        }

        # Statutárny orgán: obsahuje typ orgánu (konateľ/predstavenstvo) + ľudí
        stat_entries = sections.get("Štatutárny orgán", [])
        organ_type, stat_people = self._split_organ_header(stat_entries)
        result["statutarny_organ"] = [self._entry_to_person(e, default_role=organ_type) for e in stat_people]

        # Druzstvo: Predstavenstvo je niekedy samostatna sekcia
        if sections.get("Predstavenstvo"):
            _, preds = self._split_organ_header(sections.get("Predstavenstvo", []))
            result["predstavenstvo"] = [self._entry_to_person(e, default_role="člen predstavenstva") for e in preds]
        elif organ_type and "predstavenstv" in organ_type.lower():
            # Presmeruj štatutárov ako predstavenstvo (družstvá/a.s.)
            result["predstavenstvo"] = result["statutarny_organ"]

        if sections.get("Kontrolná komisia"):
            _, kk = self._split_organ_header(sections.get("Kontrolná komisia", []))
            result["kontrolna_komisia"] = [self._entry_to_person(e, default_role="člen kontrolnej komisie") for e in kk]

        if sections.get("Dozorná rada"):
            _, dr = self._split_organ_header(sections.get("Dozorná rada", []))
            result["dozorna_rada"] = [self._entry_to_person(e, default_role="člen dozornej rady") for e in dr]

        # Spoločníci - pri s.r.o., v.o.s., k.s.
        result["spolocnici"] = [self._entry_to_person(e, default_role="spoločník") for e in sections.get("Spoločníci", [])]

        # Akcionár - pri a.s.
        result["akcionari"] = [self._entry_to_person(e, default_role="akcionár") for e in sections.get("Akcionár", [])]

        # Prokúra - samostatná sekcia, tu môžu byť ale aj textové entries (popis oprávnenia)
        prokura_entries = sections.get("Prokúra", [])
        result["prokura"] = [self._entry_to_person(e, default_role="prokurista") for e in prokura_entries if self._is_person_entry(e)]
        result["prokura_oprávnenie"] = [e.text for e in prokura_entries if not self._is_person_entry(e) and e.text]

        # Vklady spoločníkov
        for e in sections.get("Výška vkladu každého spoločníka", []):
            result["vklady_spolocnikov"].append(self._entry_to_contribution(e))

        # Predmet podnikania
        for e in sections.get("Predmet podnikania (činnosti)", []):
            text = e.text.strip()
            if text:
                result["predmet_podnikania"].append({"text": text, "od": e.od})

        # Ďalšie právne skutočnosti
        for e in sections.get("Ďalšie právne skutočnosti", []):
            text = e.text.strip()
            if text:
                result["dalsie_pravne_skutocnosti"].append({"text": text, "od": e.od})

        # Akcie
        for e in sections.get("Akcie", []):
            text = e.text.strip()
            if text:
                result["akcie"].append({"text": text, "od": e.od})

        # Výška základného imania ako dict
        zi = sections.get("Výška základného imania", [])
        if zi:
            result["vyska_zakladneho_imania"] = self._entry_to_capital(zi[0])

        # Oddiel/Vlozka typu orgánu (pre UI)
        if organ_type:
            result["statutarny_organ_typ"] = organ_type

        # Konanie
        konanie_entries = sections.get("Konanie", []) or sections.get("Konanie menom spoločnosti", [])
        if konanie_entries:
            result["konanie"] = " ".join(e.text for e in konanie_entries if e.text)

        return result

    # ---------------------------------------------- entry -> person / etc.

    def _split_organ_header(
        self, entries: List[OrsrEntry]
    ) -> Tuple[str, List[OrsrEntry]]:
        """Prvý entry v "Štatutárny orgán" bežne obsahuje iba typ orgánu
        ("konateľ" / "predstavenstvo"), ostatné sú konkrétni ľudia."""
        if not entries:
            return "", []

        first = entries[0]
        first_text = first.text.strip()
        first_text_lower = first_text.casefold()

        if (
            first.link_name == ""
            and len(first.lines) == 1
            and (
                first_text_lower in {"konateľ", "konatelia", "konateľ/konatelia",
                                      "predstavenstvo", "riaditeľ", "štatutárny orgán"}
                or first_text_lower in PERSON_ROLE_TOKENS
            )
        ):
            return first_text, entries[1:]

        return "", entries

    def _is_person_entry(self, entry: OrsrEntry) -> bool:
        if entry.link_name:
            return True
        # detekuj osobu bez linku (zriedkavo, ale stáva sa v starších výpisoch)
        if not entry.lines:
            return False
        first = entry.lines[0]
        tokens = first.split()
        if len(tokens) < 2:
            return False
        if any(ch.isdigit() for ch in first):
            return False
        if not any(word[:1].isupper() for word in tokens if word):
            return False
        # Popisné vety (obvykle prokúra popis oprávnenia alebo konanie)
        lower = first.lower()
        if re.search(r"\b(je oprávnen|konatelia kon|koná v mene|konateľ je|je povinn|spoločnosti samost|predstavenstvom)", lower):
            return False
        # veta končiaca bodkou typicky nie je meno
        if first.rstrip().endswith(".") and len(tokens) > 3:
            return False
        return True

    def _entry_to_person(self, entry: OrsrEntry, default_role: str = "") -> Dict:
        """Premenuje entry na strukturu osoby/entity."""
        lines = list(entry.lines)
        name = entry.link_name
        title = ""
        role = ""
        vznik_funkcie = ""
        ine_id = ""
        ico_person = ""
        address_lines: List[str] = []
        note_lines: List[str] = []

        if lines:
            first_line = lines[0]
            # Ak máme linked meno, extrahuj titul pred menom a rolu za ním
            if name and name in first_line:
                before, _, after = first_line.partition(name)
                title = self._normalize_whitespace(before).rstrip(",").strip()
                role = self._clean_role_suffix(after)
            else:
                # Žiadny link - skusime rozdelit zo struktury riadku
                # (napr. družstvo s menom bez linku)
                parts = first_line.split(" - ", 1)
                core = parts[0]
                role = parts[1].strip() if len(parts) > 1 else ""
                name_tokens = core.split()
                # vyfiltruj tituly z začiatku
                titles: List[str] = []
                while name_tokens and self._looks_like_title(name_tokens[0]):
                    titles.append(name_tokens.pop(0))
                title = " ".join(titles)
                name = " ".join(name_tokens).strip()

        # Zvyšné riadky: adresa + vznik funkcie + ine id
        for line in lines[1:]:
            stripped = line.strip()
            if not stripped:
                continue
            lower = stripped.lower()
            if stripped.startswith("Vznik funkcie"):
                # "Vznik funkcie: 01.09.2023"
                m = re.search(r"(\d{2}\.\d{2}\.\d{4})", stripped)
                if m:
                    vznik_funkcie = m.group(1)
                continue
            if stripped.startswith("Iné identifikačné číslo"):
                ine_id = stripped.split(":", 1)[-1].strip()
                continue
            if stripped.startswith("IČO"):
                ico_person = re.sub(r"\D", "", stripped)
                continue
            if lower.startswith(("osoba je", "osoba má", "osoba ma", "prokurista je",
                                 "konateľ je", "konatelia")):
                note_lines.append(stripped)
                continue
            if "je oprávnen" in lower or "je stotožn" in lower:
                note_lines.append(stripped)
                continue
            address_lines.append(stripped)

        return {
            "name": self._normalize_whitespace(name),
            "title": title,
            "role": role or default_role,
            "address": self._format_address(address_lines),
            "address_lines": address_lines,
            "vznik_funkcie": vznik_funkcie,
            "ine_id": ine_id,
            "person_ico": ico_person,
            "od": entry.od,
            "notes": note_lines,
        }

    def _entry_to_contribution(self, entry: OrsrEntry) -> Dict:
        """Výška vkladu každého spoločníka -> {name, vklad, splatene, typ, currency}."""
        lines = entry.lines
        name = ""
        vklad = ""
        splatene = ""
        typ = ""
        currency = "EUR"

        if lines:
            # prvý riadok býva meno (dva span.ra tokeny)
            first = lines[0]
            # detekuj či prvý riadok obsahuje "Vklad:" (jednoriadkový zápis)
            if "Vklad:" in first or "vklad:" in first.lower():
                detail_line = first
            else:
                name = first
                detail_line = " ".join(lines[1:])

            # Vklad: X EUR ( peňažný vklad ) Splatené: Y EUR
            m_vklad = re.search(r"Vklad:\s*([\d\s.,]+)\s*(EUR|Sk)?", detail_line, re.IGNORECASE)
            if m_vklad:
                vklad = self._normalize_whitespace(m_vklad.group(1))
                if m_vklad.group(2):
                    currency = m_vklad.group(2)
            m_spl = re.search(r"Splatené:\s*([\d\s.,]+)\s*(EUR|Sk)?", detail_line, re.IGNORECASE)
            if m_spl:
                splatene = self._normalize_whitespace(m_spl.group(1))
            m_typ = re.search(r"\(\s*(peňažný vklad|nepeňažný vklad|peňažný|nepeňažný)\s*\)", detail_line, re.IGNORECASE)
            if m_typ:
                typ = m_typ.group(1).strip()

        summary_parts = []
        if name:
            summary_parts.append(name)
        if vklad:
            summary_parts.append(f"vklad {vklad} {currency}".strip())
        if splatene:
            summary_parts.append(f"splatené {splatene} {currency}".strip())
        if typ:
            summary_parts.append(f"({typ})")

        return {
            "name": self._normalize_whitespace(name),
            "vklad": vklad,
            "splatene": splatene,
            "typ": typ,
            "currency": currency,
            "od": entry.od,
            "summary": " • ".join(summary_parts),
        }

    def _entry_to_capital(self, entry: OrsrEntry) -> Dict:
        text = " ".join(entry.lines)
        # napr. "146 911 642,43511 EUR Rozsah splatenia: 146 911 642,43511 EUR"
        imanie = ""
        rozsah = ""
        currency = "EUR"
        m = re.search(r"([\d\s.,]+)\s*(EUR|Sk)", text)
        if m:
            imanie = self._normalize_whitespace(m.group(1))
            currency = m.group(2)
        m_ros = re.search(r"Rozsah splatenia:\s*([\d\s.,]+)\s*(EUR|Sk)?", text, re.IGNORECASE)
        if m_ros:
            rozsah = self._normalize_whitespace(m_ros.group(1))
        return {
            "imanie": imanie,
            "rozsah_splatenia": rozsah,
            "currency": currency,
            "raw": text,
            "od": entry.od,
        }

    # --------------------------------------------------------------- helpers

    def _extract_oddiel_and_vlozka(self, soup: BeautifulSoup) -> Tuple[str, str]:
        """Nájde Oddiel/Vložka - môže byť v hlavičke (span.tl) alebo vo full-texte."""
        # Prvý prístup: hlavička nad výpisom
        for tr in soup.find_all("tr"):
            tds = tr.find_all("td", recursive=False)
            if len(tds) < 2:
                continue
            tl0 = tds[0].find("span", class_="tl")
            tl1 = tds[1].find("span", class_="tl")
            if tl0 and "Oddiel" in tl0.get_text():
                oddiel_val = tds[0].find("span", class_="ra")
                vlozka_val = tds[1].find("span", class_="ra") if tl1 else None
                oddiel = oddiel_val.get_text(" ", strip=True) if oddiel_val else ""
                vlozka = vlozka_val.get_text(" ", strip=True) if vlozka_val else ""
                if oddiel or vlozka:
                    return (self._normalize_whitespace(oddiel), self._normalize_whitespace(vlozka))

        # Fallback: regex cez cely text
        text = soup.get_text(" ", strip=True)
        match = ODDIEL_PATTERN.search(text)
        if match:
            return (
                self._normalize_whitespace(match.group("oddiel")),
                self._normalize_whitespace(match.group("vlozka")),
            )
        return ("", "")

    def _extract_footer_dates(self, soup: BeautifulSoup) -> Dict[str, str]:
        text = soup.get_text("\n", strip=True)
        result: Dict[str, str] = {}
        for key, pattern in FOOTER_DATES.items():
            m = pattern.search(text)
            if m:
                result[key] = m.group(1)
        return result

    def _normalize_oddiel_type(self, oddiel: str) -> str:
        if not oddiel:
            return ""
        return oddiel.strip().split()[0].lower()

    def _normalize_whitespace(self, value: str) -> str:
        return re.sub(r"\s+", " ", (value or "")).strip()

    def _normalize_ico(self, value: str) -> str:
        return re.sub(r"\D", "", (value or "")).zfill(8)

    def _parse_date(self, value: Optional[str]) -> Optional[date]:
        if not value:
            return None
        cleaned = self._normalize_whitespace(value)
        if not DATE_PATTERN.match(cleaned):
            return None
        d, m, y = cleaned.split(".")
        try:
            return date(int(y), int(m), int(d))
        except ValueError:
            return None

    def _first_line(self, entries: Optional[List[OrsrEntry]]) -> str:
        if not entries:
            return ""
        entry = entries[0]
        if not entry.lines:
            return ""
        # Skomprimuj multi-line entry do jedného textu ak ma zmysel
        return self._normalize_whitespace(" ".join(entry.lines))

    def _join_section_text(self, entries: List[OrsrEntry]) -> str:
        parts: List[str] = []
        for entry in entries:
            if entry.text:
                parts.append(entry.text)
        return "\n".join(parts)

    def _format_address(self, lines) -> str:
        """Adresa ako "Ulica 123, 921 01 Mesto[, Krajina]" v jednom texte."""
        if isinstance(lines, list) and lines and isinstance(lines[0], OrsrEntry):
            # Sídlo je list[OrsrEntry]
            first = lines[0]
            line_list = first.lines
        else:
            line_list = list(lines or [])

        clean = [self._normalize_whitespace(line) for line in line_list if line]
        clean = [l for l in clean if l]
        if not clean:
            return ""

        return ", ".join(clean)

    def _raw_sections(self, sections: Dict[str, List[OrsrEntry]]) -> Dict[str, List[str]]:
        """Spätná kompatibilita: raw_sections[key] = list riadkov."""
        result: Dict[str, List[str]] = {}
        for key, entries in sections.items():
            flat: List[str] = []
            for entry in entries:
                for line in entry.lines:
                    if line:
                        flat.append(line)
                if entry.od:
                    flat.append(f"(od: {entry.od})")
            result[key] = flat
        return result

    def _looks_like_title(self, token: str) -> bool:
        return token.lower().rstrip(".") in TITLE_TOKENS

    def _clean_role_suffix(self, text: str) -> str:
        value = self._normalize_whitespace(text).lstrip("-").strip()
        if value.lower().startswith("- "):
            value = value[2:].strip()
        return value


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
