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

# The two column labels this module reads. The site's own words, taken from the
# rendered `<thead>` -- not from the `id` attributes Drupal puts beside them
# (`view-price-table-column--2`), whose trailing number is per-view and changes
# whenever the view is edited.
_SP_AMOUNT_COLUMN = "Dlžná suma"
_SP_PERIOD_COLUMN = "Chýbajúce podklady za obdobie"

# What the site prints in the amount column when the listing carries no sum.
#
# The registry holds two populations under one heading: companies owing at
# least 5,00 € carry an amount, while an employer that failed to submit its
# výkaz poistného a príspevkov -- or a foreign SZČO that failed to report
# income and expenses -- is listed with a bare hyphen and the missing periods
# published in the column beside it. Measured on the live site 2026-09-15:
# the two columns are complementary, money with "-" (43 of 50 rows) or "-" with
# periods (5 of 50). So a hyphen is not "owes an unknown amount"; it is a
# listing for a reporting breach.
#
# Only these marks count. A cell we cannot read for any other reason is a
# parsing fault, and answering `LISTED_NO_AMOUNT` there would put a claim in
# the register's mouth that it never made.
_SP_NO_AMOUNT_TOKENS = frozenset({"-", "–", "—", "−"})


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


def _header_label(th) -> str:
    """The visible name of a column, without the sort control's own text.

    Drupal renders a sort link inside every sortable `<th>`, and that link
    carries screen-reader text of its own -- `zoradiť podľa Dlžná suma`. So
    `th.get_text()` on the live page yields

        "Dlžná suma zoradiť podľa Dlžná suma"

    which equals no column name at all. The first version of this module read
    the label that way, and the consequence was not confined to the dash branch
    it was written for: `_result_table` found no table, so the *money* path
    broke too and every SP check came back `unknown`. Measured on the live site
    2026-09-15, where the amount column renders as

        <th class="views-field views-field-price" id="view-price-table-column--2">
          <span class="th-span">Dlžná suma
            <a class="arrowBtn" href="?...&order=price&sort=desc">
              <span class="sr-only">zoradiť podľa Dlžná suma</span></a></span></th>

    The sort control is furniture, not part of the name, so the strings under it
    are dropped and the rest read as written. The screen-reader class is the
    thing being excluded rather than the anchor, because the anchor is what a
    future revision of the view would keep while moving the text.
    """
    kept = []
    for text in th.find_all(string=True):
        if any(
            parent.name == "a" or "sr-only" in (parent.get("class") or [])
            for parent in text.parents
        ):
            continue
        if text.strip():
            kept.append(text.strip())
    return " ".join(kept)


def _result_table(view):
    """The view's result table, with its header labels.

    Found by the header rather than by position, because the view renders more
    than one table (`views-table` for the results, a pager below it) and only
    one of them names the amount column.
    """
    for table in view.find_all("table"):
        labels = [_header_label(th) for th in table.find_all("th")]
        if _SP_AMOUNT_COLUMN in labels:
            return table, labels
    return None, []


def _column_index(labels: list[str], label: str) -> int | None:
    """Where the header puts a named column, or None when it is not there."""
    try:
        return labels.index(label)
    except ValueError:
        return None


def _is_no_amount_mark(cell: str) -> bool:
    return cell.strip() in _SP_NO_AMOUNT_TOKENS


def _result_from_rows(table, labels: list[str], ico: str) -> DebtCheckResult | None:
    """The verdict carried by the result table, or None when it has no row for `ico`.

    The amount is read only from the row that itself names this IČO, and only
    when that row holds exactly one readable figure. The previous version took
    the first "€" anywhere on the page, which would happily attribute another
    company's debt -- or a number from the page furniture -- to this one.

    A row with *no* figure is read from the column the header calls "Dlžná
    suma", never from whichever cell happens to be empty. That asymmetry is
    deliberate and points the safe way: an amount is recognised wherever it
    is printed, so a reordered table still finds the money, while the absence
    of an amount is only accepted from the one column that is defined to carry
    it. If the header ever stops naming that column, the dash branch goes
    quiet and the row reads `unknown` -- a re-queue rather than a wrong answer.
    """
    amount_index = _column_index(labels, _SP_AMOUNT_COLUMN)
    period_index = _column_index(labels, _SP_PERIOD_COLUMN)

    for row in table.find_all("tr"):
        cells = [cell.get_text(" ", strip=True) for cell in row.find_all("td")]
        if not any(_is_same_ico(cell, ico) for cell in cells):
            continue

        amounts = [cell for cell in cells if is_money(cell)]
        if len(amounts) == 1:
            return DebtCheckResult.found(parse_money(amounts[0]))

        if (
            amount_index is not None
            and amount_index < len(cells)
            and _is_no_amount_mark(cells[amount_index])
        ):
            periods = ""
            if period_index is not None and period_index < len(cells):
                candidate = cells[period_index].strip()
                if candidate and not _is_no_amount_mark(candidate):
                    periods = candidate

            detail = (
                "Sociálna poisťovňa uvádza spoločnosť v zozname dlžníkov bez "
                "zverejnenej sumy."
            )
            if periods:
                detail += f" Chýbajúce podklady za obdobie: {periods}."
            return DebtCheckResult.listed_without_amount(detail)

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
        table, labels = _result_table(view)
        row_result = _result_from_rows(table, labels, ico) if table is not None else None
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
