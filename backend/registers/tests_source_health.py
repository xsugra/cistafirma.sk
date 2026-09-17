from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from companies.models import Company
from registers.models import CompanySyncStatus, SyncFocusModeState

DEBT_FIELDS = {"vszp": "debt_vszp", "social": "debt_soc_poist"}

# Every value the model declares, in declaration order -- which is the order the
# command prints them in, because it now builds its table from the vocabulary
# rather than from the rows that happen to exist.
SOURCES = ("ruz", "orsr", "financials", "vszp", "social", "fs")

# A distinct block of `ruz_id`/`ico` per source, so one test can seed several
# without colliding.
_BLOCK = {source: index for index, source in enumerate(SOURCES)}

# The sources whose task draws from a due-list that cannot be empty. The command
# fails any of these that attempts nothing, so a test seeding only the source it
# is about would fail on the *others'* silence instead -- these get a healthy
# baseline. `ruz` is deliberately absent: it is allowed to be quiet, and `fs`
# records no attempts at all.
ALWAYS_EXPECTED = ("orsr", "financials", "vszp", "social")


def _seed_source(source, attempts, successes, *, succeeded_ago_hours=1, with_debt=0):
    """Seed `attempts` rows, of which `successes` succeeded and `with_debt` report a debt.

    `with_debt` applies to the successful rows, which are the first ones -- a
    check that reported a debt is exactly a success whose stored amount is
    non-zero.
    """
    now = timezone.now()
    attempted_at = now - timedelta(hours=1)
    succeeded_at = now - timedelta(hours=succeeded_ago_hours)
    debt_field = DEBT_FIELDS.get(source)
    block = _BLOCK[source] * 10000

    companies = Company.objects.bulk_create([
        Company(
            ruz_id=800000 + block + i,
            ico=f"{90000000 + block + i}",
            nazov_UJ=f"Test {source} {i}",
            pravna_forma="112",
            **(
                {debt_field: Decimal("100.00") if i < with_debt else Decimal("0.00")}
                if debt_field
                else {}
            ),
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


def _seed_baseline(*sources):
    """Healthy rows for the given expected sources, so only the test's own source is judged.

    `with_debt=25` of 250 successes is what makes this *healthy* for the two
    insurance sources: both the found branch and the no-record branch are
    present, which is the split they are judged on. The other two are judged on
    having any success at all.
    """
    for source in sources:
        _seed_source(source, attempts=250, successes=250, with_debt=25)


def _seed(source, attempts, successes, *, succeeded_ago_hours=1, with_debt=0):
    """The source under test, plus a healthy baseline for the other expected ones."""
    companies = _seed_source(
        source,
        attempts,
        successes,
        succeeded_ago_hours=succeeded_ago_hours,
        with_debt=with_debt,
    )
    _seed_baseline(*(s for s in ALWAYS_EXPECTED if s != source))
    return companies


def _run_command(**options):
    out = StringIO()
    try:
        call_command("source_health", stdout=out, **options)
    except SystemExit as exc:
        return out.getvalue(), exc.code
    return out.getvalue(), 0


class SourceHealthCommandTests(TestCase):
    """The control that would have caught the VSZP parser going silent.

    Queue depth cannot see this: the insurance queue kept draining at its
    configured rate the whole time the scraper returned nothing usable.
    """

    def test_source_with_no_successes_is_unmet(self):
        _seed("vszp", attempts=250, successes=0)

        output, code = _run_command()

        self.assertEqual(code, 1)
        self.assertIn("Source health: 1 unmet", output)
        self.assertIn("FAIL", output)

    def test_a_low_but_nonzero_success_rate_is_healthy(self):
        """Only a few percent of companies owe the SP anything -- that is fine."""
        _seed("social", attempts=250, successes=8)

        output, code = _run_command()

        self.assertEqual(code, 0)
        self.assertIn("Source health: 0 unmet", output)

    def test_source_below_the_attempt_threshold_is_not_judged(self):
        _seed("vszp", attempts=10, successes=0)

        output, code = _run_command()

        self.assertEqual(code, 0)
        self.assertIn("Source health: 0 unmet", output)
        self.assertIn("not judged", output)

    def test_a_success_older_than_the_window_does_not_count(self):
        """Attempts inside the window with no success inside it is the signal."""
        _seed("vszp", attempts=250, successes=250, succeeded_ago_hours=48)

        output, code = _run_command(window_hours=24)

        self.assertEqual(code, 1)
        self.assertIn("Source health: 1 unmet", output)

    def test_a_source_that_never_reports_no_record_is_unmet(self):
        """The shape the SP scraper was found in.

        Debtors are still found, so the source is plainly alive and a zero
        success count would never fire -- but every company that owes nothing
        comes back `unknown`, is never marked checked, and stays due forever.
        """
        _seed("social", attempts=250, successes=60, with_debt=60)

        output, code = _run_command()

        self.assertEqual(code, 1)
        self.assertIn("Source health: 1 unmet", output)
        self.assertIn("stays due forever", output)

    def test_a_source_that_never_reports_a_debt_is_unmet(self):
        """The dangerous direction: every real debtor written as debt-free."""
        _seed("vszp", attempts=250, successes=60, with_debt=0)

        output, code = _run_command()

        self.assertEqual(code, 1)
        self.assertIn("Source health: 1 unmet", output)
        self.assertIn("recorded as debt-free", output)

    def test_a_source_reporting_both_outcomes_is_healthy(self):
        _seed("social", attempts=250, successes=60, with_debt=12)

        output, code = _run_command()

        self.assertEqual(code, 0)
        self.assertIn("Source health: 0 unmet", output)
        self.assertIn("12", output)

    def test_the_split_is_not_judged_on_too_few_successes(self):
        """Eight successes with no no-record answer is luck, not a dead branch."""
        _seed("social", attempts=250, successes=8, with_debt=8)

        output, code = _run_command()

        self.assertEqual(code, 0)
        self.assertIn("Source health: 0 unmet", output)


class SourceHealthVocabularyTests(TestCase):
    """The omission that hid two sources from the gate entirely.

    The table used to be built from `CompanySyncStatus.objects.values("source")`,
    so a source with no rows produced no line -- and a missing line reads as a
    source that was checked and found fine. Measured on the live stack
    2026-09-11, `make ops-check` listed `financials`, `social` and `vszp` and
    said nothing at all about `ruz` or `orsr`, one of which had no writer and
    the other of which had never produced a row.
    """

    def test_every_declared_source_is_named_even_when_none_has_a_row(self):
        """The whole point: silence about a source must be impossible.

        With an empty `CompanySyncStatus` there is nothing at all to group, and
        the old command printed no table whatsoever.
        """
        output, code = _run_command()

        for source in SOURCES:
            self.assertIn(f"\n  {source} ", output, f"{source} is missing from the table")
        self.assertEqual(code, 1)

    def test_a_source_expected_to_attempt_and_silent_is_unmet_and_named(self):
        _seed_baseline("orsr", "financials", "vszp")

        output, code = _run_command()

        self.assertEqual(code, 1)
        self.assertIn("Source health: 1 unmet", output)
        self.assertIn("source 'social': no attempt at all", output)

    def test_ruz_silence_is_a_reading_not_a_failure(self):
        """`ruz` writes a row per company the registry reported as *changed*.

        A window in which nothing changed produces zero rows on a run that
        worked, so failing it would be a false alarm -- but it still has to say
        so, which is what distinguishes this from the omission above.
        """
        _seed_baseline(*ALWAYS_EXPECTED)

        output, code = _run_command()

        self.assertEqual(code, 0)
        self.assertIn("Source health: 0 unmet", output)
        self.assertIn("source 'ruz': no attempt in the last 24h, which is expected", output)

    def test_a_source_that_records_no_attempts_is_named_and_not_judged(self):
        """`fs` is a bulk file ingest: it has no per-company attempt to report.

        It must not read as healthy either. "not measured" is the only verdict
        this command can honestly reach about it.
        """
        _seed_baseline(*ALWAYS_EXPECTED)

        output, code = _run_command()

        self.assertEqual(code, 0)
        self.assertIn("\n  fs ", output)
        self.assertIn("not measured", output)
        self.assertIn("nothing here measures its freshness", output)

    def test_focus_mode_makes_a_pausable_source_silence_expected(self):
        """Entering Focus Mode switches off `vszp`/`social` scheduling.

        Without this the gate would go red every time an operator used a
        documented feature, and a gate that cries wolf is one that gets ignored.
        """
        SyncFocusModeState.objects.update_or_create(pk=1, defaults={"active": True})
        _seed_baseline("orsr", "financials")

        output, code = _run_command()

        self.assertEqual(code, 0)
        self.assertIn("Source health: 0 unmet", output)
        self.assertIn("source 'vszp': no attempt in the last 24h, which is expected", output)
        self.assertIn("Focus Mode is active", output)

    def test_focus_mode_does_not_excuse_a_source_it_keeps_running(self):
        """`orsr` and `financials` are in `FOCUS_KEEP_TASKS`, so silence there is still a finding."""
        SyncFocusModeState.objects.update_or_create(pk=1, defaults={"active": True})
        _seed_baseline("vszp", "social", "financials")

        output, code = _run_command()

        self.assertEqual(code, 1)
        self.assertIn("source 'orsr': no attempt at all", output)
        self.assertNotIn("source 'orsr': no attempt in the last 24h, which is expected", output)
