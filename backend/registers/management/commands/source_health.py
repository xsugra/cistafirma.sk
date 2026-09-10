"""Report whether each external source is still producing usable results.

Queue depth answers "how much work is waiting"; it says nothing about whether
that work *achieves* anything. A queue can drain steadily forever against a
source that has stopped producing usable answers, and look identical to a busy
one -- which is how the VSZP scraper went a day returning `unknown` for every
company while `make ops-check` reported OK.

This command answers the other question, from data the stack already records.

A source is judged only once it has made enough attempts for silence to mean
something. Three conditions fail it, and each is a way a parser dies without
the queue noticing:

- no successful check at all -- the parser recognises nothing;
- successes, but not one of them reported a debt -- the "found" branch is gone,
  and every real debtor would be recorded as debt-free;
- successes, but not one of them reported *no* debt -- the "no record" branch
  is gone, so a company that owes nothing is never marked checked and stays due
  forever, which is how the insurance queue refills itself indefinitely.

The last two are measurable without recording anything new. For a check that
succeeded inside the window the amount the source reported is already stored on
the company, and `not_found` is authoritative with an amount of exactly zero --
so a stored zero on a recently-succeeded row *is* that source's "no record"
answer. Only sources whose answer carries an amount can be read this way; the
rest are reported with their counts and left unjudged on the split.

The counts are deliberately the signal rather than a rate. Only a few percent
of companies owe Socialna poistovna anything, so a low rate is normal; what is
never normal is a whole branch of a parser going quiet.

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
DEFAULT_MIN_SUCCESSES = 20

# Sources whose answer carries an amount, mapped to the company field that
# stores it. tasks.update_insurance_debt writes the source's amount there for
# every authoritative answer, zero included.
AMOUNT_FIELDS = {
    CompanySyncStatus.SOURCE_VSZP: "debt_vszp",
    CompanySyncStatus.SOURCE_SOCIAL: "debt_soc_poist",
}


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
        "with enough attempts has produced no successful result at all, or has "
        "lost one of the two answers a check can carry."
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
        parser.add_argument(
            "--min-successes",
            type=int,
            default=_env_int("CISTAFIRMA_SOURCE_MIN_SUCCESSES", DEFAULT_MIN_SUCCESSES),
            help=(
                "Successful checks a source needs before the found / no-record "
                "split is judged (default: CISTAFIRMA_SOURCE_MIN_SUCCESSES or 20)."
            ),
        )

    def handle(self, *args, **options):
        window_hours = options["window_hours"]
        min_attempts = options["min_attempts"]
        min_successes = options["min_successes"]
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
            f"  {'source':<15} {'attempts':>8}  {'succeeded':>9}  "
            f"{'found':>7}  {'no-record':>9}  ({window_hours}h window)"
        )

        unmet = 0
        below_threshold = []
        notes = []
        for row in rows:
            source = row["source"]
            attempts = row["attempts"]
            succeeded = row["succeeded"]
            reported = self._found_count(source, window_start) if succeeded else None

            if reported is None:
                counts = f"{'-':>7}  {'-':>9}"
            else:
                counts = f"{reported:>7}  {succeeded - reported:>9}"

            # A split is only worth judging once there are enough successes for
            # "none of them" to mean the branch is gone rather than merely
            # unlucky.
            split_is_judgeable = (
                reported is not None and succeeded >= min_successes
            )

            if attempts < min_attempts:
                below_threshold.append((source, attempts))
                verdict = "OK"
            elif succeeded == 0:
                verdict = "FAIL"
                unmet += 1
                notes.append(
                    f"source '{source}': {attempts} attempt(s) and no successful "
                    f"check at all -- the parser recognises nothing"
                    f"{self._recorded_errors(source, window_start)}"
                )
            elif split_is_judgeable and reported == 0:
                verdict = "FAIL"
                unmet += 1
                notes.append(
                    f"source '{source}': {succeeded} check(s) succeeded and not one "
                    f"reported a debt -- a company that owes would be recorded as "
                    f"debt-free"
                )
            elif split_is_judgeable and succeeded - reported == 0:
                verdict = "FAIL"
                unmet += 1
                notes.append(
                    f"source '{source}': {succeeded} check(s) succeeded and not one "
                    f"reported the source's no-record answer -- a company that owes "
                    f"nothing can never be marked checked, so it stays due forever"
                )
            else:
                verdict = "OK"

            self.stdout.write(
                f"  {source:<15} {attempts:>8}  {succeeded:>9}  {counts}  {verdict}"
            )

        for note in notes:
            self.stdout.write(f"  ({note})")

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

    def _recorded_errors(self, source: str, window_start) -> str:
        """The error types actually recorded in the window, as a suffix.

        "The parser recognises nothing" is one cause of a source failing with
        no successes, and not the only one -- RUZ refusing a date field it
        cannot read fails identically while every record it does read is
        fine. Naming what was recorded is what stops the verdict sending an
        operator to the wrong file.
        """
        rows = (
            CompanySyncStatus.objects.filter(
                source=source, last_attempted_at__gte=window_start
            )
            .exclude(last_error_type="")
            .values("last_error_type")
            .annotate(n=Count("id"))
            .order_by("-n")
        )
        parts = [f"{row['last_error_type']} x{row['n']}" for row in rows]
        return f" (recorded: {', '.join(parts)})" if parts else ""

    def _found_count(self, source: str, window_start) -> int | None:
        """How many of this source's in-window successes reported a real amount.

        None for a source whose answer carries no amount: that source cannot be
        read this way, and is left unjudged rather than guessed at.
        """
        field = AMOUNT_FIELDS.get(source)
        if field is None:
            return None
        return (
            CompanySyncStatus.objects.filter(
                source=source, last_succeeded_at__gte=window_start
            )
            .filter(**{f"company__{field}__gt": 0})
            .count()
        )
