"""Client for the RPO (Register právnických osôb) REST API.

Public API provided by ŠÚ SR under CC-BY 4.0 license.
Docs: https://susrrpo.docs.apiary.io/
Base URL: https://api.statistics.sk/rpo/v1/
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

import requests

from registers.http_client import build_retry_session

logger = logging.getLogger(__name__)

BASE_URL = "https://api.statistics.sk/rpo/v1"
HEADERS = {"User-Agent": "CistaFirma SK App / 1.0", "Accept": "application/json"}


class RpoApiError(Exception):
    pass


class RpoEntityNotFound(RpoApiError):
    pass


@dataclass
class RpoAddress:
    street: str = ""
    building_number: str = ""
    reg_number: int = 0
    postal_code: str = ""
    municipality: str = ""
    country: str = ""
    valid_from: str = ""
    valid_to: str = ""

    def format(self) -> str:
        parts = []
        if self.street:
            parts.append(self.street)
        if self.building_number:
            parts.append(self.building_number)
        if self.municipality:
            parts.append(self.municipality)
        if self.postal_code:
            parts.append(self.postal_code)
        if self.country and self.country != "Slovenská republika":
            parts.append(self.country)
        return ", ".join(parts)


@dataclass
class RpoPerson:
    formatted_name: str = ""
    family_names: list[str] = field(default_factory=list)
    given_names: list[str] = field(default_factory=list)
    stakeholder_type: str = ""
    stakeholder_type_code: str = ""
    address: Optional[RpoAddress] = None
    valid_from: str = ""
    valid_to: str = ""
    identifier: str = ""
    full_name: str = ""
    establishment: str = ""

    @property
    def is_current(self) -> bool:
        return not self.valid_to

    @property
    def display_name(self) -> str:
        return self.formatted_name or self.full_name


@dataclass
class RpoEquity:
    value: Optional[float] = None
    value_paid: Optional[float] = None
    currency: str = "EUR"
    valid_from: str = ""
    valid_to: str = ""

    @property
    def is_current(self) -> bool:
        return not self.valid_to


@dataclass
class RpoDeposit:
    full_name: str = ""
    amount: Optional[float] = None
    currency: str = "EUR"
    valid_from: str = ""
    valid_to: str = ""

    @property
    def is_current(self) -> bool:
        return not self.valid_to


@dataclass
class RpoActivity:
    description: str = ""
    valid_from: str = ""
    valid_to: str = ""

    @property
    def is_current(self) -> bool:
        return not self.valid_to


@dataclass
class RpoAuthorization:
    value: str = ""
    valid_from: str = ""
    valid_to: str = ""

    @property
    def is_current(self) -> bool:
        return not self.valid_to


@dataclass
class RpoSourceRegister:
    register_name: str = ""
    registration_office: str = ""
    registration_number: str = ""


@dataclass
class RpoEntity:
    rpo_id: int = 0
    ico: str = ""
    current_name: str = ""
    current_address: Optional[RpoAddress] = None
    legal_form: str = ""
    legal_form_code: str = ""
    establishment: str = ""
    db_modification_date: str = ""

    activities: list[RpoActivity] = field(default_factory=list)
    statutory_bodies: list[RpoPerson] = field(default_factory=list)
    stakeholders: list[RpoPerson] = field(default_factory=list)
    equities: list[RpoEquity] = field(default_factory=list)
    deposits: list[RpoDeposit] = field(default_factory=list)
    authorizations: list[RpoAuthorization] = field(default_factory=list)
    other_legal_facts: list[dict[str, str]] = field(default_factory=list)
    source_register: Optional[RpoSourceRegister] = None

    full_names: list[dict[str, str]] = field(default_factory=list)
    addresses: list[RpoAddress] = field(default_factory=list)

    raw: dict[str, Any] = field(default_factory=dict)


class RpoClient:
    """Client for RPO REST API (api.statistics.sk)."""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = build_retry_session(headers=HEADERS, total_retries=4, backoff_factor=1.5)

    def search_by_ico(self, ico: str) -> Optional[int]:
        """Search RPO by ICO, return entity ID or None."""
        ico = ico.strip().zfill(8)
        url = f"{BASE_URL}/search"
        try:
            resp = self.session.get(url, params={"identifier": ico}, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            logger.error("RPO search failed for ICO %s: %s", ico, exc)
            raise RpoApiError(f"RPO search failed: {exc}") from exc

        results = data.get("results", [])
        if not results:
            return None

        return results[0].get("id")

    def get_entity(self, entity_id: int) -> RpoEntity:
        """Fetch full entity detail by RPO ID."""
        url = f"{BASE_URL}/entity/{entity_id}"
        params = {"showHistoricalData": "true", "showOrganizationUnits": "true"}
        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
            if resp.status_code == 404:
                raise RpoEntityNotFound(f"RPO entity {entity_id} not found")
            resp.raise_for_status()
            data = resp.json()
        except RpoEntityNotFound:
            raise
        except requests.RequestException as exc:
            logger.error("RPO entity fetch failed for ID %s: %s", entity_id, exc)
            raise RpoApiError(f"RPO entity fetch failed: {exc}") from exc

        return self._parse_entity(data)

    def get_entity_by_ico(self, ico: str) -> Optional[RpoEntity]:
        """Search by ICO and fetch full entity. Returns None if not found."""
        entity_id = self.search_by_ico(ico)
        if entity_id is None:
            return None
        try:
            return self.get_entity(entity_id)
        except RpoEntityNotFound:
            logger.info("RPO entity detail missing for ICO %s (entity_id=%s)", ico, entity_id)
            return None

    def _parse_entity(self, data: dict[str, Any]) -> RpoEntity:
        entity = RpoEntity(raw=data)
        entity.rpo_id = data.get("id", 0)
        entity.db_modification_date = data.get("dbModificationDate", "")
        entity.establishment = data.get("establishment", "")

        identifiers = data.get("identifiers", [])
        if identifiers:
            entity.ico = self._current_value(identifiers)

        full_names = data.get("fullNames", [])
        entity.full_names = full_names
        entity.current_name = self._current_value(full_names)

        addresses = data.get("addresses", [])
        entity.addresses = [self._parse_address(a) for a in addresses]
        current_addr = self._find_current(addresses)
        if current_addr:
            entity.current_address = self._parse_address(current_addr)

        legal_forms = data.get("legalForms", [])
        current_lf = self._find_current(legal_forms)
        if current_lf and isinstance(current_lf.get("value"), dict):
            entity.legal_form = current_lf["value"].get("value", "")
            entity.legal_form_code = current_lf["value"].get("code", "")

        entity.activities = [self._parse_activity(a) for a in data.get("activities", [])]
        entity.statutory_bodies = [self._parse_person(p) for p in data.get("statutoryBodies", [])]
        entity.stakeholders = [self._parse_person(p) for p in data.get("stakeholders", [])]
        entity.equities = [self._parse_equity(e) for e in data.get("equities", [])]
        entity.deposits = [self._parse_deposit(d) for d in data.get("deposits", [])]
        entity.authorizations = [self._parse_authorization(a) for a in data.get("authorizations", [])]
        entity.other_legal_facts = data.get("otherLegalFacts", [])

        sr = data.get("sourceRegister")
        if sr:
            entity.source_register = self._parse_source_register(sr)

        return entity

    def _parse_address(self, data: dict[str, Any]) -> RpoAddress:
        postal_codes = data.get("postalCodes", [])
        municipality = data.get("municipality", {})
        country = data.get("country", {})
        return RpoAddress(
            street=data.get("street", ""),
            building_number=data.get("buildingNumber", ""),
            reg_number=data.get("regNumber", 0),
            postal_code=postal_codes[0] if postal_codes else "",
            municipality=municipality.get("value", "") if isinstance(municipality, dict) else "",
            country=country.get("value", "") if isinstance(country, dict) else "",
            valid_from=data.get("validFrom", ""),
            valid_to=data.get("validTo", ""),
        )

    def _parse_person(self, data: dict[str, Any]) -> RpoPerson:
        person = RpoPerson(
            valid_from=data.get("validFrom", ""),
            valid_to=data.get("validTo", ""),
            identifier=data.get("identifier", ""),
            full_name=data.get("fullName", ""),
            establishment=data.get("establishment", ""),
        )

        st = data.get("stakeholderType", {})
        if isinstance(st, dict):
            person.stakeholder_type = st.get("value", "")
            person.stakeholder_type_code = st.get("code", "")

        pn = data.get("personName", {})
        if isinstance(pn, dict):
            person.formatted_name = pn.get("formatedName", "")
            person.family_names = pn.get("familyNames", [])
            person.given_names = pn.get("givenNames", [])

        addr = data.get("address", {})
        if isinstance(addr, dict) and addr:
            person.address = self._parse_address(addr)

        return person

    def _parse_equity(self, data: dict[str, Any]) -> RpoEquity:
        currency = data.get("currency", {})
        return RpoEquity(
            value=data.get("value"),
            value_paid=data.get("valuePaid"),
            currency=currency.get("code", "EUR") if isinstance(currency, dict) else "EUR",
            valid_from=data.get("validFrom", ""),
            valid_to=data.get("validTo", ""),
        )

    def _parse_deposit(self, data: dict[str, Any]) -> RpoDeposit:
        currency = data.get("currency", {})
        return RpoDeposit(
            full_name=data.get("fullName", ""),
            amount=data.get("amount"),
            currency=currency.get("code", "EUR") if isinstance(currency, dict) else "EUR",
            valid_from=data.get("validFrom", ""),
            valid_to=data.get("validTo", ""),
        )

    def _parse_activity(self, data: dict[str, Any]) -> RpoActivity:
        return RpoActivity(
            description=data.get("economicActivityDescription", ""),
            valid_from=data.get("validFrom", ""),
            valid_to=data.get("validTo", ""),
        )

    def _parse_authorization(self, data: dict[str, Any]) -> RpoAuthorization:
        return RpoAuthorization(
            value=data.get("value", ""),
            valid_from=data.get("validFrom", ""),
            valid_to=data.get("validTo", ""),
        )

    def _parse_source_register(self, data: dict[str, Any]) -> RpoSourceRegister:
        sr = RpoSourceRegister()
        val = data.get("value", {})
        if isinstance(val, dict):
            sr.register_name = val.get("value", "")

        offices = data.get("registrationOffices", [])
        if offices:
            current = self._find_current(offices)
            if current:
                sr.registration_office = current.get("value", "")

        numbers = data.get("registrationNumbers", [])
        if numbers:
            current = self._find_current(numbers)
            if current:
                sr.registration_number = current.get("value", "")

        return sr

    @staticmethod
    def _find_current(items: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
        """Find the item without validTo (= currently valid)."""
        for item in items:
            if not item.get("validTo"):
                return item
        return items[-1] if items else None

    @staticmethod
    def _current_value(items: list[dict[str, Any]]) -> str:
        """Get 'value' from the currently valid item."""
        for item in items:
            if not item.get("validTo"):
                return item.get("value", "")
        return items[-1].get("value", "") if items else ""
