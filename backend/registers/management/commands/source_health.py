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

A second kind of row is judged separately: a source that refuses a *field* it
cannot read rather than failing a company outright. `ruz` records one only when
it declines to apply an unparseable date, so its rows carry no attempt count and
no success, and a format change shows up as a flood of them. Those are rendered
and judged on their own terms -- see `FIELD_REFUSAL_SOURCES`.

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

# Sources that can also *refuse* a field, mapped to what it is they could not
# read. Every source now writes one row per company per attempt carrying
# whether it succeeded -- `ruz` included, which is why it is no longer held out
# of the attempts table: it used to write a row only when it refused to apply a
# field, never a success, so counting its rows as attempts read "N attempts, 0
# succeeded" -- false in both halves.
#
# The refusal is a second, distinct failure mode, and it needs its own line: a
# format change shows up as *some* attempts succeeding while a growing set of
# companies cannot be read at all, which the attempts table cannot distinguish
# from ordinary health. So `ruz` appears in both tables -- the attempts row is
# the denominator, this one is the diagnosis -- and a source that fails both
# lines is one event, counted once.
FIELD_REFUSAL_SOURCES = {
    CompanySyncStatus.SOURCE_RUZ: "date field",
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
        "with enough attempts has produced no successful result at all, has "
        "lost one of the two answers a check can carry, or is refusing to read "
        "a field of the records it is answering with."
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
                "Attempts a source needs before its silence is judged, and "
                "companies a source needs to be refusing before that is judged "
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
                # A refusal is a company *currently* refusing, not a row that
                # once refused: the row records the latest attempt, so a
                # company whose next sync read its dates cleanly is back to
                # `consecutive_failures = 0` and drops out of this count. That
                # is what keeps the column self-clearing instead of a permanent
                # scar -- the failure mode that made writing these failures
                # unsafe while there was no success path to clear them.
                refusing=Count(
                    "id",
                    filter=Q(
                        last_attempted_at__gte=window_start,
                        consecutive_failures__gt=0,
                    ),
                ),
            )
            .order_by("source")
        )

        # Every source is an attempt source now; a source in
        # `FIELD_REFUSAL_SOURCES` gets a second line as well. See the comment
        # on that mapping.
        refusal_rows = [r for r in rows if r["source"] in FIELD_REFUSAL_SOURCES]
        attempt_rows = rows

        if attempt_rows:
            self.stdout.write(
                f"  {'source':<15} {'attempts':>8}  {'succeeded':>9}  "
                f"{'found':>7}  {'no-record':>9}  ({window_hours}h window)"
            )

        unmet = 0
        below_threshold = []
        notes = []
        failed_sources: set[str] = set()
        for row in attempt_rows:
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

            if verdict == "FAIL":
                failed_sources.add(source)

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

        for row in refusal_rows:
            source = row["source"]
            refusals = row["refusing"]
            what = FIELD_REFUSAL_SOURCES[source]
            plural = "company" if refusals == 1 else "companies"

            if refusals == 0:
                # Not silence: the source answered in the window and refused
                # nothing. Zero here is a reading, not a lack of evidence.
                verdict = "OK"
            elif refusals < min_attempts:
                verdict = f"OK (below the {min_attempts} threshold -- not judged)"
            elif source in failed_sources:
                # The attempts line already failed this source and already
                # counted it. When every attempt refuses, "no successes" and
                # "N companies refusing" are one event, and reporting it twice
                # would make the gate's own count of unmet controls wrong.
                verdict = "FAIL"
            else:
                verdict = "FAIL"
                unmet += 1

            self.stdout.write(
                f"  {source:<15} {refusals:>8} {plural} refusing a {what}  {verdict}"
            )
            if verdict == "FAIL":
                self.stdout.write(
                    f"  (source '{source}': {refusals} {plural} have a {what} that "
                    f"cannot be read -- the source's shape has changed. The "
                    f"affected values were kept, not overwritten, so the stored "
                    f"data is stale rather than gone. A company leaves this count "
                    f"as soon as a sync reads its dates cleanly again."
                )

        self.stdout.write("")
        self.stdout.write(f"Source health: {unmet} unmet")

        if unmet:
            sys.exit(1)

    def _recorded_errors(self, source: str, window_start) -> str:
        """The error types actually recorded in the window, as a suffix.

        "The parser recognises nothing" is the reading a source with no
        successes invites, and it is only one of the ways to get there: a
        source whose every attempt timed out, or was refused, reaches the
        same verdict while its parser is fine. Naming what was actually
        recorded is what stops the note sending an operator to the wrong
        file.
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
