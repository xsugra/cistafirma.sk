"""The gate that finally reads `registers_syncjob`.

Queue depth reports load and `source_health` reports what the sources achieve;
neither looked at sync jobs at all, so job #3 was counted as an active import
by the dashboard for fifteen days while `make ops-check` reported OK.
"""

from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from registers.models import SyncFocusModeState, SyncJob, SyncProgress
from registers.services import sync_engine


class SyncHealthCommandTests(TestCase):
    def _job(self, **kwargs):
        defaults = {
            "job_type": "ruz_incremental",
            "status": "running",
            "started_at": timezone.now(),
        }
        defaults.update(kwargs)
        return SyncJob.objects.create(**defaults)

    def _queued_since(self, age):
        """A job whose `queued_at` is `age` old.

        `queued_at` is `auto_now_add`, so it can only be moved after the row
        exists.
        """
        job = self._job(status="queued", started_at=None, queued_at=None)
        SyncJob.objects.filter(pk=job.pk).update(queued_at=timezone.now() - age)
        job.refresh_from_db()
        return job

    def _run(self, **options):
        out = StringIO()
        try:
            call_command("sync_health", stdout=out, **options)
        except SystemExit as exc:
            return out.getvalue(), exc.code
        return out.getvalue(), 0

    def test_a_stuck_running_job_is_unmet(self):
        self._job(last_heartbeat=timezone.now() - timedelta(days=15))

        output, code = self._run()

        self.assertEqual(code, 1)
        self.assertIn("Sync jobs: 1 unmet", output)
        self.assertIn("FAIL", output)
        self.assertIn("the worker is gone", output)

    def test_a_healthy_running_job_is_fine(self):
        self._job(last_heartbeat=timezone.now())

        output, code = self._run()

        self.assertEqual(code, 0)
        self.assertIn("Sync jobs: 0 unmet", output)

    def test_a_job_queued_past_the_threshold_is_unmet(self):
        """Accepted, then silently dropped -- nothing is picking it up."""
        self._queued_since(timedelta(hours=20))

        output, code = self._run(queued_minutes=720)

        self.assertEqual(code, 1)
        self.assertIn("Sync jobs: 1 unmet", output)
        self.assertIn("never claimed", output)

    def test_a_job_queued_briefly_is_not_judged(self):
        self._queued_since(timedelta(minutes=5))

        output, code = self._run(queued_minutes=720)

        self.assertEqual(code, 0)
        self.assertIn("Sync jobs: 0 unmet", output)

    def test_the_queued_threshold_is_configurable(self):
        self._queued_since(timedelta(minutes=30))

        _, strict = self._run(queued_minutes=10)
        _, relaxed = self._run(queued_minutes=600)

        self.assertEqual(strict, 1)
        self.assertEqual(relaxed, 0)

    def test_the_queued_threshold_can_come_from_the_environment(self):
        """The container's environment is where ops sets it, not the CLI."""
        self._queued_since(timedelta(minutes=30))

        with patch.dict("os.environ", {"CISTAFIRMA_QUEUED_JOB_MINUTES": "10"}):
            output, code = self._run()

        self.assertEqual(code, 1)
        self.assertIn("Sync jobs: 1 unmet", output)

    def test_a_completed_job_with_no_counters_is_reported_but_not_judged(self):
        """Job #8's shape: `completed` with zero processed items.

        How many items a job *should* process depends on the run, not on its
        type, so there is no honest threshold -- but the zero is still shown,
        because a job that reports nothing cannot be told from one that did
        nothing.
        """
        self._job(
            status="completed",
            last_heartbeat=timezone.now(),
            completed_at=timezone.now(),
            processed_items=0,
        )

        output, code = self._run()

        self.assertEqual(code, 0)
        self.assertIn("Sync jobs: 0 unmet", output)
        self.assertIn("not judged", output)
        self.assertIn("completed", output)

    def test_a_cancelled_job_is_listed_but_not_judged(self):
        """Cancelling is a decision somebody made, not a control that failed.

        Judging it would make the gate red for the operator's own deliberate
        action -- and for a RUZ job it cannot even happen, since the admin API
        refuses both cancel and resume for them.
        """
        self._job(
            status="cancelled",
            started_at=timezone.now() - timedelta(days=40),
            last_heartbeat=timezone.now() - timedelta(days=40),
        )

        output, code = self._run()

        self.assertEqual(code, 0)
        self.assertIn("Sync jobs: 0 unmet", output)
        self.assertIn("cancelled", output)

    def test_the_gate_agrees_with_the_reaper(self):
        """The property that makes the gate worth reading.

        `sync_health` must not re-derive what "stuck" means: a job it reports
        as healthy while the watchdog is about to fail it would be worse than
        no gate at all.
        """
        stuck = self._job(last_heartbeat=timezone.now() - timedelta(hours=2))
        healthy = self._job(last_heartbeat=timezone.now())

        self.assertTrue(sync_engine.is_stuck(stuck))
        self.assertFalse(sync_engine.is_stuck(healthy))

        output, code = self._run()

        self.assertEqual(code, 1)
        self.assertIn("Sync jobs: 1 unmet", output)
        self.assertIn(f"job #{stuck.pk}", output)
        self.assertNotIn(f"job #{healthy.pk} (", output)

    def test_the_reaper_clears_the_gates_only_complaint(self):
        """End to end: what the reaper failed, the gate stops reporting."""
        self._job(last_heartbeat=timezone.now() - timedelta(days=15))

        before, _ = self._run()
        self.assertIn("Sync jobs: 1 unmet", before)

        self.assertEqual(sync_engine.detect_and_fail_stuck_jobs(), 1)

        after, code = self._run()
        self.assertEqual(code, 0)
        self.assertIn("Sync jobs: 0 unmet", after)


class FailedBeatJobTests(TestCase):
    """The run nobody is watching.

    A beat-scheduled import that dies has no operator in front of it: the row
    says `failed`, the table prints it, and until 2026-09-10 the gate's verdict
    still read `Sync jobs: 0 unmet` -- so a schedule that had stopped
    delivering data looked exactly like one that was working. Job #11 (18:22,
    an `ImportError` after a deploy) and job #3 (reaped by the watchdog) were
    both on screen while the gate said zero.
    """

    def _beat_job(self, *, status, age, queued_age=None, job_type="ruz_incremental",
                  **kwargs):
        job = SyncJob.objects.create(
            job_type=job_type,
            status=status,
            triggered_via="beat_schedule",
            started_at=timezone.now() - age,
            last_heartbeat=timezone.now() - age,
            completed_at=timezone.now() - age,
            **kwargs,
        )
        SyncJob.objects.filter(pk=job.pk).update(
            queued_at=timezone.now() - (queued_age if queued_age is not None else age)
        )
        job.refresh_from_db()
        return job

    def _run(self, **options):
        out = StringIO()
        try:
            call_command("sync_health", stdout=out, **options)
        except SystemExit as exc:
            return out.getvalue(), exc.code
        return out.getvalue(), 0

    def test_a_failed_beat_run_is_unmet(self):
        self._beat_job(
            status="failed", age=timedelta(hours=1), last_error="ImportError: boom"
        )

        output, code = self._run()

        self.assertEqual(code, 1)
        self.assertIn("Sync jobs: 1 unmet", output)
        self.assertIn("the newest beat-scheduled run", output)
        self.assertIn("ImportError: boom", output)

    def test_a_manual_run_that_failed_is_not_the_schedules_problem(self):
        """The distinction the whole rule rests on.

        Someone starting a sync by hand is watching it; a run that dies at
        00:22 is not. Judging both would put the gate red on an operator's own
        failed experiment.
        """
        SyncJob.objects.create(
            job_type="ruz_incremental",
            status="failed",
            triggered_via="admin_ui",
            started_at=timezone.now(),
            completed_at=timezone.now(),
            last_error="operator cancelled the wrong thing",
        )

        output, code = self._run()

        self.assertEqual(code, 0)
        self.assertIn("Sync jobs: 0 unmet", output)

    def test_a_later_successful_run_clears_it(self):
        """A failure the next run supersedes is history, not state.

        Otherwise the gate would stay red for a transient failure that fixed
        itself -- the alarm that stops being read.
        """
        self._beat_job(
            status="failed", age=timedelta(hours=2), last_error="ReadTimeoutError"
        )
        self._beat_job(status="completed", age=timedelta(minutes=30))

        output, code = self._run()

        self.assertEqual(code, 0)
        self.assertIn("Sync jobs: 0 unmet", output)

    def test_a_failure_the_window_has_passed_is_not_judged(self):
        """It bounds the complaint as well as opening it.

        Past the window the job is history. A control that cannot clear is one
        nobody reads, and the failure this catches -- a schedule that has
        stopped -- will produce a fresh failed row long before the window runs
        out.
        """
        self._beat_job(status="failed", age=timedelta(days=3))

        output, code = self._run(failed_job_hours=24)

        self.assertEqual(code, 0)
        self.assertIn("Sync jobs: 0 unmet", output)

    def test_the_failed_window_is_configurable_and_can_come_from_the_env(self):
        self._beat_job(status="failed", age=timedelta(days=3))

        _, strict = self._run(failed_job_hours=24 * 7)
        self.assertEqual(strict, 1)

        with patch.dict("os.environ", {"CISTAFIRMA_FAILED_JOB_HOURS": "168"}):
            output, code = self._run()
        self.assertEqual(code, 1)
        self.assertIn("Sync jobs: 1 unmet", output)

    def test_an_empty_window_says_so_instead_of_going_quiet(self):
        """Absence of evidence, labelled as such.

        A schedule that has stopped dispatching leaves no failed row to judge,
        so this control cannot see it -- and saying that out loud is what keeps
        `0 unmet` from being read as "the schedule is fine".
        """
        output, code = self._run()

        self.assertEqual(code, 0)
        self.assertIn("beat-scheduled job types", output)
        self.assertIn("none recorded in the window", output)

    def test_a_long_run_that_ended_failed_is_judged_though_its_queue_time_is_old(self):
        """The window runs from when an attempt *ended*, not when it was queued.

        The walk this stack now runs takes five days. Anchored on `queued_at`,
        it left the window on its first day, so on the day it finally failed
        this gate would already have stopped looking -- the one run it most
        needs to see, invisible exactly when it matters.
        """
        self._beat_job(
            status="failed",
            age=timedelta(hours=1),
            queued_age=timedelta(days=5),
            job_type="ruz_full",
            last_error="ReadTimeoutError: registeruz.sk",
        )

        output, code = self._run(failed_job_hours=24)

        self.assertEqual(code, 1)
        self.assertIn("Sync jobs: 1 unmet", output)
        self.assertIn("the newest beat-scheduled run", output)

    def test_a_five_day_run_still_in_flight_is_seen_and_is_not_a_failure(self):
        """The other half of the same anchor.

        Judging only *ended* runs would drop the walk out of the gate entirely:
        the newest attempt of `ruz_full` would become whichever short run was
        queued last, and the long one would be absent rather than merely fine.
        A run in progress is not a failure, and this says so by judging it OK.
        """
        job = self._beat_job(
            status="running",
            age=timedelta(seconds=5),
            queued_age=timedelta(days=5),
            job_type="ruz_full",
        )

        output, code = self._run()

        self.assertEqual(code, 0)
        self.assertIn(f"ruz_full", output)
        self.assertIn(f"job #{job.pk}", output)
        self.assertIn("running", output)

    def test_an_abandoned_long_run_is_still_the_reapers_complaint(self):
        """The risk the `completed_at IS NULL` branch introduces, pinned.

        A five-day-old `running` row with a frozen heartbeat is now always in
        the beat section, where its status judges OK -- so if that were the only
        control looking at it, reaping would have been traded away for the
        window fix. The heartbeat condition is a separate one and still fails
        it; this test is what keeps that from silently becoming untrue.
        """
        job = self._beat_job(
            status="running",
            age=timedelta(days=5),
            job_type="ruz_full",
        )

        output, code = self._run()

        self.assertEqual(code, 1)
        self.assertIn("Sync jobs: 1 unmet", output)
        self.assertIn(f"#{job.pk}", output)
        self.assertIn("heartbeat", output)


class SyncWindowTests(TestCase):
    """The fourth condition: a window that stopped moving.

    The three conditions above cannot see this one, and that is the whole
    point. From 2026-09-11 the RUZ incremental resumed from a cursor a previous
    run had left at the end of its own window, asked for changes past that
    point, read an empty page, and stored `completed` with zero items. Nothing
    failed. Ten runs over three days, every job row honest, and the register's
    changes went unread because `zmenene_od` sat on 2026-08-04.

    The window is the one row that recorded it.
    """

    def _window(self, *, status="completed", days_old=1, sync_type="incremental"):
        return SyncProgress.objects.create(
            sync_type=sync_type,
            status=status,
            zmenene_od=timezone.localdate() - timedelta(days=days_old),
        )

    def _run(self, **options):
        out = StringIO()
        try:
            call_command("sync_health", stdout=out, **options)
        except SystemExit as exc:
            return out.getvalue(), exc.code
        return out.getvalue(), 0

    def test_a_window_that_stopped_moving_is_unmet(self):
        self._window(days_old=40)

        output, code = self._run(window_max_age_days=3)

        self.assertEqual(code, 1)
        self.assertIn("Sync jobs: 1 unmet", output)
        self.assertIn("no longer covers its changes", output)

    def test_a_window_inside_the_threshold_is_fine(self):
        self._window(days_old=1)

        output, code = self._run(window_max_age_days=3)

        self.assertEqual(code, 0)
        self.assertIn("Sync jobs: 0 unmet", output)

    def test_it_is_judged_on_age_alone_not_on_a_count_of_items(self):
        """The reason this condition exists at all.

        The command prints item counters and refuses to judge them, because how
        many items a run *should* process depends on the run. Window age does
        not: `fetch_ruz_data` advances it on every walk that reaches the end, so
        an old window on a completed row is a state, not a threshold on volume.
        """
        self._window(days_old=40)

        output, code = self._run(window_max_age_days=3)

        self.assertEqual(code, 1)
        self.assertIn("every run since has reported success without moving it", output)

    def test_a_paused_window_is_not_judged(self):
        """Stopped by an operator who knows -- judging it would be reporting on
        the operator, not on the sync."""
        self._window(status="paused", days_old=40)

        output, code = self._run(window_max_age_days=3)

        self.assertEqual(code, 0)
        self.assertIn("paused", output)

    def test_a_running_window_is_not_judged(self):
        """A walk in progress legitimately holds an old window until it ends."""
        self._window(status="running", days_old=40)

        output, code = self._run(window_max_age_days=3)

        self.assertEqual(code, 0)

    def test_a_failed_window_is_not_judged(self):
        """Consistent with the rest of the command, which judges `failed` only
        for the unattended schedule -- a failed manual run has a person on it."""
        self._window(status="failed", days_old=40)

        output, code = self._run(window_max_age_days=3)

        self.assertEqual(code, 0)

    def test_a_window_that_was_never_set_is_not_judged(self):
        """Written by a run that never got as far as choosing a window. There
        is nothing to age, so there is nothing to say about it."""
        SyncProgress.objects.create(sync_type="incremental", status="completed")

        output, code = self._run(window_max_age_days=3)

        self.assertEqual(code, 0)
        self.assertIn("no window set", output)

    def test_the_window_is_printed_even_when_it_is_healthy(self):
        """Visible rather than silent: the verdict is `OK`, and the date it was
        judged on is on screen next to it."""
        self._window(days_old=1)

        output, code = self._run(window_max_age_days=3)

        self.assertEqual(code, 0)
        self.assertIn("incremental sync windows", output)
        self.assertIn("incremental", output)
        self.assertIn("OK", output)

    def test_the_threshold_is_configurable_and_can_come_from_the_env(self):
        self._window(days_old=10)

        _, strict = self._run(window_max_age_days=3)
        self.assertEqual(strict, 1)

        _, lenient = self._run(window_max_age_days=30)
        self.assertEqual(lenient, 0)

        with patch.dict("os.environ", {"CISTAFIRMA_SYNC_WINDOW_DAYS": "3"}):
            output, code = self._run()
        self.assertEqual(code, 1)
        self.assertIn("Sync jobs: 1 unmet", output)

    def test_no_incremental_row_at_all_says_so_instead_of_going_quiet(self):
        output, code = self._run(window_max_age_days=3)

        self.assertEqual(code, 0)
        self.assertIn("no incremental sync has ever been recorded", output)

    def test_a_window_held_by_item_errors_says_so_instead_of_claiming_success(self):
        """A deliberate hold and a silent stall look identical from the date.

        `fetch_ruz_data` advances the window only on a clean run, so a walk that
        finishes with item errors holds it on purpose -- and still stores
        `completed`, because the run did complete. The gate fails both, which is
        right (the source's changes go unread either way), but reporting the
        second as "every run since has reported success" would be false: it
        reported errors, on purpose, and stopped.
        """
        window = self._window(days_old=40)
        window.total_errors = 1
        window.last_error = "value too long for type character varying(8)"
        window.save(update_fields=["total_errors", "last_error"])

        output, code = self._run(window_max_age_days=3)

        self.assertEqual(code, 1)
        self.assertIn("held on purpose", output)
        self.assertIn("character varying(8)", output)
        self.assertNotIn("every run since has reported success", output)

    def test_focus_mode_does_not_redden_the_window_it_switched_off(self):
        """Focus Mode takes the RUZ beat entry out of the schedule, so no run is
        meant to move this window while it is on.

        Without the carve-out the gate would fail after three days -- and would
        explain itself with "every run since has reported success", a sentence
        that is false precisely because there were no runs. The sibling control
        settled this first: `source_health` names the sources Focus Mode
        silences rather than judging them.
        """
        self._window(days_old=40)
        SyncFocusModeState.objects.update_or_create(pk=1, defaults={"active": True})

        output, code = self._run(window_max_age_days=3)

        self.assertEqual(code, 0)
        self.assertIn("Sync jobs: 0 unmet", output)

    def test_leaving_focus_mode_brings_the_judgement_back(self):
        """The carve-out is scoped to Focus Mode being *on*.

        A gate that stayed silent after Focus Mode ended would be the same
        defect one state later: the window would still be stalled, and nothing
        would say so. The reason line is checked too, so the skip is visible
        rather than the row simply going quiet.
        """
        self._window(days_old=40)
        SyncFocusModeState.objects.update_or_create(pk=1, defaults={"active": True})

        paused, code = self._run(window_max_age_days=3)
        self.assertEqual(code, 0)
        self.assertIn("Focus Mode is active", paused)
        self.assertIn("incremental", paused)

        SyncFocusModeState.objects.filter(pk=1).update(active=False)

        judged, code = self._run(window_max_age_days=3)
        self.assertEqual(code, 1)
        self.assertIn("no longer covers its changes", judged)
