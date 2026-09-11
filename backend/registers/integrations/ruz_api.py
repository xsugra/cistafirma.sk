import requests
import logging
from typing import Dict, Any, Optional, List

from django.utils.dateparse import parse_date

from registers.http_client import build_retry_session

logger = logging.getLogger(__name__)


class RuzUnreachable(RuntimeError):
    """The registry could not be read, as distinct from "it has no such record".

    Every `get_*` here answers `None` for a record that does not exist, which is
    a real answer. Transport failures and server-side refusals used to arrive as
    the same `None`, and a caller that read it as "nothing there" had no way to
    tell. This exception is the difference, and it is raised only by a client
    built with `raise_on_transport_error=True`.
    """


class RuzApi:
    """
    A client for the Slovak Register of Financial Statements (RUZ) API.
    Documentation: https://www.registeruz.sk/cruz-public/home/api
    """
    BASE_URL = "https://www.registeruz.sk/cruz-public/api"
    HEADERS = {"User-Agent": "CistaFirma SK App / 1.0"}

    def __init__(self, timeout: int = 20, raise_on_transport_error: bool = False):
        """`raise_on_transport_error` decides what a transport failure becomes.

        Default `False` is the historical behaviour -- every `get_*` answers
        `None`, and the six existing construction sites plus every test keep
        working byte for byte. `True` raises `RuzUnreachable` instead, for
        callers that must not mistake an unreachable registry for an empty one.

        A **404 is not a transport failure** and stays `None` either way: the
        registry answered, and its answer was "no such record". A 5xx after the
        retry session has exhausted its attempts is one, because nothing was
        answered at all.
        """
        self.timeout = timeout
        self.raise_on_transport_error = raise_on_transport_error
        self.session = build_retry_session(headers=self.HEADERS, total_retries=4, backoff_factor=0.6)

    def _on_transport_error(self, context: str, exc: Exception) -> None:
        """The one place that decides whether a swallowed error stays swallowed.

        Returns `None` when the client is not strict, so the caller's existing
        `return None` goes through unchanged. Raises otherwise, chaining the
        original exception so the transport cause is still in the traceback.
        """
        if self.raise_on_transport_error:
            raise RuzUnreachable(f"{context}: {exc}") from exc

    def _get_json(self, url: str, *, params: Dict[str, Any], timeout: Optional[int] = None) -> Optional[Dict[str, Any]]:
        response = self.session.get(url, params=params, timeout=timeout or self.timeout)
        response.raise_for_status()
        return response.json()

    def get_changed_company_ids(
        self, zmenene_od: str, pokracovat_za_id: int = None, max_zaznamov: int = 1000
    ) -> Dict[str, Any]:
        """
        Gets a list of company IDs that have changed since a given date.
        Hits /api/uctovne-jednotky

        Propagates `requests.exceptions.RequestException` instead of folding it
        into `None`, which every other method here does and their callers can
        live with -- a company that cannot be read is counted as a failed item
        and stays visible. This one cannot: its caller reads a falsy answer as
        "the registry has nothing further", so a transport failure on the first
        call ended the import loop, ran `progress.complete()` and stored the run
        as `completed` with `processed_items=0`. Two beat runs did exactly that
        on 2026-09-11 (jobs #13 and #14), both re-requesting the same page. An
        empty page and an unreachable registry must not arrive as the same
        value.
        """
        url = f"{self.BASE_URL}/uctovne-jednotky"
        params = {
            "zmenene-od": zmenene_od,
            "max-zaznamov": max_zaznamov,
        }
        if pokracovat_za_id:
            params["pokracovat-za-id"] = pokracovat_za_id

        try:
            return self._get_json(url, params=params, timeout=30)
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching changed company IDs from RUZ: {e}")
            raise

    def get_company_id_by_ico(self, ico: str) -> Optional[int]:
        """
        Gets the RUZ ID for a company by its ICO.
        Uses /api/uctovne-jednotky with ico parameter.
        Returns the first matching RUZ ID or None if not found.
        """
        url = f"{self.BASE_URL}/uctovne-jednotky"
        params = {
            "zmenene-od": "2000-01-01",
            "ico": ico.strip().zfill(8),
            "max-zaznamov": 1,
        }
        try:
            data = self._get_json(url, params=params, timeout=15)
            ids = data.get('id', [])
            if ids:
                return ids[0]
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching company ID by ICO {ico}: {e}")
            self._on_transport_error(f"RUZ unreachable looking up ICO {ico}", e)
            return None

    def get_company_by_ico(self, ico: str) -> Optional[Dict[str, Any]]:
        """
        Gets company details by ICO.
        First finds the RUZ ID, then fetches full details.
        """
        ruz_id = self.get_company_id_by_ico(ico)
        if ruz_id:
            return self.get_company_details(ruz_id)
        logger.warning(f"Company with ICO {ico} not found in RUZ.")
        return None

    def get_company_details(self, company_id: int) -> Optional[Dict[str, Any]]:
        """
        Gets the detailed attributes for a single company by its RUZ ID.
        Hits /api/uctovna-jednotka
        """
        url = f"{self.BASE_URL}/uctovna-jednotka"
        params = {"id": company_id}
        try:
            data = self._get_json(url, params=params, timeout=15)
            # The API can return a status object for deleted items
            if data.get("stav") == "ZMAZANÉ":
                logger.info(f"Company with RUZ ID {company_id} is marked as DELETED.")
                return None
            return data
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                logger.warning(f"Company with RUZ ID {company_id} not found (404).")
            else:
                logger.error(f"HTTP error fetching details for RUZ ID {company_id}: {e}")
                self._on_transport_error(f"RUZ refused company {company_id}", e)
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error fetching details for RUZ ID {company_id}: {e}")
            self._on_transport_error(f"RUZ unreachable reading company {company_id}", e)
            return None

    def get_financial_statement_details(self, statement_id: int) -> Optional[Dict[str, Any]]:
        """
        Gets details for one financial statement.
        Hits /api/uctovna-zavierka
        """
        url = f"{self.BASE_URL}/uctovna-zavierka"
        params = {"id": statement_id}
        try:
            data = self._get_json(url, params=params, timeout=20)
            if data.get("stav") == "ZMAZANÉ":
                return None
            return data
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                logger.warning("Financial statement %s not found (404).", statement_id)
            else:
                logger.error("HTTP error fetching financial statement %s: %s", statement_id, e)
                self._on_transport_error(f"RUZ refused statement {statement_id}", e)
            return None
        except requests.exceptions.RequestException as e:
            logger.error("Network error fetching financial statement %s: %s", statement_id, e)
            self._on_transport_error(f"RUZ unreachable reading statement {statement_id}", e)
            return None

    def get_financial_report_details(self, report_id: int) -> Optional[Dict[str, Any]]:
        """
        Gets details for one financial report.
        Hits /api/uctovny-vykaz
        """
        url = f"{self.BASE_URL}/uctovny-vykaz"
        params = {"id": report_id}
        try:
            data = self._get_json(url, params=params, timeout=25)
            if data.get("stav") == "ZMAZANÉ":
                return None
            return data
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                logger.warning("Financial report %s not found (404).", report_id)
            else:
                logger.error("HTTP error fetching financial report %s: %s", report_id, e)
                self._on_transport_error(f"RUZ refused report {report_id}", e)
            return None
        except requests.exceptions.RequestException as e:
            logger.error("Network error fetching financial report %s: %s", report_id, e)
            self._on_transport_error(f"RUZ unreachable reading report {report_id}", e)
            return None

    def get_report_template_details(self, template_id: int) -> Optional[Dict[str, Any]]:
        """Gets details of one financial report template (/api/sablona)."""
        url = f"{self.BASE_URL}/sablona"
        params = {"id": template_id}
        try:
            return self._get_json(url, params=params, timeout=20)
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                logger.warning("Report template %s not found (404).", template_id)
            else:
                logger.error("HTTP error fetching report template %s: %s", template_id, e)
                self._on_transport_error(f"RUZ refused template {template_id}", e)
            return None
        except requests.exceptions.RequestException as e:
            logger.error("Network error fetching report template %s: %s", template_id, e)
            self._on_transport_error(f"RUZ unreachable reading template {template_id}", e)
            return None


# The date fields every RUZ accounting-unit record carries, as
# (payload key, model field). Three writers map these by hand; keeping the
# pairs here means a new one cannot quietly map only two of them.
RUZ_DATE_FIELDS = (
    ('datumZalozenia', 'datum_zalozenia'),
    ('datumZrusenia', 'datum_zrusenia'),
    ('datumPoslednejUpravy', 'datum_poslednej_upravy'),
)

# `parse_ruz_date` returns this when the payload held a value we could not
# read. It is deliberately not `None`, because `None` means something else
# entirely -- see below.
UNREADABLE = object()


def parse_ruz_date(data: Dict[str, Any], key: str, ico: Optional[str] = None):
    """Read one RUZ date field, distinguishing "absent" from "unreadable".

    `django.utils.dateparse.parse_date` collapses two very different things
    into `None`, and the writers cannot tell them apart afterwards:

    * the key is **absent or empty** -- a statement. Measured against the live
      API on 2026-09-10: 20/20 dissolved records carry `datumZrusenia`, 8/8
      active ones omit it. So absence means "this company is not dissolved",
      and it is what clears a date when RUZ revokes a dissolution.
    * the key holds **something we cannot parse** -- noise, not a statement.
      RUZ sends ISO dates; a switch to `31.07.2026` would make every value
      unreadable at once, and writing that `None` through would erase 120 289
      dissolution dates in a single sync -- and the next sync, with the format
      fixed, would restore them as 120 289 false dissolution notifications.

    Absence therefore returns `None` (the caller may clear), and noise returns
    `UNREADABLE` (the caller must keep what is stored). The guard cannot block
    a legitimate correction, because RUZ has no way to say "clear this date"
    other than by omitting the key.
    """
    raw = data.get(key)
    if not raw:
        return None

    parsed = parse_date(raw)
    if parsed is None:
        logger.error(
            "Unreadable RUZ date %s=%r for ICO %s; keeping the stored value "
            "rather than erasing it. The source's date format has probably "
            "changed.",
            key, raw, ico or data.get('ico'),
        )
        return UNREADABLE

    return parsed


def apply_ruz_dates(defaults: Dict[str, Any], data: Dict[str, Any]) -> List[tuple]:
    """Fill the three date fields of `defaults` from a RUZ payload.

    A field comes back `UNREADABLE` when the payload held something we cannot
    parse; leaving the key out of `defaults` is what makes
    `update_or_create` keep the stored value instead of overwriting it with
    `None`.

    Returns the fields that were refused, as `(payload key, raw value)` pairs,
    so the caller can record them against the source. Returning them *all*, as
    one list, is the point on both counts: a refusal that only reaches a log
    line is not a control, and
    `registers.services.sync_engine.record_ruz_date_outcome` turns the list
    into one attempt row per company -- so two unreadable dates are one
    failure, not two, and a company that reads cleanly later clears it.
    """
    ico = data.get('ico')
    refused = []
    for key, field in RUZ_DATE_FIELDS:
        value = parse_ruz_date(data, key, ico)
        if value is UNREADABLE:
            refused.append((key, data.get(key)))
        else:
            defaults[field] = value
    return refused

