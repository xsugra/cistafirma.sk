from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import NotificationEvent
from .serializers import NotificationEventSerializer
from .services import CLAIM_LEASE, MAX_ATTEMPTS, send_pending_email_notifications

User = get_user_model()


def make_event(user, **overrides):
    """Create a NotificationEvent with sane defaults; override any field."""
    defaults = {
        'user': user,
        'company_ico': '12345678',
        'company_name': 'Test s.r.o.',
        'event_type': NotificationEvent.EventType.STATUS_CHANGE,
        'title': 'Test s.r.o. — zmena statusu',
        'details': {'old_status': 'Aktívna', 'new_status': 'V likvidácii'},
    }
    defaults.update(overrides)
    return NotificationEvent.objects.create(**defaults)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class SendPendingEmailNotificationsTests(TestCase):
    def setUp(self):
        mail.outbox.clear()

    def test_success_flips_event_to_sent_and_is_not_resent(self):
        user = User.objects.create_user(email='recipient@example.com', password='testpass123')
        event = make_event(user)

        sent = send_pending_email_notifications()

        self.assertEqual(sent, 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [user.email])
        event.refresh_from_db()
        self.assertEqual(event.status, NotificationEvent.Status.SENT)
        self.assertIsNotNone(event.sent_at)
        self.assertEqual(event.attempts, 1)
        self.assertEqual(event.last_error, '')

        # A second run must not resend the already-delivered event.
        self.assertEqual(send_pending_email_notifications(), 0)
        self.assertEqual(len(mail.outbox), 1)

    def test_failure_marks_failed_then_auto_retries_on_next_run(self):
        user = User.objects.create_user(email='recipient@example.com', password='testpass123')
        event = make_event(user)

        with patch('notifications.services.send_mail', side_effect=RuntimeError('SMTP down')):
            sent = send_pending_email_notifications()

        # fail_silently is gone: a failed send must NOT count as delivered.
        self.assertEqual(sent, 0)
        self.assertEqual(len(mail.outbox), 0)
        event.refresh_from_db()
        self.assertEqual(event.status, NotificationEvent.Status.FAILED)
        self.assertEqual(event.attempts, 1)
        self.assertIn('SMTP down', event.last_error)
        self.assertIsNone(event.sent_at)

        # Next run (no failure) auto-retries the failed event.
        sent = send_pending_email_notifications()
        self.assertEqual(sent, 1)
        self.assertEqual(len(mail.outbox), 1)
        event.refresh_from_db()
        self.assertEqual(event.status, NotificationEvent.Status.SENT)
        self.assertEqual(event.attempts, 2)
        self.assertEqual(event.last_error, '')

    def test_freshly_claimed_sending_is_not_resent_but_stale_lease_is_reclaimed(self):
        user = User.objects.create_user(email='recipient@example.com', password='testpass123')
        now = timezone.now()
        fresh = make_event(
            user,
            status=NotificationEvent.Status.SENDING,
            claimed_at=now,
            attempts=1,
        )
        stale = make_event(
            user,
            status=NotificationEvent.Status.SENDING,
            claimed_at=now - CLAIM_LEASE - timedelta(minutes=1),
            attempts=1,
        )

        sent = send_pending_email_notifications()

        # Only the stale (crashed-worker) event is reclaimed and delivered.
        self.assertEqual(sent, 1)
        self.assertEqual(len(mail.outbox), 1)
        fresh.refresh_from_db()
        self.assertEqual(fresh.status, NotificationEvent.Status.SENDING)
        self.assertEqual(fresh.attempts, 1)
        stale.refresh_from_db()
        self.assertEqual(stale.status, NotificationEvent.Status.SENT)
        self.assertEqual(stale.attempts, 2)
        self.assertIsNotNone(stale.sent_at)

    def test_exhausted_failed_events_are_not_retried(self):
        user = User.objects.create_user(email='recipient@example.com', password='testpass123')
        exhausted = make_event(
            user,
            status=NotificationEvent.Status.FAILED,
            attempts=MAX_ATTEMPTS,
            last_error='permanent',
        )
        retryable = make_event(
            user,
            status=NotificationEvent.Status.FAILED,
            attempts=MAX_ATTEMPTS - 1,
            last_error='transient',
        )

        sent = send_pending_email_notifications()

        # Only the event below the attempt cap is retried.
        self.assertEqual(sent, 1)
        self.assertEqual(len(mail.outbox), 1)
        exhausted.refresh_from_db()
        self.assertEqual(exhausted.status, NotificationEvent.Status.FAILED)
        self.assertEqual(exhausted.attempts, MAX_ATTEMPTS)
        retryable.refresh_from_db()
        self.assertEqual(retryable.status, NotificationEvent.Status.SENT)
        self.assertEqual(retryable.attempts, MAX_ATTEMPTS)


class NotificationEventSerializerTests(TestCase):
    def test_sent_email_field_mirrors_status(self):
        user = User.objects.create_user(email='recipient@example.com', password='testpass123')
        event = make_event(user, status=NotificationEvent.Status.SENT, sent_at=timezone.now())

        data = NotificationEventSerializer(event).data
        self.assertIs(True, data['sentEmail'])
        self.assertEqual(data['deliveryStatus'], 'sent')

        event.status = NotificationEvent.Status.PENDING
        event.sent_at = None
        data = NotificationEventSerializer(event).data
        self.assertIs(False, data['sentEmail'])
        self.assertEqual(data['deliveryStatus'], 'pending')
