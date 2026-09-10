import logging
import re

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from ..utils import parse_money, is_money
from .debt_result import DebtCheckResult

logger = logging.getLogger(__name__)

# The results are rendered by a single Drupal view. Its presence is the one
# thing on the page that proves the site actually processed the query: an
# error, a captcha or a maintenance page does not carry it, and without it the
# page says nothing about the company either way. Everything below is anchored
# on this container rather than on loose page text, which is what makes a
# returned zero defensible.
_SP_RESULTS_VIEW_CLASS = "view-id-debitors"

# "Dlžníci podľa zadaných kritérií: <strong>1</strong>" -- the result count,
# rendered only when the view holds a result set. When nothing matches, the
# same view still renders but this line is omitted entirely. Measured against
# the live site on 2026-09-10, for both a debtor and a non-debtor IČO.
_SP_RESULT_COUNT_RE = re.compile(r"Dlžníci podľa zadaných kritérií:\s*(\d+)")

# The wording the site used to publish. Kept because, wherever it still
# appears, it states the absence outright.
_SP_NO_RECORD_MARKER = "nevyhovuje žiaden záznam"


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


def _is_same_ico(cell: str, ico: str) -> bool:
    """True when a table cell is exactly the searched IČO.

    The two are compared as numbers rather than as strings: either side may be
    zero-padded differently, and a substring test would accept a longer
    identifier that merely begins with the searched one.
    """
    candidate = cell.strip()
    if not candidate.isdigit():
        return False
    return candidate.lstrip("0") == ico.strip().lstrip("0")


def _result_from_rows(view, ico: str) -> DebtCheckResult | None:
    """The verdict carried by the result table, or None when it has no row for `ico`.

    The amount is read only from the row that itself names this IČO, and only
    when that row holds exactly one readable figure. The previous version took
    the first "€" anywhere on the page, which would happily attribute another
    company's debt -- or a number from the page furniture -- to this one.
    """
    for row in view.find_all("tr"):
        cells = [cell.get_text(" ", strip=True) for cell in row.find_all("td")]
        if not any(_is_same_ico(cell, ico) for cell in cells):
            continue

        amounts = [cell for cell in cells if is_money(cell)]
        if len(amounts) == 1:
            return DebtCheckResult.found(parse_money(amounts[0]))

        message = (
            f"SP result row for ICO {ico} did not carry a single readable debt amount."
        )
        logger.warning(message)
        return DebtCheckResult.unknown(message, "parse_error")

    return None


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

    except requests.exceptions.RequestException as e:
        logger.error(f"Network error pri SP {ico}: {e}")
        return DebtCheckResult.unknown(str(e), "network")

    soup = BeautifulSoup(response.text, "html.parser")
    view = soup.find("div", class_=_SP_RESULTS_VIEW_CLASS)

    if view is not None:
        # A row naming this company is the strongest evidence available, so it
        # is read first: an absent result set must never be able to turn a
        # company that *is* listed into a zero.
        row_result = _result_from_rows(view, ico)
        if row_result is not None:
            return row_result

        # The view rendered, so the search ran, and it holds no row for this
        # company. The site states that by omitting the result count -- or, if
        # it ever renders one, by reporting zero. A count that *does* include
        # results, none of them this company, is not an answer about it, so it
        # stays unknown rather than becoming a zero.
        header = view.find("div", class_="view-header")
        count_match = _SP_RESULT_COUNT_RE.search(
            header.get_text(" ", strip=True) if header else ""
        )

        if count_match is None or int(count_match.group(1)) == 0:
            return DebtCheckResult.not_found()

        message = (
            f"SP view reported {count_match.group(1)} result(s) but none for ICO {ico}."
        )
        logger.warning(message)
        return DebtCheckResult.unknown(message, "parse_error")

    # The search view never rendered, so this page is not an answer about this
    # company -- far more likely an error or an interstitial. An explicit
    # statement of absence still settles it, wherever it appears.
    if _SP_NO_RECORD_MARKER in response.text:
        return DebtCheckResult.not_found()

    message = f"SP response did not contain a recognized result for ICO {ico}."
    logger.warning(message)
    return DebtCheckResult.unknown(message, "parse_error")
