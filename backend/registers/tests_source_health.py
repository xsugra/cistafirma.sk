from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from companies.models import Company
from registers.models import CompanySyncStatus


class SourceHealthCommandTests(TestCase):
    """The control that would have caught the VSZP parser going silent.

    Queue depth cannot see this: the insurance queue kept draining at its
    configured rate the whole time the scraper returned nothing usable.
    """

    def _seed(self, source, attempts, successes, *, succeeded_ago_hours=1):
        now = timezone.now()
        attempted_at = now - timedelta(hours=1)
        succeeded_at = now - timedelta(hours=succeeded_ago_hours)

        companies = Company.objects.bulk_create([
            Company(
                ruz_id=800000 + i,
                ico=f"{90000000 + i}",
                nazov_UJ=f"Test {source} {i}",
                pravna_forma="112",
            )
            for i in range(attempts)
        ])
        CompanySyncStatus.objects.bulk_create([
            CompanySyncStatus(
                company=company,
                source=source,
                last_attempted_at=attempted_at,
                last_succeeded_at=succeeded_at if i < successes else None,
                last_error_type="" if i < successes else "parse_error",
            )
            for i, company in enumerate(companies)
        ])
        return companies

    def _run(self, **options):
        out = StringIO()
        try:
            call_command("source_health", stdout=out, **options)
        except SystemExit as exc:
            return out.getvalue(), exc.code
        return out.getvalue(), 0

    def test_source_with_no_successes_is_unmet(self):
        self._seed("vszp", attempts=250, successes=0)

        output, code = self._run()

        self.assertEqual(code, 1)
        self.assertIn("Source health: 1 unmet", output)
        self.assertIn("FAIL", output)

    def test_a_low_but_nonzero_success_rate_is_healthy(self):
        """Only a few percent of companies owe the SP anything -- that is fine."""
        self._seed("social", attempts=250, successes=8)

        output, code = self._run()

        self.assertEqual(code, 0)
        self.assertIn("Source health: 0 unmet", output)

    def test_source_below_the_attempt_threshold_is_not_judged(self):
        self._seed("vszp", attempts=10, successes=0)

        output, code = self._run()

        self.assertEqual(code, 0)
        self.assertIn("Source health: 0 unmet", output)
        self.assertIn("not judged", output)

    def test_a_success_older_than_the_window_does_not_count(self):
        """Attempts inside the window with no success inside it is the signal."""
        self._seed("vszp", attempts=250, successes=250, succeeded_ago_hours=48)

        output, code = self._run(window_hours=24)

        self.assertEqual(code, 1)
        self.assertIn("Source health: 1 unmet", output)
