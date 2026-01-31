import logging
import requests
from bs4 import BeautifulSoup
from ..utils import parse_money, is_money

logger = logging.getLogger(__name__)


def check_socpoist_debt(ico: str) -> float:
    """
    Overí dlh v Sociálnej poisťovni pre zadané IČO.
    Vracia sumu v EUR (float).
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
        # 3. GET Request
        # Timeout dávame dlhší (15s), štátne weby sú niekedy pomalé
        response = requests.get(base_url, params=params, headers=headers, timeout=15)
        response.raise_for_status()

        # 4. Parsing (Tu musíme byť detektívi)
        soup = BeautifulSoup(response.text, "html.parser")

        # Stratégia:
        # SP zvyčajne vypíše výsledok do nejakého kontajnera.
        # Ak nenájde nič, vypíše "Zadaným kritériám nevyhovuje žiaden záznam".

        if "nevyhovuje žiaden záznam" in response.text:
            return 0.0

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
                return parse_money(text)

        # Ak sme nenašli sumu, ale ani hlášku "nič sa nenašlo", je to podozrivé.
        # Možno zmenili dizajn. Pre istotu vrátime 0, ale zalogujeme warning.
        logger.warning(f"SP: Stránka načítaná, ale DLH nenájdený pre IČO {ico}")
        return 0.0

    except requests.exceptions.RequestException as e:
        logger.error(f"Network error pri SP {ico}: {e}")
        return None  # Alebo raise, podľa toho ako máš nastavený retry mechanizmus
    except Exception as e:
        logger.error(f"Chyba parsovania SP {ico}: {e}")
        return 0.0