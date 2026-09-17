"""The "refresh this company" control asks every source -- and says what it did not ask.

The company page is public: `/firma/:ico` sits outside `ProtectedRoute` and
`CompanyViewSet` is `AllowAny`. So the interesting properties of this endpoint
are not only what it dispatches but who may reach it, and the tests below pin
both. They also pin the two refusals that *are* allowed to happen -- an
ineligible legal form, and a source an admin has blocked -- because a control
that drops a source in silence is indistinguishable from one that asked it and
got nothing.
"""

from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from companies.models import Company
from registers.models import CompanySyncStatus, SyncJob
from users.models import User

LOCMEM = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "company-refresh-tests",
    }
}


@override_settings(CACHES=LOCMEM)
class CompanyRefreshTests(TestCase):
    def setUp(self):
        cache.clear()
        self.staff = User.objects.create_user(
            email="admin@example.com", password="testpass123", is_staff=True
        )
        self.mortal = User.objects.create_user(
            email="user@example.com", password="testpass123"
        )
        self.company = Company.objects.create(
            ruz_id=10_001,
            ico="90000001",
            nazov_UJ="Testovacia s.r.o.",
            pravna_forma="112",
        )
        self.url = f"/api/admin/companies/{self.company.pk}/refresh/"
        self.client = APIClient()

    def _post(self, **kwargs):
        return self.client.post(self.url, **kwargs)

    # -- who may reach it ---------------------------------------------------

    def test_an_anonymous_visitor_cannot_spend_the_scrapers_budget(self):
        response = self._post()

        self.assertIn(response.status_code, (401, 403))

    def test_a_signed_in_non_staff_user_cannot_either(self):
        self.client.force_authenticate(self.mortal)

        response = self._post()

        self.assertEqual(response.status_code, 403)

    # -- what it asks -------------------------------------------------------

    def test_a_staff_refresh_dispatches_the_full_pass_once(self):
        self.client.force_authenticate(self.staff)

        with patch("registers.tasks.orchestrate_full_company_sync") as task:
            response = self._post()

        self.assertEqual(response.status_code, 200)
        task.apply_async.assert_called_once()
        self.assertEqual(task.apply_async.call_args.kwargs.get("args"), [self.company.pk])

    def test_an_eligible_company_is_asked_of_every_source(self):
        self.client.force_authenticate(self.staff)

        with patch("registers.tasks.orchestrate_full_company_sync"):
            response = self._post()

        self.assertEqual(
            response.data["dispatched"], ["ruz", "financials", "orsr", "vszp", "social"]
        )
        self.assertEqual(response.data["skipped"], [])

    def test_an_ineligible_legal_form_is_reported_rather_than_dropped(self):
        other = Company.objects.create(
            ruz_id=10_002, ico="90000002", nazov_UJ="Fyzická osoba", pravna_forma="100"
        )
        self.client.force_authenticate(self.staff)

        with patch("registers.tasks.orchestrate_full_company_sync"):
            response = self.client.post(f"/api/admin/companies/{other.pk}/refresh/")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("orsr", response.data["dispatched"])
        self.assertIn({"source": "orsr", "reason": "not_eligible"}, response.data["skipped"])

    def test_a_blocked_insurance_source_is_not_asked(self):
        # `update_insurance_debt` refuses to make the request for a blocked
        # source, so the plan must not claim it was asked.
        CompanySyncStatus.objects.create(
            company=self.company, source=CompanySyncStatus.SOURCE_VSZP, is_blocked=True
        )
        self.client.force_authenticate(self.staff)

        with patch("registers.tasks.orchestrate_full_company_sync"):
            response = self._post()

        self.assertNotIn("vszp", response.data["dispatched"])
        self.assertIn("social", response.data["dispatched"])
        self.assertIn({"source": "vszp", "reason": "blocked"}, response.data["skipped"])

    def test_a_blocked_orsr_row_is_asked_anyway_and_the_answer_says_so(self):
        # The asymmetry, pinned rather than tidied: the rotation honours
        # `is_blocked` through `sync_due_q`, but neither
        # `orchestrate_full_company_sync` nor `sync_company_orsr_data` reads the
        # flag -- so a manual refresh asks a blocked ORSR row. The endpoint does
        # not change that; it reports it, so the admin who blocked the source
        # learns that the button asked anyway instead of reading a list that
        # looks obedient.
        CompanySyncStatus.objects.create(
            company=self.company, source=CompanySyncStatus.SOURCE_ORSR, is_blocked=True
        )
        self.client.force_authenticate(self.staff)

        with patch("registers.tasks.orchestrate_full_company_sync"):
            response = self._post()

        self.assertIn("orsr", response.data["dispatched"])
        self.assertEqual(response.data["blocked_but_asked"], ["orsr"])

    def test_nothing_is_reported_as_asked_while_blocked_when_nothing_is(self):
        self.client.force_authenticate(self.staff)

        with patch("registers.tasks.orchestrate_full_company_sync"):
            response = self._post()

        self.assertEqual(response.data["blocked_but_asked"], [])

    # -- the second click ---------------------------------------------------

    def test_a_second_click_inside_the_window_does_not_dispatch_again(self):
        self.client.force_authenticate(self.staff)

        with patch("registers.tasks.orchestrate_full_company_sync") as task:
            first = self._post()
            second = self._post()

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)
        self.assertEqual(second.data["detail"], "already_running")
        task.apply_async.assert_called_once()

    def test_the_wait_it_states_is_the_wait_that_is_left(self):
        # Not the whole window: a pass that started 14 minutes ago has one
        # minute left, and a number that never moves teaches an admin to stop
        # reading it.
        self.client.force_authenticate(self.staff)

        with patch("registers.tasks.orchestrate_full_company_sync"):
            self._post()
            cache.set(
                f"company-refresh:{self.company.pk}",
                "2020-01-01T00:00:00+00:00",
                900,
            )
            later = self._post()

        self.assertEqual(later.status_code, 409)
        self.assertEqual(later.data["retry_after_seconds"], 1)

    def test_a_cache_that_cannot_be_reached_refuses_rather_than_fans_out(self):
        # Without the claim there is no de-duplication, and a silent fallback
        # would turn one click into as many passes as it was clicked. Redis is
        # also what the queue runs on, so this is not a state in which the
        # dispatch would have worked.
        self.client.force_authenticate(self.staff)

        with patch("registers.tasks.orchestrate_full_company_sync") as task, patch(
            "adminapi.views.sync.cache"
        ) as broken_cache:
            broken_cache.add.side_effect = OSError("redis is down")
            response = self._post()

        self.assertEqual(response.status_code, 503)
        task.apply_async.assert_not_called()

    def test_a_dispatch_that_failed_leaves_the_button_usable(self):
        # The claim exists to stop a second pass, and a pass that never started
        # is not one. Held, a broker outage would look like a company that had
        # just been refreshed.
        self.client.force_authenticate(self.staff)

        with patch("registers.tasks.orchestrate_full_company_sync") as task:
            task.apply_async.side_effect = OSError("broker is down")
            failed = self._post()

            self.assertEqual(failed.status_code, 502)

            task.apply_async.side_effect = None
            retried = self._post()

        self.assertEqual(retried.status_code, 200)

    # -- what it must not do ------------------------------------------------

    def test_it_creates_no_sync_job(self):
        # The orchestrated task never claims a `SyncJob`, so a row created here
        # would sit `queued` for ever and `make ops-check` would fail it as a
        # job whose worker never came.
        self.client.force_authenticate(self.staff)

        with patch("registers.tasks.orchestrate_full_company_sync"):
            self._post()

        self.assertEqual(SyncJob.objects.count(), 0)

    def test_a_company_that_does_not_exist_is_a_404(self):
        self.client.force_authenticate(self.staff)

        response = self.client.post("/api/admin/companies/99999999/refresh/")

        self.assertEqual(response.status_code, 404)
