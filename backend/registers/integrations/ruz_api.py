import requests
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

class RuzApi:
    """
    A client for the Slovak Register of Financial Statements (RUZ) API.
    Documentation: https://www.registeruz.sk/cruz-public/home/api
    """
    BASE_URL = "https://www.registeruz.sk/cruz-public/api"
    HEADERS = {"User-Agent": "CistaFirma SK App / 1.0"}

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
            response = requests.get(url, params=params, headers=self.HEADERS, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching changed company IDs from RUZ: {e}")
            return None

    def get_company_details(self, company_id: int) -> Optional[Dict[str, Any]]:
        """
        Gets the detailed attributes for a single company by its RUZ ID.
        Hits /api/uctovna-jednotka
        """
        url = f"{self.BASE_URL}/uctovna-jednotka"
        params = {"id": company_id}
        try:
            response = requests.get(url, params=params, headers=self.HEADERS, timeout=15)
            response.raise_for_status()
            data = response.json()
            # The API can return a status object for deleted items
            if data.get("stav") == "ZMAZANÉ":
                logger.info(f"Company with RUZ ID {company_id} is marked as DELETED.")
                # You might want to handle this by deleting it from your DB
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
