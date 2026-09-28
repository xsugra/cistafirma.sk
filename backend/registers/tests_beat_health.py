"""The gate that reads the schedule entries themselves.

Every other control in `make ops-check` reads what a run left behind, so an
entry that stopped firing is invisible: `compute-sector-benchmarks-daily` had
an entry and a row and dispatched nothing for 32 h while the whole gate stayed
green. These tests pin the four exemptions that keep this new control from
being red on a healthy host, and the one case it exists for.

The tests create their rows directly rather than through the scheduler, which
is deliberate: what is under test is the *reading* of a row, and
`ModelEntry`'s in-memory substitution of `date_changed` for a missing
`last_run_at` is one of the things that must not be reproduced here.
"""

from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone
from django_celery_beat.models import (
    CrontabSchedule,
    IntervalSchedule,
    PeriodicTask,
)

from backend.celery import app as celery_app
from registers.management.commands.beat_health import Command
from registers.models import SyncFocusModeState


class BeatHealthCommandTests(TestCase):
    def _entry(
        self,
        name="an-entry",
        task="registers.tasks.fetch_ruz_data_task",
        every=10,
        period=None,
        last_run_at=None,
        **kwargs,
    ):
        # The model's own constants, never the bare strings: `period` holds
        # lowercase values ('minutes', not 'MINUTES'), and a literal written
        # from memory is exactly how a row ends up unreadable -- which this
        # file also tests for, having got it wrong once.
        period = period or IntervalSchedule.MINUTES
        interval, _ = IntervalSchedule.objects.get_or_create(
            every=every, period=period
        )
        return PeriodicTask.objects.create(
            name=name,
            task=task,
            interval=interval,
            last_run_at=last_run_at,
            **kwargs,
        )

    def _stopped_since(self, age):
        """An enabled entry whose last run is `age` old and which has stopped.

        `last_run_at` is `editable=False` and never `auto_now`, so it can be
        set at creation -- but a *disabled* row cannot hold one (`save()` nulls
        it), which is what `_paused_since` is for.
        """
        return self._entry(name="stopped", last_run_at=timezone.now() - age)

    def _paused_since(self, age):
        """A row switched off *without* losing its last run.

        This is not a contrived shape: Focus Mode disables rows with
        `pt.save(update_fields=["enabled"])`, and because `update_fields`
        excludes `last_run_at`, `PeriodicTask.save()`'s `self.last_run_at = None`
        never reaches the database. A full save (the admin's toggle) does null
        it. Both are exercised below, because the table's age column differs.
        """
        row = self._entry(name="paused", last_run_at=timezone.now() - age)
        PeriodicTask.objects.filter(pk=row.pk).update(enabled=False)
        row.refresh_from_db()
        return row

    def _never_ran_since(self, age):
        """A row that has never run, last written `age` ago.

        `date_changed` is `auto_now`, so it can only be moved after the row
        exists.
        """
        row = self._entry(
            name="never-ran", every=1, period=IntervalSchedule.DAYS, last_run_at=None
        )
        PeriodicTask.objects.filter(pk=row.pk).update(
            last_run_at=None, date_changed=timezone.now() - age
        )
        row.refresh_from_db()
        return row

    def _run(self, **options):
        out = StringIO()
        try:
            call_command("beat_health", stdout=out, **options)
        except SystemExit as exc:
            return out.getvalue(), exc.code
        return out.getvalue(), 0

    # -- the case it exists for ------------------------------------------

    def test_an_entry_past_its_interval_is_unmet(self):
        self._stopped_since(timedelta(hours=2))

        output, code = self._run()

        self.assertEqual(code, 1)
        self.assertIn("Beat schedule: 1 unmet", output)
        self.assertIn("FAIL", output)
        self.assertIn("it has simply stopped", output)

    def test_an_entry_inside_its_interval_is_fine(self):
        """The positive control: without it, a gate that always fails passes."""
        self._entry(name="running", last_run_at=timezone.now() - timedelta(minutes=2))

        output, code = self._run()

        self.assertEqual(code, 0)
        self.assertIn("Beat schedule: 0 unmet", output)
        self.assertIn("OK", output)

    def test_an_entry_inside_the_grace_is_not_a_miss_yet(self):
        """12 min into a 10 min interval is a late dispatch, not a stopped one."""
        self._entry(name="late", last_run_at=timezone.now() - timedelta(minutes=12))

        output, code = self._run()

        self.assertEqual(code, 0)
        self.assertIn("Beat schedule: 0 unmet", output)

    def test_an_entry_older_than_its_whole_interval_plus_grace_is_unmet(self):
        """26 min on a 10 min interval is past 10 + 15, so it is judged."""
        self._entry(name="late", last_run_at=timezone.now() - timedelta(minutes=26))

        output, code = self._run()

        self.assertEqual(code, 1)
        self.assertIn("Beat schedule: 1 unmet", output)

    def test_the_grace_is_configurable(self):
        self._entry(name="late", last_run_at=timezone.now() - timedelta(minutes=30))

        _, strict = self._run(grace_minutes=5)
        _, relaxed = self._run(grace_minutes=600)

        self.assertEqual(strict, 1)
        self.assertEqual(relaxed, 0)

    def test_the_grace_can_come_from_the_environment(self):
        """The container's environment is where ops sets it, not the CLI."""
        self._entry(name="late", last_run_at=timezone.now() - timedelta(minutes=30))

        with patch.dict("os.environ", {"CISTAFIRMA_BEAT_GRACE_MINUTES": "5"}):
            _, code = self._run()

        self.assertEqual(code, 1)

    # -- the exemptions that keep it honest on a healthy host -------------

    def test_a_switched_off_entry_is_not_judged(self):
        self._paused_since(timedelta(days=21))

        output, code = self._run()

        self.assertEqual(code, 0)
        self.assertIn("Beat schedule: 0 unmet", output)
        self.assertIn("switched off", output)
        # ...and it is still shown, with the age that makes a forgotten pause
        # visible. "Not judged" must not read as "not seen".
        self.assertIn("paused", output)
        self.assertIn("21d", output)

    def test_a_switched_off_entry_names_focus_mode_when_it_is_active(self):
        """The same row reads differently depending on why it is off."""
        self._paused_since(timedelta(days=21))
        SyncFocusModeState.objects.create(pk=1, active=True)

        output, _ = self._run()

        self.assertIn("Focus Mode is active", output)
        self.assertNotIn("switched off, so not judged", output)

    def test_celerys_own_entry_is_not_judged_even_on_an_interval(self):
        """Isolated from the crontab exemption, which happens to cover it too.

        On production `celery.backend_cleanup` is a crontab row *and* has the
        `celery.` prefix. This test gives it an interval schedule, so the
        prefix is the only thing that can exempt it.
        """
        self._entry(
            name="celery.backend_cleanup",
            task="celery.backend_cleanup",
            every=1,
            period=IntervalSchedule.DAYS,
        )
        PeriodicTask.objects.filter(name="celery.backend_cleanup").update(
            date_changed=timezone.now() - timedelta(days=30)
        )

        output, code = self._run()

        self.assertEqual(code, 0)
        self.assertIn("Beat schedule: 0 unmet", output)
        self.assertIn("celery's own housekeeping", output)

    def test_a_crontab_entry_is_not_judged(self):
        """The branch that cannot run on today's host, so it gets a test.

        All ten live rows are interval rows except celery's own crontab, which
        the prefix exemption reaches first -- so nothing on production exercises
        this. A crontab's `remaining_estimate` is a different quantity from an
        interval's, and reading one as the other would be a confident wrong age.
        """
        crontab, _ = CrontabSchedule.objects.get_or_create(
            minute="0", hour="3", day_of_week="*", day_of_month="*", month_of_year="*"
        )
        PeriodicTask.objects.create(
            name="a-crontab-entry",
            task="registers.tasks.fetch_ruz_data_task",
            crontab=crontab,
            last_run_at=timezone.now() - timedelta(days=5),
        )

        output, code = self._run()

        self.assertEqual(code, 0)
        self.assertIn("Beat schedule: 0 unmet", output)
        self.assertIn("a crontab's `remaining_estimate`", output)
        self.assertIn("a-crontab-entry (crontab)", output)

    def test_an_interval_whose_period_is_unreadable_is_not_judged(self):
        """A `period` outside the model's choices yields no interval at all.

        Not hypothetical: the first draft of these tests wrote `"MINUTES"`
        where the field's choices hold `"minutes"`, and
        `IntervalSchedule.schedule` builds `timedelta(**{period: every})` -- so
        such a row raises rather than producing an age. Judging it would crash
        the gate; skipping it silently would hide it. It is printed with its
        reason instead.
        """
        PeriodicTask.objects.create(
            name="a-corrupt-interval",
            task="registers.tasks.fetch_ruz_data_task",
            interval=IntervalSchedule.objects.create(every=10, period="MINUTES"),
            last_run_at=timezone.now() - timedelta(days=9),
        )

        output, code = self._run()

        self.assertEqual(code, 0)
        self.assertIn("Beat schedule: 0 unmet", output)
        self.assertIn(
            "nothing to compare the last run against: "
            "a-corrupt-interval (MINUTES)",
            output,
        )

    # -- the row that has never run ---------------------------------------

    def test_a_never_run_entry_is_unmet_once_it_is_provably_late(self):
        self._never_ran_since(timedelta(days=3))

        output, code = self._run()

        self.assertEqual(code, 1)
        self.assertIn("Beat schedule: 1 unmet", output)
        self.assertIn("has never run", output)

    def test_a_never_run_entry_too_young_to_judge_is_reported_as_a_hole(self):
        """The blind spot has to be stated, not hidden behind a pass."""
        self._never_ran_since(timedelta(minutes=1))

        output, code = self._run()

        self.assertEqual(code, 0)
        self.assertIn("Beat schedule: 0 unmet", output)
        self.assertIn("Read this as a hole and not as a pass", output)
        self.assertIn("never-ran", output)

    def test_a_never_run_entry_is_never_read_as_its_date_changed(self):
        """`last_run_at or date_changed` would hide exactly this row.

        A row three days old on a one-day interval has provably missed a run,
        so reading `date_changed` as a substitute last run would call it
        healthy. It must not.
        """
        self._never_ran_since(timedelta(days=3))

        output, _ = self._run()

        self.assertIn("FAIL", output)

    # -- the task name, reported and never judged -------------------------

    def test_the_registry_read_gives_a_real_answer_not_an_unknown(self):
        """Without this, the sentence below is only ever silence.

        `_registered_task_names` returns None when the registry cannot be read,
        and the command only speaks on a name being absent from a real set --
        so a registry that always failed would make the naming tests below pass
        while saying nothing.
        """
        names = Command()._registered_task_names()

        self.assertIsNotNone(names)
        self.assertIn("registers.tasks.fetch_ruz_data_task", names)
        self.assertNotIn("registers.tasks.gone_away", names)

    def test_the_registry_is_loaded_before_it_is_read(self):
        """`finalize()` alone leaves it empty, and the answer wrong.

        Measured on production 2026-09-28: nine tasks before and after
        `finalize()` in a `manage.py` process, none of them this app's, so
        every live row -- including one that had run three minutes earlier --
        was reported as naming a task nothing implements. Asserting the *set*
        cannot catch that here, because Django's own start-up imports the task
        modules in a test process and the answer comes out right for the wrong
        reason; so the load itself is what is pinned.
        """
        with patch.object(
            celery_app.loader, "import_default_modules"
        ) as import_modules:
            Command()._registered_task_names()

        import_modules.assert_called_once()

    def test_every_task_the_schedule_names_is_implemented(self):
        """The invariant behind the sentence, checked on the real settings.

        A rename is the failure this covers: `PeriodicTask` rows are keyed on
        the task's *name*, so a name that no longer exists stops the job with
        no error anywhere.
        """
        names = Command()._registered_task_names()

        self.assertIsNotNone(names)
        for entry in settings.CELERY_BEAT_SCHEDULE.values():
            self.assertIn(entry["task"], names)

    def test_a_stale_entry_naming_an_unregistered_task_says_so(self):
        self._entry(
            name="a-renamed-task",
            task="registers.tasks.gone_away",
            last_run_at=timezone.now() - timedelta(days=2),
        )

        output, code = self._run()

        self.assertEqual(code, 1)
        self.assertIn("is not registered in this app", output)

    def test_a_stale_entry_naming_a_registered_task_does_not(self):
        """The control: the sentence must mean something when it appears."""
        self._entry(
            name="a-real-task",
            task="registers.tasks.fetch_ruz_data_task",
            last_run_at=timezone.now() - timedelta(days=2),
        )

        output, code = self._run()

        self.assertEqual(code, 1)
        self.assertNotIn("is not registered in this app", output)

    # -- shape of the report ----------------------------------------------

    def test_the_whole_schedule_being_stale_is_called_out(self):
        """One red row is a task; every red row is beat itself."""
        self._entry(name="stopped-a", last_run_at=timezone.now() - timedelta(days=1))
        self._entry(name="stopped-b", last_run_at=timezone.now() - timedelta(days=1))

        output, code = self._run()

        self.assertEqual(code, 1)
        self.assertIn("Beat schedule: 2 unmet", output)
        self.assertIn("all 2 judged entries are stale at once", output)

    def test_one_healthy_row_is_enough_to_drop_that_note(self):
        self._entry(name="stopped", last_run_at=timezone.now() - timedelta(days=1))
        self._entry(name="running", last_run_at=timezone.now() - timedelta(minutes=1))

        output, code = self._run()

        self.assertEqual(code, 1)
        self.assertIn("Beat schedule: 1 unmet", output)
        self.assertNotIn("judged entries are stale at once", output)

    def test_a_row_that_is_not_judged_does_not_count_towards_that_note(self):
        """The note says *every judged row*, and a `--` row was never judged.

        A never-run row young enough to be unprovable reaches the same block as
        a judged one, so counting rows on arrival there turned two stale entries
        plus one young never-run entry into "all 3 judged entries are stale at
        once" -- the note silently not firing (3 != 2), which is why the
        assertion here is that it is *present* with the honest count.
        """
        self._entry(name="stopped-a", last_run_at=timezone.now() - timedelta(days=1))
        self._entry(name="stopped-b", last_run_at=timezone.now() - timedelta(days=1))
        self._never_ran_since(timedelta(minutes=1))

        output, code = self._run()

        self.assertEqual(code, 1)
        self.assertIn("Beat schedule: 2 unmet", output)
        self.assertIn("all 2 judged entries are stale at once", output)

    def test_the_note_needs_more_than_one_judged_row(self):
        """With one judged row it claims a distinction that does not exist.

        "Beat itself is not dispatching" and "this one task stopped" are the
        same observation when only one entry could be judged, so the sentence
        would be dressing a single FAIL row in a diagnosis.
        """
        self._entry(name="stopped", last_run_at=timezone.now() - timedelta(days=1))
        self._never_ran_since(timedelta(minutes=1))

        output, code = self._run()

        self.assertEqual(code, 1)
        self.assertIn("Beat schedule: 1 unmet", output)
        self.assertNotIn("judged entries are stale at once", output)

    def test_an_empty_schedule_is_reported_rather_than_passed_quietly(self):
        output, code = self._run()

        self.assertEqual(code, 0)
        self.assertIn("no periodic task rows exist at all", output)
        self.assertIn("Beat schedule: 0 unmet", output)

    # -- read-only ---------------------------------------------------------

    def test_it_writes_nothing(self):
        """It runs inside a gate that must be safe to run at any moment.

        `SyncFocusModeState` is the one row this command could plausibly
        create, because `load()` is a `get_or_create` -- so the flag is read
        through a filtered `values_list` instead, and this asserts it.
        """
        row = self._stopped_since(timedelta(hours=2))

        self._run()

        row.refresh_from_db()
        self.assertIsNotNone(row.last_run_at)
        self.assertEqual(row.total_run_count, 0)
        self.assertEqual(row.enabled, True)
        self.assertEqual(SyncFocusModeState.objects.count(), 0)

    def test_an_unknown_registry_is_not_a_claim(self):
        """A failure to read the registry must stay silent, not assert a gap.

        The False half runs in the same test on purpose: it is the positive
        control that the patch reached the command at all, without which the
        silent half would pass whether or not the stub bound.
        """
        self._entry(
            name="a-real-task",
            task="registers.tasks.fetch_ruz_data_task",
            last_run_at=timezone.now() - timedelta(days=2),
        )

        with patch.object(Command, "_registered_task_names", return_value=None):
            output, code = self._run()

        self.assertEqual(code, 1)
        self.assertNotIn("is not registered in this app", output)

        # The positive control: the stub must be shown to reach the command,
        # or the silent half above would pass whether or not it bound.
        with patch.object(Command, "_registered_task_names", return_value=set()):
            output, _ = self._run()

        self.assertIn("is not registered in this app", output)

    def test_a_negative_grace_is_refused(self):
        """It would fail every entry at once -- a gate nobody can read."""
        self._entry(name="running", last_run_at=timezone.now() - timedelta(minutes=1))

        with self.assertRaises(CommandError):
            call_command("beat_health", stdout=StringIO(), grace_minutes=-1)
