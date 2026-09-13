"""One person, several `Person` rows -- and what we do about it.

The register renders the same officer under two sections of one document, so the
extractor stores two rows, and a reader searching a name meets the same man two
or three times. Measured 2026-09-13: of 4 238 `(company, name)` duplicate
groups, 3 558 (84 %) have every member created within 60 s of the others, median
7.7 ms apart -- one document, one person, written twice.

These tests hold the line between the two ways of answering that. A group that
is *shown* as one person, carries every office its rows hold, and discloses the
rows it was built from is checkable, so a wrong group is visible. A merge is
neither. Only the first is implemented, and the tests below are as much about
what refuses to join as about what joins.
"""

from datetime import date
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APITestCase

from companies.models import Company
from .identity import (
    PersonEvidence,
    base_name,
    cluster_evidence,
    extract_psc,
)
from .models import Person, PersonCompanyRelation


def ev(id, name, address="", person_ico="", companies=()):
    """One row, reduced the way the resolver reduces it."""
    return PersonEvidence(
        id=id, name=name, address=address, person_ico=person_ico, companies=companies
    )


class BaseNameTests(TestCase):
    """A title is not part of a name -- but `name_normalized` keeps it."""

    def test_a_leading_title_is_removed(self):
        self.assertEqual(base_name("Ing. Miroslav Trnka"), "miroslav trnka")
        self.assertEqual(base_name("Miroslav Trnka"), "miroslav trnka")

    def test_a_chain_of_titles_is_removed(self):
        # 791 live rows carry two titles in a row: the register writes
        # `Ing. arch.`, `Mgr. art.`, `Dipl. oec.` and `Ing. Mgr.`.
        self.assertEqual(base_name("Ing. arch. Jozef Kaliský"), "jozef kalisky")
        self.assertEqual(base_name("Dipl. oec. Susanna Haberland"), "susanna haberland")

    def test_a_title_inside_a_name_is_left_alone(self):
        # Only *leading* titles go. A token in the middle is part of the name,
        # and eating it would join two different people.
        self.assertEqual(base_name("Ján Ing Novák"), "jan ing novak")

    def test_a_name_that_is_only_a_title_is_not_emptied(self):
        # Otherwise every such row would share one key and be reported as one
        # person -- the failure mode the whole module exists to avoid.
        self.assertEqual(base_name("Ing."), "ing.")
        self.assertEqual(base_name(""), "")

    def test_diacritics_are_stripped(self):
        self.assertEqual(base_name("Štefan Kováč"), "stefan kovac")


class ExtractPscTests(TestCase):
    """The defect #89 was actually filed against.

    `compute_fingerprint` walks back from the end of an address looking for a
    component that is `not part.isdigit()` -- and a bare Slovak postcode
    (`81103`) *is* a digit string, so the rule skips it and lands on the city.
    Bare in 33 424 live rows against spaced in only 6 426, which is why the
    identity key had degenerated to "name + city": `bratislava` alone appears in
    3 832 of them.
    """

    def test_a_bare_postcode_is_found(self):
        self.assertEqual(extract_psc("Beniakova 12, Bratislava, 84105"), "84105")

    def test_a_spaced_postcode_is_found(self):
        self.assertEqual(
            extract_psc("Beniakova, 3100/12, Bratislava - mestská časť Karlova Ves, 841 05"),
            "84105",
        )

    def test_a_postcode_written_into_the_city_component_is_found(self):
        # 76 live rows reach their postcode only this way, which is why the
        # pattern is not anchored to the whole component.
        self.assertEqual(
            extract_psc("Bajkalská 5/C, Bratislava - mestská časť Nové Mesto 831 04"),
            "83104",
        )

    def test_the_last_component_wins(self):
        # The postcode is the last part of a Slovak address, and an earlier
        # component can hold a number that looks like one.
        self.assertEqual(extract_psc("Hlavná 5, 040 01 Košice, 821 01"), "82101")

    def test_a_birth_date_is_not_a_postcode(self):
        # The pseudo-address the ORSR scraper writes when the document carries
        # `Dátum narodenia` where the address goes. Fourteen live rows.
        self.assertEqual(extract_psc("Dátum narodenia: 20.08.1992"), "")

    def test_a_street_number_is_not_a_postcode(self):
        self.assertEqual(extract_psc("Stará Klenová 13250/28D, Bratislava"), "")

    def test_a_birth_number_is_not_a_postcode(self):
        self.assertEqual(extract_psc("920820/1234"), "")

    def test_an_absent_address_has_no_postcode(self):
        self.assertEqual(extract_psc(""), "")
        self.assertEqual(extract_psc(None), "")


class ClusterEvidenceTests(TestCase):
    """Two kinds of evidence join rows. Nothing else does."""

    def test_one_document_written_twice_is_one_person(self):
        """The #89 case, with the real addresses.

        `Matej Vácha` under `Predstavenstvo` carries a birth date where the
        address goes, under `Spoločníci` carries nothing at all, and a third
        read has his street. Three rows, one man, three fingerprints -- so no
        key computed over a single row can join them, which is the whole reason
        this resolves at read time instead.
        """
        clusters = cluster_evidence([
            ev(44903, "Matej Vácha", "Dátum narodenia: 20.08.1992", companies=[7]),
            ev(44904, "Matej Vácha", "", companies=[7]),
            ev(45335, "Matej Vácha", "Beniakova, 3100/12, ..., 841 05", companies=[7]),
        ])
        self.assertEqual(len(clusters), 1)
        self.assertEqual([m.id for m in clusters[0]], [44903, 44904, 45335])

    def test_a_title_does_not_make_a_second_person(self):
        clusters = cluster_evidence([
            ev(1, "Miroslav Trnka", "Hlavná 5, 040 01 Košice", companies=[10]),
            ev(2, "Ing. Miroslav Trnka", "Hlavná 5, 04001", companies=[11]),
        ])
        self.assertEqual(len(clusters), 1)

    def test_two_postcodes_in_one_company_stay_apart(self):
        """These may genuinely be two people, and a false merge is worse than a
        duplicate: it would show a role the register never states, invisibly."""
        clusters = cluster_evidence([
            ev(44906, "Peter Knap", "Miloslavov 900 91", companies=[204]),
            ev(44907, "Peter Knap", "Dunajská Lužná 040 13", companies=[204]),
        ])
        self.assertEqual(len(clusters), 2)

    def test_a_row_with_no_postcode_does_not_join_either_side(self):
        """It could belong to either, which is not evidence that it belongs to
        both. The row stands with its own kind."""
        clusters = cluster_evidence([
            ev(1, "Peter Knap", "900 91", companies=[204]),
            ev(2, "Peter Knap", "040 13", companies=[204]),
            ev(3, "Peter Knap", "", companies=[204]),
        ])
        self.assertEqual(len(clusters), 3)

    def test_two_person_icos_are_never_one_person(self):
        """An IČO names an organisation. Measured, exactly one company group in
        the live data would otherwise be joined this way."""
        clusters = cluster_evidence([
            ev(1, "RB Portfolio 72 s.r.o.", "Bratislava 821 01",
               person_ico="55849431", companies=[9]),
            ev(2, "RB Portfolio 72 s.r.o.", "Bratislava 821 01",
               person_ico="56091401", companies=[9]),
        ])
        self.assertEqual(len(clusters), 2)

    def test_a_row_without_an_ico_joins_the_one_that_has_it(self):
        clusters = cluster_evidence([
            ev(1, "Ján Novák", "Hlavná 5, 040 01", person_ico="12345678", companies=[9]),
            ev(2, "Ján Novák", "Hlavná 5, 04001", companies=[9]),
        ])
        self.assertEqual(len(clusters), 1)

    def test_a_row_without_an_ico_does_not_bridge_two_icos(self):
        """The guard has to refuse the second join while allowing the first, or
        an unlabelled row becomes a bridge between two organisations."""
        clusters = cluster_evidence([
            ev(1, "Firma X", "Bratislava 821 01", person_ico="11111111", companies=[9]),
            ev(2, "Firma X", "Bratislava 821 01", person_ico="22222222", companies=[9]),
            ev(3, "Firma X", "Bratislava 821 01", companies=[9]),
        ])
        self.assertEqual(len(clusters), 2)

    def test_the_same_name_in_two_places_stays_apart(self):
        clusters = cluster_evidence([
            ev(1, "Ján Kováč", "Kvetoslavov 930 41", companies=[1]),
            ev(2, "Ján Kováč", "Tomášov 900 44", companies=[2]),
        ])
        self.assertEqual(len(clusters), 2)

    def test_different_names_are_never_joined(self):
        clusters = cluster_evidence([
            ev(1, "Ján Novák", "Hlavná 5, 040 01", companies=[1]),
            ev(2, "Peter Novák", "Hlavná 5, 040 01", companies=[1]),
        ])
        self.assertEqual(len(clusters), 2)

    def test_a_lone_row_is_its_own_cluster(self):
        clusters = cluster_evidence([ev(1, "Ján Novák", "Hlavná 5", companies=[1])])
        self.assertEqual(len(clusters), 1)
        self.assertEqual(len(clusters[0]), 1)

    def test_no_rows_is_no_clusters(self):
        self.assertEqual(cluster_evidence([]), [])


class PersonGroupingAPITests(APITestCase):
    """What a reader sees, which is the whole point of the exercise."""

    def setUp(self):
        self.company = Company.objects.create(
            ruz_id=1, ico="52366332", nazov_UJ="Test s.r.o."
        )
        self.birth_date_row = Person.objects.create(
            fingerprint="name:matej vacha|addr:datum narodenia: 20.08.1992",
            name="Matej Vácha",
            address="Dátum narodenia: 20.08.1992",
        )
        self.empty_row = Person.objects.create(
            fingerprint="name:matej vacha|addr:",
            name="Matej Vácha",
        )
        PersonCompanyRelation.objects.create(
            person=self.birth_date_row, company=self.company,
            role="konatel", is_active=True,
        )
        PersonCompanyRelation.objects.create(
            person=self.empty_row, company=self.company,
            role="spolocnik", is_active=True,
        )

    def test_search_answers_with_one_person_not_two_rows(self):
        data = self.client.get("/api/persons/?q=vacha").json()
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["name"], "Matej Vácha")

    def test_the_row_count_is_still_reported_apart_from_the_people_count(self):
        data = self.client.get("/api/persons/?q=vacha").json()
        self.assertEqual(data["total_matches"], 2)
        self.assertEqual(data["total_people"], 1)

    def test_the_grouped_answer_says_how_many_rows_it_gathered(self):
        data = self.client.get("/api/persons/?q=vacha").json()
        self.assertEqual(data["results"][0]["records"], 2)

    def test_the_grouped_answer_carries_every_office(self):
        """Rows are merged, claims are not: both roles survive, each with its
        own dates and its own answer about whether the function still runs."""
        companies = self.client.get("/api/persons/?q=vacha").json()["results"][0]["companies"]
        self.assertEqual({c["role"] for c in companies}, {"konatel", "spolocnik"})

    def test_the_detail_page_lists_the_rows_it_merged(self):
        """The judgement is disclosed, so a wrong one is visible to the reader
        it is wrong about. That is what makes grouping safer than a merge."""
        data = self.client.get(f"/api/persons/{self.birth_date_row.pk}/").json()
        self.assertEqual(data["records"], 2)
        self.assertEqual(len(data["members"]), 2)
        self.assertIn("Dátum narodenia", data["members"][0]["address"])

    def test_the_detail_page_serves_the_same_answer_from_either_row(self):
        """Both rows are the person; which one a reader arrived through must not
        change what they are told."""
        first = self.client.get(f"/api/persons/{self.birth_date_row.pk}/").json()
        second = self.client.get(f"/api/persons/{self.empty_row.pk}/").json()
        self.assertEqual(first["companies"], second["companies"])
        self.assertEqual(first["members"], second["members"])

    def test_an_undated_relation_does_not_contradict_a_dated_one(self):
        """Grouping can put two relations for one office side by side where a
        single row never did. The register's legend spells "nevieme" out as
        "this company has not been read yet" -- printed under a dated relation
        for the same office in the same company, that sentence is false: we
        demonstrably read it. The undated row states no period, so it cannot be
        a second tenure, and it is the one that goes."""
        dated = Person.objects.create(
            fingerprint="name:jozef novak|addr:bratislava, 811 03",
            name="Jozef Novák",
            address="Bratislava, 811 03",
        )
        undated = Person.objects.create(
            fingerprint="name:jozef novak|addr:",
            name="Jozef Novák",
        )
        PersonCompanyRelation.objects.create(
            person=dated, company=self.company, role="konatel",
            is_active=True, vznik_funkcie=date(2019, 5, 18),
        )
        PersonCompanyRelation.objects.create(
            person=undated, company=self.company, role="konatel", is_active=None,
        )

        companies = self.client.get(f"/api/persons/{dated.pk}/").json()["companies"]

        self.assertEqual(len(companies), 1)
        self.assertIs(companies[0]["is_active"], True)
        self.assertEqual(companies[0]["vznik_funkcie"], "2019-05-18")

    def test_a_real_second_tenure_is_not_collapsed(self):
        """The rule above drops rows that state no period. It must not become a
        rule that hides history: two dated tenures in one office are two facts
        and both stay."""
        person = Person.objects.create(
            fingerprint="name:jozef novak|addr:bratislava, 811 03",
            name="Jozef Novák",
            address="Bratislava, 811 03",
        )
        PersonCompanyRelation.objects.create(
            person=person, company=self.company, role="konatel",
            is_active=False, vznik_funkcie=date(2005, 1, 1),
            zanik_funkcie=date(2010, 6, 30),
        )
        PersonCompanyRelation.objects.create(
            person=person, company=self.company, role="konatel",
            is_active=True, vznik_funkcie=date(2019, 5, 18),
        )

        companies = self.client.get(f"/api/persons/{person.pk}/").json()["companies"]

        self.assertEqual(
            sorted(c["vznik_funkcie"] for c in companies),
            ["2005-01-01", "2019-05-18"],
        )

    def test_the_company_graph_draws_one_node_per_person(self):
        data = self.client.get(f"/api/companies/{self.company.ico}/graph/").json()
        persons = [n for n in data["nodes"] if n["type"] == "person"]
        self.assertEqual(len(persons), 1)
        # The edges are not merged: two offices are two lines, each labelled
        # with its own role.
        self.assertEqual(len(data["edges"]), 2)

    def test_two_people_with_one_name_are_not_fused(self):
        other = Person.objects.create(
            fingerprint="name:peter knap|addr:040 13",
            name="Peter Knap",
            address="Dunajská Lužná 040 13",
        )
        PersonCompanyRelation.objects.create(
            person=other, company=self.company, role="konatel", is_active=True,
        )
        knap = Person.objects.create(
            fingerprint="name:peter knap|addr:900 91",
            name="Peter Knap",
            address="Miloslavov 900 91",
        )
        PersonCompanyRelation.objects.create(
            person=knap, company=self.company, role="konatel", is_active=True,
        )

        data = self.client.get("/api/persons/?q=knap").json()

        self.assertEqual(len(data["results"]), 2)
        for result in data["results"]:
            self.assertEqual(result["records"], 1)

    def test_total_people_is_unknown_when_the_window_stops_short(self):
        """`null`, not a smaller number dressed as an answer -- the same
        distinction `coverage` makes. A count we did not compute is not a count
        of zero, and reporting the part we read would understate the answer by
        however much we skipped.
        """
        for index in range(4):
            person = Person.objects.create(
                fingerprint=f"name:test osoba {index}|addr:",
                name=f"Test Osoba {index}",
            )
            PersonCompanyRelation.objects.create(
                person=person, company=self.company, role="konatel", is_active=True,
            )

        with patch("connections.views.CLUSTER_SCAN_LIMIT", 2):
            data = self.client.get("/api/persons/?q=osoba").json()

        self.assertGreater(data["total_matches"], 2)
        self.assertIsNone(data["total_people"])
        self.assertTrue(data["truncated"])

    def test_a_refused_query_says_so_about_people_too(self):
        """The short-query answer is a shape like any other, and a reader of the
        API should not have to special-case it."""
        data = self.client.get("/api/persons/?q=a").json()
        self.assertIsNone(data["total_people"])
        self.assertEqual(data["results"], [])
