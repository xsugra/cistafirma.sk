"""A refused field has to be visible where a human actually looks.

`source_health` judges a source and `make ops-check` reaches a verdict, but
neither is a screen an operator opens. Four admin readers answer "is this
company's sync healthy?" and every one of them reads
`CompanySyncStatus.consecutive_failures` and nothing else:

- `dashboard_overview`'s `company_failures_24h` card,
- `dashboard_sync`'s per-source `failing_count` and `avg_consecutive_failures`,
- `company_filters`' `sync_state` filter,
- `lead_scoring`'s average.

While `ruz` wrote a refusal row without incrementing that counter, all four
said the source was immaculate -- and the one control that did see the refusal
could say how many records were affected but never which company. These tests
go through the real HTTP endpoints rather than the ORM, because the claim is
about what the screens report, not about what the rows contain.
"""

from datetime import date, timedelta

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from companies.models import Company
from users.models import User


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class DashboardSeesARefusedDateTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            email="admin@example.com", password="testpass123", is_staff=True
        )
        self.company = Company.objects.create(
            ruz_id=111,
            ico="90000111",
            nazov_UJ="Zrušená s.r.o.",
            datum_zrusenia=date(2026, 3, 12),
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.staff)

    def _record(self, **overrides):
        data = {
            "ico": self.company.ico,
            "id": self.company.ruz_id,
            "nazovUJ": self.company.nazov_UJ,
        }
        data.update(overrides)
        return data

    def _refuse_then_recover(self):
        from registers.tasks import _update_company_from_ruz_data

        with self.assertLogs("registers.integrations.ruz_api", level="ERROR"):
            _update_company_from_ruz_data(self._record(datumZrusenia="12.03.2026"))
        _update_company_from_ruz_data(self._record(datumZrusenia="2026-03-12"))

    def _overview(self):
        """`company_failures_24h` -- the card the four readers share."""
        response = self.client.get("/api/admin/metrics/overview/")
        self.assertEqual(response.status_code, 200)
        return response.json()["sync"]["company_failures_24h"]

    def _ruz_card(self):
        response = self.client.get("/api/admin/metrics/sync/")
        self.assertEqual(response.status_code, 200)
        return next(s for s in response.json()["sources"] if s["source"] == "ruz")

    def test_a_refused_date_shows_up_on_the_dashboard(self):
        from registers.tasks import _update_company_from_ruz_data

        self.assertEqual(self._overview(), 0)

        with self.assertLogs("registers.integrations.ruz_api", level="ERROR"):
            _update_company_from_ruz_data(self._record(datumZrusenia="12.03.2026"))

        self.assertEqual(self._overview(), 1)
        card = self._ruz_card()
        self.assertEqual(card["failing_count"], 1)
        self.assertEqual(card["avg_consecutive_failures"], 1.0)

    def test_a_clean_sync_shows_as_coverage_rather_than_as_nothing(self):
        """`ruz` reported 0 % coverage while it was the healthiest source.

        With no success path there was no `last_succeeded_at` to count, so the
        coverage card read zero for the source that syncs every six hours and
        never fails. The success row is what makes the number mean something.
        """
        from registers.tasks import _update_company_from_ruz_data

        _update_company_from_ruz_data(self._record(datumZrusenia="2026-03-12"))

        card = self._ruz_card()
        self.assertEqual(card["synced_count"], 1)
        self.assertEqual(card["coverage_pct"], 100.0)
        self.assertEqual(card["failing_count"], 0)
        self.assertEqual(self._overview(), 0)

    def test_the_dashboard_clears_once_the_date_reads_again(self):
        """An upstream typo that is fixed has to stop being an alarm.

        The row records the latest attempt, so a company whose next sync reads
        its dates cleanly is healthy again on every one of the four readers.
        A failure that could not be cleared is what made writing it unsafe
        while `ruz` had no success path.
        """
        self._refuse_then_recover()

        self.assertEqual(self._overview(), 0)
        card = self._ruz_card()
        self.assertEqual(card["failing_count"], 0)
        self.assertEqual(card["synced_count"], 1)

    def test_the_recovery_is_a_success_row_and_not_a_deleted_one(self):
        """Clearing has to be a recorded success, not an absent row.

        Deleting the failure would also make the dashboard read zero, and
        would lose the attempt in the same stroke -- the card would be
        right for the wrong reason and the next refusal would start from a
        count that was never written.
        """
        from registers.models import CompanySyncStatus

        self._refuse_then_recover()

        status = CompanySyncStatus.objects.get(
            company=self.company, source=CompanySyncStatus.SOURCE_RUZ
        )
        self.assertEqual(status.consecutive_failures, 0)
        self.assertIsNotNone(status.last_succeeded_at)
        self.assertIsNotNone(status.last_attempted_at)
        self.assertGreaterEqual(
            status.last_attempted_at, timezone.now() - timedelta(minutes=5)
        )
