"""A repair run is a tracked RUZ job, or it is not allowed to run.

Both repair commands walk the register for hours and write company rows. Until
now neither had a `SyncJob` at all: no heartbeat for the watchdog, no outcome
for `ops-check` and the admin's job list, and -- the part that matters for data
safety -- no claim on `ruz:global`, the one key that keeps two writers of
company data apart.

The tasks that dispatch them are covered in `tests_sync_job_singleton.py`.
What is pinned here is the command-side half: the heartbeat the claimed job
needs in order to survive the reaper, and the outcome written on every exit
path so a repair that finished cannot be read as one that did nothing.
"""

from datetime import timedelta
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from companies.models import Company
from registers.models import SyncGapAnalysis, SyncJob


class _InlineExecutor:
    """Runs the batch on the calling thread instead of a worker pool.

    Both commands fetch a page through `concurrent.futures.ThreadPoolExecutor`.
    A worker thread opens its own database connection and that connection
    outlives the test -- enough for `DROP DATABASE test_cistafirma` to fail at
    teardown with "being accessed by other users" and take the whole run down
    with it. Nothing here is about concurrency: the per-record work and the
    counters it feeds are identical either way, so the pool is replaced rather
    than tolerated.
    """

    def __init__(self, max_workers=None):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def map(self, func, iterable):
        return [func(item) for item in iterable]


_INLINE_CONCURRENCY = SimpleNamespace(
    futures=SimpleNamespace(ThreadPoolExecutor=_InlineExecutor)
)


class _FakeRuzApi:
    """Pages of ids and one canned detail record per id."""

    def __init__(self, pages, missing_ico_ids=()):
        self._pages = list(pages)
        # Ids whose record answers without an IČO, which the command files as
        # skipped rather than storing.
        self.missing_ico_ids = set(missing_ico_ids)
        self.detail_calls = []

    def get_changed_company_ids(self, zmenene_od=None, pokracovat_za_id=None, max_zaznamov=None):
        if not self._pages:
            return {"id": [], "existujeDalsieId": False}
        page = self._pages.pop(0)
        # An exception in the page list is how a transport failure arrives: the
        # command's client is strict and raises rather than answering empty.
        if isinstance(page, Exception):
            raise page
        return {"id": page, "existujeDalsieId": bool(self._pages)}

    def get_company_details(self, company_id):
        self.detail_calls.append(company_id)
        if company_id in self.missing_ico_ids:
            return {"id": company_id, "nazovUJ": f"Bez IČO {company_id}"}
        return {
            "ico": f"9{company_id:07d}",
            "id": company_id,
            "nazovUJ": f"Firma {company_id}",
            "pravnaForma": "112",
            "datumZalozenia": "2020-01-01",
        }


class RepairCommandJobTrackingTests(TestCase):
    """`repair_ruz_sync_v2` reports to the job it was handed -- and to nothing
    else when it was handed nothing."""

    def _job(self, **kwargs):
        # No `concurrency_key`: the partial unique index guarding the RUZ
        # singleton is owned by `tests_sync_job_singleton.py`, and these tests
        # are about what the command writes to a row it was given.
        defaults = {
            "job_type": "ruz_repair",
            "status": "running",
            "started_at": timezone.now(),
            "last_heartbeat": timezone.now(),
        }
        defaults.update(kwargs)
        return SyncJob.objects.create(**defaults)

    def _run(self, pages, missing_ico_ids=(), **options):
        api = _FakeRuzApi(pages, missing_ico_ids=missing_ico_ids)
        with patch(
            "registers.management.commands.repair_ruz_sync_v2.RuzApi",
            return_value=api,
        ), patch(
            "registers.management.commands.repair_ruz_sync_v2.concurrent",
            _INLINE_CONCURRENCY,
        ):
            call_command(
                "repair_ruz_sync_v2",
                stdout=StringIO(),
                stderr=StringIO(),
                **options,
            )
        return api

    def test_the_run_beats_the_heart_of_the_job_it_was_given(self):
        """The page loop can sit inside one request for minutes, and nothing
        else writes `last_heartbeat` -- so a command that does not beat its own
        job is reaped as dead while it is working."""
        stale = timezone.now() - timedelta(hours=3)
        job = self._job(started_at=stale, last_heartbeat=stale)

        self._run([[111, 222]], sync_job_id=job.pk)

        job.refresh_from_db()
        self.assertGreater(job.last_heartbeat, stale + timedelta(hours=2))

    def test_the_run_records_what_it_created(self):
        job = self._job()

        self._run([[111, 222, 333]], sync_job_id=job.pk)

        job.refresh_from_db()
        self.assertEqual(job.processed_items, 3)
        self.assertEqual(job.succeeded_items, 3)
        self.assertEqual(job.failed_items, 0)
        self.assertEqual(Company.objects.filter(ruz_id__in=[111, 222, 333]).count(), 3)

    def test_a_record_without_an_ico_is_counted_as_skipped(self):
        job = self._job()

        self._run([[111, 222]], missing_ico_ids={222}, sync_job_id=job.pk)

        job.refresh_from_db()
        self.assertEqual(job.processed_items, 2)
        self.assertEqual(job.succeeded_items, 1)
        self.assertEqual(job.skipped_items, 1)

    def test_the_counters_describe_this_run_not_the_repair_row_before_it(self):
        """`SyncProgress` reuses its row across runs, so a resumed repair
        inherits every counter the last one left. Reporting its totals as this
        run's outcome would credit it with work it did not do."""
        job = self._job()
        self._run([[111, 222]], sync_job_id=job.pk)

        second = self._job()
        self._run([[333]], sync_job_id=second.pk)

        second.refresh_from_db()
        self.assertEqual(second.processed_items, 1)
        self.assertEqual(second.succeeded_items, 1)

    def test_recording_the_outcome_never_writes_the_status(self):
        """`status` belongs to the lifecycle, and this run does not own the
        job -- it was handed an id. A second writer of `status` is how a run
        gets marked `completed` before anyone has decided it is."""
        job = self._job()

        self._run([[111]], sync_job_id=job.pk)

        job.refresh_from_db()
        self.assertEqual(job.status, "running")
        self.assertIsNone(job.completed_at)

    def test_a_run_that_dies_still_records_what_it_managed(self):
        """The `finally` exists so a truncated run is legible. Without it a
        crash leaves the counters at zero, which reads exactly like a run that
        did nothing."""
        job = self._job()
        api = _FakeRuzApi([[111], RuntimeError("connection reset")])

        with patch(
            "registers.management.commands.repair_ruz_sync_v2.RuzApi",
            return_value=api,
        ), patch(
            "registers.management.commands.repair_ruz_sync_v2.concurrent",
            _INLINE_CONCURRENCY,
        ):
            with self.assertRaises(RuntimeError):
                call_command(
                    "repair_ruz_sync_v2", sync_job_id=job.pk, stdout=StringIO()
                )

        job.refresh_from_db()
        self.assertEqual(job.processed_items, 1)
        self.assertEqual(job.succeeded_items, 1)

    def test_without_a_job_id_nothing_is_written_anywhere(self):
        """The negative control. These counters are only meaningful on a row
        the caller claimed, and a command run by hand has no such row -- so it
        must not invent one, and must not touch whichever row exists."""
        stale = timezone.now() - timedelta(hours=3)
        job = self._job(started_at=stale, last_heartbeat=stale)

        self._run([[111, 222]])

        job.refresh_from_db()
        self.assertEqual(job.processed_items, 0)
        self.assertEqual(job.succeeded_items, 0)
        # Not merely old -- untouched.
        self.assertEqual(job.last_heartbeat, stale)


class GapRepairCommandJobTrackingTests(TestCase):
    """`repair_ruz_gaps` counts per analysis, not per run, so its outcome has
    to be a difference rather than the total."""

    def _job(self, **kwargs):
        defaults = {
            "job_type": "ruz_repair",
            "status": "running",
            "started_at": timezone.now(),
            "last_heartbeat": timezone.now(),
        }
        defaults.update(kwargs)
        return SyncJob.objects.create(**defaults)

    def _analysis(self, gap_ranges, **kwargs):
        defaults = {
            "status": "ready",
            "analyzed_min_id": 111,
            "analyzed_max_id": 333,
            "total_missing": 3,
            "total_gaps": len(gap_ranges),
            "gap_ranges": gap_ranges,
        }
        defaults.update(kwargs)
        return SyncGapAnalysis.objects.create(**defaults)

    def _run(self, analysis, **kwargs):
        api = _FakeRuzApi([])
        with patch(
            "registers.management.commands.repair_ruz_gaps.RuzApi",
            return_value=api,
        ), patch(
            "registers.management.commands.repair_ruz_gaps.concurrent",
            _INLINE_CONCURRENCY,
        ):
            call_command(
                "repair_ruz_gaps",
                analysis_id=analysis.pk,
                stdout=StringIO(),
                stderr=StringIO(),
                **kwargs,
            )
        return api

    def test_the_run_beats_the_heart_of_the_job_it_was_given(self):
        stale = timezone.now() - timedelta(hours=3)
        job = self._job(started_at=stale, last_heartbeat=stale)
        analysis = self._analysis([[111, 111]])

        self._run(analysis, sync_job_id=job.pk)

        job.refresh_from_db()
        self.assertGreater(job.last_heartbeat, stale + timedelta(hours=2))

    def test_the_run_records_what_it_repaired(self):
        job = self._job()
        analysis = self._analysis([[111, 113]])

        self._run(analysis, sync_job_id=job.pk)

        job.refresh_from_db()
        self.assertEqual(job.processed_items, 3)
        self.assertEqual(job.succeeded_items, 3)
        self.assertEqual(Company.objects.filter(ruz_id__in=[111, 112, 113]).count(), 3)

    def test_a_resumed_repair_reports_only_what_it_added(self):
        """`analysis.repaired_count` accumulates -- a resume reopens the same
        row and its counters keep climbing from wherever the last pass left
        them. A run that reported the total would claim the whole repair every
        time it was resumed."""
        analysis = self._analysis([[111, 112]], repaired_count=40)
        job = self._job()

        self._run(analysis, sync_job_id=job.pk)

        analysis.refresh_from_db()
        job.refresh_from_db()
        # The analysis carries the whole repair; the job carries this pass.
        self.assertEqual(analysis.repaired_count, 42)
        self.assertEqual(job.processed_items, 2)
        self.assertEqual(job.succeeded_items, 2)

    def test_without_a_job_id_nothing_is_written_anywhere(self):
        stale = timezone.now() - timedelta(hours=3)
        job = self._job(started_at=stale, last_heartbeat=stale)
        analysis = self._analysis([[111, 111]])

        self._run(analysis)

        job.refresh_from_db()
        self.assertEqual(job.processed_items, 0)
        self.assertEqual(job.last_heartbeat, stale)

    def test_an_analysis_with_nothing_left_still_records_its_outcome(self):
        """The early return is before the `try`, so the `finally` has to run
        for it too -- otherwise the most ordinary outcome there is (a resume
        that finds no work) would leave the job reading as one that did
        nothing."""
        stale = timezone.now() - timedelta(hours=3)
        job = self._job(started_at=stale, last_heartbeat=stale)
        analysis = self._analysis([[111, 113]], repaired_count=3, repair_progress_id=113)

        self._run(analysis, sync_job_id=job.pk, resume=True)

        job.refresh_from_db()
        self.assertEqual(job.processed_items, 0)
        self.assertEqual(job.succeeded_items, 0)
        self.assertGreater(job.last_heartbeat, stale)


class RepairDispatchWiringTests(TestCase):
    """The admin API's own path to a repair: it must hand the job it created
    to the task, or the row it just wrote holds `ruz:global` for ever."""

    def test_the_admin_dispatch_hands_the_repair_job_its_own_id(self):
        from adminapi.views.sync import _dispatch_job
        from registers.models import SyncJob

        job = SyncJob.objects.create(
            job_type="ruz_repair",
            status="queued",
            queued_at=timezone.now(),
            parameters={"start_id": 2000000, "workers": 5},
        )

        with patch("registers.tasks.start_repair_sync.apply_async") as apply_async:
            apply_async.return_value = type("R", (), {"id": "abc"})()

            _dispatch_job(job)

        apply_async.assert_called_once_with(
            kwargs={"start_id": 2000000, "workers": 5, "sync_job_id": job.pk}
        )
