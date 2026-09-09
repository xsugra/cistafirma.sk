"""Sync service that maps RPO API data to OrsrCompanyProfile.

Replaces OrsrSyncService for companies available in RPO. Falls back to
ORSR scraping only when RPO returns no result (non-commercial-register entities
are not in RPO).
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from companies.models import Company
from registers.integrations.rpo_client import (
    RpoClient,
    RpoEntity,
    RpoPerson,
)
from registers.models import OrsrCompanyProfile
from registers.services.orsr_sync import OrsrSyncService

logger = logging.getLogger(__name__)


class RpoSyncService:
    """Synchronize company profile from RPO REST API."""

    def __init__(self, client: Optional[RpoClient] = None):
        self.client = client or RpoClient()

    def sync_company(self, company: Company) -> OrsrCompanyProfile:
        """Fetch RPO data and upsert into OrsrCompanyProfile, with ORSR fallback."""
        entity = self.client.get_entity_by_ico(company.ico)
        if entity is None:
            logger.info("RPO: no usable entity for ICO %s, falling back to ORSR.", company.ico)
            return OrsrSyncService().sync_company(company)

        structured = self._build_structured(entity)
        flat = self._build_flat_fields(entity)

        profile, _ = OrsrCompanyProfile.objects.update_or_create(
            company=company,
            defaults={
                "ico": entity.ico or company.ico,
                "obchodne_meno": entity.current_name,
                "sidlo": entity.current_address.format() if entity.current_address else "",
                "den_zapisu": self._parse_date(entity.establishment),
                "pravna_forma": entity.legal_form,
                "oddiel": self._extract_oddiel(entity),
                "oddiel_type": self._extract_oddiel_type(entity),
                "vlozka_cislo": self._extract_vlozka(entity),
                "konanie": flat["konanie"],
                "konanie_menom_spolocnosti": flat["konanie"],
                "vyska_zakladneho_imania": flat["vyska_zakladneho_imania"],
                "zapisovane_zakladne_imanie": flat["zapisovane_zakladne_imanie"],
                "zakladny_clensky_vklad": "",
                "predmet_podnikania": flat["predmet_podnikania"],
                "statutarny_organ": flat["statutarny_organ"],
                "spolocnici": flat["spolocnici"],
                "vklady_spolocnikov": flat["vklady_spolocnikov"],
                "prokura": flat["prokura"],
                "predstavenstvo": flat["predstavenstvo"],
                "kontrolna_komisia": flat["kontrolna_komisia"],
                "dalske_pravne_skutocnosti": flat["dalske_pravne_skutocnosti"],
                "orsr_aktualizacia_dat": self._parse_date(entity.db_modification_date),
                "orsr_datum_vypisu": None,
                "source_url": f"https://api.statistics.sk/rpo/v1/entity/{entity.rpo_id}",
                "raw_sections": {},
                "raw_payload": {"structured": structured, "source": "rpo", "rpo_id": entity.rpo_id},
                "fetch_ok": True,
                "last_error": "",
            },
        )

        self._extract_persons(profile)
        return profile

    # statutoryBodies codelist CL010113
    STATUTORY_CODE_KONATEL = "3"
    STATUTORY_CODE_PREDSTAVENSTVO = "99"
    STATUTORY_CODE_SPRAVCA = "16"
    STATUTORY_CODE_LIKVIDATOR = "17"

    # Verejnoprávne štatutárne orgány (CL010113)
    STATUTORY_CODE_PRIMATOR = "15"
    STATUTORY_CODE_STAROSTA = "14"
    STATUTORY_CODE_PREDNOSTA = "13"
    STATUTORY_CODE_RIADITEL = "11"
    STATUTORY_CODE_STATUTAR = "12"
    STATUTORY_CODE_VEDUCI = "30"
    STATUTORY_CODE_DEKAN = "35"
    STATUTORY_CODE_ARCIBISKUP = "36"

    # Cirkevné
    STATUTORY_CODE_BISKUP = "37"
    STATUTORY_CODE_FARAR = "38"

    # stakeholders codelist CL010109
    STAKEHOLDER_CODE_SPOLOCNIK = "99"
    STAKEHOLDER_CODE_PROKURISTA = "24"
    STAKEHOLDER_CODE_AKCIONAR = "94"
    STAKEHOLDER_CODE_DOZORNY = "98"

    def _build_structured(self, entity: RpoEntity) -> dict:
        """Build the 'structured' dict that the frontend reads from raw_payload."""
        current_statutory = [p for p in entity.statutory_bodies if p.is_current]
        current_stakeholders = [p for p in entity.stakeholders if p.is_current]

        # Obchodné spoločnosti
        konatelia = [p for p in current_statutory if p.stakeholder_type_code == self.STATUTORY_CODE_KONATEL]
        predstavenstvo = [p for p in current_statutory if p.stakeholder_type_code == self.STATUTORY_CODE_PREDSTAVENSTVO]
        spravcovia = [p for p in current_statutory if p.stakeholder_type_code == self.STATUTORY_CODE_SPRAVCA]
        likvidatori = [p for p in current_statutory if p.stakeholder_type_code == self.STATUTORY_CODE_LIKVIDATOR]

        # Verejná správa
        starostovia = [p for p in current_statutory if p.stakeholder_type_code == self.STATUTORY_CODE_STAROSTA]
        primatori = [p for p in current_statutory if p.stakeholder_type_code == self.STATUTORY_CODE_PRIMATOR]
        prednostovia = [p for p in current_statutory if p.stakeholder_type_code == self.STATUTORY_CODE_PREDNOSTA]
        riaditelia = [p for p in current_statutory if p.stakeholder_type_code == self.STATUTORY_CODE_RIADITEL]
        statutari = [p for p in current_statutory if p.stakeholder_type_code == self.STATUTORY_CODE_STATUTAR]
        veduci = [p for p in current_statutory if p.stakeholder_type_code == self.STATUTORY_CODE_VEDUCI]

        # Cirkevné a akademické
        dekani = [p for p in current_statutory if p.stakeholder_type_code == self.STATUTORY_CODE_DEKAN]
        arcibiskupi = [p for p in current_statutory if p.stakeholder_type_code == self.STATUTORY_CODE_ARCIBISKUP]
        biskupi = [p for p in current_statutory if p.stakeholder_type_code == self.STATUTORY_CODE_BISKUP]
        farari = [p for p in current_statutory if p.stakeholder_type_code == self.STATUTORY_CODE_FARAR]

        # All categorized
        categorized = konatelia + predstavenstvo + spravcovia + likvidatori + \
                      starostovia + primatori + prednostovia + riaditelia + \
                      statutari + veduci + dekani + arcibiskupi + biskupi + farari

        # Fallback: any statutory bodies we couldn't categorize (unknown codes)
        others = [p for p in current_statutory if p not in categorized]
        if not categorized:
            # No codes matched at all — use all as fallback "štatutári"
            others = current_statutory

        spolocnici = [p for p in current_stakeholders if p.stakeholder_type_code == self.STAKEHOLDER_CODE_SPOLOCNIK]
        prokuristi = [p for p in current_stakeholders if p.stakeholder_type_code == self.STAKEHOLDER_CODE_PROKURISTA]
        akcionari = [p for p in current_stakeholders if p.stakeholder_type_code == self.STAKEHOLDER_CODE_AKCIONAR]
        dozorna_rada = [p for p in current_stakeholders if p.stakeholder_type_code == self.STAKEHOLDER_CODE_DOZORNY]

        current_auth = next((a for a in entity.authorizations if a.is_current), None)
        current_activities = [a for a in entity.activities if a.is_current]
        current_equities = [e for e in entity.equities if e.is_current]

        capital = None
        equity_val = next((e for e in current_equities if e.value is not None), None)
        equity_paid = next((e for e in current_equities if e.value_paid is not None), None)
        if equity_val:
            capital = {
                "imanie": self._format_amount(equity_val.value),
                "currency": equity_val.currency,
            }
            if equity_paid:
                capital["rozsah_splatenia"] = self._format_amount(equity_paid.value_paid)

        current_deposits = [d for d in entity.deposits if d.is_current]

        return {
            "statutarny_organ": [self._person_to_structured(p) for p in (konatelia + others)],
            "statutarny_organ_typ": (konatelia[0].stakeholder_type if konatelia else (others[0].stakeholder_type if others else "")),
            "predstavenstvo": [self._person_to_structured(p) for p in predstavenstvo],
            "spravcovia": [self._person_to_structured(p) for p in spravcovia],
            "likvidatori": [self._person_to_structured(p) for p in likvidatori],
            "starostovia": [self._person_to_structured(p) for p in starostovia],
            "primatori": [self._person_to_structured(p) for p in primatori],
            "riaditelia": [self._person_to_structured(p) for p in (prednostovia + riaditelia + statutari + veduci)],
            "cirkevni_hodnostari": [self._person_to_structured(p) for p in (dekani + arcibiskupi + biskupi + farari)],
            "spolocnici": [self._person_to_structured(p) for p in spolocnici],
            "prokura": [self._person_to_structured(p) for p in prokuristi],
            "prokura_oprávnenie": [],
            "dozorna_rada": [self._person_to_structured(p) for p in dozorna_rada],
            "kontrolna_komisia": [],
            "akcionari": [self._person_to_structured(p) for p in akcionari],
            "predmet_podnikania": [{"text": a.description} for a in current_activities],
            "dalsie_pravne_skutocnosti": [
                {"text": f.get("value", "")} for f in entity.other_legal_facts if not f.get("validTo")
            ],
            "vyska_zakladneho_imania": capital,
            "konanie": current_auth.value if current_auth else "",
            "vklady_spolocnikov": [
                {
                    "name": d.full_name,
                    "vklad": f"{d.amount:,.2f}".replace(",", " ") if d.amount else "",
                    "currency": d.currency,
                }
                for d in current_deposits
            ],
        }

    def _build_flat_fields(self, entity: RpoEntity) -> dict:
        """Build flat field values for OrsrCompanyProfile columns."""
        current_statutory = [p for p in entity.statutory_bodies if p.is_current]
        current_stakeholders = [p for p in entity.stakeholders if p.is_current]
        current_activities = [a for a in entity.activities if a.is_current]
        current_auth = next((a for a in entity.authorizations if a.is_current), None)
        current_equities = [e for e in entity.equities if e.is_current]
        current_deposits = [d for d in entity.deposits if d.is_current]

        konatelia = [p for p in current_statutory if p.stakeholder_type_code == self.STATUTORY_CODE_KONATEL]
        predstavenstvo = [p for p in current_statutory if p.stakeholder_type_code == self.STATUTORY_CODE_PREDSTAVENSTVO]
        spravcovia = [p for p in current_statutory if p.stakeholder_type_code == self.STATUTORY_CODE_SPRAVCA]
        likvidatori = [p for p in current_statutory if p.stakeholder_type_code == self.STATUTORY_CODE_LIKVIDATOR]
        starostovia = [p for p in current_statutory if p.stakeholder_type_code == self.STATUTORY_CODE_STAROSTA]
        primatori = [p for p in current_statutory if p.stakeholder_type_code == self.STATUTORY_CODE_PRIMATOR]
        others = [p for p in current_statutory if p.stakeholder_type_code not in {
            self.STATUTORY_CODE_KONATEL, self.STATUTORY_CODE_PREDSTAVENSTVO,
            self.STATUTORY_CODE_SPRAVCA, self.STATUTORY_CODE_LIKVIDATOR,
            self.STATUTORY_CODE_STAROSTA, self.STATUTORY_CODE_PRIMATOR,
        }]
        if not konatelia and not predstavenstvo and not spravcovia and not likvidatori and not starostovia and not primatori:
            others = current_statutory

        # Build statutory display: group by role
        def _role_name(p):
            return p.stakeholder_type or "Štatutár"
        statutory_flat = []
        for p in konatelia + spravcovia + likvidatori + predstavenstvo + starostovia + primatori + others:
            label = f"{p.display_name} ({_role_name(p)})" if p.stakeholder_type else p.display_name
            statutory_flat.append(label)

        spolocnici = [p for p in current_stakeholders if p.stakeholder_type_code == self.STAKEHOLDER_CODE_SPOLOCNIK]
        prokuristi = [p for p in current_stakeholders if p.stakeholder_type_code == self.STAKEHOLDER_CODE_PROKURISTA]

        equity_val = next((e for e in current_equities if e.value is not None), None)
        equity_paid = next((e for e in current_equities if e.value_paid is not None), None)

        imanie_str = ""
        if equity_val:
            imanie_str = f"{self._format_amount(equity_val.value)} {equity_val.currency}".strip()
            if equity_paid:
                imanie_str += f" (Rozsah splatenia: {self._format_amount(equity_paid.value_paid)} {equity_paid.currency})".replace(",", " ")

        return {
            "predmet_podnikania": [a.description for a in current_activities],
            "statutarny_organ": statutory_flat,
            "spolocnici": [p.display_name or p.full_name for p in spolocnici],
            "prokura": [p.display_name for p in prokuristi],
            "predstavenstvo": [p.display_name for p in predstavenstvo],
            "kontrolna_komisia": [],
            "vklady_spolocnikov": [
                {"name": d.full_name, "vklad": f"{d.amount:,.2f} {d.currency}".replace(",", " ") if d.amount else ""}
                for d in current_deposits
            ],
            "konanie": current_auth.value if current_auth else "",
            "vyska_zakladneho_imania": imanie_str,
            "zapisovane_zakladne_imanie": "",
            "dalske_pravne_skutocnosti": "\n".join(
                f.get("value", "") for f in entity.other_legal_facts if not f.get("validTo")
            ),
        }

    def _person_to_structured(self, person: RpoPerson) -> dict:
        """Convert RpoPerson to the structured dict format the frontend expects (OrsrPerson)."""
        result: dict = {"name": person.display_name}

        if person.stakeholder_type:
            result["role"] = person.stakeholder_type

        if person.address:
            result["address"] = person.address.format()

        if person.valid_from:
            result["vznik_funkcie"] = person.valid_from

        if person.identifier and person.identifier != "Neuvedené":
            result["person_ico"] = person.identifier

        return result

    @staticmethod
    def _extract_oddiel(entity: RpoEntity) -> str:
        sr = entity.source_register
        if not sr or not sr.registration_number:
            return ""
        num = sr.registration_number
        parts = num.split("/")
        if len(parts) >= 2:
            return parts[0]
        # Non-standard format (municipalities etc.) — return whole number as-is
        return num

    @staticmethod
    def _extract_oddiel_type(entity: RpoEntity) -> str:
        sr = entity.source_register
        if not sr or not sr.registration_number:
            return ""
        num = sr.registration_number
        parts = num.split("/")
        if len(parts) >= 1:
            prefix = parts[0].lower()
            if prefix.startswith("sro"):
                return "sro"
            elif prefix.startswith("sa"):
                return "sa"
            elif prefix.startswith("dr"):
                return "dr"
            elif prefix.startswith("psp"):
                return "psp"
            elif prefix.startswith("nsp"):
                return "nsp"
            # Non-standard — leave empty (municipalities etc.)
        return ""

    @staticmethod
    def _extract_vlozka(entity: RpoEntity) -> str:
        sr = entity.source_register
        if not sr or not sr.registration_number:
            return ""
        num = sr.registration_number
        parts = num.split("/")
        if len(parts) >= 2:
            return parts[1]
        # Non-standard format — empty vlozka
        return ""

    @staticmethod
    def _parse_date(date_str: str) -> Optional[date]:
        if not date_str:
            return None
        try:
            return date.fromisoformat(date_str)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _format_amount(value: Optional[float]) -> str:
        if value is None:
            return ""
        return f"{float(value):,.2f}".replace(",", " ")

    @staticmethod
    def _extract_persons(profile: OrsrCompanyProfile) -> None:
        try:
            from connections.services import PersonExtractionService
            PersonExtractionService().extract_from_profile(profile)
        except Exception as exc:
            logger.warning("Person extraction failed for RPO profile %s: %s", profile.ico, exc)


