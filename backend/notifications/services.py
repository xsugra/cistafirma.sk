"""
Notification service — creates events when watched companies change.
"""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db.models import QuerySet

from .models import NotificationEvent, NotificationPreference

logger = logging.getLogger(__name__)
User = get_user_model()


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

    title = f'{company_name} — zmena dlhov ({", ".join(parts)})'

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
            company_name=company_name,
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

    title = f'{company_name} — zmena statusu: {old_status} → {new_status}'

    prefs = NotificationPreference.objects.filter(
        user_id__in=watcher_ids,
        email_enabled=True,
        on_status_change=True,
    ).values_list('user_id', flat=True)

    events = [
        NotificationEvent(
            user_id=uid,
            company_ico=company_ico,
            company_name=company_name,
            event_type=NotificationEvent.EventType.STATUS_CHANGE,
            title=title,
            details={'old_status': old_status, 'new_status': new_status},
        )
        for uid in prefs
    ]

    if events:
        NotificationEvent.objects.bulk_create(events)

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

    title = f'{company_name} — zmena štatutárov ({", ".join(changes[:3])})'

    prefs = NotificationPreference.objects.filter(
        user_id__in=watcher_ids,
        email_enabled=True,
        on_executive_change=True,
    ).values_list('user_id', flat=True)

    events = [
        NotificationEvent(
            user_id=uid,
            company_ico=company_ico,
            company_name=company_name,
            event_type=NotificationEvent.EventType.EXECUTIVE_CHANGE,
            title=title,
            details={'changes': changes},
        )
        for uid in prefs
    ]

    if events:
        NotificationEvent.objects.bulk_create(events)

    return len(events)


def send_pending_email_notifications() -> int:
    """Send pending email notifications.

    Returns:
        Number of emails sent.
    """
    events = NotificationEvent.objects.filter(sent_email=False).select_related('user')[:200]
    sent = 0

    for event in events:
        try:
            send_mail(
                subject=f'[CistaFirma] {event.title}',
                message=_build_email_body(event),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[event.user.email],
                fail_silently=True,
            )
            event.sent_email = True
            event.save(update_fields=['sent_email'])
            sent += 1
        except Exception as e:
            logger.warning('Failed to send notification email %d: %s', event.id, e)

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
