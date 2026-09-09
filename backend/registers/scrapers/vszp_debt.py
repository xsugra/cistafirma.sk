import logging

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from ..utils import parse_money, is_money
from .debt_result import DebtCheckResult

logger = logging.getLogger(__name__)


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
    rows = soup.find_all("tr")

    for row in rows:
        cells = row.find_all("td")
        if not cells or len(cells) < 5:
            continue

        if ico not in cells[0].get_text(strip=True):
            continue

        debt_text = cells[4].get_text(strip=True)
        if debt_text and is_money(debt_text):
            return DebtCheckResult.found(parse_money(debt_text))

        message = f"VSZP result row for ICO {ico} did not contain a valid debt amount."
        logger.warning(message)
        return DebtCheckResult.unknown(message, "parse_error")

    message = f"VSZP response did not contain a recognized result row for ICO {ico}."
    logger.warning(message)
    return DebtCheckResult.unknown(message, "parse_error")