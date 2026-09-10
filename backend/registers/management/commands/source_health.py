"""Report whether each external source is still producing usable results.

Queue depth answers "how much work is waiting"; it says nothing about whether
that work *achieves* anything. A queue can drain steadily forever against a
source that has stopped producing usable answers, and look identical to a busy
one -- which is how the VSZP scraper went a day returning `unknown` for every
company while `make ops-check` reported OK.

This command answers the other question, from data the stack already records:
across all companies, did this source succeed for *anyone* recently?

A source is judged only once it has made enough attempts for silence to mean
something, and the failing condition is deliberately **zero** successes rather
than a low rate: a low rate is normal (only a few percent of companies owe
Socialna poistovna anything), while zero means the parser no longer matches the
page. Anything between those two is a judgement call, not a control.

Read-only: it issues SELECTs and writes nothing.
"""

from __future__ import annotations

import os
import sys
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from django.utils import timezone

from registers.models import CompanySyncStatus

DEFAULT_WINDOW_HOURS = 24
DEFAULT_MIN_ATTEMPTS = 200


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


class Command(BaseCommand):
    help = (
        "Report per-source sync success over a window and fail when a source "
        "with enough attempts has produced no successful result at all."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--window-hours",
            type=int,
            default=_env_int("CISTAFIRMA_SOURCE_WINDOW_HOURS", DEFAULT_WINDOW_HOURS),
            help="How far back to look (default: CISTAFIRMA_SOURCE_WINDOW_HOURS or 24).",
        )
        parser.add_argument(
            "--min-attempts",
            type=int,
            default=_env_int("CISTAFIRMA_SOURCE_MIN_ATTEMPTS", DEFAULT_MIN_ATTEMPTS),
            help=(
                "Attempts a source needs before its silence is judged "
                "(default: CISTAFIRMA_SOURCE_MIN_ATTEMPTS or 200)."
            ),
        )

    def handle(self, *args, **options):
        window_hours = options["window_hours"]
        min_attempts = options["min_attempts"]
        window_start = timezone.now() - timedelta(hours=window_hours)

        rows = list(
            CompanySyncStatus.objects.values("source")
            .annotate(
                attempts=Count("id", filter=Q(last_attempted_at__gte=window_start)),
                succeeded=Count("id", filter=Q(last_succeeded_at__gte=window_start)),
            )
            .order_by("source")
        )

        self.stdout.write(
            f"  source          attempts  succeeded  ({window_hours}h window)"
        )

        unmet = 0
        below_threshold = []
        for row in rows:
            attempts = row["attempts"]
            succeeded = row["succeeded"]
            if attempts < min_attempts:
                below_threshold.append((row["source"], attempts))
                verdict = "OK"
            elif succeeded == 0:
                verdict = "FAIL"
                unmet += 1
            else:
                verdict = "OK"
            self.stdout.write(
                f"  {row['source']:<15} {attempts:>8}  {succeeded:>9}  {verdict}"
            )

        # A source nobody has attempted recently is not evidence of health, and
        # saying so out loud is cheaper than a reader assuming it was checked.
        for source, attempts in below_threshold:
            self.stdout.write(
                f"  (source '{source}': {attempts} attempt(s), below the "
                f"{min_attempts} threshold -- not judged)"
            )

        self.stdout.write("")
        self.stdout.write(f"Source health: {unmet} unmet")

        if unmet:
            sys.exit(1)
