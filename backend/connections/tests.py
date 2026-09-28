import re
from datetime import date
from unittest import mock

import redis
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APITestCase

from companies.models import Company
from registers.models import OrsrCompanyProfile
from registers.scrapers.orsr_person_search import OrsrPersonHit, OrsrPersonResult
from . import views
from .views import _coverage
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
    without produced two `Person` rows. Measured 2026-09-15: 14 rows of 121 558
    carried it, in every one of them as the whole address, and migration
    `connections/0004` repaired all 14 (11 re-keyed, 3 absorbed).
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

    def test_one_human_in_two_companies_gets_one_node_id(self):
        """The id must not depend on which company drew the person.

        Two rows of one human that no single company's officer list holds both
        of -- one row works here, the other works there, and only the name and
        postcode say they are the same person (rule 2). Resolving against each
        company's own officers therefore saw one row each and keyed the node on
        it, so this company drew `person_<self.person>` and the other drew
        `person_<other>`. The client dedups nodes by exact id, so expanding from
        one into the other drew the same human twice, which is the report.

        `rolesCount` moves with it, and for the same reason: a count computed
        from the rows one company happens to hold is a number that changes with
        the click path.
        """
        self.person.address = "Hlavná 1, 811 01 Bratislava"
        self.person.save(update_fields=["address"])
        other = Person.objects.create(
            fingerprint="name:jan novak|addr:vedlajsia",
            name="Ján Novák",
            address="Vedľajšia 2, 811 01 Bratislava",
        )
        self.assertLess(self.person.id, other.id)
        company2 = Company.objects.create(
            ruz_id=7, ico="12345678", nazov_UJ="Iná Firma s.r.o."
        )
        PersonCompanyRelation.objects.create(
            person=other, company=company2, role="konatel", is_active=True
        )

        data = self.client.get(f"/api/companies/{company2.ico}/graph/").json()

        people = [n for n in data["nodes"] if n["type"] == "person"]
        self.assertEqual([n["id"] for n in people], [f"person_{self.person.id}"])
        self.assertEqual(people[0]["rolesCount"], 2)

    def test_an_officer_whose_row_states_no_name_still_gets_a_node(self):
        """A row with no name cannot be found by a name query, so it is carried.

        The candidate rows come from the names the company's officers have, and
        a blank one contributes no name to search by. It is added to the set by
        hand rather than left out: dropping it would drop an officer from the
        graph, which is a worse answer than a node labelled with nothing.
        """
        blank = Person.objects.create(fingerprint="name:|addr:", name="")
        PersonCompanyRelation.objects.create(
            person=blank, company=self.company, role="konatel", is_active=True
        )

        data = self.client.get(f"/api/companies/{self.company.ico}/graph/").json()

        people = sorted(n["id"] for n in data["nodes"] if n["type"] == "person")
        self.assertEqual(
            people, sorted([f"person_{self.person.id}", f"person_{blank.id}"])
        )

    def test_a_near_miss_surname_is_a_second_person(self):
        """`novakova` is fetched by the `novak` query and must not be merged.

        The candidate query matches on a substring, so it deliberately returns
        rows it will not use -- `base_name` equality is the gate, and applying
        it in Python as well as in the query is what keeps the two answers the
        same one. Both rows are officers of *this* company, so rule 1 is in play
        too, and it keys on the base name: two surnames are two people.
        """
        other = Person.objects.create(
            fingerprint="name:jan novakova|addr:hlavna",
            name="Ján Nováková",
            address="Hlavná 1, 811 01 Bratislava",
        )
        PersonCompanyRelation.objects.create(
            person=other, company=self.company, role="konatel", is_active=True
        )

        data = self.client.get(f"/api/companies/{self.company.ico}/graph/").json()

        people = sorted(n["id"] for n in data["nodes"] if n["type"] == "person")
        self.assertEqual(
            people,
            sorted([f"person_{self.person.id}", f"person_{other.id}"]),
        )


class PersonGraphAPITests(APITestCase):
    """The person-centred graph.

    It had no test at all, which is where the duplicate-node report came from:
    it keyed its node on the row that was asked for, so the same human arrived
    under one id from a company's graph and another from here.
    """

    def setUp(self):
        self.company = Company.objects.create(
            ruz_id=11, ico="50059959", nazov_UJ="Prvá s.r.o."
        )
        self.other_company = Company.objects.create(
            ruz_id=12, ico="12345678", nazov_UJ="Druhá s.r.o."
        )
        # Two rows of one human, each known to a different company, so only the
        # name and postcode join them.
        self.first = Person.objects.create(
            fingerprint="name:jan novak|addr:hlavna",
            name="Ján Novák",
            address="Hlavná 1, 811 01 Bratislava",
        )
        self.second = Person.objects.create(
            fingerprint="name:jan novak|addr:vedlajsia",
            name="Ján Novák",
            address="Vedľajšia 2, 811 01 Bratislava",
        )
        PersonCompanyRelation.objects.create(
            person=self.first, company=self.company, role="konatel", is_active=True
        )
        PersonCompanyRelation.objects.create(
            person=self.second,
            company=self.other_company,
            role="spolocnik",
            is_active=True,
        )

    def test_the_graph_is_the_same_from_either_row_of_the_human(self):
        """Asking about a row and asking about its sibling is one question."""
        from_first = self.client.get(f"/api/persons/{self.first.id}/graph/").json()
        from_second = self.client.get(f"/api/persons/{self.second.id}/graph/").json()

        self.assertEqual(
            sorted(n["id"] for n in from_first["nodes"]),
            sorted(n["id"] for n in from_second["nodes"]),
        )
        self.assertEqual(
            from_first["meta"]["center_node"], from_second["meta"]["center_node"]
        )

    def test_the_node_is_the_clusters_first_row_not_the_requested_one(self):
        self.assertLess(self.first.id, self.second.id)

        data = self.client.get(f"/api/persons/{self.second.id}/graph/").json()

        people = [n for n in data["nodes"] if n["type"] == "person"]
        self.assertEqual([n["id"] for n in people], [f"person_{self.first.id}"])
        self.assertEqual(people[0]["rolesCount"], 2)
        self.assertEqual(data["meta"]["center_node"], f"person_{self.first.id}")

    def test_the_two_graphs_draw_the_same_person_node(self):
        """One human, one id, whichever view drew them."""
        from_company = self.client.get(
            f"/api/companies/{self.other_company.ico}/graph/"
        ).json()
        from_person = self.client.get(
            f"/api/persons/{self.second.id}/graph/"
        ).json()

        company_people = {n["id"]: n for n in from_company["nodes"] if n["type"] == "person"}
        person_people = {n["id"]: n for n in from_person["nodes"] if n["type"] == "person"}
        shared = set(company_people) & set(person_people)

        self.assertEqual(shared, {f"person_{self.first.id}"})
        for node_id in shared:
            self.assertEqual(
                company_people[node_id]["rolesCount"],
                person_people[node_id]["rolesCount"],
            )

    def test_person_graph_404_for_unknown(self):
        response = self.client.get("/api/persons/99999/graph/")
        self.assertEqual(response.status_code, 404)


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


class _WorkingCache:
    """Just enough of `django.core.cache.cache` to tell a hit from a miss.

    A bare `Mock` cannot do this: `get` would return the same thing every time,
    so "the second caller was served from cache" would be untestable -- and
    with it the question of whether the outage tests below exercise a path the
    endpoint actually takes.
    """

    def __init__(self):
        self.store = {}

    def get(self, key, default=None):
        return self.store.get(key, default)

    def set(self, key, value, timeout=None):
        self.store[key] = value


class OrsrPersonSearchCacheOutageTests(APITestCase):
    """A dead cache costs latency here, not the endpoint.

    `/api/persons/orsr/` consults the cache before it asks the register, and it
    did so unprotected: an unreachable Redis raised straight out of the view.
    That is the wrong branch to lose, because the whole design of this view is
    degradation -- the scrape one line below already carries `result.error`
    into the payload rather than failing, and the cache is only there to save
    repeat traffic. The failure mode has to be the register answering slowly,
    never a 500.
    """

    def setUp(self):
        # Module-level and never reset in production, where it buys one
        # traceback per outage instead of one per request. Here it would leak
        # the first test's ERROR into the next test's DEBUG.
        views._cache_outage_logged = False

        patcher = mock.patch("registers.scrapers.orsr_person_search.OrsrPersonSearch")
        self.addCleanup(patcher.stop)
        self.scraper = patcher.start()
        self.scraper.return_value.search.return_value = OrsrPersonResult(
            hits=[
                OrsrPersonHit(
                    person_name="Miroslav Trnka",
                    company_name="Test Firma s.r.o.",
                )
            ],
            total=1,
            source_url="https://www.orsr.sk/hladaj_osoba.asp",
        )

    def _dead_cache(self):
        """Every operation raises, the way a stopped Redis does."""
        dead = mock.Mock()
        dead.get.side_effect = redis.exceptions.ConnectionError("redis is down")
        dead.set.side_effect = redis.exceptions.ConnectionError("redis is down")
        return mock.patch("connections.views.cache", dead)

    def test_an_unreadable_cache_is_a_miss_not_a_500(self):
        with self._dead_cache():
            response = self.client.get("/api/persons/orsr/", {"q": "Trnka"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 1)
        self.assertNotIn("cached", response.json())
        self.scraper.return_value.search.assert_called_once_with("Trnka")

    def test_the_answer_survives_a_failed_write(self):
        # The scrape succeeded, so this response is already correct; only the
        # next caller pays. Losing it to an exception would be gratuitous.
        half_dead = mock.Mock()
        half_dead.get.return_value = None
        half_dead.set.side_effect = redis.exceptions.ConnectionError("redis is down")

        with mock.patch("connections.views.cache", half_dead):
            response = self.client.get("/api/persons/orsr/", {"q": "Trnka"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [hit["person_name"] for hit in response.json()["hits"]],
            ["Miroslav Trnka"],
        )

    def test_a_live_cache_still_serves_the_second_caller_from_it(self):
        # The positive control for the two tests above: if the view stopped
        # consulting the cache, both would still pass while proving nothing.
        with mock.patch("connections.views.cache", _WorkingCache()):
            first = self.client.get("/api/persons/orsr/", {"q": "Trnka"})
            second = self.client.get("/api/persons/orsr/", {"q": "Trnka"})

        self.assertNotIn("cached", first.json())
        self.assertTrue(second.json()["cached"])
        self.scraper.return_value.search.assert_called_once_with("Trnka")

    def test_the_outage_is_reported_at_error(self):
        # A degradation nobody can see is the defect class this repo keeps
        # finding: the endpoint would read healthy while scraping orsr.sk on
        # every keystroke.
        with self.assertLogs("connections.views", level="ERROR") as caught:
            with self._dead_cache():
                self.client.get("/api/persons/orsr/", {"q": "Trnka"})

        self.assertIn("Cache is unavailable (get)", caught.output[0])


class CompanyPersonFusionTests(APITestCase):
    """One human, one node -- even when the register wrote them twice.

    The register keeps filings, not people. One human who moved is written
    under two sections in two tenures, each row carrying the address the
    register knew at the time -- and `cluster_evidence` rule 1 refuses to join
    rows stating two different postcodes, because two postcodes *may* be two
    people. That refusal is right about the evidence and wrong on the screen:
    the two rows carry the same name, so the graph drew one person twice with
    nothing to say which was which. The graph folds them by name itself, inside
    one company, and discloses that it did.
    """

    def setUp(self):
        self.company = Company.objects.create(
            ruz_id=1,
            ico="50059959",
            nazov_UJ="Test Firma s.r.o.",
        )

    def _person(self, fingerprint, name, address="", **kwargs):
        return Person.objects.create(
            fingerprint=fingerprint, name=name, address=address, **kwargs
        )

    def _office(self, person, role, **kwargs):
        return PersonCompanyRelation.objects.create(
            person=person, company=self.company, role=role, **kwargs
        )

    def _graph(self, **params):
        return self.client.get(
            f"/api/companies/{self.company.ico}/graph/", params
        ).json()

    def _people(self, data):
        return [node for node in data["nodes"] if node["type"] == "person"]

    def test_one_officer_in_two_roles_is_one_node_with_two_edges(self):
        # The live shape, from 00007838 Rudné bane: one human, moved, written
        # once as konateľ and once as spoločník, the two rows carrying the two
        # postcodes. Two nodes with one label each is what this replaces.
        old = self._person(
            "name:jan novak|addr:porac", "Ján Novák", "Poráč 12, 053 23",
        )
        new = self._person(
            "name:jan novak|addr:snp", "Ján Novák",
            "Letná 4, 052 01 Spišská Nová Ves",
        )
        self._office(
            old, "konatel",
            vznik_funkcie=date(2004, 4, 1),
            zanik_funkcie=date(2025, 3, 13),
            is_active=False,
        )
        self._office(
            new, "spolocnik",
            vznik_funkcie=date(2025, 4, 15),
            is_active=True,
        )

        data = self._graph()
        people = self._people(data)

        self.assertEqual([node["label"] for node in people], ["Ján Novák"])
        # One line per role, which is what the request was: two lines, each
        # carrying its own legend, off one node. The edge carries the register's
        # own wording in `role` -- the graph has no separate display field.
        self.assertEqual(
            sorted(edge["role"] for edge in data["edges"]),
            ["Konateľ", "Spoločník"],
        )
        self.assertEqual(
            {edge["isActive"] for edge in data["edges"]}, {False, True}
        )

    def test_the_fold_is_disclosed_on_the_node(self):
        # A merge the reader cannot see is a merge the reader cannot check.
        old = self._person(
            "name:jan novak|addr:porac", "Ján Novák", "Poráč 12, 053 23",
        )
        new = self._person(
            "name:jan novak|addr:snp", "Ján Novák",
            "Letná 4, 052 01 Spišská Nová Ves",
        )
        self._office(old, "konatel", is_active=False)
        self._office(new, "spolocnik", is_active=True)

        node = self._people(self._graph())[0]

        self.assertEqual(node["records"], 2)
        self.assertEqual(node["clusters"], 2)

    def test_the_node_is_the_lowest_row_of_the_group(self):
        # The id has to be stable and it has to be the one the person table
        # would give, or two screens keyed on it disagree about who this is.
        old = self._person(
            "name:jan novak|addr:porac", "Ján Novák", "Poráč 12, 053 23",
        )
        new = self._person(
            "name:jan novak|addr:snp", "Ján Novák",
            "Letná 4, 052 01 Spišská Nová Ves",
        )
        self._office(old, "konatel", is_active=False)
        self._office(new, "spolocnik", is_active=True)

        self.assertEqual(
            self._people(self._graph())[0]["id"], f"person_{old.id}"
        )

    def test_two_birth_dates_are_not_one_person(self):
        # The one piece of evidence in the table that can *refute* a merge. A
        # drawing fix that folds over it would undo the only guard there is.
        first = self._person(
            "name:jan novak|addr:a", "Ján Novák", "Poráč 12, 053 23",
            birth_date=date(1960, 1, 1),
        )
        second = self._person(
            "name:jan novak|addr:b", "Ján Novák",
            "Letná 4, 052 01 Spišská Nová Ves",
            birth_date=date(1985, 6, 30),
        )
        self._office(first, "konatel", is_active=True)
        self._office(second, "spolocnik", is_active=True)

        self.assertEqual(len(self._people(self._graph())), 2)

    def test_two_person_icos_are_not_one_person(self):
        first = self._person(
            "name:jan novak|addr:a", "Ján Novák", "Poráč 12, 053 23",
            person_ico="11111111",
        )
        second = self._person(
            "name:jan novak|addr:b", "Ján Novák",
            "Letná 4, 052 01 Spišská Nová Ves",
            person_ico="22222222",
        )
        self._office(first, "konatel", is_active=True)
        self._office(second, "spolocnik", is_active=True)

        self.assertEqual(len(self._people(self._graph())), 2)

    def test_one_address_still_gathers_without_a_fold(self):
        # The control. When the two rows agree on the postcode, clustering
        # already joins them -- so this node is one *cluster*, not one cluster
        # standing in for two, and the disclosure has to say so.
        first = self._person(
            "name:jan novak|addr:one", "Ján Novák",
            "Hlavná 5, 811 03 Bratislava",
        )
        second = self._person(
            "name:jan novak|addr:two", "Ján Novák",
            "Hlavná 7, 811 03 Bratislava",
        )
        self._office(first, "konatel", is_active=True)
        self._office(second, "spolocnik", is_active=True)

        people = self._people(self._graph())

        self.assertEqual(len(people), 1)
        self.assertEqual(people[0]["records"], 2)
        self.assertEqual(people[0]["clusters"], 1)

    def test_a_title_does_not_hide_the_fold(self):
        # `base_name` strips leading academic titles, and the fold keys on it --
        # so `Ing. Ján Novák` and `Ján Novák` are one node, which is what a
        # reader sees too.
        titled = self._person(
            "name:ing jan novak|addr:a", "Ing. Ján Novák", "Poráč 12, 053 23",
        )
        plain = self._person(
            "name:jan novak|addr:b", "Ján Novák",
            "Letná 4, 052 01 Spišská Nová Ves",
        )
        self._office(titled, "konatel", is_active=True)
        self._office(plain, "spolocnik", is_active=True)

        people = self._people(self._graph())

        self.assertEqual(len(people), 1)
        self.assertEqual(people[0]["records"], 2)

    def test_two_people_with_different_names_stay_two_nodes(self):
        # The other control: the fold keys on the base name and nothing else.
        self._office(
            self._person("f-a", "Ján Novák"), "konatel", is_active=True,
        )
        self._office(
            self._person("f-b", "Peter Malý"), "spolocnik", is_active=True,
        )

        self.assertEqual(len(self._people(self._graph())), 2)

    def test_the_fold_does_not_cross_into_another_company(self):
        # Two same-named officers of two different companies are not one
        # person, and one company's graph must not say they are.
        other = Company.objects.create(
            ruz_id=2, ico="12345678", nazov_UJ="Iná Firma s.r.o.",
        )
        mine = self._person(
            "name:jan novak|addr:a", "Ján Novák", "Poráč 12, 053 23",
        )
        theirs = self._person(
            "name:jan novak|addr:b", "Ján Novák",
            "Letná 4, 052 01 Spišská Nová Ves",
        )
        self._office(mine, "konatel", is_active=True)
        PersonCompanyRelation.objects.create(
            person=theirs, company=other, role="konatel", is_active=True,
        )

        people = self._people(self._graph())

        self.assertEqual(len(people), 1)
        self.assertEqual(people[0]["records"], 1)
        self.assertEqual(people[0]["clusters"], 1)


class CompanyGraphPeriodTests(APITestCase):
    """The graph, asked about a day instead of about today.

    The relations we hold are the company's whole record: everyone who ever
    held an office, marked ended. A graph that draws all of them at once shows
    a company that never existed -- and the reader has no way to ask for the
    one that did. `?as_of=YYYY-MM-DD` is that question.
    """

    def setUp(self):
        self.company = Company.objects.create(
            ruz_id=1,
            ico="50059959",
            nazov_UJ="Test Firma s.r.o.",
        )
        self.old = Person.objects.create(fingerprint="f-old", name="Ján Novák")
        self.new = Person.objects.create(fingerprint="f-new", name="Peter Malý")
        PersonCompanyRelation.objects.create(
            person=self.old,
            company=self.company,
            role="konatel",
            vznik_funkcie=date(2000, 1, 1),
            zanik_funkcie=date(2010, 12, 31),
            is_active=False,
        )
        PersonCompanyRelation.objects.create(
            person=self.new,
            company=self.company,
            role="konatel",
            vznik_funkcie=date(2015, 1, 1),
            is_active=True,
        )

    def _graph(self, **params):
        return self.client.get(
            f"/api/companies/{self.company.ico}/graph/", params
        ).json()

    def _people(self, data):
        return [node for node in data["nodes"] if node["type"] == "person"]

    def test_a_period_draws_the_officer_of_that_day(self):
        data = self._graph(as_of="2005-06-01")

        self.assertEqual(
            [node["label"] for node in self._people(data)], ["Ján Novák"]
        )

    def test_a_period_draws_the_other_officer_on_another_day(self):
        data = self._graph(as_of="2020-01-01")

        self.assertEqual(
            [node["label"] for node in self._people(data)], ["Peter Malý"]
        )

    def test_a_day_between_two_tenures_draws_nobody(self):
        # Not an error and not an empty answer: on 1 January 2012 this company
        # had filed neither office, and the picture has to be able to say so.
        data = self._graph(as_of="2012-01-01")

        self.assertEqual(self._people(data), [])
        self.assertEqual(len(data["nodes"]), 1)

    def test_an_office_running_then_is_not_drawn_as_ended(self):
        # `is_active` is False today because the office ended in 2010. On a 2005
        # graph it was running, and a dashed "Ukončené" line would be a claim
        # about a company the caller did not ask about.
        data = self._graph(as_of="2005-06-01")

        self.assertEqual([edge["isActive"] for edge in data["edges"]], [True])

    def test_today_is_still_todays_answer(self):
        data = self._graph()

        self.assertIsNone(data["meta"]["as_of"])
        by_label = {node["label"]: node for node in self._people(data)}
        self.assertEqual(sorted(by_label), ["Ján Novák", "Peter Malý"])

    def test_a_relation_without_a_start_date_cannot_be_placed(self):
        # `vznik` unknown means the office cannot be shown to have run on any
        # day, so a period view leaves it out -- and counts it, because a row
        # dropped in silence is a row the reader cannot miss.
        undated = Person.objects.create(fingerprint="f-undated", name="Anna Malá")
        PersonCompanyRelation.objects.create(
            person=undated,
            company=self.company,
            role="spolocnik",
            is_active=True,
        )

        period = self._graph(as_of="2005-06-01")
        today = self._graph()

        self.assertNotIn(
            "Anna Malá", [n["label"] for n in self._people(period)]
        )
        self.assertEqual(period["meta"]["undated_excluded"], 1)
        self.assertIn("Anna Malá", [n["label"] for n in self._people(today)])
        self.assertEqual(today["meta"]["undated_excluded"], 0)

    def test_the_periods_offered_are_the_days_the_company_changed(self):
        # A chip for every year would be 27 chips of which 25 draw the same
        # picture. The record changes on 31 December 2010 (the konateľ ends) and
        # not again until 2015, which is today's shape -- so one chip.
        self.assertEqual(self._graph()["meta"]["periods"], [2010])

    def test_the_current_year_is_never_offered(self):
        # Its 31 December is in the future, and the chip that means "now" is
        # `Dnes`.
        self.assertNotIn(date.today().year, self._graph()["meta"]["periods"])

    def test_as_of_is_echoed_back(self):
        self.assertEqual(
            self._graph(as_of="2005-06-01")["meta"]["as_of"], "2005-06-01"
        )

    def test_a_malformed_date_is_refused(self):
        # Quietly answering with today while the control still reads 2015 would
        # put a period on the screen that the picture below it does not show.
        response = self.client.get(
            f"/api/companies/{self.company.ico}/graph/", {"as_of": "31.12.2015"}
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("RRRR-MM-DD", response.json()["detail"])

    def test_an_empty_as_of_is_today(self):
        # The control's "Dnes" sends nothing; that has to mean today rather than
        # a 400.
        self.assertIsNone(self._graph(as_of="")["meta"]["as_of"])

    def test_the_other_companies_of_a_person_are_filtered_too(self):
        # The expanded node says "Pôsobí v N firmách". On a period graph N is
        # the count for that period, and a company the person joined later must
        # not be drawn at all.
        later = Company.objects.create(
            ruz_id=2, ico="12345678", nazov_UJ="Neskoršia Firma s.r.o.",
        )
        PersonCompanyRelation.objects.create(
            person=self.old,
            company=later,
            role="spolocnik",
            vznik_funkcie=date(2018, 1, 1),
            is_active=True,
        )

        period = self._graph(as_of="2005-06-01")
        today = self._graph()

        self.assertEqual(self._people(period)[0]["rolesCount"], 1)
        self.assertEqual(self._people(today)[0]["rolesCount"], 2)
        self.assertNotIn(
            "Neskoršia Firma s.r.o.",
            [node["label"] for node in period["nodes"]],
        )
        self.assertIn(
            "Neskoršia Firma s.r.o.",
            [node["label"] for node in today["nodes"]],
        )


class CompanyPersonsAPITests(APITestCase):
    """`GET /api/companies/<ico>/persons/` -- the record behind the graph.

    The Osoby cards read the register's extract, which is the bodies as they
    stand today; everyone who held an office before is in the same stored
    relations and nothing read them. This endpoint is the history, from the
    same helper and the same rows as the graph, so the list and the picture
    cannot disagree.
    """

    def setUp(self):
        self.company = Company.objects.create(
            ruz_id=1,
            ico="50059959",
            nazov_UJ="Test Firma s.r.o.",
        )

    def _person(self, fingerprint, name, address="", **kwargs):
        return Person.objects.create(
            fingerprint=fingerprint, name=name, address=address, **kwargs
        )

    def _office(self, person, role, **kwargs):
        return PersonCompanyRelation.objects.create(
            person=person, company=self.company, role=role, **kwargs
        )

    def _persons(self, **params):
        return self.client.get(
            f"/api/companies/{self.company.ico}/persons/", params
        ).json()

    def test_lists_every_person_the_company_ever_had(self):
        current = self._person("f-now", "Peter Malý")
        former = self._person("f-then", "Ján Novák")
        self._office(
            current, "konatel", vznik_funkcie=date(2015, 1, 1), is_active=True,
        )
        self._office(
            former, "konatel",
            vznik_funkcie=date(2000, 1, 1), zanik_funkcie=date(2010, 12, 31),
            is_active=False,
        )

        data = self._persons()

        self.assertEqual(data["ico"], self.company.ico)
        self.assertEqual(
            sorted(group["name"] for group in data["groups"]),
            ["Ján Novák", "Peter Malý"],
        )
        by_name = {group["name"]: group for group in data["groups"]}
        self.assertIs(by_name["Peter Malý"]["offices"][0]["is_active"], True)
        self.assertIs(by_name["Ján Novák"]["offices"][0]["is_active"], False)
        self.assertEqual(
            by_name["Ján Novák"]["offices"][0]["zanik_funkcie"], "2010-12-31"
        )

    def test_one_person_written_twice_is_one_group_with_both_addresses(self):
        old = self._person(
            "name:jan novak|addr:porac", "Ján Novák", "Poráč 12, 053 23",
        )
        new = self._person(
            "name:jan novak|addr:snp", "Ján Novák",
            "Letná 4, 052 01 Spišská Nová Ves",
        )
        self._office(
            old, "konatel",
            vznik_funkcie=date(2004, 4, 1), zanik_funkcie=date(2025, 3, 13),
            is_active=False,
        )
        self._office(
            new, "spolocnik", vznik_funkcie=date(2025, 4, 15), is_active=True,
        )

        group = self._persons()["groups"][0]

        self.assertEqual(group["records"], 2)
        self.assertEqual(group["clusters"], 2)
        # The judgement is a judgement, so the evidence behind it travels with
        # it: two addresses is exactly what a reader would use to disagree.
        self.assertEqual(
            sorted(member["address"] for member in group["members"]),
            ["Letná 4, 052 01 Spišská Nová Ves", "Poráč 12, 053 23"],
        )
        self.assertEqual(
            sorted(office["role_display"] for office in group["offices"]),
            ["Konateľ", "Spoločník"],
        )

    def test_a_birth_date_stays_on_the_row_that_states_it(self):
        # Two dates are the case this must not present as one person, and the
        # rows are kept apart -- so the dates must stay per row, not be lifted
        # onto a grouping that is one person by definition.
        first = self._person(
            "name:jan novak|addr:a", "Ján Novák", "Poráč 12, 053 23",
            birth_date=date(1960, 1, 1),
        )
        second = self._person(
            "name:jan novak|addr:b", "Ján Novák",
            "Letná 4, 052 01 Spišská Nová Ves",
            birth_date=date(1985, 6, 30),
        )
        self._office(first, "konatel", is_active=True)
        self._office(second, "spolocnik", is_active=True)

        data = self._persons()

        self.assertEqual(len(data["groups"]), 2)
        for group in data["groups"]:
            for member in group["members"]:
                self.assertIsNotNone(member["birth_date"])

    def test_consecutive_filings_of_one_office_are_one_office(self):
        # The register keeps filings, not functions. One tenure from 2011 to
        # 2020 arrives as two rows that meet day to day, and the history list
        # has to show one line -- and say it was folded from two, because a row
        # that quietly replaced two filings reads like a row that always was one.
        person = self._person("f-jan", "Ján Novák")
        self._office(
            person, "konatel",
            vznik_funkcie=date(2011, 1, 1), zanik_funkcie=date(2015, 12, 31),
            is_active=False,
        )
        self._office(
            person, "konatel",
            vznik_funkcie=date(2016, 1, 1), zanik_funkcie=date(2020, 12, 31),
            is_active=False,
        )

        offices = self._persons()["groups"][0]["offices"]

        self.assertEqual(len(offices), 1)
        self.assertEqual(offices[0]["intervals"], 2)
        self.assertEqual(offices[0]["vznik_funkcie"], "2011-01-01")
        self.assertEqual(offices[0]["zanik_funkcie"], "2020-12-31")

    def test_a_period_shows_only_the_people_in_force_then(self):
        current = self._person("f-now", "Peter Malý")
        former = self._person("f-then", "Ján Novák")
        self._office(
            current, "konatel", vznik_funkcie=date(2015, 1, 1), is_active=True,
        )
        self._office(
            former, "konatel",
            vznik_funkcie=date(2000, 1, 1), zanik_funkcie=date(2010, 12, 31),
            is_active=False,
        )

        data = self._persons(as_of="2005-06-01")

        self.assertEqual([group["name"] for group in data["groups"]], ["Ján Novák"])
        self.assertEqual(data["as_of"], "2005-06-01")

    def test_the_periods_offered_match_the_ones_the_graph_offers(self):
        # Same helper, same rows: a chip that draws one thing on the canvas and
        # another in the list is worse than no chip.
        former = self._person("f-then", "Ján Novák")
        current = self._person("f-now", "Peter Malý")
        self._office(
            former, "konatel",
            vznik_funkcie=date(2000, 1, 1), zanik_funkcie=date(2010, 12, 31),
            is_active=False,
        )
        self._office(
            current, "konatel", vznik_funkcie=date(2015, 1, 1), is_active=True,
        )

        graph = self.client.get(
            f"/api/companies/{self.company.ico}/graph/"
        ).json()

        self.assertEqual(self._persons()["periods"], graph["meta"]["periods"])

    def test_the_list_and_the_graph_name_the_same_people(self):
        old = self._person(
            "name:jan novak|addr:a", "Ján Novák", "Poráč 12, 053 23",
        )
        new = self._person(
            "name:jan novak|addr:b", "Ján Novák",
            "Letná 4, 052 01 Spišská Nová Ves",
        )
        self._office(old, "konatel", is_active=False)
        self._office(new, "spolocnik", is_active=True)

        graph = self.client.get(
            f"/api/companies/{self.company.ico}/graph/"
        ).json()
        listed = self._persons()

        self.assertEqual(
            sorted(group["name"] for group in listed["groups"]),
            sorted(
                node["label"] for node in graph["nodes"]
                if node["type"] == "person"
            ),
        )
        self.assertEqual(
            [group["records"] for group in listed["groups"]],
            [
                node["records"] for node in graph["nodes"]
                if node["type"] == "person"
            ],
        )

    def test_a_relation_without_a_start_date_is_listed_and_counted(self):
        # Today's answer is everyone we hold, so an undated row is in it -- and
        # a *period* answer says how many rows it had to leave out.
        person = self._person("f-undated", "Anna Malá")
        self._office(person, "spolocnik", is_active=True)

        today = self._persons()
        period = self._persons(as_of="2005-06-01")

        self.assertEqual([group["name"] for group in today["groups"]], ["Anna Malá"])
        self.assertEqual(today["undated_excluded"], 0)
        self.assertEqual(period["groups"], [])
        self.assertEqual(period["undated_excluded"], 1)

    def test_a_malformed_date_is_refused(self):
        response = self.client.get(
            f"/api/companies/{self.company.ico}/persons/", {"as_of": "nope"}
        )

        self.assertEqual(response.status_code, 400)

    def test_unknown_company_is_404(self):
        response = self.client.get("/api/companies/00000000/persons/")

        self.assertEqual(response.status_code, 404)

    def test_a_company_with_no_people_answers_with_an_empty_list(self):
        data = self._persons()

        self.assertEqual(data["groups"], [])
        self.assertEqual(data["periods"], [])
        self.assertEqual(data["name"], self.company.nazov_UJ)


class CoverageQueryShapeTests(TestCase):
    """`_coverage()` must count ids, not whole company rows.

    This is a test of a query's *shape*, which is usually a smell -- it is here
    because the defect it guards is invisible to every other kind of test. Both
    forms return the same number, so `test_coverage_is_reported_with_every_answer`
    passes either way; the difference is that one of them makes Postgres sort
    every column of every matched company row.

    Measured on production 2026-09-28: `SELECT DISTINCT <all 45 columns>` over
    ~168k rows took 9.5-11.8 s per call, and the call sits in the response path
    of the person search, the person detail page and the short-query refusal.
    Counting distinct ids took 0.37 s and is the form the other five coverage
    counts in this project already use.

    A rewrite that is fast but shaped differently is fine and will pass: what is
    forbidden is a DISTINCT that selects more than one expression.
    """

    def test_no_coverage_query_distincts_over_a_whole_row(self):
        Company.objects.create(ruz_id=1, ico="50059959", nazov_UJ="Test Firma")

        with CaptureQueriesContext(connection) as captured:
            _coverage()

        wide = [
            sql
            for sql in (q["sql"] for q in captured.captured_queries)
            if self._distinct_selects(sql)
        ]

        self.assertEqual(wide, [], "DISTINCT must be over ids, not whole rows")

    @staticmethod
    def _distinct_selects(sql: str) -> list[str]:
        """The expressions of every `SELECT DISTINCT ... FROM` in `sql`."""
        selects = []
        for match in re.finditer(
            r"SELECT\s+DISTINCT\s+(.*?)\s+FROM\s", sql, re.IGNORECASE | re.DOTALL
        ):
            # Split on commas that are not inside parentheses: `AS "col1"` and
            # `COUNT(DISTINCT x)` both appear in this project's SQL.
            body = match.group(1)
            depth = 0
            expression = ""
            parts = []
            for char in body:
                if char == "(":
                    depth += 1
                elif char == ")":
                    depth -= 1
                if char == "," and depth == 0:
                    parts.append(expression)
                    expression = ""
                    continue
                expression += char
            parts.append(expression)
            selects.append([p.strip() for p in parts if p.strip()])
        return [s for s in selects if len(s) > 1]
