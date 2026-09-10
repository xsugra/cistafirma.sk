import logging
import re

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from ..utils import parse_money
from .debt_result import DebtCheckResult

logger = logging.getLogger(__name__)

# VSZP renders the claim column as a bare number ("6 641,86") and the page
# carries no currency symbol at all -- "€" appears zero times. The shared
# is_money()/parse_money() pair requires one, so it cannot decide this column,
# and loosening it would weaken the guard the Socialna poistovna scraper relies
# on. The column is therefore validated against VSZP's own format here, first
# and strictly, before parse_money() converts it.
_VSZP_AMOUNT_RE = re.compile(r"^\d[\d \xa0]*(?:,\d{1,2})?$")

# The one message that makes an absent row authoritative. An empty table
# *without* it is ambiguous -- it can equally be a server-side error -- and per
# docs/SOURCE_DATA_INTEGRITY.md an ambiguous response must not be written as a
# zero.
_VSZP_NO_RECORD_MARKER = "Nenašli sa žiadne záznamy"

# The first cell of a result row reads "NAME<br/>IČO: 34136088".
_VSZP_ROW_ICO_RE = re.compile(r"IČO:\s*(\d+)")


def _parse_vszp_amount(text: str) -> float | None:
    """Convert VSZP's bare amount cell to a float, or None if it is not one."""
    candidate = text.strip()
    if not _VSZP_AMOUNT_RE.match(candidate):
        return None
    try:
        return parse_money(candidate)
    except ValueError:
        return None


def get_session_with_retry() -> requests.Session:
    """Vytvorí requests session s retry stratégiou."""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def check_vszp_debt_get(ico: str) -> DebtCheckResult:
    """
    Stiahne dlh z VšZP pomocou GET requestu (simuluje vyhľadávanie v URL).
    Vracia overený výsledok. Nulu smie vrátiť iba explicitný no-record signál.
    """

    # 1. Konstrukcia s URL parametrami
    base_url = "https://www.vszp.sk/platitelia/platenie-poistneho/zoznam-dlznikov.html"
    params = {
        "typ": "1",  # 1 = Zamestnavatelia a SZCO
        "nazov": ico,  # Hladane ICO
        "proceed": "true",  # Spustit hladanie
        "docid": "227",  # ID dokumentu (zda sa byt staticke, ale overime)
    }

    # 2. Hlavicky (aby sme nevyzerali ako bot)
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; CistaFirmaBot/1.0; +https://cistafirma.sk)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    }

    try:
        # 3. GET request with retry session and longer timeout
        session = get_session_with_retry()
        response = session.get(base_url, params=params, headers=headers, timeout=15)
        response.raise_for_status()

    except requests.exceptions.RequestException as e:
        # This catches ConnectionError, Timeout, HTTPError, etc.
        logger.warning(f"Network error pri VSZP pre ICO {ico}: {e}")
        return DebtCheckResult.unknown(str(e), "network")

    soup = BeautifulSoup(response.text, "html.parser")

    # A matching row is the strongest evidence available, so it is looked for
    # first: the no-record marker must never be able to turn a company that *is*
    # listed into a zero.
    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if not cells or len(cells) < 5:
            continue

        # The first cell holds the name and, after a <br>, "IČO: <number>".
        # The identifier is extracted and compared numerically rather than as a
        # substring: "IČO: 3413608" is a prefix of "IČO: 34136088", and the two
        # may differ only in zero padding. Whitespace is normalized so a
        # non-breaking space after the colon does not defeat the match.
        row_text = " ".join(cells[0].get_text(" ", strip=True).split())
        row_ico = _VSZP_ROW_ICO_RE.search(row_text)
        if row_ico is None or row_ico.group(1).lstrip("0") != ico.strip().lstrip("0"):
            continue

        amount = _parse_vszp_amount(cells[4].get_text(strip=True))
        if amount is not None:
            return DebtCheckResult.found(amount)

        message = f"VSZP result row for ICO {ico} did not contain a valid debt amount."
        logger.warning(message)
        return DebtCheckResult.unknown(message, "parse_error")

    # No row matched. VSZP states the absence explicitly; only that message is
    # authoritative. Without it the result stays unknown.
    if _VSZP_NO_RECORD_MARKER in response.text:
        return DebtCheckResult.not_found()

    message = f"VSZP response did not contain a recognized result row for ICO {ico}."
    logger.warning(message)
    return DebtCheckResult.unknown(message, "parse_error")