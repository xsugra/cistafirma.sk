import requests
import logging
from typing import Dict, Any, Optional, List

from registers.http_client import build_retry_session

logger = logging.getLogger(__name__)

class RuzApi:
    """
    A client for the Slovak Register of Financial Statements (RUZ) API.
    Documentation: https://www.registeruz.sk/cruz-public/home/api
    """
    BASE_URL = "https://www.registeruz.sk/cruz-public/api"
    HEADERS = {"User-Agent": "CistaFirma SK App / 1.0"}

    def __init__(self, timeout: int = 20):
        self.timeout = timeout
        self.session = build_retry_session(headers=self.HEADERS, total_retries=4, backoff_factor=0.6)

    def _get_json(self, url: str, *, params: Dict[str, Any], timeout: Optional[int] = None) -> Optional[Dict[str, Any]]:
        response = self.session.get(url, params=params, timeout=timeout or self.timeout)
        response.raise_for_status()
        return response.json()

    def get_changed_company_ids(
        self, zmenene_od: str, pokracovat_za_id: int = None, max_zaznamov: int = 1000
    ) -> Optional[Dict[str, Any]]:
        """
        Gets a list of company IDs that have changed since a given date.
        Hits /api/uctovne-jednotky
        """
        url = f"{self.BASE_URL}/uctovne-jednotky"
        params = {
            "zmenene-od": zmenene_od,
            "max-zaznamov": max_zaznamov,
        }
        if pokracovat_za_id:
            params["pokracovat-za-id"] = pokracovat_za_id

        try:
            data = self._get_json(url, params=params, timeout=30)
            return data
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching changed company IDs from RUZ: {e}")
            return None

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
            if e.response.status_code == 404:
                logger.warning(f"Company with RUZ ID {company_id} not found (404).")
            else:
                logger.error(f"HTTP error fetching details for RUZ ID {company_id}: {e}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error fetching details for RUZ ID {company_id}: {e}")
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
            return None
        except requests.exceptions.RequestException as e:
            logger.error("Network error fetching financial statement %s: %s", statement_id, e)
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
            return None
        except requests.exceptions.RequestException as e:
            logger.error("Network error fetching financial report %s: %s", report_id, e)
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
            return None
        except requests.exceptions.RequestException as e:
            logger.error("Network error fetching report template %s: %s", template_id, e)
            return None

