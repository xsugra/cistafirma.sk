"""
Focus Mode: zastaví všetky Celery tasky a periodic beat entries,
ktoré nepatria do ORSR + financials pipeline, aby worker výkon
smeroval len na doplnenie chýbajúcich ORSR profilov a hospodárskych výsledkov.
"""
from __future__ import annotations

import logging
from typing import Iterable

from django.db import transaction
from django.utils import timezone

from backend.celery import app as celery_app
from registers.models import SyncFocusModeState

logger = logging.getLogger(__name__)


# Dotted task paths, ktoré majú naďalej bežať aj počas focus mode.
# Pozor: musí ísť o presný `name` ktorý Celery vidí (dotted path k @shared_task).
FOCUS_KEEP_TASKS: frozenset[str] = frozenset({
    "registers.tasks.sync_company_orsr_data",
    "registers.tasks.schedule_missing_orsr_sync",
    "registers.tasks.sync_company_financials_from_ruz",
    "registers.tasks.schedule_ruz_financials_sync",
})

# Queues kde keep-tasky bežia. Pri purge ich vynechávame, aby sme nezmazali
# už zaradenú prácu, ktorú chceme dobehnúť.
FOCUS_KEEP_QUEUES: frozenset[str] = frozenset({"orsr", "financials"})

# Všetky queues definované v Celery config. Mimo keep-listu sa purgnú.
ALL_KNOWN_QUEUES: frozenset[str] = frozenset({
    "celery", "ruz_full", "orsr", "financials", "insurance",
})


def _iter_task_buckets(inspect) -> Iterable[tuple[str, str, str]]:
    """Prejde active/reserved/scheduled buckets a vráti (worker, task_name, task_id)."""
    if inspect is None:
        return
    for bucket_fn in (inspect.active, inspect.reserved, inspect.scheduled):
        data = bucket_fn() or {}
        for worker, tasks in data.items():
            for t in tasks:
                # Celery "scheduled" items wrap the real task info in `request`.
                request = t.get("request") if isinstance(t, dict) else None
                source = request if isinstance(request, dict) else t
                if not isinstance(source, dict):
                    continue
                name = source.get("name")
                task_id = source.get("id")
                if name and task_id:
                    yield worker, name, task_id


def revoke_non_focus_tasks(keep: frozenset[str] = FOCUS_KEEP_TASKS) -> list[dict]:
    """Revokne všetky aktívne/rezervované/naplánované tasky mimo keep-listu."""
    inspect = celery_app.control.inspect(timeout=2.0)
    revoked: list[dict] = []
    seen_ids: set[str] = set()

    for worker, name, task_id in _iter_task_buckets(inspect):
        if name in keep or task_id in seen_ids:
            continue
        seen_ids.add(task_id)
        try:
            celery_app.control.revoke(task_id, terminate=True, signal="SIGTERM")
        except Exception as exc:
            logger.warning("Failed to revoke %s (%s): %s", name, task_id, exc)
            continue
        revoked.append({"worker": worker, "name": name, "id": task_id})
        logger.info("Revoked task %s (%s) on %s", name, task_id, worker)

    return revoked


def purge_broker_queues(
    keep_queues: frozenset[str] = FOCUS_KEEP_QUEUES,
) -> int:
    """
    Selektívne purgne len queues mimo `keep_queues`. Tým NEzahodíme
    už zaradené ORSR/financial tasky, ktoré chceme aby dobehli.

    Implementácia ide cez Kombu connection a `Queue.purge()` per-queue,
    pretože `celery_app.control.purge()` zmaže VŠETKY queues bez filtra.
    """
    queues_to_purge = sorted(set(ALL_KNOWN_QUEUES) - set(keep_queues))
    if not queues_to_purge:
        return 0

    total = 0
    try:
        with celery_app.connection_or_acquire() as conn:
            channel = conn.default_channel
            for queue_name in queues_to_purge:
                try:
                    purged = channel.queue_purge(queue_name) or 0
                    total += purged
                    logger.info("Purged %d messages from queue '%s'.", purged, queue_name)
                except Exception as exc:
                    # Queue might not exist yet — that's fine.
                    logger.debug("queue_purge('%s') failed: %s", queue_name, exc)
    except Exception as exc:
        logger.warning("Failed selective broker purge: %s", exc)
        return total
    return total


def _set_periodic_tasks_enabled(keep: frozenset[str]) -> list[dict]:
    """
    Disable všetky PeriodicTask entries mimo keep-listu.
    Vráti snapshot pôvodného stavu pre neskoršiu obnovu.
    """
    from django_celery_beat.models import PeriodicTask, PeriodicTasks

    snapshot: list[dict] = []
    qs = PeriodicTask.objects.exclude(task__in=keep)
    for pt in qs:
        snapshot.append({"id": pt.id, "enabled": pt.enabled})
        if pt.enabled:
            pt.enabled = False
            pt.save(update_fields=["enabled"])
    # Force beat scheduler reload.
    PeriodicTasks.update_changed()
    return snapshot


def _restore_periodic_tasks(snapshot: list[dict]) -> int:
    """Vráti PeriodicTask.enabled do stavu pred enter_focus_mode."""
    from django_celery_beat.models import PeriodicTask, PeriodicTasks

    restored = 0
    for entry in snapshot:
        pt_id = entry.get("id")
        prev_enabled = bool(entry.get("enabled", False))
        if pt_id is None:
            continue
        try:
            pt = PeriodicTask.objects.get(pk=pt_id)
        except PeriodicTask.DoesNotExist:
            continue
        if pt.enabled != prev_enabled:
            pt.enabled = prev_enabled
            pt.save(update_fields=["enabled"])
            restored += 1
    PeriodicTasks.update_changed()
    return restored


@transaction.atomic
def enter_focus_mode(
    user=None,
    *,
    keep: frozenset[str] = FOCUS_KEEP_TASKS,
    purge: bool = True,
) -> SyncFocusModeState:
    """
    Aktivuje focus mode:
      1. Disable periodic tasks mimo keep-listu.
      2. Revokne aktívne/prefetched tasky mimo keep-listu.
      3. (Voliteľne) selektívne purge broker queues mimo FOCUS_KEEP_QUEUES.
         Whitelisted queues (orsr, financials) zostanú nedotknuté, takže
         už nakopené ORSR/financial tasky nezahodíme.
    Idempotentné — druhé volanie na už aktívnom stave nerobí nič.
    """
    state = SyncFocusModeState.objects.select_for_update().filter(pk=1).first()
    if state is None:
        state = SyncFocusModeState.objects.create(pk=1)
        state = SyncFocusModeState.objects.select_for_update().get(pk=1)

    if state.active:
        return state

    snapshot = _set_periodic_tasks_enabled(keep)
    revoked = revoke_non_focus_tasks(keep)
    purged = purge_broker_queues() if purge else 0

    state.active = True
    state.snapshot = snapshot
    state.last_revoked = revoked
    state.activated_at = timezone.now()
    state.deactivated_at = None
    state.activated_by = user if (user and getattr(user, "is_authenticated", False)) else None
    state.notes = f"Purged {purged} pending messages from broker queues."
    state.save()
    logger.info(
        "Focus mode activated by %s; disabled %d periodic, revoked %d running, purged %d pending.",
        getattr(user, "username", "system"), len(snapshot), len(revoked), purged,
    )
    return state


@transaction.atomic
def exit_focus_mode(user=None) -> SyncFocusModeState:
    """Deaktivuje focus mode a obnoví pôvodný stav PeriodicTask entries."""
    state = SyncFocusModeState.objects.select_for_update().filter(pk=1).first()
    if state is None or not state.active:
        # Nothing to do, ensure singleton row exists for consistency.
        if state is None:
            state = SyncFocusModeState.objects.create(pk=1)
        return state

    restored = _restore_periodic_tasks(state.snapshot or [])
    state.active = False
    state.snapshot = []
    state.deactivated_at = timezone.now()
    state.save()
    logger.info(
        "Focus mode deactivated by %s; restored %d periodic tasks.",
        getattr(user, "username", "system"), restored,
    )
    return state


def focus_mode_status() -> dict:
    """Aktuálny stav pre zobrazenie v admin dashboarde."""
    state = SyncFocusModeState.load()
    active_by_name: dict[str, int] = {}
    workers: set[str] = set()
    inspect_ok = True
    try:
        inspect = celery_app.control.inspect(timeout=1.5)
        active = inspect.active() if inspect else None
        if active is None:
            inspect_ok = False
        else:
            for worker, tasks in active.items():
                workers.add(worker)
                for t in tasks:
                    name = t.get("name") if isinstance(t, dict) else None
                    if name:
                        active_by_name[name] = active_by_name.get(name, 0) + 1
    except Exception as exc:
        logger.debug("Focus mode inspect failed: %s", exc)
        inspect_ok = False

    return {
        "active": state.active,
        "activated_at": state.activated_at,
        "deactivated_at": state.deactivated_at,
        "activated_by": state.activated_by,
        "snapshot_size": len(state.snapshot or []),
        "last_revoked_count": len(state.last_revoked or []),
        "active_by_name": active_by_name,
        "workers": sorted(workers),
        "inspect_ok": inspect_ok,
        "keep_tasks": sorted(FOCUS_KEEP_TASKS),
    }
