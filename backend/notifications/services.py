"""
Notification service — creates events when watched companies change.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import F, Q, QuerySet
from django.utils import timezone

from .models import NotificationEvent, NotificationPreference

logger = logging.getLogger(__name__)
User = get_user_model()

# Outbox claim / retry policy for outbound notification emails.
BATCH = 200
MAX_ATTEMPTS = 5
CLAIM_LEASE = timedelta(minutes=30)


def _column_width(field_name: str) -> int:
    """The model column's own width, so the bound cannot drift from the schema."""
    return NotificationEvent._meta.get_field(field_name).max_length


def _fit(value: str, limit: int) -> str:
    """Cut a value to a column's width, marking it when something was dropped."""
    if len(value) <= limit:
        return value
    return value[: max(limit - 1, 0)] + '…'


def _compose_title(company_name: str, suffix: str) -> str:
    """Build a title that fits `NotificationEvent.title`, keeping the suffix.

    The suffix carries the change itself -- the news the reader is being told.
    The company name is what they already know, so the name is what gives way.

    This is not hypothetical: `Company.nazov_UJ` allows 500 characters and live
    rows already reach 200, while a debt suffix names two sources. Together they
    overflow the 255-character title. Postgres rejects such a row rather than
    trimming it, so an unbounded title does not degrade the notification -- it
    loses it.
    """
    limit = _column_width('title')
    if len(suffix) >= limit:
        return _fit(suffix, limit)
    return _fit(company_name, limit - len(suffix)) + suffix


def _extract_orsr_person_names(profile) -> list[str]:
    """Extract person names from an OrsrCompanyProfile for comparison."""
    names: list[str] = []
    if not profile:
        return names

    # Try structured data first (RPO API format)
    payload = getattr(profile, 'raw_payload', None) or {}
    structured = payload.get('structured') if isinstance(payload, dict) else None
    if structured:
        for group_key in ('statutarny_organ', 'predstavenstvo', 'prokura', 'spolocnici'):
            for person in structured.get(group_key, []):
                if isinstance(person, dict):
                    name = (person.get('name') or '').strip()
                    if name:
                        names.append(name)
        if names:
            return names

    # Fallback: flat text fields (old format)
    for field in ('statutarny_organ', 'spolocnici', 'prokura', 'predstavenstvo', 'kontrolna_komisia'):
        raw = getattr(profile, field, None) or []
        if isinstance(raw, str):
            raw = [raw]
        for item in raw:
            text = (item or '').strip()
            if text:
                names.append(text)

    return names


def detect_executive_changes(
    company_ico: str,
    company_name: str,
    old_names: list[str],
    new_names: list[str],
) -> int:
    """Compare old and new executive names, create notifications for changes."""
    old_set = set(n.casefold().strip() for n in old_names)
    new_set = set(n.casefold().strip() for n in new_names)

    added = new_set - old_set
    removed = old_set - new_set

    if not added and not removed:
        return 0

    changes: list[str] = []
    for name in added:
        changes.append(f'Pribudol: {name}')
    for name in removed:
        changes.append(f'Odobraný: {name}')

    return create_executive_change_event(
        company_ico=company_ico,
        company_name=company_name,
        changes=changes,
    )


# The two states the product actually derives from `Company.datum_zrusenia`.
# `companies/serializers.py` and `connections/views.py` spell these the same way;
# there is no shared constant for them (yet), so this pair is the notification
# layer's own copy of the vocabulary rather than a sixth divergent one.
STATUS_ACTIVE = 'Aktívna'
STATUS_DISSOLVED = 'Vymazaná'


def _status_label(datum_zrusenia) -> str:
    """Name a company's legal status, with the date when there is one.

    The date is the actionable half: "Vymazaná" alone does not say whether the
    company was struck off last month or in 2011.
    """
    if datum_zrusenia is None:
        return STATUS_ACTIVE
    return f'{STATUS_DISSOLVED} ({datum_zrusenia:%d.%m.%Y})'


def detect_status_change(
    company_ico: str,
    company_name: str,
    old_datum_zrusenia,
    new_datum_zrusenia,
) -> int:
    """Notify watchers that a company has been dissolved.

    Only one transition is in scope: `None` -> a date. A date that moved or
    disappeared is a correction, and raising an alarm on those would turn RUZ's
    own fixes into false notifications.

    The same `old_datum_zrusenia is not None` guard is what makes a caller safe
    to repeat. Every RUZ upsert writes the new value before calling this, so on
    the next sync of the same company the stored value is already a date and
    there is nothing left to announce -- idempotent without a dedupe table.

    `new_datum_zrusenia` must be the value the caller *wrote*, not the row read
    back afterwards. Those differ whenever a writer declines to write -- see
    `registers.integrations.ruz_api.apply_ruz_dates`, which leaves a date alone
    when it cannot read the incoming one. Handing over `company.datum_zrusenia`
    there reports a stored date as though it were new, with `old=None`, and
    announces a dissolution that never happened. Likewise `old_datum_zrusenia`
    must be the value read *before* the write: passing `None` for "I did not
    look" is indistinguishable from "it was not dissolved".
    """
    if new_datum_zrusenia is None or old_datum_zrusenia is not None:
        return 0

    return create_status_change_event(
        company_ico=company_ico,
        company_name=company_name,
        old_status=_status_label(old_datum_zrusenia),
        new_status=_status_label(new_datum_zrusenia),
    )


def create_debt_change_event(
    company_id: int,
    company_ico: str,
    company_name: str,
    changes: dict[str, dict[str, Any]],
) -> int:
    """Create notification events for all users watching a company with changed debts.

    Args:
        company_id: Company DB id (unused for FK, kept for interface).
        company_ico: Company IČO.
        company_name: Company name.
        changes: Dict like {'vszp': {'old': 0, 'new': 500}, 'soc_poist': {...}}.

    Returns:
        Number of events created.
    """
    from companies.models import Watchlist
    watcher_ids = Watchlist.objects.filter(company__ico=company_ico).values_list('user_id', flat=True)
    if not watcher_ids:
        return 0

    # Build title
    parts = []
    for source, ch in changes.items():
        if ch.get('new', 0) != ch.get('old', 0):
            source_name = {'vszp': 'VšZP', 'soc_poist': 'Sociálna poisťovňa', 'tax': 'Finančná správa'}.get(source, source)
            diff = float(ch.get('new', 0)) - float(ch.get('old', 0))
            sign = '+' if diff > 0 else ''
            try:
                from core.formatting import format_currency_eur
                parts.append(f'{source_name}: {sign}{format_currency_eur(abs(diff))}')
            except Exception:
                parts.append(f'{source_name}: {sign}{diff:,.0f} €')

    if not parts:
        return 0

    name = _fit(company_name, _column_width('company_name'))
    title = _compose_title(name, f' — zmena dlhov ({", ".join(parts)})')

    # Get users with preferences enabled
    prefs = NotificationPreference.objects.filter(
        user_id__in=watcher_ids,
        email_enabled=True,
        on_debt_change=True,
    ).values_list('user_id', flat=True)

    events = [
        NotificationEvent(
            user_id=uid,
            company_ico=company_ico,
            company_name=name,
            event_type=NotificationEvent.EventType.DEBT_CHANGE,
            title=title,
            details={'changes': changes},
        )
        for uid in prefs
    ]

    if events:
        NotificationEvent.objects.bulk_create(events)
        logger.info('Created %d debt-change notifications for %s', len(events), company_ico)

    return len(events)


def create_status_change_event(
    company_ico: str,
    company_name: str,
    old_status: str,
    new_status: str,
) -> int:
    """Create notification events for company status changes."""
    from companies.models import Watchlist
    watcher_ids = Watchlist.objects.filter(company__ico=company_ico).values_list('user_id', flat=True)
    if not watcher_ids:
        return 0

    name = _fit(company_name, _column_width('company_name'))
    title = _compose_title(name, f' — zmena statusu: {old_status} → {new_status}')

    prefs = NotificationPreference.objects.filter(
        user_id__in=watcher_ids,
        email_enabled=True,
        on_status_change=True,
    ).values_list('user_id', flat=True)

    events = [
        NotificationEvent(
            user_id=uid,
            company_ico=company_ico,
            company_name=name,
            event_type=NotificationEvent.EventType.STATUS_CHANGE,
            title=title,
            details={'old_status': old_status, 'new_status': new_status},
        )
        for uid in prefs
    ]

    if events:
        NotificationEvent.objects.bulk_create(events)
        logger.info('Created %d status-change notifications for %s', len(events), company_ico)

    return len(events)


def create_executive_change_event(
    company_ico: str,
    company_name: str,
    changes: list[str],
) -> int:
    """Create notification events for executive changes."""
    from companies.models import Watchlist
    watcher_ids = Watchlist.objects.filter(company__ico=company_ico).values_list('user_id', flat=True)
    if not watcher_ids:
        return 0

    name = _fit(company_name, _column_width('company_name'))
    title = _compose_title(name, f' — zmena štatutárov ({", ".join(changes[:3])})')

    prefs = NotificationPreference.objects.filter(
        user_id__in=watcher_ids,
        email_enabled=True,
        on_executive_change=True,
    ).values_list('user_id', flat=True)

    events = [
        NotificationEvent(
            user_id=uid,
            company_ico=company_ico,
            company_name=name,
            event_type=NotificationEvent.EventType.EXECUTIVE_CHANGE,
            title=title,
            details={'changes': changes},
        )
        for uid in prefs
    ]

    if events:
        NotificationEvent.objects.bulk_create(events)

    return len(events)


def _claim_pending_events(now) -> list[int]:
    """Atomically claim up to BATCH events for sending; a single worker wins.

    Mirrors the repo's `claim_ruz_job` pattern (registers/services/sync_engine.py):
    each row is claimed by a conditional UPDATE — only the first caller can flip a
    pending / retryable-failed / stale-sending row to `sending`, so duplicate
    deliveries are impossible even across concurrent workers, and no row locks are
    held while the email is being sent. (Chosen over SELECT ... FOR UPDATE SKIP
    LOCKED because that raises NotSupportedError on SQLite, the documented local
    fallback for `make test`.)
    """
    eligible = Q(
        Q(status=NotificationEvent.Status.PENDING)
        | Q(status=NotificationEvent.Status.FAILED, attempts__lt=MAX_ATTEMPTS)
        | Q(status=NotificationEvent.Status.SENDING, claimed_at__lt=now - CLAIM_LEASE)
    )

    candidate_ids = list(
        NotificationEvent.objects.filter(eligible).order_by('pk')[:BATCH].values_list('pk', flat=True)
    )
    claimed: list[int] = []
    with transaction.atomic():
        for pk in candidate_ids:
            if len(claimed) >= BATCH:
                break
            won = NotificationEvent.objects.filter(Q(pk=pk) & eligible).update(
                status=NotificationEvent.Status.SENDING,
                claimed_at=now,
                attempts=F('attempts') + 1,
            )
            if won:
                claimed.append(pk)
    return claimed


def send_pending_email_notifications() -> int:
    """Send pending email notifications via an atomic outbox claim.

    Each run atomically claims up to BATCH events (pending, retryable `failed`,
    or stale `sending` past the claim lease) and marks them `sending` under a
    row lock. The email itself is sent *outside* the lock; an event flips to
    `sent` only after `send_mail` succeeds, otherwise to `failed` (re-attempted
    on later runs up to MAX_ATTEMPTS). Concurrent workers never double-send: a
    freshly claimed `sending` row is invisible to other runs.

    Returns:
        Number of emails sent.
    """
    now = timezone.now()
    claimed_ids = _claim_pending_events(now)
    if not claimed_ids:
        return 0

    events = (
        NotificationEvent.objects.filter(pk__in=claimed_ids, status=NotificationEvent.Status.SENDING)
        .select_related('user')
        .order_by('pk')
    )
    sent = 0
    for event in events:
        try:
            send_mail(
                subject=f'[CistaFirma] {event.title}',
                message=_build_email_body(event),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[event.user.email],
                fail_silently=False,
            )
        except Exception as exc:  # noqa: BLE001 — a failed send must not kill the batch
            logger.warning(
                'Notification email %d failed (attempt %d): %s', event.pk, event.attempts, exc
            )
            NotificationEvent.objects.filter(
                pk=event.pk, status=NotificationEvent.Status.SENDING
            ).update(
                status=NotificationEvent.Status.FAILED,
                last_error=str(exc)[:500],
            )
            continue

        NotificationEvent.objects.filter(
            pk=event.pk, status=NotificationEvent.Status.SENDING
        ).update(
            status=NotificationEvent.Status.SENT,
            sent_at=timezone.now(),
            last_error='',
        )
        sent += 1

    return sent


def _build_email_body(event: NotificationEvent) -> str:
    """Build a plain-text email body."""
    lines = [
        f'{event.title}',
        '',
        f'Firma: {event.company_name} (IČO: {event.company_ico})',
        f'Typ udalosti: {event.get_event_type_display()}',
        '',
    ]

    details = event.details or {}
    if event.event_type == NotificationEvent.EventType.DEBT_CHANGE:
        for source, ch in details.get('changes', {}).items():
            old = ch.get('old', 0)
            new = ch.get('new', 0)
            try:
                from core.formatting import format_currency_eur
                lines.append(f'  {source}: {format_currency_eur(old)} → {format_currency_eur(new)}')
            except Exception:
                lines.append(f'  {source}: {old:,.0f} € → {new:,.0f} €')
    elif event.event_type == NotificationEvent.EventType.STATUS_CHANGE:
        lines.append(f'  {details.get("old_status", "?")} → {details.get("new_status", "?")}')
    elif event.event_type == NotificationEvent.EventType.EXECUTIVE_CHANGE:
        for change in details.get('changes', []):
            lines.append(f'  {change}')

    lines.extend([
        '',
        'Zobraziť detail: https://cistafirma.sk/monitoring?ico=' + event.company_ico,
        '',
        '--',
        'CistaFirma.sk — monitoring slovenských firiem',
        'Tento email bol vygenerovaný automaticky. Ak si neželáte dostávať notifikácie, upravte si nastavenia vo svojom profile.',
    ])
    return '\n'.join(lines)
