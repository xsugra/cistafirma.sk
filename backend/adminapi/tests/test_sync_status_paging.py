"""The sync-status table is as large as the book is, so it cannot answer in one page.

`CompanySyncStatus` holds one row per company per source. When the admin screen
was finally wired up to it, the table held 111 071 rows — `vszp` and `social`
54 007 each — and the endpoint, having no pagination class, serialised every one
of them into a single response. Nothing had ever called it, which is why nobody
had noticed.

These go through the real endpoint rather than the ORM, because the claim is
about what the screen is able to receive.
"""

from django.test import TestCase
from rest_framework.test import APIClient

from companies.models import Company
from registers.models import CompanySyncStatus
from users.models import User


class SyncStatusPagingTests(TestCase):
    URL = "/api/admin/sync/companies/"

    def setUp(self):
        self.staff = User.objects.create_user(
            email="admin@example.com", password="testpass123", is_staff=True
        )
        self.client = APIClient()
        self.client.force_authenticate(self.staff)

    def _rows(self, count: int, source: str, detail: str = "", offset: int = 0) -> None:
        for index in range(count):
            number = offset + index
            company = Company.objects.create(
                ruz_id=10_000 + number,
                ico=f"90{number:06d}",
                nazov_UJ=f"Firma {number}",
            )
            CompanySyncStatus.objects.create(
                company=company, source=source, last_detail=detail
            )

    def test_the_answer_is_a_page_and_not_the_whole_table(self):
        self._rows(120, CompanySyncStatus.SOURCE_ORSR)

        response = self.client.get(self.URL)

        self.assertEqual(response.status_code, 200)
        self.assertIn("results", response.data)
        self.assertEqual(response.data["count"], 120)
        self.assertEqual(len(response.data["results"]), 50)

    def test_the_last_page_holds_what_is_left(self):
        self._rows(120, CompanySyncStatus.SOURCE_ORSR)

        third = self.client.get(self.URL, {"page": 3})

        self.assertEqual(third.status_code, 200)
        self.assertEqual(len(third.data["results"]), 20)

    def test_a_filter_is_counted_by_the_rows_it_returns(self):
        # The reason an operator opens this screen: `financials` rows whose
        # statements were read and none of them recordable. They are answered
        # attempts, so their failure count is 0 and the default ordering buries
        # them -- `has_detail` is what makes them reachable at all.
        self._rows(
            3,
            CompanySyncStatus.SOURCE_FINANCIALS,
            detail="4 statement(s) present, none carrying a headline figure",
        )
        self._rows(60, CompanySyncStatus.SOURCE_ORSR, offset=100)

        response = self.client.get(self.URL, {"has_detail": "1"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 3)
        self.assertEqual(len(response.data["results"]), 3)
        self.assertTrue(
            all(row["source"] == "financials" for row in response.data["results"])
        )

    def test_the_page_size_can_be_raised_within_its_ceiling(self):
        self._rows(120, CompanySyncStatus.SOURCE_ORSR)

        response = self.client.get(self.URL, {"page_size": 200})

        self.assertEqual(len(response.data["results"]), 120)
