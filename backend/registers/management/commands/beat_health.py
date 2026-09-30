"""Report whether the Celery beat schedule is still dispatching.

Every other control in `make ops-check` reads something a *run* left behind:
queue depth, per-source success, sync job rows, the incremental windows. None
of them can see an entry that has stopped firing, because a task that never
runs writes nothing anywhere -- no row to be stale, no error, no failed job.
That is the failure with nobody in front of it, and until now nothing watched
the entries themselves.

The truth is in the row. Real dispatch is governed by `django_celery_beat`'s
`PeriodicTask` table and not by `CELERY_BEAT_SCHEDULE` -- the scheduler
reconciles that dict *into* these rows, and a row's `queue`, `args` and
`expires` win over it -- so judging the settings dict would be judging a
configuration the dispatcher may not be following. This command reads each
row's own `last_run_at` against that row's own interval.

**Judged:** an enabled row on an interval schedule whose `last_run_at` is
older than its interval plus the grace. A healthy beat dispatches within
seconds of a row coming due, so the grace is not jitter tolerance; it is how
far behind a restart may put a run before that counts as a miss.

**Not judged, each because judging it would make the gate lie:**

- **celery's own entries** (`task` starting with `celery.`). Measured on
  production 2026-09-28: `celery.backend_cleanup` is `enabled=True`,
  `one_off=False`, `total_run_count=33` and `last_run_at IS NULL` -- neither
  one-off nor never-run, so no exemption written for those two covers it. Its
  NULL survives because `install_default_entries` re-saves it from the
  in-memory default at every beat start. Judged on `last_run_at` it fails for
  ever on a healthy system.
- **a disabled row.** Switched off is the only signal of intent this table
  carries: `enabled` is not among the `defaults` the scheduler reconciles, so
  a pause by hand survives a beat start, and Focus Mode uses exactly this
  field (`_set_periodic_tasks_enabled` sets `enabled=False` for every entry
  outside `FOCUS_KEEP_TASKS`). A disabled row is therefore not an unmet
  control, and it is printed with the age of its last run instead -- so a
  pause meant to last an afternoon and now three weeks old is *visible*
  without reddening the gate. Telling that apart from a deliberate long pause
  is not something this table can do, and a threshold invented for it would be
  a guess wearing a control's clothes.
- **a schedule that is not an interval.** Nine of the ten live rows are
  `IntervalSchedule`; the tenth is celery's own, which the prefix exemption
  above reaches first. Another kind is printed with its reason rather than
  judged, because `remaining_estimate` does not mean the same thing for a
  `crontab` as for a `schedule`, and reading one as the other would produce a
  confident wrong age. The consequence is that **nothing on production
  exercises this branch** -- which is why it has a test of its own.

**`last_run_at IS NULL`** -- a row that has never run -- is the case this
command exists for: `compute-sector-benchmarks-daily` had both an entry and a
row, and dispatched nothing for 32 h while every other control stayed green.
Its `last_run_at` cannot judge it, and the usual substitute is worse than
nothing: `ModelEntry.__init__` replaces a falsy `last_run_at` with
`date_changed or now()` **in memory**, so a never-run row presents itself to
the scheduler as one that just ran, and its first run is pushed a full
interval out. `last_run_at or date_changed` therefore hides exactly this row,
which is why this command never reads it that way.

What it reads instead is `date_changed` on its own, and only as an **upper
bound**: `date_changed` (auto_now) moves on any full save, and
`update_from_dict` rewrites every code-defined row at every beat start --
measured 2026-09-28, ten rows written inside 300 ms of a beat start while
dispatching nothing. A row cannot be older than its `date_changed`, so a NULL
row whose `date_changed` is older than its interval plus the grace has
provably lived through a due date without running, and it fails. The other
direction is a **blind spot this command states rather than hides**: a row
whose `date_changed` keeps being refreshed by beat starts never accumulates
that age, so a first run pushed out indefinitely by a beat that restarts more
often than the interval is invisible here. That sentence is printed whenever a
never-run row is in scope, so this section cannot be read as covering more
than it does.

Read-only: SELECTs only, and no `SyncFocusModeState` row is created to read
the flag (`load()` is a `get_or_create`, so it is read with a filtered
`values_list` here, exactly as `sync_health` does).

**One more thing is reported, never judged on its own:** whether the app still
implements the task the row names. A `PeriodicTask` row is keyed on the task's
*name*, so a rename leaves an enabled row pointing at a name nothing
implements and the job simply stops, with no error anywhere. That sentence is
only ever added to a staleness this command has already found, so it can
explain a failure but cannot invent one -- which matters, because reading the
registry is itself a trap: `finalize()` alone leaves it holding only celery's
own entries in a `manage.py` process, so every live row claimed the task was
gone. `_registered_task_names` carries that measurement.

**The decision now lives in `registers.services.ops_health`** and this command
renders it, so that an exporter or an admin endpoint can read the same verdict
without re-implementing the rule. The table, the five carve-out notes and the
`Beat schedule: N unmet` summary are unchanged -- `scripts/local/ops_check.sh`
parses that line. The registry reader stays here and is handed to the
evaluator, because the evaluator only needs it to decorate a verdict it has
already reached.
"""

from __future__ import annotations

import sys

from django.core.management.base import BaseCommand, CommandError

from backend.celery import app as celery_app
from registers.services.ops_health import (
    CELERY_OWN_PREFIX,  # re-exported: the module's constants used to live here
    DEFAULT_GRACE_MINUTES,
    env_int as _env_int,
    evaluate_beat_health,
)


class Command(BaseCommand):
    help = (
        "Report every PeriodicTask row whose own interval has passed without a "
        "run, so a schedule entry that stopped firing is visible instead of "
        "silent. Judged on the row's `last_run_at`, never on the settings dict."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--grace-minutes",
            type=int,
            default=_env_int("CISTAFIRMA_BEAT_GRACE_MINUTES", DEFAULT_GRACE_MINUTES),
            help=(
                "How far past its interval a row may be before the miss counts "
                "(default: CISTAFIRMA_BEAT_GRACE_MINUTES or 15). It covers a "
                "restarted beat, not scheduling jitter: beat dispatches within "
                "seconds of a row coming due, so this is the slack a restart is "
                "given before it reads as a missed run."
            ),
        )

    def handle(self, *args, **options):
        grace_minutes = options["grace_minutes"]
        if grace_minutes < 0:
            # A negative grace makes every enabled entry fail at once, which is
            # a control that is always red -- and a control that is always red
            # is one nobody reads. Refused rather than obeyed. It stays in the
            # command because it is argument validation, not a judgement.
            raise CommandError(
                "--grace-minutes cannot be negative: it would make every "
                "enabled entry fail at once, which is a gate nobody can read."
            )

        report = evaluate_beat_health(
            grace_minutes=grace_minutes,
            registry_loader=self._registered_task_names,
        )
        ctx = report.context

        self.stdout.write(
            f"  {'entry':<44} {'scheduled':<14} {'last run':<21} {'age':>8}  verdict"
        )
        if not ctx["rows"]:
            self.stdout.write("  (no periodic task rows exist at all)")

        for item in ctx["rows"]:
            row = item["row"]
            last = item["last"]
            line = (
                f"  {row.name:<44} {item['schedule_label']:<14} "
                f"{(last.strftime('%Y-%m-%d %H:%M:%S') if last else '-'):<21} "
                f"{item['age_text']:>8}  "
            )
            self.stdout.write(f"{line}{item['verdict']}")

        # Each carve-out printed with its reason, so "not judged" cannot be read
        # as "not seen" -- the standard the sibling commands already hold to.
        if ctx["celery_owned"]:
            self.stdout.write(
                "  (celery's own housekeeping entries are not judged -- they are "
                "re-saved from the in-memory defaults at every beat start, so "
                "`last_run_at` stays NULL on one that has run 33 times and any "
                f"age read from it would be fiction: {', '.join(ctx['celery_owned'])})"
            )
        if ctx["switched_off"]:
            self.stdout.write(
                "  (switched off, so not judged -- switched off is the only "
                "marker of a deliberate pause this table carries, and their last "
                "runs are in the table above, where a pause that has lasted "
                f"weeks shows as one: {', '.join(ctx['switched_off'])})"
            )
        if ctx["paused_by_focus_mode"]:
            self.stdout.write(
                "  (Focus Mode is active, which switches every entry outside "
                "FOCUS_KEEP_TASKS off, so no run is meant while it lasts -- not "
                f"judged for: {', '.join(ctx['paused_by_focus_mode'])})"
            )
        if ctx["odd_schedule"]:
            self.stdout.write(
                "  (not judged -- this control reads interval schedules, and a "
                "crontab's `remaining_estimate` does not mean the same thing as "
                f"an interval's, so no age is claimed for: {', '.join(ctx['odd_schedule'])})"
            )
        if ctx["unreadable_interval"]:
            self.stdout.write(
                "  (not judged -- the interval on this row cannot be turned into "
                "a duration, because its `period` is not one of the model's "
                "choices, so there is nothing to compare the last run against: "
                f"{', '.join(ctx['unreadable_interval'])})"
            )
        if ctx["never_run"]:
            self.stdout.write(
                "  (never run, and not provably late yet, so not judged. Read "
                "this as a hole and not as a pass: a never-run row is "
                "indistinguishable from a fresh one, because the scheduler "
                "substitutes `date_changed` for a missing `last_run_at` in "
                "memory and every beat start rewrites `date_changed` -- so a "
                "first run pushed out indefinitely by restarts is invisible "
                f"here: {', '.join(ctx['never_run'])})"
            )
        # At least two, or the note claims a distinction it cannot make: with a
        # single judged row, "beat itself is not dispatching" and "this one task
        # stopped" are the same observation, and the sentence would be dressing
        # one FAIL row in a diagnosis. It is worth printing only when the
        # staleness is plural -- which is exactly when it stops being about a
        # task. (`judged` counts rows that got a verdict, so a never-run row
        # that ended `--` cannot pad it into firing.)
        judged = report.counters.get("judged", 0)
        stale = report.counters.get("stale", 0)
        if judged >= 2 and stale == judged:
            self.stdout.write(
                f"  (all {judged} judged entries are stale at once, which reads "
                "as beat itself not dispatching rather than that many tasks "
                "stopping independently)"
            )

        for note in report.notes:
            self.stdout.write(f"  ({note})")

        self.stdout.write("")
        self.stdout.write(f"Beat schedule: {report.unmet} unmet")

        if report.unmet:
            sys.exit(1)

    def _registered_task_names(self) -> set[str] | None:
        """Every task name this app implements, or None if that cannot be read.

        `finalize()` on its own is **not** enough, and that is measured rather
        than assumed: in a `manage.py` process it left the registry holding
        celery's nine built-ins before and after the call, with none of this
        app's tasks in it -- so all ten live rows read as "nothing implements
        this", a false claim printed on rows that had run minutes earlier. The
        test process hid it, because Django's own start-up imports the task
        modules there and the answer came out right for the wrong reason.

        Importing the task modules is what a worker does and what actually
        fills the registry: 41 names, with every task in `CELERY_BEAT_SCHEDULE`
        among them.

        None when any of it raises. The answer only ever decorates a verdict
        reached from `last_run_at`, so an unreadable registry has to stay silent
        rather than become a claim -- and a broken import must certainly not
        redden a gate whose verdict does not depend on it.
        """
        try:
            celery_app.finalize()
            celery_app.loader.import_default_modules()
            return set(celery_app.tasks)
        except Exception:
            return None
