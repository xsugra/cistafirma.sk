from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from companies.models import Company
from registers.models import CompanySyncStatus

DEBT_FIELDS = {"vszp": "debt_vszp", "social": "debt_soc_poist"}


class SourceHealthCommandTests(TestCase):
    """The control that would have caught the VSZP parser going silent.

    Queue depth cannot see this: the insurance queue kept draining at its
    configured rate the whole time the scraper returned nothing usable.
    """

    def _seed(self, source, attempts, successes, *, succeeded_ago_hours=1, with_debt=0):
        """Seed `attempts` rows, of which `successes` succeeded and `with_debt` report a debt.

        `with_debt` applies to the successful rows, which are the first ones --
        a check that reported a debt is exactly a success whose stored amount
        is non-zero.
        """
        now = timezone.now()
        attempted_at = now - timedelta(hours=1)
        succeeded_at = now - timedelta(hours=succeeded_ago_hours)
        debt_field = DEBT_FIELDS[source]

        companies = Company.objects.bulk_create([
            Company(
                ruz_id=800000 + i,
                ico=f"{90000000 + i}",
                nazov_UJ=f"Test {source} {i}",
                pravna_forma="112",
                **{debt_field: Decimal("100.00") if i < with_debt else Decimal("0.00")},
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

    def test_a_source_that_never_reports_no_record_is_unmet(self):
        """The shape the SP scraper was found in.

        Debtors are still found, so the source is plainly alive and a zero
        success count would never fire -- but every company that owes nothing
        comes back `unknown`, is never marked checked, and stays due forever.
        """
        self._seed("social", attempts=250, successes=60, with_debt=60)

        output, code = self._run()

        self.assertEqual(code, 1)
        self.assertIn("Source health: 1 unmet", output)
        self.assertIn("stays due forever", output)

    def test_a_source_that_never_reports_a_debt_is_unmet(self):
        """The dangerous direction: every real debtor written as debt-free."""
        self._seed("vszp", attempts=250, successes=60, with_debt=0)

        output, code = self._run()

        self.assertEqual(code, 1)
        self.assertIn("Source health: 1 unmet", output)
        self.assertIn("recorded as debt-free", output)

    def test_a_source_reporting_both_outcomes_is_healthy(self):
        self._seed("social", attempts=250, successes=60, with_debt=12)

        output, code = self._run()

        self.assertEqual(code, 0)
        self.assertIn("Source health: 0 unmet", output)
        self.assertIn("12", output)

    def test_the_split_is_not_judged_on_too_few_successes(self):
        """Eight successes with no no-record answer is luck, not a dead branch."""
        self._seed("social", attempts=250, successes=8, with_debt=8)

        output, code = self._run()

        self.assertEqual(code, 0)
        self.assertIn("Source health: 0 unmet", output)
