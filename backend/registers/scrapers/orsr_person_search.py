"""Searching the register by a person's name.

`search_ico.asp` searches by company; `search_osoba.asp` searches by the
*person*, which is a different question and a different answer. It is the one
thing the register does that our own person graph cannot do for everyone --
we hold relations for 19 906 of 445 626 companies, so for most names the honest
answer here is "not in our data, but the register has these".

Three properties of that endpoint shape the parser, all verified against it on
2026-09-13 rather than assumed:

* the page is `cp1250`, not UTF-8;
* **diacritics are exact** -- `PR=novak` returns zero records, `PR=Novák`
  returns 24. A reader typing without them gets an empty list and concludes the
  person is not in the register, which is why the stripped spelling is tried as
  a second attempt -- but only when the first answered nothing, never merged
  into it;
* the result row is `Meno | Obchodné meno subjektu | Výpis | Zbierka
  dokumentov`. There is **no capacity column**: the register says that a person
  is in a company, not as what. Anyone wanting the role needs one `vypis.asp`
  request per company, which is why we do not do it here and say so instead.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from urllib.parse import quote

from bs4 import BeautifulSoup

from registers.http_client import build_retry_session

logger = logging.getLogger(__name__)


ORSR_PERSON_SEARCH_URL = "https://www.orsr.sk/hladaj_osoba.asp"
ORSR_BASE_URL = "https://www.orsr.sk"

# "Záznamy: 1 - 18 / 18" -- the only place the total appears. Reading it is what
# lets us say the list is partial instead of quietly showing the first page.
RECORD_COUNT_PATTERN = re.compile(r"Z[áa]znamy:\s*([\d\s]+)\s*-\s*([\d\s]+)\s*/\s*([\d\s]+)")
VYPIS_ID_PATTERN = re.compile(r"vypis\.asp\?ID=(\d+)&(?:amp;)?SID=(\d+)")

PAGE_SIZE = 20


@dataclass
class OrsrPersonHit:
    """One row: a person, a company they are recorded in, and the way in."""

    person_name: str
    company_name: str
    orsr_id: str = ""
    court_id: str = ""
    current_url: str = ""
    full_url: str = ""

    def as_dict(self) -> dict:
        return {
            "person_name": self.person_name,
            "company_name": self.company_name,
            "current_url": self.current_url,
            "full_url": self.full_url,
        }


@dataclass
class OrsrPersonResult:
    hits: list[OrsrPersonHit] = field(default_factory=list)
    total: int = 0
    source_url: str = ""
    # Filled in when the register could not be read. The caller shows the
    # difference between "no records" and "we could not ask".
    error: str = ""

    @property
    def truncated(self) -> bool:
        return self.total > len(self.hits)


def split_name(query: str) -> tuple[str, str]:
    """Split a typed name into (surname, given names) the way the form wants it.

    The form is surname-first, but people type given-name-first -- and so do we
    when we display a name. The surname is taken as the last token, which is
    right for Slovak names in both orders and for the `Ing. Miroslav Trnka`
    shape the register itself returns.
    """
    tokens = [t for t in re.split(r"\s+", (query or "").strip()) if t]
    if not tokens:
        return "", ""
    if len(tokens) == 1:
        return tokens[0], ""
    return tokens[-1], " ".join(tokens[:-1])


class OrsrPersonSearch:
    """One bounded request per call. No pagination walk, no follow-up fetches."""

    def __init__(self, session=None, timeout: int = 20):
        self.session = session or build_retry_session(
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; CistaFirma/1.0)",
                "Accept-Language": "sk,cs;q=0.9",
            }
        )
        self.timeout = timeout

    def search(self, query: str) -> OrsrPersonResult:
        surname, given = split_name(query)
        if not surname:
            return OrsrPersonResult()

        params = {"PR": surname, "MENO": given, "SID": "0", "T": "f0", "R": "on"}
        url = f"{ORSR_PERSON_SEARCH_URL}?" + "&".join(
            f"{key}={quote(value)}" for key, value in params.items()
        )

        # The register is diacritics-exact, so a query typed without them asks
        # a question the register answers "nothing" to. Trying the stripped
        # spelling as well costs one extra request and is the difference
        # between a working search and a misleading empty one.
        attempts = [query]
        stripped = _strip_diacritics(query)
        if stripped.casefold() != query.casefold():
            attempts.append(stripped)

        hits: list[OrsrPersonHit] = []
        total = 0
        last_error = ""

        for attempt in attempts:
            result = self._search_once(attempt)
            if result.error:
                last_error = result.error
                continue
            total = max(total, result.total)
            if result.hits:
                # The exact spelling answered. The stripped one is not asked:
                # it would widen the list with different people who share a
                # surname, and the register's own count would no longer describe
                # what is shown.
                hits = result.hits
                break

        if not hits and last_error:
            return OrsrPersonResult(total=0, source_url=url, error=last_error)

        return OrsrPersonResult(hits=hits, total=max(total, len(hits)), source_url=url)

    def _search_once(self, query: str) -> OrsrPersonResult:
        surname, given = split_name(query)
        params = {"PR": surname, "MENO": given, "SID": "0", "T": "f0", "R": "on"}
        try:
            response = self.session.get(
                ORSR_PERSON_SEARCH_URL, params=params, timeout=self.timeout
            )
            response.raise_for_status()
        except Exception as exc:  # noqa: BLE001 -- reported, never swallowed
            logger.warning("ORSR person search failed for %r: %s", query, exc)
            return OrsrPersonResult(error=f"{type(exc).__name__}: {exc}")

        response.encoding = "cp1250"
        return self.parse(response.text, source_url=response.url)

    def parse(self, html: str, *, source_url: str = "") -> OrsrPersonResult:
        soup = BeautifulSoup(html, "html.parser")
        total = _read_total(soup)

        hits: list[OrsrPersonHit] = []
        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 3:
                continue

            person_name = _clean(cells[1].get_text(" "))
            company_cell = cells[2]
            link = company_cell.find("a", href=True)
            if not person_name or link is None:
                continue

            company_name = _clean(link.get_text(" "))
            if not company_name:
                continue

            ids = VYPIS_ID_PATTERN.search(link["href"])
            orsr_id = ids.group(1) if ids else ""
            court_id = ids.group(2) if ids else ""
            base = f"{ORSR_BASE_URL}/vypis.asp?ID={orsr_id}&SID={court_id}"

            hits.append(
                OrsrPersonHit(
                    person_name=person_name,
                    company_name=company_name,
                    orsr_id=orsr_id,
                    court_id=court_id,
                    current_url=f"{base}&P=0" if orsr_id else "",
                    full_url=f"{base}&P=1" if orsr_id else "",
                )
            )

        return OrsrPersonResult(hits=hits, total=max(total, len(hits)), source_url=source_url)


def _read_total(soup) -> int:
    """The number of matching records, read from the element that states it.

    Deliberately not from `soup.get_text(" ")`. That concatenates the whole
    page, so the header runs straight into the first row's cells -- and the
    count pattern tolerates spaces inside a number (some registers write
    `1 234`), which makes `... / 18` followed by a row number `1` read as
    `181`. Measured on the fixture here: a page stating 18 reported 181, which
    made `truncated` permanently true and the total useless. Reading the
    smallest element that carries the header bounds the text at both ends, so
    the same fixture reports 18.
    """
    for element in soup.find_all(["div", "td", "p", "span", "b", "font", "strong"]):
        match = RECORD_COUNT_PATTERN.search(element.get_text(" "))
        if match:
            return _to_int(match.group(3))
    return 0


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\xa0", " ")).strip()


def _to_int(text: str) -> int:
    digits = re.sub(r"\D", "", text or "")
    return int(digits) if digits else 0


def _strip_diacritics(text: str) -> str:
    import unicodedata

    decomposed = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in decomposed if not unicodedata.combining(c))
