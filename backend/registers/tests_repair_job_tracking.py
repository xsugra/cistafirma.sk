"""A repair run is a tracked RUZ job, or it is not allowed to run.

Both repair commands walk the register for hours and write company rows. Until
#186 neither had a `SyncJob` at all: no heartbeat for the watchdog, no outcome
for `ops-check` and the admin's job list, and -- the part that matters for data
safety -- no claim on `ruz:global`, the one key that keeps two writers of
company data apart. #186 fixed the four *dispatched* entry points; the command
typed by hand was left out, and it was the one the operator was told to use.

The tasks that dispatch them are covered in `tests_sync_job_singleton.py`. What
is pinned here is the command-side half: the claim and the refusal when the slot
is taken, the heartbeat the claimed job needs in order to survive the reaper,
and the outcome written on every exit path so a repair that finished cannot be
read as one that did nothing.
"""

from datetime import timedelta
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from companies.models import Company
from registers.models import SyncGapAnalysis, SyncJob
from registers.services import sync_engine


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

    def test_a_hand_run_claims_its_own_row_and_leaves_others_alone(self):
        """This test used to assert the opposite, and the old name said so:
        `test_without_a_job_id_nothing_is_written_anywhere`. That was the defect
        written down as the contract -- a command run by hand claimed nothing,
        so it took no `ruz:global` slot and could write company rows beside the
        full walk. It claims a row of its own now; what it still must not do is
        touch a row it was not handed.
        """
        stale = timezone.now() - timedelta(hours=3)
        other = self._job(started_at=stale, last_heartbeat=stale)

        self._run([[111, 222]])

        other.refresh_from_db()
        self.assertEqual(other.processed_items, 0)
        self.assertEqual(other.succeeded_items, 0)
        # Not merely old -- untouched.
        self.assertEqual(other.last_heartbeat, stale)

        claimed = SyncJob.objects.get(concurrency_key="ruz:global")
        self.assertEqual(claimed.job_type, "ruz_repair")
        self.assertEqual(claimed.parameters["command"], "repair_ruz_sync_v2")
        self.assertEqual(claimed.status, "completed")
        self.assertEqual(claimed.processed_items, 2)


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

    def test_a_hand_run_claims_its_own_row_and_leaves_others_alone(self):
        """Same inversion as its twin in `RepairCommandJobTrackingTests`: the
        old assertion was that a hand-run command wrote nothing anywhere, which
        is exactly why it stopped taking `ruz:global`."""
        stale = timezone.now() - timedelta(hours=3)
        other = self._job(started_at=stale, last_heartbeat=stale)
        analysis = self._analysis([[111, 111]])

        self._run(analysis)

        other.refresh_from_db()
        self.assertEqual(other.processed_items, 0)
        self.assertEqual(other.last_heartbeat, stale)

        claimed = SyncJob.objects.get(concurrency_key="ruz:global")
        self.assertEqual(claimed.job_type, "ruz_repair")
        self.assertEqual(claimed.parameters["command"], "repair_ruz_gaps")
        self.assertEqual(claimed.status, "completed")
        self.assertEqual(claimed.processed_items, 1)

    def test_a_dispatched_run_with_nothing_left_writes_no_status(self):
        """A Celery-dispatched run whose work list is empty must write nothing.

        `owns_job_lifecycle` is what keeps this command from becoming a second
        writer of `status`: the row was claimed and handed down by
        `_run_ruz_command`, which marks it `completed` once the command
        returns. So the assertion with teeth is that the status is still
        `running` -- an unconditional `complete_job` here would fail it. The
        heartbeat is the one thing that has to move: it is written from the
        work-list build, before the empty list is known.

        (The previous version of this test claimed "the early return is before
        the `try`, so the `finally` has to run for it too" and asserted
        `processed_items == 0`. The `finally` never runs for that return, and
        both counters were already 0 on the row the fixture created -- so it
        could not fail for the mechanism it named.)"""
        stale = timezone.now() - timedelta(hours=3)
        job = self._job(started_at=stale, last_heartbeat=stale)
        analysis = self._analysis([[111, 113]], repaired_count=3, repair_progress_id=113)

        self._run(analysis, sync_job_id=job.pk, resume=True)

        job.refresh_from_db()
        self.assertEqual(job.status, "running")
        self.assertEqual(job.processed_items, 0)
        self.assertEqual(job.succeeded_items, 0)
        self.assertGreater(job.last_heartbeat, stale)
        analysis.refresh_from_db()
        self.assertEqual(analysis.status, "completed")


class _ExplodingExecutor(_InlineExecutor):
    """A pool that refuses to start.

    The gap repair catches failures per record inside `_fetch_and_save`, so
    nothing the API does can reach its `except Exception`. A pool that cannot
    start is a failure of the run itself rather than of one record -- and it is
    a real one, not a contrivance.
    """

    def map(self, func, iterable):
        raise RuntimeError("can't start new thread")


class _InterruptingApi(_FakeRuzApi):
    """Ctrl+C where it actually arrives: inside the run, on the first page."""

    def get_changed_company_ids(self, **kwargs):
        raise KeyboardInterrupt


class _InterruptingGapRanges(list):
    """A work list that raises Ctrl+C while it is being read.

    The gap repair builds its list from `analysis.gap_ranges` before it claims
    anything, and that loop runs once per missing RUZ id -- minutes on a real
    analysis. This is the interrupt that arrives in there, where nothing catches
    it: the command's own `except KeyboardInterrupt` is inside the `try` that
    this loop is not in.
    """

    def __iter__(self):
        yield (111, 112)
        raise KeyboardInterrupt


class _StubAnalysis(SimpleNamespace):
    """Just enough analysis to reach the build loop, with the writes forbidden.

    Nothing after the build may run in that test, so any write means the test
    measured the wrong path -- an assertion rather than a mock's silence.
    """

    def save(self, *args, **kwargs):
        raise AssertionError("the analysis must not be written for an interrupted build")


class ManualRunClaimsTheSlotTests(TestCase):
    """A command typed by an operator runs as a tracked RUZ job, or not at all.

    A hand-run command arrives with no `--sync-job-id`, so nothing upstream
    claims `ruz:global` for it -- not `_run_ruz_command` (no task), not
    `_dispatch_job` (no admin). Both repair commands could be started by hand
    and did exactly that: they wrote company rows beside the full walk, and
    doing it was the *recommended* recovery, because `repair_ruz_gaps`'s own
    Ctrl+C message ends with "Pokračujte: python manage.py repair_ruz_gaps
    --resume".

    The Celery half of both commands is pinned in `tests_sync_job_singleton.py`;
    what is pinned here is the command's own half, and the exits that only the
    hand-run path owns.
    """

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

    def _walk_holds_the_slot(self):
        """The thing the slot exists to keep apart: the full walk, running."""
        walk, _ = sync_engine.enqueue_ruz_job(job_type="ruz_full")
        sync_engine.claim_ruz_job(walk.pk)
        return walk

    def _run_v2(self, pages, concurrency=_INLINE_CONCURRENCY, **options):
        api = pages if isinstance(pages, _FakeRuzApi) else _FakeRuzApi(pages)
        with patch(
            "registers.management.commands.repair_ruz_sync_v2.RuzApi",
            return_value=api,
        ), patch(
            "registers.management.commands.repair_ruz_sync_v2.concurrent", concurrency
        ):
            call_command(
                "repair_ruz_sync_v2", stdout=StringIO(), stderr=StringIO(), **options
            )
        return api

    def _run_gaps(self, analysis, concurrency=_INLINE_CONCURRENCY, **options):
        api = _FakeRuzApi([])
        with patch(
            "registers.management.commands.repair_ruz_gaps.RuzApi",
            return_value=api,
        ), patch(
            "registers.management.commands.repair_ruz_gaps.concurrent", concurrency
        ):
            call_command(
                "repair_ruz_gaps",
                analysis_id=analysis.pk,
                stdout=StringIO(),
                stderr=StringIO(),
                **options,
            )
        return api

    def test_a_hand_run_refuses_while_the_walk_holds_the_slot(self):
        """The whole point, on both commands. A refused run must not have read a
        page or written a company row either -- a claim that happens after the
        first write would pass a status assertion and still corrupt the data."""
        analysis = self._analysis([[111, 112]])
        walk = self._walk_holds_the_slot()

        for label, run in (
            ("repair_ruz_sync_v2", lambda: self._run_v2([[111, 112]])),
            ("repair_ruz_gaps", lambda: self._run_gaps(analysis)),
        ):
            with self.subTest(command=label):
                with self.assertRaises(CommandError) as caught:
                    run()

                self.assertIn("already active", str(caught.exception))
                self.assertEqual(Company.objects.filter(ruz_id__in=[111, 112]).count(), 0)
                walk.refresh_from_db()
                self.assertEqual(walk.status, "running")
                # No repair row was invented beside it.
                self.assertEqual(
                    SyncJob.objects.filter(job_type="ruz_repair").count(), 0
                )

    def test_a_run_given_a_job_id_that_names_no_row_refuses(self):
        """`--sync-job-id` says which row this run reports against, and the
        guard reading it has to test for `None` rather than truthiness.

        `--sync-job-id 0` is falsy, so the claim was skipped for it too: the
        command imported company rows beside a live walk with no heartbeat and
        an outcome write that matched no row -- the very defect the no-flag
        path was fixed for, reachable by a typo or a stale id. `fetch_ruz_data`
        refuses every id that names no row; these two now do the same."""
        analysis = self._analysis([[111, 112]])
        walk = self._walk_holds_the_slot()

        for bad_id in (0, 999999):
            for label, run in (
                (
                    "repair_ruz_sync_v2",
                    lambda: self._run_v2([[111, 112]], sync_job_id=bad_id),
                ),
                (
                    "repair_ruz_gaps",
                    lambda: self._run_gaps(analysis, sync_job_id=bad_id),
                ),
            ):
                with self.subTest(sync_job_id=bad_id, command=label):
                    with self.assertRaises(CommandError) as caught:
                        run()

                    self.assertIn("does not exist", str(caught.exception))
                    self.assertEqual(
                        Company.objects.filter(ruz_id__in=[111, 112]).count(), 0
                    )
                    walk.refresh_from_db()
                    self.assertEqual(walk.status, "running")

    def test_a_hand_run_claims_and_closes_its_own_row(self):
        self._run_v2([[111, 222]])

        job = SyncJob.objects.get(concurrency_key="ruz:global")
        self.assertEqual(job.job_type, "ruz_repair")
        self.assertEqual(job.triggered_via, "cli")
        self.assertEqual(job.parameters["command"], "repair_ruz_sync_v2")
        self.assertEqual(job.status, "completed")
        self.assertIsNotNone(job.completed_at)
        self.assertEqual(job.processed_items, 2)

    def test_a_hand_gap_repair_that_finds_nothing_claims_nothing(self):
        """The claim sits below the work-list build and below this return, so a
        run with no work claims no row at all.

        A claimed row holds `ruz:global` for as long as it is `queued` or
        `running`, so claiming above this return would mean a run that did
        nothing claims a job for having did nothing -- and it would have held the
        slot across the build loop and across this return, where nothing closes
        it.
        """
        analysis = self._analysis([[111, 113]], repaired_count=3, repair_progress_id=113)

        self._run_gaps(analysis, resume=True)

        self.assertFalse(
            SyncJob.objects.filter(concurrency_key="ruz:global").exists()
        )
        analysis.refresh_from_db()
        self.assertEqual(analysis.status, "completed")

    def test_an_interrupt_in_the_work_list_leaves_no_job_row(self):
        """The build loop runs once per missing RUZ id -- minutes on a real
        analysis -- and `except KeyboardInterrupt` is inside the `try`, so an
        interrupt in there is caught by nothing and escapes `handle`.

        Nothing has been claimed at that point, so there is nothing to leak. A
        claim made above the loop would hold `ruz:global` for up to the
        watchdog's 30 minutes on a plain Ctrl+C, with no database failure needed.
        This is the property the claim's position exists to keep, so it is pinned
        rather than argued: against a version that claims first, this test fails
        on the row it finds.
        """
        stub = _StubAnalysis(
            pk=1,
            id=1,
            status="ready",
            analyzed_min_id=111,
            analyzed_max_id=333,
            total_missing=2,
            total_gaps=1,
            gap_ranges=_InterruptingGapRanges(),
            repair_progress_id=None,
            repaired_count=0,
            skipped_count=0,
            error_count=0,
        )

        with patch(
            "registers.management.commands.repair_ruz_gaps.SyncGapAnalysis",
            SimpleNamespace(
                objects=SimpleNamespace(
                    filter=lambda **kwargs: SimpleNamespace(first=lambda: stub)
                )
            ),
        ):
            with self.assertRaises(KeyboardInterrupt):
                self._run_gaps(stub)

        self.assertFalse(
            SyncJob.objects.filter(concurrency_key="ruz:global").exists()
        )

    def test_an_interrupted_hand_run_pauses_its_job_and_frees_the_slot(self):
        """Ctrl+C is the run an operator resumes, and the command catches it, so
        it returns normally -- nothing else would mark the job. `paused`, not
        `completed`: the row must say the repair stopped where it stopped.
        Deliberately no `assertRaises` here: catching the interrupt is what makes
        the Ctrl+C message's "--resume" advice a real next step.
        """
        self._run_v2(_InterruptingApi([]))

        job = SyncJob.objects.get(concurrency_key="ruz:global")
        self.assertEqual(job.status, "paused")
        self.assertIn("Ctrl+C", job.notes)

        # The slot is free again: only `queued` and `running` hold it, and a
        # paused row that kept it would block every later RUZ run for good.
        walk, created = sync_engine.enqueue_ruz_job(job_type="ruz_full")
        self.assertTrue(created)

    def test_a_failed_hand_run_fails_its_job_and_frees_the_slot(self):
        with self.assertRaises(RuntimeError):
            self._run_v2([[111], RuntimeError("connection reset")])

        job = SyncJob.objects.get(concurrency_key="ruz:global")
        self.assertEqual(job.status, "failed")
        self.assertIn("connection reset", job.last_error)
        self.assertEqual(Company.objects.filter(ruz_id=111).count(), 1)

    def test_a_failed_hand_gap_repair_fails_its_job(self):
        analysis = self._analysis([[111, 113]])

        with self.assertRaises(RuntimeError):
            self._run_gaps(analysis, concurrency=SimpleNamespace(
                futures=SimpleNamespace(ThreadPoolExecutor=_ExplodingExecutor)
            ))

        job = SyncJob.objects.get(concurrency_key="ruz:global")
        self.assertEqual(job.status, "failed")
        self.assertIn("can't start new thread", job.last_error)
        self.assertEqual(Company.objects.count(), 0)

    def test_a_dispatched_run_claims_nothing_of_its_own(self):
        """The negative control for the claim. A Celery dispatcher already holds
        a row and hands its id down; a command that claimed a second one would
        deadlock against the first, and a command that closed it would mark a
        job completed before the task it belongs to had decided."""
        job = SyncJob.objects.create(
            job_type="ruz_repair",
            status="running",
            started_at=timezone.now(),
            last_heartbeat=timezone.now(),
        )

        self._run_v2([[111]], sync_job_id=job.pk)

        job.refresh_from_db()
        self.assertEqual(job.status, "running")
        self.assertIsNone(job.completed_at)
        self.assertEqual(job.processed_items, 1)
        self.assertFalse(SyncJob.objects.filter(concurrency_key="ruz:global").exists())


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
