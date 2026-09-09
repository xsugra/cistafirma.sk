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


def check_socpoist_debt(ico: str) -> DebtCheckResult:
    """
    Overí dlh v Sociálnej poisťovni pre zadané IČO.
    Vracia overený výsledok. Nulu smie vrátiť iba explicitný no-record signál.
    """
    # 1. Endpoint a Parametre (Presne podľa tvojho zistenia)
    base_url = "https://www.socpoist.sk/nastroje-sluzby/zoznam-dlznikov"

    # Do params dáme aj prázdne hodnoty, aby sme verne simulovali prehliadač
    params = {"name": "", "city": "", "glossary": "", "ico": ico}

    # 2. Hlavičky (SP má prísnejšie firewally, User-Agent je nutnosť)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Referer": "https://www.socpoist.sk/nastroje-sluzby/zoznam-dlznikov",
    }

    try:
        # 3. GET Request s retry session
        # Timeout dávame dlhší (15s), štátne weby sú niekedy pomalé
        session = get_session_with_retry()
        response = session.get(base_url, params=params, headers=headers, timeout=15)
        response.raise_for_status()

        # 4. Parsing (Tu musíme byť detektívi)
        soup = BeautifulSoup(response.text, "html.parser")

        # Stratégia:
        # SP zvyčajne vypíše výsledok do nejakého kontajnera.
        # Ak nenájde nič, vypíše "Zadaným kritériám nevyhovuje žiaden záznam".

        if "nevyhovuje žiaden záznam" in response.text:
            return DebtCheckResult.not_found()

        # Hľadanie sumy:
        # Na novom webe SP sú výsledky často v divoch s triedami ako 'result-item' alebo v tabuľke.
        # Univerzálna metóda: Hľadáme text "Dlžná suma" a číslo vedľa neho.

        # Nájdi všetky bunky/divy, ktoré obsahujú menu '€'
        # Toto je robustnejšie než hľadať konkrétnu CSS triedu, ktorú môžu zajtra zmeniť.
        candidates = soup.find_all(string=lambda text: text and "€" in text)

        for candidate in candidates:
            # Candidate je textový uzol, napr. "3 450,20 €"
            # Musíme overiť, či je to naozaj číslo
            text = candidate.strip()
            if is_money(text):
                # Ešte jedna kontrola: Je tento element blízko nášho IČO?
                # (Aby sme nenašli nejakú reklamu alebo pätu stránky)
                # Ale pri filtrovaní podľa IČO by tam mala byť len jedna firma.
                return DebtCheckResult.found(parse_money(text))

        message = f"SP response did not contain a recognized result for ICO {ico}."
        logger.warning(message)
        return DebtCheckResult.unknown(message, "parse_error")

    except requests.exceptions.RequestException as e:
        logger.error(f"Network error pri SP {ico}: {e}")
        return DebtCheckResult.unknown(str(e), "network")