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

**The table is built from the declared vocabulary, not from the rows that
exist.** It used to group `CompanySyncStatus` by source and print whatever came
back, so a source with no rows was not printed at all -- and a missing line
reads exactly like a source that was checked and found healthy, which is the
one thing it never means. Measured 2026-09-11: `make ops-check` listed
`financials`, `social` and `vszp` and said nothing whatsoever about `ruz` or
`orsr`, a silence in which a writer that did not exist and a task that had never
run were both invisible. Every source in `CompanySyncStatus.SOURCE_CHOICES` now
gets a line, including the ones with nothing to report, and the two that have no
per-company attempts to give are declared as such (`SOURCES_WITHOUT_ATTEMPT_ROWS`)
rather than left to be inferred from an absence.

Silence is then judged per source rather than uniformly, because it does not
mean the same thing everywhere: a source whose task draws from a due-list that
cannot be empty is failing if it attempts nothing, while a source that only
records what the registry reported as changed is merely quiet. See
`SOURCES_THAT_MAY_BE_SILENT` and `SOURCES_PAUSED_BY_FOCUS_MODE`.

Read-only: it issues SELECTs and writes nothing.
"""

from __future__ import annotations

import os
import sys
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from django.utils import timezone

from registers.models import CompanySyncStatus, SyncFocusModeState

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

# Sources that never write per-company attempt rows, with the reason. They are
# rendered as a line of their own rather than omitted, because an absence in
# this table is read as health and this is the opposite: it is a source whose
# freshness nothing here measures. `fs` is a bulk ingest -- `update_fs_data`
# downloads the national dataset, matches it by ICO in one pass and
# `bulk_update`s the matches -- so it has no per-company attempt to record, and
# inventing one would be pretending to a precision that does not exist.
SOURCES_WITHOUT_ATTEMPT_ROWS = {
    CompanySyncStatus.SOURCE_FS: (
        "bulk file ingest, matched by ICO -- it never visits a company, so it "
        "records no per-company attempt and nothing here measures its freshness"
    ),
}

# Sources whose silence in the window is a legitimate reading, with the reason.
# Everything not listed here and not in `SOURCES_WITHOUT_ATTEMPT_ROWS` is
# expected to attempt, and attempting nothing fails it.
#
# `ruz` is the one that would be a false alarm: `record_ruz_date_outcome` is
# called per company the registry reported as *changed*, so a 24 h window in
# which nothing changed produces zero rows on a run that worked perfectly. Its
# absence from this table used to be indistinguishable from a dead task.
SOURCES_THAT_MAY_BE_SILENT = {
    CompanySyncStatus.SOURCE_RUZ: (
        "it records only the companies the registry reported as changed, so a "
        "quiet window means nothing changed upstream"
    ),
}

# Sources whose periodic task Focus Mode switches off. Silence from these is not
# judged *while Focus Mode is active*, because that state deliberately stops
# their scheduling -- an operator entering it would otherwise turn this gate red
# and learn to ignore it. `registers.services.focus_mode.FOCUS_KEEP_TASKS` is
# the source of truth for what keeps running; these are the ones it excludes.
SOURCES_PAUSED_BY_FOCUS_MODE = frozenset({
    CompanySyncStatus.SOURCE_VSZP,
    CompanySyncStatus.SOURCE_SOCIAL,
})


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

        rows_by_source = {
            row["source"]: row
            for row in CompanySyncStatus.objects.values("source")
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
        }

        # Both tables are driven by the declared vocabulary rather than by the
        # rows that came back, so a source with nothing to report is a line
        # saying zero instead of a line that is not there. A zero-row source
        # used to be absent from *both* tables -- including `ruz`, which is in
        # `FIELD_REFUSAL_SOURCES`, so the refusal table could not tell "no
        # company is refusing" from "the refusal counter is gone".
        declared_sources = [value for value, _label in CompanySyncStatus.SOURCE_CHOICES]
        attempt_rows = [
            rows_by_source.get(source)
            or {"source": source, "attempts": 0, "succeeded": 0, "refusing": 0}
            for source in declared_sources
        ]
        refusal_rows = [
            row for row in attempt_rows if row["source"] in FIELD_REFUSAL_SOURCES
        ]

        focus_mode_active = self._focus_mode_active()

        self.stdout.write(
            f"  {'source':<15} {'attempts':>8}  {'succeeded':>9}  "
            f"{'found':>7}  {'no-record':>9}  ({window_hours}h window)"
        )

        unmet = 0
        below_threshold = []
        notes = []
        unmeasured = []
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

            if source in SOURCES_WITHOUT_ATTEMPT_ROWS:
                # Nothing here is a reading about the source. Saying "OK" would
                # claim a check that this command cannot make, so it says so.
                verdict = "not measured"
                unmeasured.append(
                    f"source '{source}': {SOURCES_WITHOUT_ATTEMPT_ROWS[source]}"
                )
            elif attempts == 0:
                reason = self._silence_reason(
                    source, focus_mode_active=focus_mode_active
                )
                if reason is None:
                    verdict = "FAIL"
                    unmet += 1
                    notes.append(
                        f"source '{source}': no attempt at all in the last "
                        f"{window_hours}h -- its task draws from a due-list that "
                        f"is not empty, so silence means it did not run or did "
                        f"not write"
                    )
                else:
                    # A reading, not a lack of evidence -- and named, so a
                    # reader cannot mistake it for one.
                    verdict = "OK"
                    notes.append(
                        f"source '{source}': no attempt in the last "
                        f"{window_hours}h, which is expected -- {reason}"
                    )
            elif attempts < min_attempts:
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

        # Printed on every run, not only when something looks wrong: a line with
        # no numbers needs its reason attached to it, or the next reader counts
        # it as a source that was checked.
        for note in unmeasured:
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

    def _focus_mode_active(self) -> bool:
        """Whether Focus Mode is on, read without creating the singleton row.

        `SyncFocusModeState.load()` is `get_or_create`, so using it here would
        make this command write on a fresh database -- and it says of itself
        that it issues SELECTs and writes nothing.
        """
        return bool(
            SyncFocusModeState.objects.filter(pk=1)
            .values_list("active", flat=True)
            .first()
        )

    def _silence_reason(self, source: str, *, focus_mode_active: bool) -> str | None:
        """Why this source may legitimately have attempted nothing, or None.

        `None` is the judgement, not a missing value: a source whose task draws
        from a due-list that is never empty has no way to be idle by accident,
        so silence there is a finding rather than a reading. Everything that can
        be quiet for an ordinary reason is named in one of the two mappings
        above, so the distinction is a fact written down rather than a guess
        made per run.
        """
        if source in SOURCES_THAT_MAY_BE_SILENT:
            return SOURCES_THAT_MAY_BE_SILENT[source]
        if focus_mode_active and source in SOURCES_PAUSED_BY_FOCUS_MODE:
            return (
                "Focus Mode is active, which switches this source's periodic "
                "task off until it is exited"
            )
        return None

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
