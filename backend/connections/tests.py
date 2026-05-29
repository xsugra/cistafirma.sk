from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from companies.models import Company
from registers.models import OrsrCompanyProfile
from .models import Person, PersonCompanyRelation, compute_fingerprint
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
