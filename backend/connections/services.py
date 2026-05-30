import logging
from datetime import date, datetime

from core.person_utils import is_valid_person_name
from .models import Person, PersonCompanyRelation, compute_fingerprint

logger = logging.getLogger(__name__)

ROLE_MAP = {
    "konateľ": PersonCompanyRelation.RoleType.KONATEL,
    "konatelia": PersonCompanyRelation.RoleType.KONATEL,
    "spoločník": PersonCompanyRelation.RoleType.SPOLOCNIK,
    "prokurista": PersonCompanyRelation.RoleType.PROKURISTA,
    "člen predstavenstva": PersonCompanyRelation.RoleType.CLEN_PREDSTAVENSTVA,
    "predseda predstavenstva": PersonCompanyRelation.RoleType.PREDSEDA_PREDSTAVENSTVA,
    "člen dozornej rady": PersonCompanyRelation.RoleType.CLEN_DOZORNEJ_RADY,
    "člen kontrolnej komisie": PersonCompanyRelation.RoleType.CLEN_KONTROLNEJ_KOMISIE,
    "akcionár": PersonCompanyRelation.RoleType.AKCIONAR,
    "riaditeľ": PersonCompanyRelation.RoleType.RIADITEL,
}

SECTION_DEFAULT_ROLES = {
    "statutarny_organ": PersonCompanyRelation.RoleType.KONATEL,
    "spolocnici": PersonCompanyRelation.RoleType.SPOLOCNIK,
    "prokura": PersonCompanyRelation.RoleType.PROKURISTA,
    "predstavenstvo": PersonCompanyRelation.RoleType.CLEN_PREDSTAVENSTVA,
    "kontrolna_komisia": PersonCompanyRelation.RoleType.CLEN_KONTROLNEJ_KOMISIE,
    "dozorna_rada": PersonCompanyRelation.RoleType.CLEN_DOZORNEJ_RADY,
    "akcionari": PersonCompanyRelation.RoleType.AKCIONAR,
}


def _parse_date(value) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _map_role(role_text: str) -> PersonCompanyRelation.RoleType:
    if not role_text:
        return PersonCompanyRelation.RoleType.INE
    normalized = role_text.strip().lower()
    for key, value in ROLE_MAP.items():
        if key in normalized:
            return value
    return PersonCompanyRelation.RoleType.INE


class PersonExtractionService:
    def extract_from_profile(self, profile) -> tuple[int, int]:
        """
        Extract persons and relations from an OrsrCompanyProfile.
        Returns (persons_created, relations_created).
        """
        company = profile.company
        structured = self._get_structured(profile)

        persons_created = 0
        relations_created = 0

        for section_key, default_role in SECTION_DEFAULT_ROLES.items():
            entries = structured.get(section_key, [])
            for entry in entries:
                person_data = self._parse_entry(entry)
                if not person_data or not is_valid_person_name(person_data["name"]):
                    continue

                person, created = self._get_or_create_person(person_data)
                if created:
                    persons_created += 1

                role_text = person_data.get("role", "")
                role = _map_role(role_text) if role_text else default_role

                _, rel_created = PersonCompanyRelation.objects.get_or_create(
                    person=person,
                    company=company,
                    role=role,
                    vznik_funkcie=person_data.get("vznik_funkcie"),
                    defaults={
                        "role_display": role_text or dict(PersonCompanyRelation.RoleType.choices).get(role, ""),
                        "is_active": True,
                        "source": "orsr",
                    },
                )
                if rel_created:
                    relations_created += 1

        return persons_created, relations_created

    def _get_structured(self, profile) -> dict:
        payload = getattr(profile, "raw_payload", None) or {}
        structured = payload.get("structured") if isinstance(payload, dict) else None
        return structured or {}

    def _parse_entry(self, entry) -> dict | None:
        if isinstance(entry, dict):
            name = (entry.get("name") or "").strip()
            if not name:
                return None
            return {
                "name": name,
                "title": (entry.get("title") or "").strip(),
                "address": (entry.get("address") or "").strip(),
                "person_ico": (entry.get("person_ico") or "").strip(),
                "role": (entry.get("role") or "").strip(),
                "vznik_funkcie": _parse_date(entry.get("vznik_funkcie")),
            }
        elif isinstance(entry, str):
            name = entry.strip()
            if not name:
                return None
            return {"name": name, "title": "", "address": "", "person_ico": "", "role": "", "vznik_funkcie": None}
        return None

    def _get_or_create_person(self, data: dict) -> tuple[Person, bool]:
        fingerprint = compute_fingerprint(
            name=data["name"],
            address=data.get("address", ""),
            person_ico=data.get("person_ico", ""),
        )

        person, created = Person.objects.get_or_create(
            fingerprint=fingerprint,
            defaults={
                "name": data["name"],
                "title": data.get("title", ""),
                "address": data.get("address", ""),
                "person_ico": data.get("person_ico", ""),
            },
        )

        if not created and data.get("address") and not person.address:
            person.address = data["address"]
            person.save(update_fields=["address", "updated_at"])

        return person, created
