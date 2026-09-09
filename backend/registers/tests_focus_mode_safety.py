from unittest.mock import patch

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
