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

**The decision now lives in `registers.services.ops_health`** and this command
renders it, so that an exporter or an admin endpoint can read the same verdict
without re-implementing the rule. Its four output states (`FAIL`, `OK`,
`OK (below the N threshold -- not judged)` and `not measured`), the order of
its tables and notes, and the `Source health: N unmet` summary are unchanged --
`scripts/local/ops_check.sh` parses that line.
"""

from __future__ import annotations

import sys

from django.core.management.base import BaseCommand

from registers.services.ops_health import (
    AMOUNT_FIELDS,  # re-exported: the module's constants used to live here
    DEFAULT_MIN_ATTEMPTS,
    DEFAULT_MIN_SUCCESSES,
    DEFAULT_WINDOW_HOURS,
    FIELD_REFUSAL_SOURCES,
    LISTING_FIELDS,
    SOURCES_PAUSED_BY_FOCUS_MODE,
    SOURCES_THAT_MAY_BE_SILENT,
    SOURCES_WITHOUT_ATTEMPT_ROWS,
    env_int as _env_int,
    evaluate_source_health,
)


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

        report = evaluate_source_health(
            window_hours=window_hours,
            min_attempts=min_attempts,
            min_successes=min_successes,
        )
        ctx = report.context

        self.stdout.write(
            f"  {'source':<15} {'attempts':>8}  {'succeeded':>9}  "
            f"{'found':>7}  {'no-record':>9}  ({window_hours}h window)"
        )

        for row in ctx["attempt_rows"]:
            reported = row["reported"]
            if reported is None:
                counts = f"{'-':>7}  {'-':>9}"
            else:
                counts = f"{reported:>7}  {row['succeeded'] - reported:>9}"
            self.stdout.write(
                f"  {row['source']:<15} {row['attempts']:>8}  "
                f"{row['succeeded']:>9}  {counts}  {row['verdict']}"
            )

        for note in report.notes:
            self.stdout.write(f"  ({note})")

        # Printed on every run, not only when something looks wrong: a line with
        # no numbers needs its reason attached to it, or the next reader counts
        # it as a source that was checked.
        for note in ctx["unmeasured"]:
            self.stdout.write(f"  ({note})")

        # A source nobody has attempted recently is not evidence of health, and
        # saying so out loud is cheaper than a reader assuming it was checked.
        for source, attempts in ctx["below_threshold"]:
            self.stdout.write(
                f"  (source '{source}': {attempts} attempt(s), below the "
                f"{min_attempts} threshold -- not judged)"
            )

        for row in ctx["refusal_rows"]:
            source = row["source"]
            refusals = row["refusals"]
            plural = row["plural"]
            what = row["what"]
            verdict = row["verdict"]

            self.stdout.write(
                f"  {source:<15} {refusals:>8} "
                f"{plural} refusing a {what}  {verdict}"
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
        self.stdout.write(f"Source health: {report.unmet} unmet")

        if report.unmet:
            sys.exit(1)
