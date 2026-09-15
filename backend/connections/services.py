import logging
from datetime import date, datetime

from django.db.models import Q

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

        Two passes, and the order matters. `osoby_historia` goes first because
        it is the only list that carries `zanik_funkcie`, and therefore the only
        one that can say a function has ended. The role sections follow and may
        only add people history did not mention -- a current-office list entry
        must never reopen a function that history has closed.
        """
        company = profile.company
        structured = self._get_structured(profile)

        # Whether the source told us the whole story for this company. An RPO
        # profile does; an ORSR výpis lists the current office-holders and no
        # end dates at all, so for it "no end date" means "not recorded", not
        # "still in office". That distinction is the difference between the
        # three answers we are allowed to give: áno, nie, nevieme.
        history_known = isinstance(structured.get("osoby_historia"), list)

        persons_created = 0
        relations_created = 0

        for entry in structured.get("osoby_historia") or []:
            created, relations = self._record(company, entry, None, history_known, authoritative=True)
            persons_created += created
            relations_created += relations

        for section_key, default_role in SECTION_DEFAULT_ROLES.items():
            for entry in structured.get(section_key, []):
                created, relations = self._record(company, entry, default_role, history_known, authoritative=False)
                persons_created += created
                relations_created += relations

        return persons_created, relations_created

    def _record(self, company, entry, default_role, history_known, *, authoritative: bool) -> tuple[int, int]:
        """Write one person entry. Returns (persons_created, relations_created)."""
        person_data = self._parse_entry(entry)
        if not person_data or not is_valid_person_name(person_data["name"]):
            return 0, 0

        person, person_created = self._get_or_create_person(person_data)

        role_text = person_data.get("role", "")
        role = _map_role(role_text) if role_text else (default_role or PersonCompanyRelation.RoleType.INE)
        zanik = person_data.get("zanik_funkcie")

        if zanik:
            is_active = False
        elif history_known:
            is_active = True
        else:
            is_active = None

        relation, relation_created = self._find_relation(
            company, person, role, person_data, zanik, is_active, role_text, authoritative
        )

        if relation_created:
            return (1 if person_created else 0), 1

        updates = self._updates_for(relation, zanik, role_text, is_active, authoritative)
        if updates:
            for field, value in updates.items():
                setattr(relation, field, value)
            relation.save(update_fields=[*updates, "updated_at"])

        return (1 if person_created else 0), 0

    def _find_relation(
        self, company, person, role, person_data, zanik, is_active, role_text, authoritative
    ) -> tuple[PersonCompanyRelation, bool]:
        """The relation this entry is about, creating one only if it is a new one.

        The uniqueness key is `(person, company, role, vznik_funkcie)`, and for
        an authoritative entry the key alone is not always enough to recognise a
        relation we already hold. A row written from an ORSR výpis has no start
        date, because that page does not give one; the register's history does,
        so the same office arrives with a date the row does not have and
        `get_or_create` would answer it with a *second* row -- an ended one
        beside the open one, which is the duplicate-instead-of-close failure this
        whole change exists to remove.

        So an authoritative entry with a start date may also adopt a single
        relation that is open and has no start date of its own: same person,
        same company, same role, and nothing to tell it apart from what the
        register just described. "A single one" is the guard, not a detail --
        with two open rows of unknown origin there is no way to say which the
        history entry is about, and guessing would close the wrong office.

        Today this path is empty: of 64 128 relations, 23 have no start date and
        none of those is in a company with an RPO profile. It is here because
        the row it protects is exactly the kind an ORSR výpis leaves behind, and
        the companies that fall back to that reader are re-read every four hours
        -- the first one that later turns up in RPO would otherwise be written
        twice.
        """
        vznik = person_data.get("vznik_funkcie")
        exact = PersonCompanyRelation.objects.filter(
            person=person, company=company, role=role, vznik_funkcie=vznik
        ).first()
        if exact is not None:
            return exact, False
        if not authoritative or vznik is None:
            return self._create_relation(
                company, person, role, person_data, zanik, is_active, role_text
            )

        candidates = list(
            PersonCompanyRelation.objects.filter(
                Q(is_active=True) | Q(is_active__isnull=True),
                person=person,
                company=company,
                role=role,
                vznik_funkcie__isnull=True,
                zanik_funkcie__isnull=True,
            )[:2]
        )
        if len(candidates) != 1:
            return self._create_relation(
                company, person, role, person_data, zanik, is_active, role_text
            )

        # Written here rather than handed back to the caller: the start date is
        # how the row was identified, so it belongs to the identification and
        # not to the verdict `_updates_for` computes.
        adopted = candidates[0]
        adopted.vznik_funkcie = vznik
        adopted.save(update_fields=["vznik_funkcie", "updated_at"])
        return adopted, False

    @staticmethod
    def _create_relation(
        company, person, role, person_data, zanik, is_active, role_text
    ) -> tuple[PersonCompanyRelation, bool]:
        relation = PersonCompanyRelation.objects.create(
            person=person,
            company=company,
            role=role,
            vznik_funkcie=person_data.get("vznik_funkcie"),
            role_display=role_text or dict(PersonCompanyRelation.RoleType.choices).get(role, ""),
            zanik_funkcie=zanik,
            is_active=is_active,
            source="orsr",
        )
        return relation, True

    @staticmethod
    def _updates_for(relation, zanik, role_text, is_active, authoritative: bool) -> dict:
        """What may change on a relation we already hold.

        Only an authoritative entry -- one from the history list -- may move the
        verdict, and it may only close a function or confirm one. An entry from
        a current-office list carries no end date, so it can neither close
        anything nor, having no history behind it, upgrade "nevieme" to "áno".
        """
        updates: dict = {}

        if authoritative:
            if zanik:
                if relation.zanik_funkcie != zanik:
                    updates["zanik_funkcie"] = zanik
                if relation.is_active is not False:
                    updates["is_active"] = False
            elif relation.is_active is not True:
                updates["is_active"] = is_active

        if not relation.role_display and role_text:
            updates["role_display"] = role_text

        return updates

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
                "zanik_funkcie": _parse_date(entry.get("zanik_funkcie")),
                "birth_date": _parse_date(entry.get("birth_date")),
            }
        elif isinstance(entry, str):
            name = entry.strip()
            if not name:
                return None
            return {
                "name": name,
                "title": "",
                "address": "",
                "person_ico": "",
                "role": "",
                "vznik_funkcie": None,
                "zanik_funkcie": None,
                "birth_date": None,
            }
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
                "birth_date": data.get("birth_date"),
            },
        )

        # `birth_date` is not an input to `compute_fingerprint`, so filling it
        # in on a row that already exists cannot move that row -- and a row
        # whose date is already known keeps it. A blank here is "the section of
        # the document this row came from did not state one", which the section
        # that does state one is allowed to fill, in either direction of the
        # read. Only the first non-empty date wins; two dates for one row would
        # mean two people, which is a question for identity resolution rather
        # than something to overwrite silently.
        updates = []
        if data.get("address") and not person.address:
            person.address = data["address"]
            updates.append("address")
        if data.get("birth_date") and not person.birth_date:
            person.birth_date = data["birth_date"]
            updates.append("birth_date")
        if updates:
            person.save(update_fields=updates + ["updated_at"])

        return person, created
