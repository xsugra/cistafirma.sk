"""The three things that make the person-history backfill safe to leave running.

It re-reads 24 237 companies against a register that has no API and answers 15
requests a minute, so it has to be bounded, it has to stop on its own, and it
must not be able to select the same companies for ever. Those are the three
properties pinned here.

The population is a query over the profile's own payload -- the marker the new
reader writes. That is what makes it self-emptying, and it is also the one thing
that can break silently: `exclude()` on a JSON key lookup drops rows where the
key's parent is missing, because SQL NULL is not true. The last test here is the
guard against exactly that.
"""

import io
from datetime import date, timedelta
from unittest import mock

from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from companies.models import Company
from connections.models import Person, PersonCompanyRelation
from registers.eligibility import is_orsr_eligible_company
from registers.integrations.rpo_client import RpoEntity, RpoPerson
from registers.models import OrsrCompanyProfile
from registers.scrapers.orsr_person_search import (
    OrsrPersonHit,
    OrsrPersonSearch,
    split_name,
)
from registers.services.rpo_sync import (
    PERSON_HISTORY_KEY,
    RpoSyncService,
    pending_person_history,
)
from registers.tasks import (
    person_history_batch,
    read_person_history,
    schedule_person_history_resync,
)


def _company(ico: str, ruz_id: int = 1, name: str = "Test s.r.o.") -> Company:
    return Company.objects.create(ruz_id=ruz_id, ico=ico, nazov_UJ=name)


def _profile(company: Company, payload: dict, *, synced_days_ago: int = 0):
    profile = OrsrCompanyProfile.objects.create(
        company=company, ico=company.ico, raw_payload=payload
    )
    if synced_days_ago:
        # `last_synced_at` is `auto_now`, so it cannot be set on create -- the
        # ordering test needs rows that differ in it.
        OrsrCompanyProfile.objects.filter(pk=profile.pk).update(
            last_synced_at=timezone.now() - timedelta(days=synced_days_ago)
        )
        profile.refresh_from_db()
    return profile


class RpoPersonDisplayNameTests(TestCase):
    """A name that exists in parts must not be thrown away.

    The RPO API returns some natural persons with `formatedName` empty and no
    `fullName`, but with `givenNames` and `familyNames` filled in. With only
    those two fallbacks the name came out empty, and an empty name is what the
    extractor refuses to write -- so 481 companies held a statutory body with a
    role, an address and a start date, and none of it reached the person graph.
    """

    def test_formatted_name_wins(self):
        person = RpoPerson(
            formatted_name="Ing. Ján Novák", given_names=["Ján"], family_names=["Novák"]
        )
        self.assertEqual(person.display_name, "Ing. Ján Novák")

    def test_full_name_is_the_second_choice(self):
        person = RpoPerson(full_name="Ján Novák", given_names=["Ján"], family_names=["Novák"])
        self.assertEqual(person.display_name, "Ján Novák")

    def test_parts_are_assembled_when_the_whole_is_missing(self):
        # entity 16257208, the measured case: two directors of a school.
        person = RpoPerson(given_names=["Marta"], family_names=["Hanečáková"])
        self.assertEqual(person.display_name, "Marta Hanečáková")

    def test_a_nameless_stakeholder_stays_nameless(self):
        # A legal person as spoločník arrives with no personName at all. It must
        # still come out empty -- the extractor's refusal is correct there.
        self.assertEqual(RpoPerson(identifier="12345678").display_name, "")


class PersonHistoryBuildTests(TestCase):
    def setUp(self):
        self.service = RpoSyncService()

    def _entity(self, *people: RpoPerson) -> RpoEntity:
        return RpoEntity(ico="50059959", statutory_bodies=list(people))

    def test_ended_functions_are_included(self):
        entity = self._entity(
            RpoPerson(formatted_name="Ján Novák", stakeholder_type="Konateľ",
                      valid_from="2010-01-01", valid_to="2015-12-31"),
            RpoPerson(formatted_name="Mária Kováčová", stakeholder_type="Konateľ",
                      valid_from="2015-12-31"),
        )
        history = self.service._build_person_history(entity)

        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["zanik_funkcie"], "2015-12-31")
        self.assertNotIn("zanik_funkcie", history[1])

    def test_a_person_who_held_office_twice_appears_twice(self):
        entity = self._entity(
            RpoPerson(formatted_name="Ján Novák", stakeholder_type="Konateľ",
                      valid_from="2005-01-01", valid_to="2010-12-31"),
            RpoPerson(formatted_name="Ján Novák", stakeholder_type="Konateľ",
                      valid_from="2015-01-01"),
        )
        history = self.service._build_person_history(entity)

        self.assertEqual(
            [entry["vznik_funkcie"] for entry in history], ["2005-01-01", "2015-01-01"]
        )

    def test_the_same_record_listed_twice_is_listed_once(self):
        # A konateľ appears in both `statutoryBodies` and `stakeholders` in some
        # RPO records; the relation's uniqueness key cannot tell them apart.
        person = RpoPerson(formatted_name="Ján Novák", stakeholder_type="Konateľ",
                           valid_from="2010-01-01")
        duplicate = RpoPerson(formatted_name="Ján Novák", stakeholder_type="Konateľ",
                              valid_from="2010-01-01")
        entity = RpoEntity(
            ico="50059959", statutory_bodies=[person], stakeholders=[duplicate]
        )
        self.assertEqual(len(self.service._build_person_history(entity)), 1)


class PendingPersonHistoryTests(TestCase):
    """Who the rotation may select -- and who it must never select."""

    def test_selects_a_profile_without_the_marker(self):
        profile = _profile(_company("50059959"), {"rpo_id": 1, "structured": {}})
        self.assertEqual(person_history_batch(10), [profile.company_id])

    def test_skips_a_profile_the_new_reader_has_already_written(self):
        _profile(
            _company("50059959"),
            {"rpo_id": 1, "structured": {PERSON_HISTORY_KEY: []}},
        )
        self.assertEqual(person_history_batch(10), [])

    def test_skips_the_html_scraper_profiles(self):
        # 231 of them, and they will never gain the key: that reader is not the
        # one being replaced. Selecting them would spend 15 requests a minute
        # against orsr.sk for ever, on the same companies every run.
        _profile(_company("50059959"), {"structured": {"statutarny_organ": []}})
        self.assertEqual(person_history_batch(10), [])

    def test_a_payload_without_structured_is_not_dropped(self):
        # The trap: `exclude(raw_payload__structured__has_key=...)` compiles to
        # `NOT (raw_payload->'structured' ? ...)`, which is NULL -- and so
        # neither true nor false -- when `structured` is absent, and `exclude()`
        # discards rows whose condition is NULL. Such a profile would be
        # invisible to every run for ever. Empty today; the first RPO payload
        # written without `structured` would make it real.
        profile = _profile(_company("50059959"), {"rpo_id": 1})
        self.assertEqual(person_history_batch(10), [profile.company_id])

    def test_least_recently_read_first_and_the_cursor_moves(self):
        old = _profile(_company("11111111", 1), {"rpo_id": 1}, synced_days_ago=30)
        new = _profile(_company("22222222", 2), {"rpo_id": 2}, synced_days_ago=1)

        self.assertEqual(person_history_batch(10), [old.company_id, new.company_id])
        self.assertEqual(person_history_batch(1), [old.company_id])

        # Reading a company writes the marker and touches `last_synced_at`, so
        # it leaves the population -- which is also why a company that fails for
        # good cannot pin the head of the queue.
        OrsrCompanyProfile.objects.filter(pk=old.pk).update(
            raw_payload={"rpo_id": 1, "structured": {PERSON_HISTORY_KEY: []}},
            last_synced_at=timezone.now(),
        )
        self.assertEqual(person_history_batch(10), [new.company_id])

    def test_the_rotation_empties_itself(self):
        _profile(_company("11111111", 1), {"rpo_id": 1})
        self.assertEqual(pending_person_history().count(), 1)

        OrsrCompanyProfile.objects.update(
            raw_payload={"rpo_id": 1, "structured": {PERSON_HISTORY_KEY: []}}
        )
        self.assertEqual(pending_person_history().count(), 0)


class SchedulePersonHistoryResyncTests(TestCase):
    def test_dispatches_one_task_per_company(self):
        first = _profile(_company("11111111", 1), {"rpo_id": 1}, synced_days_ago=2)
        second = _profile(_company("22222222", 2), {"rpo_id": 2}, synced_days_ago=1)

        with mock.patch(
            "registers.tasks.read_person_history.delay"
        ) as delay:
            schedule_person_history_resync(10)

        self.assertEqual(
            [call.args[0] for call in delay.call_args_list],
            [first.company_id, second.company_id],
        )

    def test_does_nothing_once_the_population_is_empty(self):
        with mock.patch("registers.tasks.read_person_history.delay") as delay:
            schedule_person_history_resync(10)
        delay.assert_not_called()


class RefreshPersonHistoryCommandTests(TestCase):
    def test_dry_run_counts_the_same_population_and_dispatches_nothing(self):
        _profile(_company("11111111", 1), {"rpo_id": 1})
        _profile(_company("22222222", 2), {"rpo_id": 2})
        _profile(
            _company("33333333", 3),
            {"rpo_id": 3, "structured": {PERSON_HISTORY_KEY: []}},
        )
        _profile(_company("44444444", 4), {"structured": {}})

        out = io.StringIO()
        with mock.patch("registers.tasks.read_person_history.delay") as delay:
            call_command("refresh_person_history", "--dry-run", stdout=out)

        delay.assert_not_called()
        self.assertIn("Firmy bez precitanej historie osob: 2", out.getvalue())

    def test_ico_runs_inline_and_says_whether_the_history_was_written(self):
        """The operator's path: one company, now, with the answer in front of them.

        `--ico` is deliberately not dispatched. The interesting answer is not
        "queued" but what happened to the relations, and for a company the
        operator already suspects, that answer has to arrive in this process --
        including the case where the sync ran and wrote nothing, which is the
        failure this whole rotation exists to repair.
        """
        company = _company("00363243", 7, "Poľnohospodárske družstvo Trávnik")
        person = Person.objects.create(fingerprint="f-jn", name="Ján Novák")
        PersonCompanyRelation.objects.create(
            person=person, company=company, role="konatel", is_active=True
        )
        _profile(company, {"rpo_id": 1, "structured": {}})

        out = io.StringIO()
        with mock.patch(
            "registers.management.commands.refresh_person_history.read_person_history"
        ) as task:
            call_command("refresh_person_history", "--ico", "00363243", stdout=out)

        task.assert_called_once_with(company.id)
        # The profile is still without the key, so the command must say so
        # rather than reporting a success it cannot see.
        self.assertIn("CHYBA", out.getvalue())
        self.assertIn("vazby: spolu=1 aktualne=1 ukoncene=0 nevieme=0", out.getvalue())

    def test_an_unknown_ico_is_an_error_not_an_empty_run(self):
        with self.assertRaises(CommandError):
            call_command("refresh_person_history", "--ico", "99999999", stdout=io.StringIO())


class _FakeRpoClient:
    """A register that answers with one entity, and remembers who was asked."""

    def __init__(self, entity):
        self.entity = entity
        self.asked: list[str] = []

    def get_entity_by_ico(self, ico):
        self.asked.append(ico)
        return self.entity


def _rpo_entity(*people: RpoPerson, rpo_id: int = 864903) -> RpoEntity:
    return RpoEntity(rpo_id=rpo_id, ico="31408834", statutory_bodies=list(people))


def _ended_and_current() -> RpoEntity:
    return _rpo_entity(
        RpoPerson(
            formatted_name="Ján Novák",
            stakeholder_type="Konateľ",
            valid_from="2010-01-01",
            valid_to="2019-06-30",
        ),
        RpoPerson(
            formatted_name="Mária Kováčová",
            stakeholder_type="Konateľ",
            valid_from="2019-06-30",
        ),
    )


class PersonHistoryRefreshTests(TestCase):
    """The repair must be able to mark every company its own rotation selects.

    The population is "profiles without the marker", so a company the rotation
    selects and the worker then refuses to read is not a slow company -- it is a
    rotation that cannot end, a `--dry-run` that never reports zero, and a beat
    entry nobody can retire with confidence.

    That is what `sync_company_orsr_data` did here. Its eligibility rule answers
    a question about ORSR **monitoring** -- ORSR keeps current records, so
    watching a dissolved company spends somebody else's server on an answer that
    cannot change -- and the person-history read was inheriting it. Measured
    2026-09-13: 92 of the 24 227 waiting profiles belong to companies it skips
    (90 dissolved, 2 with a legal form ORSR does not carry), and three sampled
    answered with 16, 62 and 30 person entries. They were, in other words, the
    companies whose ended functions -- the entire reason `is_active` has a third
    value -- were furthest out of reach.
    """

    def _run(self, company, entity):
        client = _FakeRpoClient(entity)
        with mock.patch(
            "registers.services.rpo_sync.RpoClient", return_value=client
        ):
            result = read_person_history(company.id)
        return client, result

    def test_a_company_the_monitoring_rule_refuses_is_still_read(self):
        company = _company("31408834", 1, "LCS spol. s r.o. v likvidácii")
        company.pravna_forma = "112"
        company.datum_zrusenia = date(2026, 7, 24)
        company.save(update_fields=["pravna_forma", "datum_zrusenia"])
        self.assertFalse(is_orsr_eligible_company(company))  # the premise
        _profile(company, {"rpo_id": 864903, "structured": {}})

        client, _ = self._run(company, _ended_and_current())

        self.assertEqual(client.asked, ["31408834"])
        profile = OrsrCompanyProfile.objects.get(company=company)
        history = profile.raw_payload["structured"][PERSON_HISTORY_KEY]
        self.assertEqual(len(history), 2)

        ended = PersonCompanyRelation.objects.get(company=company, zanik_funkcie__isnull=False)
        self.assertIs(ended.is_active, False)
        self.assertEqual(ended.zanik_funkcie, date(2019, 6, 30))

    def test_it_writes_no_flat_fields_and_creates_no_profile(self):
        # A person read is not a profile sync. Rewriting `obchodne_meno` and the
        # rest for a dissolved company at 15 requests a minute is work nobody
        # asked for, over fields nobody reads for these companies.
        company = _company("31408834", 1, "LCS spol. s r.o. v likvidácii")
        profile = _profile(company, {"rpo_id": 864903, "structured": {}})

        self._run(company, _ended_and_current())

        profile.refresh_from_db()
        self.assertEqual(OrsrCompanyProfile.objects.filter(company=company).count(), 1)
        self.assertEqual(profile.obchodne_meno, "")
        self.assertEqual(profile.raw_payload["rpo_id"], 864903)

    def test_it_never_falls_back_to_the_orsr_scraper(self):
        """The fallback would cost more than the read it replaces.

        `sync_company` falls back to an ORSR výpis when RPO has no entity, and
        here that would be actively harmful: an ORSR payload over an RPO one
        drops `rpo_id` -- the known overwrite -- which takes the company out of
        `pending_person_history` *without* its history ever having been read.
        The population is profiles that already carry an `rpo_id`, so the
        register has answered for every one of them once already; "no entity
        now" is a fact to report, not a gap to fill from another register.
        """
        company = _company("31408834", 1, "LCS spol. s r.o. v likvidácii")
        profile = _profile(company, {"rpo_id": 864903, "structured": {}})

        with mock.patch("registers.services.rpo_sync.OrsrSyncService") as scraper:
            self._run(company, _ended_and_current())

        scraper.assert_not_called()
        profile.refresh_from_db()
        self.assertIn("rpo_id", profile.raw_payload)

    def test_a_register_that_holds_no_entity_writes_no_marker_but_moves_on(self):
        # `osoby_historia: []` would be a claim -- "this company has no people"
        # -- and it is not what happened. Nothing may be marked, so the count
        # stops above zero and the operator sees the IČO named in the log. What
        # the attempt still does is move the cursor: otherwise a company the
        # register cannot answer for would sit at the head of every rotation for
        # ever.
        company = _company("31408834", 1)
        profile = _profile(company, {"rpo_id": 864903, "structured": {}}, synced_days_ago=5)
        before = profile.last_synced_at

        _, result = self._run(company, None)

        profile.refresh_from_db()
        self.assertIn("no entity", result)
        self.assertEqual(profile.raw_payload["structured"], {})
        self.assertGreater(profile.last_synced_at, before)
        self.assertEqual(pending_person_history().count(), 1)

    def test_a_failed_extraction_leaves_the_profile_in_the_population(self):
        """The marker may not outlive the extraction it announces.

        This is the shape of the defect that started all of it: the extractor
        raised `column connections_person.name_normalized does not exist`, the
        sync logged a warning and reported success, and the profile kept a key
        saying its history had been applied. Every reader of that key -- this
        rotation included -- then treated a company with no relations as done.
        """
        company = _company("31408834", 1)
        profile = _profile(company, {"rpo_id": 864903, "structured": {}}, synced_days_ago=5)
        before = profile.last_synced_at

        with mock.patch(
            "connections.services.PersonExtractionService.extract_from_profile",
            side_effect=RuntimeError("column connections_person.name_normalized does not exist"),
        ):
            _, result = self._run(company, _ended_and_current())

        profile.refresh_from_db()
        self.assertIn("extraction failed", result)
        self.assertNotIn(PERSON_HISTORY_KEY, profile.raw_payload["structured"])
        self.assertGreater(profile.last_synced_at, before)
        self.assertEqual(pending_person_history().count(), 1)

    def test_the_profile_sync_drops_the_marker_too(self):
        # The same guard on the other writer. `sync_company` is what the ORSR
        # monitoring task calls, and a failure there must not retire a company
        # from the repair either -- the repair is the only thing that retries
        # person extraction, whichever path produced the profile.
        company = _company("50059959", 1)
        with mock.patch(
            "registers.services.rpo_sync.RpoClient",
            return_value=_FakeRpoClient(_ended_and_current()),
        ), mock.patch(
            "connections.services.PersonExtractionService.extract_from_profile",
            side_effect=RuntimeError("boom"),
        ):
            RpoSyncService().sync_company(company)

        profile = OrsrCompanyProfile.objects.get(company=company)
        self.assertNotIn(PERSON_HISTORY_KEY, profile.raw_payload["structured"])
        self.assertEqual(pending_person_history().count(), 1)

    def test_every_company_the_rotation_selects_can_be_marked(self):
        """Dispatch, read, and watch the population reach zero.

        The list is the measured shape of the tail, not a hypothetical: an
        ordinary company, a dissolved one, and one whose legal form ORSR does
        not carry. Before the reading task existed the last two were selected
        every four hours for ever and could never gain the marker, so the count
        this test asserts on could not reach zero -- and `--dry-run` reporting
        zero is the documented condition for retiring the beat row.
        """
        plain = _company("11111111", 1)
        dissolved = _company("22222222", 2)
        dissolved.datum_zrusenia = date(2026, 7, 24)
        dissolved.save(update_fields=["datum_zrusenia"])
        odd_form = _company("33333333", 3)
        odd_form.pravna_forma = "995"
        odd_form.save(update_fields=["pravna_forma"])

        for index, company in enumerate((plain, dissolved, odd_form), start=1):
            _profile(company, {"rpo_id": index, "structured": {}}, synced_days_ago=index)

        self.assertEqual(len(person_history_batch(10)), 3)
        self.assertFalse(is_orsr_eligible_company(dissolved))
        self.assertFalse(is_orsr_eligible_company(odd_form))

        with mock.patch(
            "registers.services.rpo_sync.RpoClient",
            return_value=_FakeRpoClient(_ended_and_current()),
        ), mock.patch(
            "registers.tasks.read_person_history.delay",
            side_effect=read_person_history,  # run it, do not queue it
        ) as delay:
            schedule_person_history_resync(10)

        self.assertEqual(delay.call_count, 3)
        self.assertEqual(pending_person_history().count(), 0)
        self.assertEqual(
            PersonCompanyRelation.objects.filter(is_active=False).count(), 3
        )


class OrsrPersonSearchTests(TestCase):
    """The parser, against the shape the register actually returns.

    Verified on 2026-09-13: the page is cp1250, the result row is
    `Meno | Obchodné meno subjektu | Výpis | Zbierka dokumentov`, there is no
    capacity column, and diacritics are exact.
    """

    PAGE = """
    <html><body>
    <div>Záznamy: 1 - 2 / 18</div>
    <table>
      <tr><td>1</td><td>Ing. Miroslav Trnka</td>
          <td><a href="vypis.asp?ID=1234&amp;SID=5">SLUŽBY, s.r.o.</a></td>
          <td><a href="zbierka.asp?ID=1234">Zbierka</a></td></tr>
      <tr><td>2</td><td>Miroslav Trnka</td>
          <td><a href="vypis.asp?ID=5678&amp;SID=5">IN&#201; FDI, a.s.</a></td>
          <td></td></tr>
      <tr><td>3</td><td></td><td><a href="vypis.asp?ID=9&amp;SID=5">Bez mena</a></td></tr>
      <tr><td>4</td><td>Bez odkazu</td><td>nie je odkaz</td></tr>
    </table>
    </body></html>
    """

    def test_split_name_is_surname_last(self):
        # The form is surname-first, but people type given-name-first -- and so
        # do we when we display a name.
        self.assertEqual(split_name("Miroslav Trnka"), ("Trnka", "Miroslav"))
        self.assertEqual(split_name("Trnka"), ("Trnka", ""))
        self.assertEqual(split_name("  "), ("", ""))

    def test_a_title_never_reaches_the_given_names_field(self):
        # Measured against the live register 2026-09-13: `PR=Trnka&MENO=Miroslav`
        # returns 18 records, `PR=Trnka&MENO=Ing. Miroslav` returns 0. The title
        # is not decoration in this field, it is a filter that matches nobody --
        # and our own `Person.name` carries one for 20 121 of 45 606 people.
        self.assertEqual(split_name("Ing. Miroslav Trnka"), ("Trnka", "Miroslav"))
        self.assertEqual(split_name("Ing. Andrej Chudík"), ("Chudík", "Andrej"))

    def test_titles_are_dropped_from_both_ends_and_stacked_ones_too(self):
        self.assertEqual(split_name("Miroslav Trnka, PhD."), ("Trnka", "Miroslav"))
        self.assertEqual(split_name("doc. Ing. Ján Novák, CSc."), ("Novák", "Ján"))
        # The second word of the multi-word titles is a token of its own.
        self.assertEqual(split_name("Ing. arch. Ján Novák"), ("Novák", "Ján"))
        self.assertEqual(split_name("Mgr. art. Jana Nováková"), ("Nováková", "Jana"))

    def test_a_name_that_is_only_a_title_is_not_emptied(self):
        # Stripping must not be able to empty the query: `PR=&MENO=` is a search
        # across the whole register, which is the one thing this must never do.
        # The trailing dot goes -- punctuation has no place in a form field --
        # but a surname is still a surname.
        self.assertEqual(split_name("Ing."), ("Ing", ""))
        self.assertEqual(split_name("Ing. Mgr."), ("Mgr", ""))

    def test_a_title_like_token_inside_a_name_is_left_alone(self):
        # Only the ends are stripped. Something that looks like a title between
        # a given name and a surname is part of the name, so it stays -- minus
        # the dot, which no field on the form wants.
        self.assertEqual(split_name("Ján Ing. Novák"), ("Novák", "Ján Ing"))

    def test_commas_and_dots_never_reach_the_form_fields(self):
        # `Novák,` as a surname is a different string from `Novák` to anything
        # that matches fields, and people do write the comma.
        self.assertEqual(split_name("Miroslav Trnka,"), ("Trnka", "Miroslav"))

    def test_parse_reads_the_rows_and_the_total(self):
        # 18, not 181. The header is followed by the table, whose first cell is
        # the row number `1`; read from the page's whole text the count pattern
        # swallows it, and every total on every page would be wrong.
        result = OrsrPersonSearch().parse(self.PAGE)

        self.assertEqual(result.total, 18)
        self.assertEqual(len(result.hits), 2)
        self.assertTrue(result.truncated)

    def test_a_thousands_separator_in_the_total_survives(self):
        page = self.PAGE.replace("/ 18", "/ 1 234")
        self.assertEqual(OrsrPersonSearch().parse(page).total, 1234)

    def test_parse_builds_both_vypis_urls(self):
        hit = OrsrPersonSearch().parse(self.PAGE).hits[0]

        self.assertEqual(hit.person_name, "Ing. Miroslav Trnka")
        self.assertEqual(hit.company_name, "SLUŽBY, s.r.o.")
        self.assertIn("ID=1234&SID=5", hit.current_url)
        self.assertTrue(hit.current_url.endswith("&P=0"))
        self.assertTrue(hit.full_url.endswith("&P=1"))

    def test_parse_returns_no_capacity_because_the_register_has_none(self):
        # The result row has no column for it. Saying so is the point: a client
        # that expects a role here would invent one.
        self.assertNotIn("role", OrsrPersonSearch().parse(self.PAGE).hits[0].as_dict())

    def test_a_row_without_a_name_or_a_link_is_skipped(self):
        names = [hit.person_name for hit in OrsrPersonSearch().parse(self.PAGE).hits]
        self.assertEqual(names, ["Ing. Miroslav Trnka", "Miroslav Trnka"])

    def test_a_page_without_a_readable_header_reports_zero(self):
        result = OrsrPersonSearch().parse("<table></table>")
        self.assertEqual((result.hits, result.total), ([], 0))


class OrsrPersonSearchRequestTests(TestCase):
    """One bounded request, and the retry that makes a diacritics-free query work."""

    class FakeResponse:
        def __init__(self, text):
            self.text = text
            self.url = "https://www.orsr.sk/hladaj_osoba.asp"
            self.encoding = "utf-8"

        def raise_for_status(self):
            pass

    class FakeSession:
        def __init__(self, pages):
            self.pages = list(pages)
            self.calls = []

        def get(self, url, params=None, timeout=None):
            self.calls.append(dict(params or {}))
            page = self.pages.pop(0) if self.pages else ""
            if isinstance(page, Exception):
                raise page
            return OrsrPersonSearchRequestTests.FakeResponse(page)

    ONE_HIT = (
        "<div>Záznamy: 1 - 1 / 1</div><table><tr><td>1</td><td>Ján Novák</td>"
        "<td><a href='vypis.asp?ID=1&amp;SID=2'>Firma s.r.o.</a></td></tr></table>"
    )
    NO_HITS = "<div>Záznamy: 0 - 0 / 0</div><table></table>"

    def test_a_query_the_register_can_answer_is_asked_once(self):
        # A query typed without diacritics has nothing to strip, and one the
        # register answered is not asked a second time in another spelling: the
        # second answer would be a different list of people, and the register's
        # own count would no longer describe what is shown.
        session = self.FakeSession([self.ONE_HIT, self.ONE_HIT])

        result = OrsrPersonSearch(session=session).search("Jan Novak")

        self.assertEqual(len(session.calls), 1)
        self.assertEqual(len(result.hits), 1)
        self.assertEqual(result.total, 1)

    def test_the_stripped_spelling_is_tried_when_the_first_returns_nothing(self):
        # The register is diacritics-exact: `PR=novak` returns zero records,
        # `PR=Novák` returns 24. One extra request is the difference between a
        # working search and a misleading empty one.
        session = self.FakeSession([self.NO_HITS, self.ONE_HIT])

        result = OrsrPersonSearch(session=session).search("Ján Novák")

        self.assertEqual([call["PR"] for call in session.calls], ["Novák", "Novak"])
        self.assertEqual(len(result.hits), 1)

    def test_an_empty_answer_from_both_spellings_is_an_empty_result_not_an_error(self):
        session = self.FakeSession([self.NO_HITS, self.NO_HITS])

        result = OrsrPersonSearch(session=session).search("Ján Novák")

        self.assertEqual(result.hits, [])
        self.assertEqual(result.error, "")

    def test_a_transport_failure_is_reported_not_swallowed(self):
        # "The register says nothing" and "we could not ask" are different
        # answers, and the caller shows the difference.
        session = self.FakeSession([RuntimeError("boom"), RuntimeError("boom")])

        result = OrsrPersonSearch(session=session).search("Novák")

        self.assertEqual(result.hits, [])
        self.assertIn("boom", result.error)


class OrsrPersonSearchViewTests(TestCase):
    """`GET /api/persons/orsr/` -- the one endpoint whose input reaches a third party.

    It spends a request against orsr.sk per uncached query and the query string
    is typed by anyone, so the cache, the throttle and the minimum length are
    the whole of its protection. The cache is also the only reason the endpoint
    is usable at all: the register answers one page in seconds.
    """

    def setUp(self):
        # The throttle keeps its counters in the same cache, so a leftover
        # bucket from a previous test would change what this one measures.
        cache.clear()

    class FakeResult:
        def __init__(self, *, hits=None, total=0, error=""):
            self.hits = hits or []
            self.total = total
            self.truncated = total > len(self.hits)
            self.source_url = "https://www.orsr.sk/vypis.asp?ID=1&SID=2"
            self.error = error

    def _hit(self):
        return OrsrPersonHit(
            person_name="Miroslav Trnka",
            company_name="SLUŽBY, s.r.o.",
            orsr_id="1234",
            court_id="5",
            current_url="https://www.orsr.sk/vypis.asp?ID=1234&SID=5&P=0",
            full_url="https://www.orsr.sk/vypis.asp?ID=1234&SID=5&P=1",
        )

    def test_the_answer_carries_the_register_hits_and_says_what_it_cannot_tell(self):
        with mock.patch(
            "registers.scrapers.orsr_person_search.OrsrPersonSearch.search",
            return_value=self.FakeResult(hits=[self._hit()], total=18),
        ):
            response = self.client.get("/api/persons/orsr/", {"q": "Trnka"})

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["hits"][0]["person_name"], "Miroslav Trnka")
        self.assertEqual(payload["total"], 18)
        self.assertTrue(payload["truncated"])
        # The register's list looks like ours and is not: it names companies,
        # never the capacity. Said in the payload rather than left for the
        # reader to infer from an empty column.
        self.assertIn("nie funkciu", payload["note"])

    def test_a_cached_answer_does_not_reach_the_register(self):
        with mock.patch(
            "registers.scrapers.orsr_person_search.OrsrPersonSearch.search",
            return_value=self.FakeResult(hits=[self._hit()], total=1),
        ) as search:
            first = self.client.get("/api/persons/orsr/", {"q": "Trnka"})
            second = self.client.get("/api/persons/orsr/", {"q": "Trnka"})

        self.assertEqual(search.call_count, 1)
        self.assertNotIn("cached", first.json())
        self.assertTrue(second.json()["cached"])

    def test_the_cache_key_ignores_case_and_diacritics(self):
        # `trnka`, `Trnka` and `Trnká` are one question typed three ways, and
        # the register answers all three the same. Keying on the raw string
        # would spend three requests and cache three copies.
        with mock.patch(
            "registers.scrapers.orsr_person_search.OrsrPersonSearch.search",
            return_value=self.FakeResult(hits=[self._hit()], total=1),
        ) as search:
            self.client.get("/api/persons/orsr/", {"q": "Trnka"})
            self.client.get("/api/persons/orsr/", {"q": "TRNKA"})

        self.assertEqual(search.call_count, 1)

    def test_a_failure_is_shown_and_not_cached(self):
        # Caching a failure would turn a minute of register downtime into a
        # quarter of an hour of the same wrong answer.
        with mock.patch(
            "registers.scrapers.orsr_person_search.OrsrPersonSearch.search",
            return_value=self.FakeResult(error="ConnectionError: boom"),
        ) as search:
            first = self.client.get("/api/persons/orsr/", {"q": "Trnka"})
            self.client.get("/api/persons/orsr/", {"q": "Trnka"})

        self.assertEqual(search.call_count, 2)
        self.assertIn("boom", first.json()["error"])

    def test_the_short_query_never_reaches_the_register(self):
        with mock.patch(
            "registers.scrapers.orsr_person_search.OrsrPersonSearch.search"
        ) as search:
            response = self.client.get("/api/persons/orsr/", {"q": "N"})

        search.assert_not_called()
        self.assertIn("2 znaky", response.json()["detail"])
