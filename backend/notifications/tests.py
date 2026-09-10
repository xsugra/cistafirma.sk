from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from companies.models import Company, Watchlist

from .models import NotificationEvent, NotificationPreference
from .serializers import NotificationEventSerializer
from .services import (
    CLAIM_LEASE,
    MAX_ATTEMPTS,
    create_debt_change_event,
    create_executive_change_event,
    create_status_change_event,
    detect_status_change,
    send_pending_email_notifications,
)

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


class ChangeEventTextFittingTests(TestCase):
    """A long registered name must cost the title, not the notification.

    `Company.nazov_UJ` allows 500 characters and live rows already reach 200,
    while `NotificationEvent.title` and `.company_name` are 255. Postgres
    rejects an over-long value rather than trimming it, and the caller catches
    that broadly -- so an unbounded title does not degrade the notification, it
    writes it nowhere and reports it in a single warning line.
    """

    # 496 characters: inside nazov_UJ's 500, well past the 255 of both
    # NotificationEvent columns.
    LONG_NAME = 'Dlhé meno, n.o. ' * 31

    def setUp(self):
        self.user = User.objects.create_user(
            email='watcher@example.com', password='testpass123',
        )
        self.company = Company.objects.create(
            ruz_id=990001,
            ico='99000001',
            nazov_UJ=self.LONG_NAME,
            debt_vszp=Decimal('0'),
            debt_soc_poist=Decimal('0'),
        )
        Watchlist.objects.create(user=self.user, company=self.company)
        NotificationPreference.objects.create(
            user=self.user,
            email_enabled=True,
            on_debt_change=True,
            on_status_change=True,
            on_executive_change=True,
        )

    def _assert_fits(self, event):
        title_limit = NotificationEvent._meta.get_field('title').max_length
        name_limit = NotificationEvent._meta.get_field('company_name').max_length
        self.assertLessEqual(len(event.title), title_limit)
        self.assertLessEqual(len(event.company_name), name_limit)

    def test_debt_change_fits_its_columns(self):
        created = create_debt_change_event(
            company_id=self.company.id,
            company_ico=self.company.ico,
            company_name=self.LONG_NAME,
            changes={
                'vszp': {'old': 0, 'new': 6641.86},
                'soc_poist': {'old': 0, 'new': 731.46},
            },
        )

        self.assertEqual(created, 1)
        self._assert_fits(NotificationEvent.objects.get())

    def test_the_change_survives_the_trim(self):
        """The name gives way; the news is what the reader is being told."""
        create_debt_change_event(
            company_id=self.company.id,
            company_ico=self.company.ico,
            company_name=self.LONG_NAME,
            changes={
                'vszp': {'old': 0, 'new': 6641.86},
                'soc_poist': {'old': 0, 'new': 731.46},
            },
        )

        title = NotificationEvent.objects.get().title
        self.assertIn('VšZP', title)
        self.assertIn('Sociálna poisťovňa', title)
        self.assertTrue(title.endswith(')'), title)

    def test_a_trimmed_name_says_so(self):
        create_debt_change_event(
            company_id=self.company.id,
            company_ico=self.company.ico,
            company_name=self.LONG_NAME,
            changes={'vszp': {'old': 0, 'new': 6641.86}},
        )

        self.assertIn('…', NotificationEvent.objects.get().company_name)

    def test_status_change_fits_its_columns(self):
        created = create_status_change_event(
            company_ico=self.company.ico,
            company_name=self.LONG_NAME,
            old_status='Aktívna',
            new_status='V likvidácii',
        )

        self.assertEqual(created, 1)
        self._assert_fits(NotificationEvent.objects.get())

    def test_executive_change_fits_its_columns(self):
        """Three long officer names overflow the title on their own."""
        created = create_executive_change_event(
            company_ico=self.company.ico,
            company_name=self.LONG_NAME,
            changes=[f'Pribudol: {n}' for n in ('Ing. ' + 'X' * 80,) * 3],
        )

        self.assertEqual(created, 1)
        self._assert_fits(NotificationEvent.objects.get())

    def test_a_short_name_is_left_exactly_as_it_was(self):
        """The bound must not quietly rewrite names that already fit."""
        create_debt_change_event(
            company_id=self.company.id,
            company_ico=self.company.ico,
            company_name='Krátke s.r.o.',
            changes={'vszp': {'old': 0, 'new': 100}},
        )

        event = NotificationEvent.objects.get()
        self.assertEqual(event.company_name, 'Krátke s.r.o.')
        # format_currency_eur rounds to whole euros and appends "€".
        self.assertEqual(event.title, 'Krátke s.r.o. — zmena dlhov (VšZP: +100€)')


class DetectStatusChangeTests(TestCase):
    """Only a company that *becomes* dissolved is news.

    `create_status_change_event` was written and never called, so the
    "Zmena statusu" switch in the UI could not fire. Wiring it up means
    deciding what counts as a change: the write path stores a date and can no
    longer see what it overwrote, so the transition has to be judged by the
    caller -- and the risk of getting that wrong is a notification for every
    one of the 120k companies already carrying a dissolution date.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            email='watcher@example.com', password='testpass123',
        )
        self.company = Company.objects.create(
            ruz_id=990002,
            ico='99000002',
            nazov_UJ='Sledovaná s.r.o.',
        )
        Watchlist.objects.create(user=self.user, company=self.company)
        NotificationPreference.objects.create(
            user=self.user,
            email_enabled=True,
            on_status_change=True,
        )

    def test_a_first_dissolution_notifies(self):
        created = detect_status_change(
            company_ico=self.company.ico,
            company_name=self.company.nazov_UJ,
            old_datum_zrusenia=None,
            new_datum_zrusenia=date(2026, 3, 12),
        )

        self.assertEqual(created, 1)
        event = NotificationEvent.objects.get()
        self.assertEqual(event.event_type, NotificationEvent.EventType.STATUS_CHANGE)
        self.assertEqual(event.details, {
            'old_status': 'Aktívna',
            'new_status': 'Vymazaná (12.03.2026)',
        })
        self.assertIn('Vymazaná', event.title)

    def test_an_already_dissolved_company_is_not_re_announced(self):
        """Idempotence: the second sync of the same company must be silent."""
        company = Company.objects.create(
            ruz_id=990003, ico='99000003', nazov_UJ='Zaniknutá s.r.o.',
            datum_zrusenia=date(2026, 3, 12),
        )
        Watchlist.objects.create(user=self.user, company=company)

        created = detect_status_change(
            company_ico=company.ico,
            company_name=company.nazov_UJ,
            old_datum_zrusenia=date(2026, 3, 12),
            new_datum_zrusenia=date(2026, 3, 12),
        )

        self.assertEqual(created, 0)
        self.assertEqual(NotificationEvent.objects.count(), 0)

    def test_a_company_without_a_dissolution_date_is_ignored(self):
        created = detect_status_change(
            company_ico=self.company.ico,
            company_name=self.company.nazov_UJ,
            old_datum_zrusenia=None,
            new_datum_zrusenia=None,
        )

        self.assertEqual(created, 0)
        self.assertEqual(NotificationEvent.objects.count(), 0)

    def test_a_correction_is_not_an_alarm(self):
        """RUZ moving or clearing a date is a fix, not a dissolution."""
        moved = detect_status_change(
            company_ico=self.company.ico,
            company_name=self.company.nazov_UJ,
            old_datum_zrusenia=date(2026, 3, 12),
            new_datum_zrusenia=date(2026, 4, 1),
        )
        cleared = detect_status_change(
            company_ico=self.company.ico,
            company_name=self.company.nazov_UJ,
            old_datum_zrusenia=date(2026, 3, 12),
            new_datum_zrusenia=None,
        )

        self.assertEqual((moved, cleared), (0, 0))
        self.assertEqual(NotificationEvent.objects.count(), 0)

    def test_an_unwatched_company_notifies_nobody(self):
        created = detect_status_change(
            company_ico='99999999',
            company_name='Nesledovaná s.r.o.',
            old_datum_zrusenia=None,
            new_datum_zrusenia=date(2026, 3, 12),
        )

        self.assertEqual(created, 0)

    def test_a_watcher_who_opted_out_is_not_notified(self):
        NotificationPreference.objects.filter(user=self.user).update(on_status_change=False)

        created = detect_status_change(
            company_ico=self.company.ico,
            company_name=self.company.nazov_UJ,
            old_datum_zrusenia=None,
            new_datum_zrusenia=date(2026, 3, 12),
        )

        self.assertEqual(created, 0)

    def test_a_long_name_still_fits_its_columns(self):
        """The date in `new_status` widens a title that was already bounded."""
        company = Company.objects.create(
            ruz_id=990004, ico='99000004', nazov_UJ='Dlhé meno, n.o. ' * 31,
        )
        Watchlist.objects.create(user=self.user, company=company)

        created = detect_status_change(
            company_ico=company.ico,
            company_name=company.nazov_UJ,
            old_datum_zrusenia=None,
            new_datum_zrusenia=date(2026, 3, 12),
        )

        self.assertEqual(created, 1)
        event = NotificationEvent.objects.get()
        self.assertLessEqual(
            len(event.title), NotificationEvent._meta.get_field('title').max_length
        )
        self.assertLessEqual(
            len(event.company_name),
            NotificationEvent._meta.get_field('company_name').max_length,
        )
