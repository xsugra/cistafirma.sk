"""Sync service that maps RPO API data to OrsrCompanyProfile.

Replaces OrsrSyncService for companies available in RPO. Falls back to
ORSR scraping only when RPO returns no result (non-commercial-register entities
are not in RPO).
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from django.db.models import Q

from companies.models import Company
from registers.integrations.rpo_client import (
    RpoClient,
    RpoEntity,
    RpoPerson,
)
from registers.models import OrsrCompanyProfile
from registers.services.orsr_sync import OrsrSyncService

logger = logging.getLogger(__name__)

PERSON_HISTORY_KEY = "osoby_historia"
"""Where `structured` carries every person the register records, ended included.

Two readers depend on this name and must not drift apart: the person extractor,
which is the only thing that can write `zanik_funkcie`, and the re-read
rotation, which selects the profiles that do not have it yet. A profile without
this key is one whose person history has never been read -- which is also why
the marker doubles as the population for `refresh_person_history` and empties
itself as the rotation runs.
"""

def pending_person_history():
    """Profiles whose person history has never been read from the register.

    Defined next to `PERSON_HISTORY_KEY` because it is the other half of it: the
    key names what the reader writes, this names who is missing it, and the two
    have to agree or the rotation either loops for ever or skips companies
    silently. Both the beat task and `refresh_person_history` read it from here
    rather than repeating the filter.

    Three conditions, each load-bearing:

    * **`rpo_id` present.** The 231 profiles from the HTML výpis reader carry no
      `rpo_id` and never will, because that reader is not the one being
      replaced. Leaving them in would spend 15 requests a minute against
      orsr.sk for ever, selecting the same companies every run.
    * **`structured` without the key** -- and `structured` missing altogether
      counts as missing it. Written as an explicit `isnull` disjunct because a
      JSON key lookup on an absent object yields SQL NULL, and `exclude()` on a
      NULL drops the row: a profile with an `rpo_id` and no `structured` would
      silently never be repaired. That population is empty today (all 24 237
      `rpo_id` profiles have `structured`), which is exactly why it would have
      gone unnoticed.
    * **least recently read first.** `last_synced_at` is `auto_now`, so a
      company moves to the back the moment it is read -- that is the cursor, and
      it is why a company that fails for good cannot pin the head of the queue
      the way `order_by('id')` let it: 24 000 companies come round before it is
      tried again.
    """
    missing = Q(raw_payload__structured__isnull=True) | ~Q(
        raw_payload__structured__has_key=PERSON_HISTORY_KEY
    )
    return (
        OrsrCompanyProfile.objects
        .filter(raw_payload__has_key="rpo_id")
        .filter(missing)
        .order_by("last_synced_at")
    )


def _drop_person_history_marker(profile: OrsrCompanyProfile) -> None:
    """Take `osoby_historia` back off a profile whose extraction failed.

    Saved, not merely mutated: the caller has already written the payload by the
    time extraction runs, so an in-memory removal would be gone with the next
    request while the row kept claiming a history it never applied. The save
    includes `last_synced_at` deliberately -- it is the rotation's cursor, and
    an attempt that ran has to move it, or a company that fails extraction
    every time sits at the head of every rotation for ever.
    """
    payload = profile.raw_payload
    structured = payload.get("structured") if isinstance(payload, dict) else None
    if not isinstance(structured, dict) or PERSON_HISTORY_KEY not in structured:
        return
    structured.pop(PERSON_HISTORY_KEY)
    profile.raw_payload = payload
    if profile.pk:
        profile.save(update_fields=["raw_payload", "last_synced_at"])


def _move_rotation_cursor(profile: OrsrCompanyProfile) -> None:
    """Move an attempt's profile to the back of the rotation without writing data.

    For the one outcome that is neither a success nor a reason to retry: the
    register answered, and its answer was that it holds no such entity. Nothing
    may be marked -- `osoby_historia: []` would say "this company has no
    people", which is not what happened -- so without this the profile would be
    re-selected at the head of every rotation for ever.
    """
    if profile.pk:
        profile.save(update_fields=["last_synced_at"])


NOT_STATED = "Neuvedené"
"""What RPO writes into a field it has no value for.

It is a *value*, not an absence. `entity.ico == NOT_STATED` is a truthy string,
so the `or company.ico` fallback never fired and the sentinel went into
`ico = varchar(8)` as nine characters. Measured 2026-09-11: every such write
raised `DataError`, the whole profile was lost -- and that is the only reason
the defect was visible at all. One character more of column width and the
profile would have been saved, quietly, with an IČO of "Neuvedené".
"""


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
                "ico": self._storable(entity.ico, "ico", ico=company.ico) or company.ico,
                "obchodne_meno": self._storable(entity.current_name, "obchodne_meno", ico=company.ico),
                "sidlo": self._storable(
                    entity.current_address.format() if entity.current_address else "",
                    "sidlo",
                    ico=company.ico,
                ),
                "den_zapisu": self._parse_date(entity.establishment),
                "pravna_forma": self._storable(entity.legal_form, "pravna_forma", ico=company.ico),
                "oddiel": self._storable(self._extract_oddiel(entity), "oddiel", ico=company.ico),
                "oddiel_type": self._storable(
                    self._extract_oddiel_type(entity), "oddiel_type", ico=company.ico
                ),
                "vlozka_cislo": self._storable(
                    self._extract_vlozka(entity), "vlozka_cislo", ico=company.ico
                ),
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
                "raw_payload": {
                    "structured": structured,
                    "source": "rpo",
                    "rpo_id": entity.rpo_id,
                    # Kept whole because it is what `oddiel` / `oddiel_type` /
                    # `vlozka_cislo` are *parsed* from, and parsing is lossy: a
                    # registration number that does not fit its column is
                    # refused below, and this is then the only place it exists.
                    "source_register": self._source_register_payload(entity),
                },
                "fetch_ok": True,
                "last_error": "",
            },
        )

        self._extract_persons(profile)
        return profile

    def refresh_person_history(self, profile: OrsrCompanyProfile) -> str:
        """Re-read one profile's person history from RPO, and only that.

        Narrower than `sync_company` on purpose, and the boundary is the whole
        point. The companies this serves are the ones `sync_company_orsr_data`
        refuses outright -- dissolved, or a legal form ORSR does not carry --
        and both refusals answer a question about **ORSR monitoring**: ORSR
        keeps current records, so spending its bandwidth on a company that
        cannot change is waste. Neither refusal says anything about whether the
        register holds a person history, and RPO does, in full.

        Measured 2026-09-13: 92 of the 24 227 profiles waiting for a first read
        belong to companies that task skips, and a sample of three answered with
        16, 62 and 30 person entries. Skipping them was leaving the richest
        history of all -- the *ended* functions, the entire reason `is_active`
        has a third value -- unread for ever, and a population that could never
        reach zero, so the one-off repair could never be retired with
        confidence.

        Three things it does not do, each for a reason:

        * **No flat fields.** A person read is not a profile sync, and rewriting
          `obchodne_meno`/`sidlo`/... for a dissolved company at 15 requests a
          minute is work nobody asked for from data nobody reads.
        * **No `OrsrSyncService` fallback.** It is what `sync_company` does when
          RPO has no entity, and here it would be actively harmful: an ORSR
          výpis over an RPO payload drops `rpo_id` (the known overwrite), which
          takes the company out of `pending_person_history` *without* its
          history ever having been read. The population is profiles that already
          carry an `rpo_id`, so the register has answered for every one of them
          once already; "no entity now" is a fact to report, not a gap to fill
          from another register.
        * **No `fetch_ok`.** That flag and its `CompanySyncStatus` row are ORSR
          monitoring state. A person read is not an ORSR attempt, and filing one
          as such would put companies ORSR does not carry into the ORSR retry
          lane for ever.

        The profile keeps the marker only if the extraction it announces
        succeeded -- it is written with the payload and taken back off by
        `_extract_persons` when the write fails. Returns a phrase for the log;
        the profile is the record.
        """
        company = profile.company
        entity = self.client.get_entity_by_ico(company.ico)
        if entity is None:
            logger.error(
                "Person history: RPO holds no entity for %s (profile %s)",
                company.ico, profile.pk,
            )
            _move_rotation_cursor(profile)
            return f"RPO has no entity for {company.ico}"

        history = self._build_person_history(entity)
        payload = dict(profile.raw_payload or {})
        structured = dict(payload.get("structured") or {})
        structured[PERSON_HISTORY_KEY] = history
        payload["structured"] = structured
        profile.raw_payload = payload
        if profile.pk:
            profile.save(update_fields=["raw_payload", "last_synced_at"])
        applied = self._extract_persons(profile)
        if not applied:
            return f"extraction failed for {company.ico}"
        return f"{len(history)} person entries"

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
            # Not read by any display section -- this is the person graph's
            # source, and its presence is also how the extractor knows the
            # history for this company was actually read.
            PERSON_HISTORY_KEY: self._build_person_history(entity),
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

    def _person_to_structured(self, person: RpoPerson, *, include_end: bool = False) -> dict:
        """Convert RpoPerson to the structured dict format the frontend expects (OrsrPerson).

        `include_end` adds `zanik_funkcie`. It is off for the display sections,
        which answer "who runs this company now" and must stay current-only, and
        on for `osoby_historia`, which is the only place the end of a function
        can be read from.
        """
        result: dict = {"name": person.display_name}

        if person.stakeholder_type:
            result["role"] = person.stakeholder_type

        if person.address:
            result["address"] = person.address.format()

        if person.valid_from:
            result["vznik_funkcie"] = person.valid_from

        if include_end and person.valid_to:
            result["zanik_funkcie"] = person.valid_to

        if person.identifier and person.identifier != NOT_STATED:
            result["person_ico"] = person.identifier

        return result

    def _build_person_history(self, entity: RpoEntity) -> list[dict]:
        """Every person the register records for this company, ended ones included.

        The display sections are current-only, and that is right for them -- but
        until 2026-09-13 it was the *only* thing we stored, so a function that
        had ended simply vanished from the payload instead of arriving as an
        ended function. `PersonCompanyRelation` then had nothing to write but
        the `True` it hardcoded, and the database came to assert that all 64 128
        relations were current. The evidence that it was not: six people still
        marked active in a dissolved družstvo, whose RPO record reports a
        `validTo` for every one of them.

        A person who held the same office twice appears twice here, with
        different `vznik_funkcie`, which is what the relation's uniqueness key
        expects.
        """
        everybody = list(entity.statutory_bodies) + list(entity.stakeholders)

        seen: set[tuple] = set()
        result: list[dict] = []
        for person in everybody:
            key = (
                person.display_name,
                person.stakeholder_type_code,
                person.valid_from,
                person.valid_to,
            )
            if key in seen:
                continue
            seen.add(key)
            result.append(self._person_to_structured(person, include_end=True))

        return result

    @staticmethod
    def _storable(value: Optional[str], field: str, *, ico: str = "") -> str:
        """Map a source value onto a column -- or refuse it, never truncate.

        Two ways a source value must not be stored verbatim:

        * it is `NOT_STATED`, which states an absence and therefore has to
          *become* one. This is the whole defect: the sentinel is truthy, so
          every `or fallback` and every `if not value` guard in this module
          read it as data;
        * it does not fit the column. Truncating would store a string nobody
          wrote, and would do it silently -- the row would look complete.
          Refusing leaves the column empty and this warning leaves a trace.

        The width comes from the model rather than from a literal here, so the
        guard cannot drift away from the column it is guarding.
        """
        if value is None:
            return ""
        text = str(value)
        if not text or text == NOT_STATED:
            return ""
        max_length = OrsrCompanyProfile._meta.get_field(field).max_length
        if max_length is not None and len(text) > max_length:
            logger.warning(
                "RPO: refusing %s for IČO %s -- %d characters do not fit "
                "%s(%d): %r",
                field,
                ico or "?",
                len(text),
                field,
                max_length,
                text,
            )
            return ""
        return text

    @staticmethod
    def _source_register_payload(entity: RpoEntity) -> dict:
        sr = entity.source_register
        if not sr:
            return {}
        return {
            "register_name": sr.register_name,
            "registration_office": sr.registration_office,
            "registration_number": sr.registration_number,
        }

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
    def _extract_persons(profile: OrsrCompanyProfile) -> bool:
        """Apply the person history the profile carries. True when it was applied.

        A failure here is not a warning, and it is not cosmetic. `osoby_historia`
        is the rotation's marker -- `pending_person_history` selects exactly the
        profiles that lack it -- so a profile that keeps the key after its
        extraction threw is one the repair will never look at again, with the
        relations never written. That is not hypothetical: it is what the
        missing `connections_person.name_normalized` column did, and the symptom
        was a company page that had silently lost its people while every log
        line said the sync succeeded.

        So the key comes back off when the write fails, which returns the
        company to the population to be read again. What that costs is one read
        of a register that still holds the answer; what it keeps is the meaning
        of the marker, without which the rotation cannot be trusted to end.
        """
        try:
            from connections.services import PersonExtractionService
            PersonExtractionService().extract_from_profile(profile)
            return True
        except Exception:
            logger.error(
                "Person extraction failed for RPO profile %s", profile.ico, exc_info=True
            )
            _drop_person_history_marker(profile)
            return False


