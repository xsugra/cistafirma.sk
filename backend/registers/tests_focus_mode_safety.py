from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django_celery_beat.models import IntervalSchedule, PeriodicTask

from registers.models import SyncFocusModeState
from registers.services.focus_mode import FOCUS_KEEP_TASKS, enter_focus_mode


class FocusModeSafetyTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="focus-mode-safety",
            email="focus-mode-safety@example.com",
            password="safe-password",
        )
        interval = IntervalSchedule.objects.create(every=1, period=IntervalSchedule.HOURS)
        self.keep_task = PeriodicTask.objects.create(
            name="keep-task",
            task=next(iter(FOCUS_KEEP_TASKS)),
            interval=interval,
        )
        self.paused_task = PeriodicTask.objects.create(
            name="paused-task",
            task="registers.tasks.update_insurance_debt",
            interval=interval,
        )

    def test_enter_focus_mode_preserves_broker_messages_and_running_tasks(self):
        with patch(
            "registers.services.focus_mode.revoke_non_focus_tasks"
        ) as revoke_tasks, patch(
            "registers.services.focus_mode.purge_broker_queues"
        ) as purge_queues:
            state = enter_focus_mode(self.user)

        revoke_tasks.assert_not_called()
        purge_queues.assert_not_called()
        self.keep_task.refresh_from_db()
        self.paused_task.refresh_from_db()
        self.assertTrue(self.keep_task.enabled)
        self.assertFalse(self.paused_task.enabled)
        self.assertEqual(state.last_revoked, [])
        self.assertIn("preserved", state.notes)
        self.assertTrue(SyncFocusModeState.load().active)


class FocusModeWatchdogTests(TestCase):
    """The reaper has to outlive Focus Mode, or a dead walk never comes back.

    `ruz_full_keeper_decision` answers "wait" for every `queued` and `running`
    job and hands the `running` -> `failed` transition to the watchdog alone --
    deliberately, so that transition has one owner rather than two answers to
    the same question. Focus Mode disables every `PeriodicTask` outside
    `FOCUS_KEEP_TASKS`, and the watchdog was outside it, so entering Focus Mode
    would have removed the only thing able to end a walk whose worker died and
    left the keeper waiting on it for ever. A paused import and an abandoned
    one would have been the same row -- which is the exact confusion the keeper
    exists to end.
    """

    ENTRY = "detect-stuck-sync-jobs-every-10-min"

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="focus-mode-watchdog",
            email="focus-mode-watchdog@example.com",
            password="safe-password",
        )
        interval = IntervalSchedule.objects.create(every=1, period=IntervalSchedule.HOURS)
        # Named after the beat entry, as `DatabaseScheduler` names it when it
        # reconciles `CELERY_BEAT_SCHEDULE` into rows -- that name and the
        # `task` dotted path are both what `_set_periodic_tasks_enabled`
        # matches on, and a mismatch in either is a watchdog Focus Mode pauses
        # while every surface still reports it enabled.
        self.watchdog = PeriodicTask.objects.create(
            name=self.ENTRY,
            task=settings.CELERY_BEAT_SCHEDULE[self.ENTRY]["task"],
            interval=interval,
        )
        # The positive control. "The watchdog was not disabled" is worth
        # nothing on its own -- an `enter_focus_mode` that disabled nothing at
        # all would satisfy it -- so the same run has to show something else
        # being switched off.
        self.paused_task = PeriodicTask.objects.create(
            name="paused-task",
            task="registers.tasks.update_insurance_debt",
            interval=interval,
        )

    def _watchdog_task_name(self):
        return settings.CELERY_BEAT_SCHEDULE[self.ENTRY]["task"]

    def test_the_watchdog_is_in_the_keep_list(self):
        """The one that survives a rename: the keep list holds dotted paths."""
        self.assertIn(self._watchdog_task_name(), FOCUS_KEEP_TASKS)

    def test_entering_focus_mode_leaves_the_watchdog_enabled(self):
        """And the mechanism, not just the list: the row really stays on."""
        enter_focus_mode(self.user)

        self.watchdog.refresh_from_db()
        self.paused_task.refresh_from_db()
        self.assertTrue(self.watchdog.enabled)
        self.assertFalse(self.paused_task.enabled)
