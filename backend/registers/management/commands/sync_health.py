"""Report whether the sync jobs the stack is tracking are still moving.

The queue section of `make ops-check` reports *load* and `source_health`
reports what the external sources *achieve*. Neither looks at
`registers_syncjob`, so a job whose worker died keeps its `running` status
indefinitely and is still counted as an active import by the admin dashboard.

Job #3 was exactly that: `ruz_full_firmy`, heartbeat frozen at the instant it
started, zero items processed, fifteen days old -- and with no manual remedy,
because the API refuses both cancel and resume for RUZ jobs on purpose. The
reaper that exists for this had never once been called.

This command answers the question the other two cannot.

Two conditions fail a job, and each is a control that looks alive but is not:

- `running` with a heartbeat past the watchdog's staleness threshold -- the
  worker is gone and nothing will ever finish the work;
- `queued` far past any plausible wait and never claimed -- work was accepted
  and then silently dropped.

The counters of recent jobs are printed but never judged: how many items a job
*should* process depends on the run, not on its type, so there is no honest
threshold to apply.

Read-only: it issues SELECTs and writes nothing.
"""

from __future__ import annotations

import os
import sys
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from registers.models import SyncJob
from registers.services.sync_engine import is_stuck, stuck_heartbeat_threshold

DEFAULT_QUEUED_MINUTES = 720
RECENT_LIMIT = 8


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _humanize(delta: timedelta) -> str:
    """A short age, coarse enough to read at a glance in a gate's output."""
    seconds = max(int(delta.total_seconds()), 0)
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h {(seconds % 3600) // 60}m"
    return f"{seconds // 86400}d {(seconds % 86400) // 3600}h"


class Command(BaseCommand):
    help = (
        "Report active sync jobs and fail when one is still `running` after its "
        "heartbeat went stale, or has sat `queued` far past any plausible wait."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--queued-minutes",
            type=int,
            default=_env_int("CISTAFIRMA_QUEUED_JOB_MINUTES", DEFAULT_QUEUED_MINUTES),
            help=(
                "How long a job may sit queued and unclaimed before it counts as "
                "dropped (default: CISTAFIRMA_QUEUED_JOB_MINUTES or 720). Kept "
                "generous on purpose: a busy queue is a documented normal state."
            ),
        )

    def handle(self, *args, **options):
        queued_minutes = options["queued_minutes"]
        stuck_minutes = int(stuck_heartbeat_threshold().total_seconds() // 60)
        now = timezone.now()
        queued_cutoff = now - timedelta(minutes=queued_minutes)

        running = list(SyncJob.objects.filter(status="running").order_by("started_at"))
        queued = list(SyncJob.objects.filter(status="queued").order_by("queued_at"))
        recent = list(
            SyncJob.objects.exclude(status__in=["running", "queued"]).order_by(
                "-queued_at"
            )[:RECENT_LIMIT]
        )

        unmet = 0
        notes = []

        self.stdout.write(
            f"  {'id':>5}  {'job_type':<18} {'status':<10} {'last sign of life':<21} "
            f"{'idle':>8}  {'processed':>9}  verdict"
        )

        for job in running:
            marker = job.last_heartbeat or job.started_at
            idle = _humanize(now - marker) if marker else "-"
            # Asked, not re-derived: the gate must agree with the reaper, or it
            # reports a job as healthy that the watchdog is about to fail.
            stale = is_stuck(job, cutoff=now - timedelta(minutes=stuck_minutes))
            if stale:
                verdict = "FAIL"
                unmet += 1
                notes.append(
                    f"job #{job.pk} ({job.job_type}): running with no heartbeat for "
                    f"{idle} -- the worker is gone and nothing will finish it. The "
                    f"watchdog reaps this; the API will not cancel or resume it."
                )
            else:
                verdict = "OK"
            self.stdout.write(
                f"  {job.pk:>5}  {job.job_type:<18} {job.status:<10} "
                f"{(marker.strftime('%Y-%m-%d %H:%M:%S') if marker else '-'):<21} "
                f"{idle:>8}  {job.processed_items:>9}  {verdict}"
            )

        for job in queued:
            idle = _humanize(now - job.queued_at)
            if job.queued_at < queued_cutoff:
                verdict = "FAIL"
                unmet += 1
                notes.append(
                    f"job #{job.pk} ({job.job_type}): queued {idle} and never claimed "
                    f"-- accepted, then silently dropped (no worker is picking it up)."
                )
            else:
                verdict = "OK"
            self.stdout.write(
                f"  {job.pk:>5}  {job.job_type:<18} {job.status:<10} "
                f"{job.queued_at.strftime('%Y-%m-%d %H:%M:%S'):<21} "
                f"{idle:>8}  {'-':>9}  {verdict}"
            )

        for job in recent:
            marker = job.completed_at or job.started_at
            self.stdout.write(
                f"  {job.pk:>5}  {job.job_type:<18} {job.status:<10} "
                f"{(marker.strftime('%Y-%m-%d %H:%M:%S') if marker else '-'):<21} "
                f"{'-':>8}  {job.processed_items:>9}  --"
            )

        if not running and not queued and not recent:
            self.stdout.write("  (no sync jobs have ever been recorded)")

        for note in notes:
            self.stdout.write(f"  ({note})")

        # Printed, never judged -- see the module docstring.
        self.stdout.write(
            "  (counters shown, not judged: how many items a job should process "
            "depends on the run, so no threshold would be honest)"
        )
        self.stdout.write("")
        self.stdout.write(f"Sync jobs: {unmet} unmet")

        if unmet:
            sys.exit(1)
