import logging
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from ..utils import parse_money, is_money

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


def check_vszp_debt_get(ico: str) -> Optional[float]:
    """
    Stiahne dlh z VšZP pomocou GET requestu (simuluje vyhľadávanie v URL).
    Vracia sumu v EUR. Ak dlh nie je nájdený alebo je nula, vracia 0.0.
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
        return None  # Return None to signify a network-level failure

    try:
        # 4. Parsing HTML
        soup = BeautifulSoup(response.text, "html.parser")

        # Štruktúra tabuľky VšZP:
        # Stĺpce: Obchodné meno (obsahuje IČO), Obec, Ulica, PSČ, Pohľadávka, Typ platiteľa, Rozsah ZS
        # IČO je vnorené v prvej bunke ako "NAZOV FIRMY IČO: 12345678"

        rows = soup.find_all("tr")

        for row in rows:
            cells = row.find_all("td")
            if not cells or len(cells) < 5:
                continue

            # Prvá bunka obsahuje názov firmy + IČO
            first_cell_text = cells[0].get_text(strip=True)

            # Kontrola, či riadok obsahuje hľadané IČO
            if ico in first_cell_text:
                # Pohľadávka je v 5. stĺpci (index 4)
                debt_text = cells[4].get_text(strip=True)
                if debt_text and is_money(debt_text):
                    return parse_money(debt_text)

        # If we get here, the page was loaded, but the company wasn't on the list.
        # This is a valid "zero debt" scenario for our purpose.
        logger.info(f"VSZP: Firma s ICO {ico} nebola najdena v zozname dlznikov.")
        return 0.0

    except Exception as e:
        # This will now only catch parsing errors, not network errors
        logger.error(f"Chyba parsovania VSZP pre ICO {ico}: {e}")
        return 0.0 # Return 0.0 as a fallback if parsing fails.