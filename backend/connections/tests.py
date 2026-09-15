from datetime import date

from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APITestCase

from companies.models import Company
from registers.models import OrsrCompanyProfile
from .models import (
    Person,
    PersonCompanyRelation,
    compute_fingerprint,
    normalize_name,
)
from .services import PersonExtractionService


class FingerprintTests(TestCase):
    def test_basic_name_fingerprint(self):
        fp = compute_fingerprint("Ján Novák", "Hlavná 5, Bratislava")
        self.assertTrue(fp.startswith("name:"))
        self.assertIn("jan novak", fp)
        self.assertIn("bratislava", fp)

    def test_diacritics_normalized(self):
        fp1 = compute_fingerprint("Štefan Kováč", "Bratislava")
        fp2 = compute_fingerprint("Stefan Kovac", "Bratislava")
        self.assertEqual(fp1, fp2)

    def test_person_ico_takes_priority(self):
        fp = compute_fingerprint("Ján Novák", "Bratislava", person_ico="12345678")
        self.assertEqual(fp, "ico:12345678")

    def test_empty_name_produces_fingerprint(self):
        fp = compute_fingerprint("", "")
        self.assertEqual(fp, "name:|addr:")

    def test_whitespace_normalized(self):
        fp1 = compute_fingerprint("  Ján   Novák  ", "Bratislava")
        fp2 = compute_fingerprint("Ján Novák", "Bratislava")
        self.assertEqual(fp1, fp2)

    def test_multiline_address(self):
        fp = compute_fingerprint("Test User", "Hlavná 1\n821 01\nBratislava")
        self.assertIn("bratislava", fp)


class PersonExtractionServiceTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            ruz_id=1,
            ico="50059959",
            nazov_UJ="Test Firma s.r.o.",
        )
        self.profile = OrsrCompanyProfile.objects.create(
            company=self.company,
            ico="50059959",
            raw_payload={
                "structured": {
                    "statutarny_organ": [
                        {"name": "Ing. Ján Novák", "role": "Konateľ", "address": "Hlavná 1, Bratislava", "vznik_funkcie": "01.01.2020"},
                        {"name": "Mária Kováčová", "role": "Konateľ", "address": "Dlhá 5, Košice"},
                    ],
                    "spolocnici": [
                        {"name": "Ing. Ján Novák", "role": "Spoločník", "address": "Hlavná 1, Bratislava"},
                    ],
                }
            },
        )
        self.service = PersonExtractionService()

    def test_extract_creates_persons(self):
        persons_created, relations_created = self.service.extract_from_profile(self.profile)
        self.assertEqual(persons_created, 2)
        self.assertEqual(relations_created, 3)

    def test_deduplication_by_fingerprint(self):
        self.service.extract_from_profile(self.profile)
        self.assertEqual(Person.objects.count(), 2)

    def test_relation_roles_mapped(self):
        self.service.extract_from_profile(self.profile)
        konatel_rels = PersonCompanyRelation.objects.filter(role="konatel")
        spolocnik_rels = PersonCompanyRelation.objects.filter(role="spolocnik")
        self.assertEqual(konatel_rels.count(), 2)
        self.assertEqual(spolocnik_rels.count(), 1)

    def test_vznik_funkcie_parsed(self):
        self.service.extract_from_profile(self.profile)
        from datetime import date
        rel = PersonCompanyRelation.objects.filter(
            person__name="Ing. Ján Novák", role="konatel"
        ).first()
        self.assertEqual(rel.vznik_funkcie, date(2020, 1, 1))

    def test_idempotent_extraction(self):
        self.service.extract_from_profile(self.profile)
        self.service.extract_from_profile(self.profile)
        self.assertEqual(Person.objects.count(), 2)
        self.assertEqual(PersonCompanyRelation.objects.count(), 3)

    def test_skip_invalid_names(self):
        profile = OrsrCompanyProfile.objects.create(
            company=Company.objects.create(ruz_id=2, ico="99999999", nazov_UJ="X"),
            ico="99999999",
            raw_payload={
                "structured": {
                    "statutarny_organ": [
                        {"name": "vklad: 5000 EUR", "role": ""},
                        {"name": "A", "role": "Konateľ"},
                        {"name": "Ján Novák", "role": "Konateľ"},
                    ],
                }
            },
        )
        persons_created, relations_created = self.service.extract_from_profile(profile)
        self.assertEqual(relations_created, 1)


class BirthDateTests(TestCase):
    """The register's `Dátum narodenia:` line gets its own column, not the address.

    The reader used to append that line to the address like any other
    unrecognised line of a person's block, and because `compute_fingerprint`
    keys a row by the last non-numeric part of its address, the date became the
    row's *identity* -- so the same officer written once with the line and once
    without produced two `Person` rows. Measured 2026-09-15: 14 rows of 121 257
    carried it, and in every one of them it was the whole address.
    """

    def setUp(self):
        self.company = Company.objects.create(
            ruz_id=1, ico="52366332", nazov_UJ="MaVa Company s.r.o."
        )
        self.service = PersonExtractionService()
        self.profile = OrsrCompanyProfile.objects.create(
            company=self.company,
            ico="52366332",
            raw_payload={"structured": {}},
        )

    def _extract(self, structured: dict):
        self.profile.raw_payload = {"structured": structured}
        self.profile.save(update_fields=["raw_payload"])
        self.service.extract_from_profile(self.profile)

    def test_the_date_lands_in_the_column_and_not_in_the_address(self):
        self._extract(
            {
                "statutarny_organ": [
                    {
                        "name": "Matej Vácha",
                        "role": "Konateľ",
                        "address": "",
                        "birth_date": "20.08.1992",
                    }
                ]
            }
        )

        person = Person.objects.get(name="Matej Vácha")
        self.assertEqual(person.birth_date, date(1992, 8, 20))
        self.assertEqual(person.address, "")

    def test_one_person_whether_or_not_the_section_states_the_date(self):
        """The split this change exists to stop, in one document.

        `spoločníci` states the date and `štatutárny orgán` does not -- which is
        what the live document does, and what used to write two rows for one
        officer 2.8 ms apart.
        """
        self._extract(
            {
                "statutarny_organ": [
                    {"name": "Matej Vácha", "role": "Konateľ", "address": ""}
                ],
                "spolocnici": [
                    {
                        "name": "Matej Vácha",
                        "role": "Spoločník",
                        "address": "",
                        "birth_date": "20.08.1992",
                    }
                ],
            }
        )

        self.assertEqual(Person.objects.count(), 1)
        self.assertEqual(Person.objects.get().birth_date, date(1992, 8, 20))
        self.assertEqual(PersonCompanyRelation.objects.count(), 2)

    def test_a_later_section_that_states_the_date_fills_a_blank_column(self):
        self._extract(
            {"statutarny_organ": [{"name": "Matej Vácha", "role": "Konateľ", "address": ""}]}
        )
        self.assertIsNone(Person.objects.get().birth_date)

        self._extract(
            {
                "spolocnici": [
                    {
                        "name": "Matej Vácha",
                        "role": "Spoločník",
                        "address": "",
                        "birth_date": "20.08.1992",
                    }
                ]
            }
        )

        self.assertEqual(Person.objects.count(), 1)
        self.assertEqual(Person.objects.get().birth_date, date(1992, 8, 20))

    def test_a_date_we_already_hold_is_not_overwritten(self):
        self._extract(
            {
                "statutarny_organ": [
                    {
                        "name": "Matej Vácha",
                        "role": "Konateľ",
                        "address": "",
                        "birth_date": "20.08.1992",
                    }
                ]
            }
        )

        # A section that states a *different* date for the same name is two
        # people at least as plausibly as it is a correction, and nothing here
        # can tell which. Writing it would be silent damage; the row keeps what
        # it has and the disagreement stays visible as two entries.
        self._extract(
            {
                "spolocnici": [
                    {
                        "name": "Matej Vácha",
                        "role": "Spoločník",
                        "address": "",
                        "birth_date": "01.01.1980",
                    }
                ]
            }
        )

        self.assertEqual(Person.objects.get(name="Matej Vácha").birth_date, date(1992, 8, 20))


class CompanyGraphAPITests(APITestCase):
    def setUp(self):
        self.company = Company.objects.create(
            ruz_id=1,
            ico="50059959",
            nazov_UJ="Test Firma s.r.o.",
        )
        self.person = Person.objects.create(
            fingerprint="name:jan novak|addr:bratislava",
            name="Ján Novák",
        )
        PersonCompanyRelation.objects.create(
            person=self.person,
            company=self.company,
            role="konatel",
            is_active=True,
        )

    def test_graph_endpoint_returns_nodes_and_edges(self):
        response = self.client.get(f"/api/companies/{self.company.ico}/graph/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("nodes", data)
        self.assertIn("edges", data)
        self.assertIn("meta", data)
        self.assertEqual(len(data["nodes"]), 2)
        self.assertEqual(len(data["edges"]), 1)

    def test_graph_endpoint_404_for_unknown(self):
        response = self.client.get("/api/companies/00000000/graph/")
        self.assertEqual(response.status_code, 404)

    def test_graph_node_types(self):
        response = self.client.get(f"/api/companies/{self.company.ico}/graph/")
        data = response.json()
        types = {n["type"] for n in data["nodes"]}
        self.assertEqual(types, {"company", "person"})

    def test_graph_expands_with_shared_person(self):
        company2 = Company.objects.create(ruz_id=4, ico="12345678", nazov_UJ="Inna Firma s.r.o.")
        PersonCompanyRelation.objects.create(
            person=self.person,
            company=company2,
            role="spolocnik",
            is_active=True,
        )
        response = self.client.get(f"/api/companies/{self.company.ico}/graph/")
        data = response.json()
        self.assertEqual(len(data["nodes"]), 3)
        self.assertEqual(len(data["edges"]), 2)

    def test_graph_collapses_one_office_into_one_edge(self):
        """#100: twelve rows of one office used to be twelve identical edges.

        The graph carries no time axis, so the copies said nothing the first one
        did not. The last of them is `is_active=True` on purpose: a dedup that
        kept an arbitrary copy -- the first row, the newest start date, a `set`
        -- would answer that a current officer is a former one, which is the
        defect #86 removed, mirrored.
        """
        for start in range(11):
            PersonCompanyRelation.objects.create(
                person=self.person,
                company=self.company,
                role="ine",
                is_active=False,
                vznik_funkcie=date(2000 + start, 1, 1),
            )
        PersonCompanyRelation.objects.create(
            person=self.person,
            company=self.company,
            role="ine",
            is_active=True,
            vznik_funkcie=date(2020, 1, 1),
        )

        data = self.client.get(f"/api/companies/{self.company.ico}/graph/").json()
        ine = [edge for edge in data["edges"] if edge["role"] == "Iné"]
        self.assertEqual(len(ine), 1)
        self.assertIs(ine[0]["isActive"], True)

    def test_graph_keeps_two_roles_on_one_pair_as_two_edges(self):
        """Identity is the triple, not the pair: two roles are two facts."""
        PersonCompanyRelation.objects.create(
            person=self.person,
            company=self.company,
            role="spolocnik",
            is_active=True,
        )
        data = self.client.get(f"/api/companies/{self.company.ico}/graph/").json()
        self.assertEqual(
            sorted(edge["role"] for edge in data["edges"]),
            ["Konateľ", "Spoločník"],
        )

    def test_graph_does_not_read_more_queries_for_more_rows(self):
        """Duplicated rows must cost rows, not queries.

        The old loop ran `other_relations` once per relation of the company, so
        twelve periods of one office meant twelve reads of that person's other
        companies. Measured on FREYSSINET CS: 21 edges, 9 distinct.
        """
        company2 = Company.objects.create(
            ruz_id=9, ico="87654321", nazov_UJ="Tretia Firma s.r.o."
        )
        PersonCompanyRelation.objects.create(
            person=self.person, company=company2, role="konatel", is_active=True
        )
        with CaptureQueriesContext(connection) as few:
            self.client.get(f"/api/companies/{self.company.ico}/graph/")

        for start in range(10):
            PersonCompanyRelation.objects.create(
                person=self.person,
                company=self.company,
                role="ine",
                is_active=False,
                vznik_funkcie=date(2000 + start, 1, 1),
            )
        with CaptureQueriesContext(connection) as many:
            self.client.get(f"/api/companies/{self.company.ico}/graph/")

        self.assertEqual(len(few), len(many))


class PersonDetailAPITests(APITestCase):
    def setUp(self):
        self.company = Company.objects.create(ruz_id=3, ico="50059959", nazov_UJ="Test s.r.o.")
        self.person = Person.objects.create(
            fingerprint="name:jan novak|addr:ba",
            name="Ján Novák",
        )
        PersonCompanyRelation.objects.create(
            person=self.person,
            company=self.company,
            role="konatel",
            is_active=True,
        )

    def test_person_detail(self):
        response = self.client.get(f"/api/persons/{self.person.pk}/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["name"], "Ján Novák")
        self.assertEqual(len(data["companies"]), 1)

    def test_person_not_found(self):
        response = self.client.get("/api/persons/99999/")
        self.assertEqual(response.status_code, 404)

    def test_a_member_row_carries_its_own_birth_date(self):
        """Not merged into one answer at the top, because it is the evidence.

        A grouped person is a judgement about identity, and two rows that state
        two different dates are the one case the page must not present as one
        human. `None` for a row whose section of the register stated none is
        part of that: it is what the reader compares against.
        """
        self.person.address = ""
        self.person.birth_date = date(1992, 8, 20)
        self.person.save(update_fields=["address", "birth_date"])
        second = Person.objects.create(
            fingerprint="name:jan novak|addr:",
            name="Ján Novák",
            person_ico="",
        )
        PersonCompanyRelation.objects.create(
            person=second, company=self.company, role="konatel", is_active=True
        )

        data = self.client.get(f"/api/persons/{self.person.pk}/").json()

        self.assertEqual(data["records"], 2)
        self.assertEqual(
            [(m["id"], m["address"], m["birth_date"]) for m in data["members"]],
            [(self.person.id, "", "1992-08-20"), (second.id, "", None)],
        )


class JoinedPeriodsTests(APITestCase):
    """One office, not one register filing per row (#93).

    The register does not keep a function, it keeps filings: each one closes the
    office and the next reopens it, so a single tenure from 2011 arrives as a
    chain of intervals that meet day to day. Measured live on person 56172
    (FREYSSINET CS): twelve relations for one office, eleven of them meeting the
    next -- and the reader, shown twelve rows, saw `od 07.07.2026`. The answer to
    "since when" was at the bottom of the list.

    What each test below holds down is a way the fold could lie: by merging two
    real tenures, by merging two offices, by inventing a start, or by dropping
    the `None` that means we never read the company.
    """

    def setUp(self):
        self.company = Company.objects.create(
            ruz_id=1, ico="50059959", nazov_UJ="Test s.r.o."
        )
        self.person = Person.objects.create(fingerprint="f-jan", name="Ján Novák")

    def _rel(self, vznik, zanik=None, role="konatel", is_active=None, company=None):
        return PersonCompanyRelation.objects.create(
            person=self.person,
            company=company or self.company,
            role=role,
            is_active=is_active,
            vznik_funkcie=vznik,
            zanik_funkcie=zanik,
        )

    def _companies(self):
        response = self.client.get(f"/api/persons/{self.person.pk}/")
        self.assertEqual(response.status_code, 200)
        return response.json()["companies"]

    def test_a_chain_of_filings_becomes_one_row(self):
        """The live shape: an office reopened the day after it was closed."""
        self._rel(date(2011, 6, 8), date(2011, 6, 9))
        self._rel(date(2011, 6, 10), date(2011, 6, 11))
        self._rel(date(2011, 6, 12), None, is_active=True)

        rows = self._companies()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["vznik_funkcie"], "2011-06-08")
        self.assertIsNone(rows[0]["zanik_funkcie"])
        self.assertIs(rows[0]["is_active"], True)

    def test_a_real_gap_stays_two_rows(self):
        """Person 56172 has a 34-day hole, and the hole is the fact.

        `2013-04-10 -> 2013-05-14` is not a filing rhythm, it is the office
        having ended and been taken up again. Folding it away would answer
        "continuous since 2011" to a question whose answer is two tenures.
        """
        self._rel(date(2011, 6, 8), date(2013, 4, 10), is_active=False)
        self._rel(date(2013, 5, 14), date(2019, 12, 31), is_active=False)

        rows = self._companies()

        self.assertEqual(
            [(row["vznik_funkcie"], row["zanik_funkcie"]) for row in rows],
            [("2013-05-14", "2019-12-31"), ("2011-06-08", "2013-04-10")],
        )

    def test_two_offices_on_one_company_stay_two_rows(self):
        """`konateľ` until 31 December and `prokurista` from 1 January.

        The key is `(company, role)`, not `(company)`. These two meet day to day
        exactly like a chain of filings does, so a fold keyed on the company
        alone would silently turn a change of office into a continuation of one.
        """
        self._rel(date(2010, 1, 1), date(2010, 12, 31), role="konatel")
        self._rel(date(2011, 1, 1), None, role="prokurista", is_active=True)

        rows = self._companies()

        self.assertEqual(
            sorted((row["role"], row["vznik_funkcie"]) for row in rows),
            [("konatel", "2010-01-01"), ("prokurista", "2011-01-01")],
        )

    def test_currency_comes_from_the_newest_filing(self):
        """Eleven `False`s must not outvote the one `True` (#86, from the other side)."""
        self._rel(date(2010, 1, 1), date(2010, 12, 31), is_active=False)
        self._rel(date(2011, 1, 1), None, is_active=True)

        rows = self._companies()

        self.assertEqual(len(rows), 1)
        self.assertIs(rows[0]["is_active"], True)

    def test_nevieme_survives_the_fold(self):
        """`None` is "we never read this company", and folding must not invent a yes.

        The last filing of the chain is the one whose currency the merged row
        reports, so this is also the check that the rule reads the *newest*
        filing and not the first, the richest, or any.
        """
        self._rel(date(2010, 1, 1), date(2010, 12, 31), is_active=False)
        self._rel(date(2011, 1, 1), None, is_active=None)

        rows = self._companies()

        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["is_active"])

    def test_an_open_filing_ends_the_chain(self):
        """Nothing follows an office that has not ended.

        The data can still hold a later filing (a re-read mid-write, a register
        correction). Swallowing it into the open period would extend a current
        office over a stretch the register says it was closed for, so it stays
        its own row.
        """
        self._rel(date(2010, 1, 1), None, is_active=True)
        self._rel(date(2010, 6, 1), date(2011, 1, 1), is_active=False)

        rows = self._companies()

        self.assertEqual(len(rows), 2)
        self.assertIsNone(rows[0]["zanik_funkcie"])

    def test_the_row_says_how_many_filings_it_stands_for(self):
        """The fold is disclosed, not silent.

        A row that replaced twelve register filings with one line reads exactly
        like a row that always was one line, and those are different claims.
        """
        self._rel(date(2011, 6, 8), date(2011, 6, 9))
        self._rel(date(2011, 6, 10), date(2011, 6, 11))
        self._rel(date(2011, 6, 12), None, is_active=True)
        other = Company.objects.create(ruz_id=2, ico="87654321", nazov_UJ="Iná s.r.o.")
        self._rel(date(2015, 1, 1), None, role="spolocnik", company=other)

        by_role = {row["role"]: row["intervals"] for row in self._companies()}

        self.assertEqual(by_role, {"konatel": 3, "spolocnik": 1})


class NameNormalizationTests(TestCase):
    """`name_normalized` is what search reads, so it has to be right by itself."""

    def test_diacritics_are_stripped(self):
        self.assertEqual(normalize_name("Ján Novák"), "jan novak")

    def test_title_is_folded_in_not_dropped(self):
        # The register keeps "Miroslav Trnka" and "Ing. Miroslav Trnka" as
        # separate records. A reader typing either has to reach both, and a
        # substring match on the folded form is what does it: "novak" is in
        # "ing. novak".
        self.assertIn("novak", normalize_name("Novák", "Ing."))

    def test_whitespace_collapsed(self):
        self.assertEqual(normalize_name("Ján   Novák"), "jan novak")
        self.assertEqual(normalize_name("  Novák  "), "novak")

    def test_save_fills_the_column(self):
        person = Person.objects.create(
            fingerprint="name:jan novak", name="Ján Novák", title="Ing."
        )
        person.refresh_from_db()
        self.assertEqual(person.name_normalized, "ing. jan novak")

    def test_save_recomputes_when_only_the_name_changes(self):
        person = Person.objects.create(fingerprint="f1", name="Ján Novák")
        person.name = "Štefan Kováč"
        person.save(update_fields=["name", "updated_at"])
        person.refresh_from_db()
        self.assertEqual(person.name_normalized, "stefan kovac")


class RelationCurrencyTests(TestCase):
    """The three answers: áno, nie, nevieme -- and which source may give which.

    The bug this covers: `extract_from_profile` hardcoded `is_active=True`, so
    all 64 128 relations in the live database claimed to be current. Six people
    were still marked active in a dissolved družstvo whose RPO record reports an
    end date for every one of them.
    """

    def setUp(self):
        self.service = PersonExtractionService()

    def _company(self, ico="50059959"):
        return Company.objects.create(ruz_id=1, ico=ico, nazov_UJ="Test s.r.o.")

    def _profile(self, company, structured):
        return OrsrCompanyProfile.objects.create(
            company=company,
            ico=company.ico,
            raw_payload={"structured": structured},
        )

    def test_history_gives_both_answers(self):
        company = self._company()
        profile = self._profile(company, {
            "osoby_historia": [
                {"name": "Ján Novák", "role": "Konateľ", "vznik_funkcie": "2010-01-01",
                 "zanik_funkcie": "2019-06-30"},
                {"name": "Mária Kováčová", "role": "Konateľ", "vznik_funkcie": "2019-07-01"},
            ],
        })
        self.service.extract_from_profile(profile)

        ended = PersonCompanyRelation.objects.get(person__name="Ján Novák")
        self.assertIs(ended.is_active, False)
        self.assertEqual(ended.zanik_funkcie.isoformat(), "2019-06-30")

        current = PersonCompanyRelation.objects.get(person__name="Mária Kováčová")
        self.assertIs(current.is_active, True)
        self.assertIsNone(current.zanik_funkcie)

    def test_a_profile_without_history_says_nevieme_not_ano(self):
        # An ORSR výpis (the HTML path) lists current office-holders and no end
        # dates at all. "No end date" there means "not recorded", so the honest
        # answer is null -- not the True the old code wrote.
        company = self._company()
        profile = self._profile(company, {
            "statutarny_organ": [{"name": "Ján Novák", "role": "Konateľ"}],
        })
        self.service.extract_from_profile(profile)

        relation = PersonCompanyRelation.objects.get()
        self.assertIsNone(relation.is_active)

    def test_re_extraction_closes_a_relation_we_already_held(self):
        """The path that repairs the existing 64 128 rows.

        A company read by the old code has relations claiming to be current. A
        re-read must move them to "ended", or the backfill would rewrite every
        profile and change nothing in the graph.
        """
        company = self._company()
        # The service identifies people by fingerprint, so a row it is meant to
        # recognise has to carry the fingerprint it computes.
        person = Person.objects.create(
            fingerprint=compute_fingerprint("Ján Novák"), name="Ján Novák"
        )
        relation = PersonCompanyRelation.objects.create(
            person=person, company=company, role="konatel", is_active=True,
        )

        profile = self._profile(company, {
            "osoby_historia": [
                {"name": "Ján Novák", "role": "Konateľ", "vznik_funkcie": "2010-01-01",
                 "zanik_funkcie": "2015-12-31"},
            ],
        })
        self.service.extract_from_profile(profile)

        relation.refresh_from_db()
        self.assertIs(relation.is_active, False)
        self.assertEqual(relation.zanik_funkcie.isoformat(), "2015-12-31")
        self.assertEqual(PersonCompanyRelation.objects.count(), 1)

    def test_re_extraction_refuses_to_guess_between_two_open_relations(self):
        # The adoption rule above is bounded by "exactly one". With two open
        # rows for the same (person, company, role), both without a start date,
        # there is nothing to say which one the history entry is about -- and
        # closing the wrong office is worse than holding a duplicate.
        company = self._company()
        person = Person.objects.create(
            fingerprint=compute_fingerprint("Ján Novák"), name="Ján Novák"
        )
        for _ in range(2):
            PersonCompanyRelation.objects.create(
                person=person, company=company, role="konatel", is_active=True,
            )

        profile = self._profile(company, {
            "osoby_historia": [
                {"name": "Ján Novák", "role": "Konateľ", "vznik_funkcie": "2010-01-01",
                 "zanik_funkcie": "2015-12-31"},
            ],
        })
        self.service.extract_from_profile(profile)

        # Neither was closed: the entry became its own row instead.
        self.assertEqual(
            PersonCompanyRelation.objects.filter(is_active=True).count(), 2
        )
        self.assertEqual(
            PersonCompanyRelation.objects.filter(is_active=False).count(), 1
        )

    def test_a_current_office_list_cannot_reopen_a_closed_function(self):
        # The two passes meet here. The same person is in `statutarny_organ`
        # because the register still lists the company's office-holders, and in
        # the history because the function ended. The section entry carries no
        # end date, so it may not undo the history's verdict.
        company = self._company()
        profile = self._profile(company, {
            "osoby_historia": [
                {"name": "Ján Novák", "role": "Konateľ", "vznik_funkcie": "2010-01-01",
                 "zanik_funkcie": "2015-12-31"},
            ],
            "statutarny_organ": [
                {"name": "Ján Novák", "role": "Konateľ", "vznik_funkcie": "2010-01-01"},
            ],
        })
        self.service.extract_from_profile(profile)

        self.assertEqual(PersonCompanyRelation.objects.count(), 1)
        relation = PersonCompanyRelation.objects.get()
        self.assertIs(relation.is_active, False)
        self.assertEqual(relation.zanik_funkcie.isoformat(), "2015-12-31")

    def test_a_person_who_held_office_twice_gets_two_relations(self):
        company = self._company()
        profile = self._profile(company, {
            "osoby_historia": [
                {"name": "Ján Novák", "role": "Konateľ", "vznik_funkcie": "2005-01-01",
                 "zanik_funkcie": "2010-12-31"},
                {"name": "Ján Novák", "role": "Konateľ", "vznik_funkcie": "2015-01-01"},
            ],
        })
        self.service.extract_from_profile(profile)

        relations = PersonCompanyRelation.objects.order_by("vznik_funkcie")
        self.assertEqual(relations.count(), 2)
        self.assertIs(relations[0].is_active, False)
        self.assertIs(relations[1].is_active, True)

    def test_history_only_profile_does_not_double_count_its_own_sections(self):
        # `osoby_historia` holds every person the register records; the section
        # lists hold the current ones again. Both name the same konateľ with the
        # same start date, and that is one relation, not two.
        company = self._company()
        profile = self._profile(company, {
            "osoby_historia": [
                {"name": "Mária Kováčová", "role": "Konateľ", "vznik_funkcie": "2019-07-01"},
            ],
            "statutarny_organ": [
                {"name": "Mária Kováčová", "role": "Konateľ", "vznik_funkcie": "01.07.2019"},
            ],
        })
        persons, relations = self.service.extract_from_profile(profile)

        self.assertEqual(persons, 1)
        self.assertEqual(relations, 1)
        self.assertEqual(PersonCompanyRelation.objects.count(), 1)
        self.assertIs(PersonCompanyRelation.objects.get().is_active, True)


class PersonSearchAPITests(APITestCase):
    def setUp(self):
        self.company = Company.objects.create(
            ruz_id=1, ico="50059959", nazov_UJ="Test Firma s.r.o."
        )
        self.novak = Person.objects.create(
            fingerprint="f-novak", name="Miroslav Trnka", title="Ing."
        )
        PersonCompanyRelation.objects.create(
            person=self.novak, company=self.company, role="konatel", is_active=True,
        )

    def test_finds_by_diacritics_stripped_query(self):
        person = Person.objects.create(fingerprint="f-kovac", name="Štefan Kováč")
        PersonCompanyRelation.objects.create(
            person=person, company=self.company, role="spolocnik", is_active=False,
        )

        response = self.client.get("/api/persons/", {"q": "kovac"})

        self.assertEqual(response.status_code, 200)
        names = [r["name"] for r in response.json()["results"]]
        self.assertEqual(names, ["Štefan Kováč"])

    def test_token_order_does_not_matter(self):
        for query in ("trnka miroslav", "miroslav trnka", "TRNKA"):
            with self.subTest(query=query):
                response = self.client.get("/api/persons/", {"q": query})
                self.assertEqual(len(response.json()["results"]), 1)

    def test_a_title_does_not_hide_the_person(self):
        # The register stores "Ing. Miroslav Trnka" and search reads the folded
        # form, so a reader who leaves the title out still reaches them.
        response = self.client.get("/api/persons/", {"q": "trnka"})
        self.assertEqual(len(response.json()["results"]), 1)

    def test_short_query_is_refused_with_a_reason(self):
        response = self.client.get("/api/persons/", {"q": "t"})
        data = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["results"], [])
        self.assertIn("2 znaky", data["detail"])

    def test_person_without_relations_is_not_a_result(self):
        Person.objects.create(fingerprint="f-lonely", name="Miroslav Trnka")
        response = self.client.get("/api/persons/", {"q": "trnka"})
        self.assertEqual(len(response.json()["results"]), 1)

    def test_role_filter(self):
        person = Person.objects.create(fingerprint="f-spol", name="Miroslav Trnka")
        PersonCompanyRelation.objects.create(
            person=person, company=self.company, role="spolocnik", is_active=True,
        )

        response = self.client.get("/api/persons/", {"q": "trnka", "role": "spolocnik"})

        results = response.json()["results"]
        self.assertEqual([r["name"] for r in results], ["Miroslav Trnka"])
        self.assertEqual([c["role"] for c in results[0]["companies"]], ["spolocnik"])

    def test_three_valued_is_active_survives_the_serializer(self):
        person = Person.objects.create(fingerprint="f-unknown", name="Miroslav Trnka")
        PersonCompanyRelation.objects.create(
            person=person, company=self.company, role="spolocnik",
        )

        response = self.client.get("/api/persons/", {"q": "trnka"})
        by_role = {
            company["role"]: company["is_active"]
            for result in response.json()["results"]
            for company in result["companies"]
        }

        self.assertIs(by_role["konatel"], True)
        self.assertIsNone(by_role["spolocnik"])

    def test_coverage_is_reported_with_every_answer(self):
        # An empty result has to be readable as "we do not cover this" rather
        # than "this person is in no company".
        response = self.client.get("/api/persons/", {"q": "nikto taky"})
        coverage = response.json()["coverage"]

        self.assertEqual(coverage["companies_with_persons"], 1)
        self.assertEqual(coverage["companies_total"], 1)
