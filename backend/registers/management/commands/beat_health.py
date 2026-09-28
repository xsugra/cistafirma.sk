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
- **a schedule that is not an interval.** All nine live entries are
  `IntervalSchedule` rows; another kind is printed with its reason rather than
  judged, because `remaining_estimate` does not mean the same thing for a
  `crontab` as for a `schedule`, and reading one as the other would produce a
  confident wrong age.

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
"""

from __future__ import annotations

import os
import sys
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django_celery_beat.models import PeriodicTask

from backend.celery import app as celery_app
from registers.models import SyncFocusModeState
from registers.services.focus_mode import FOCUS_KEEP_TASKS

# How far past its own interval a row may sit before the miss is reported. A
# healthy beat dispatches within seconds of a row coming due, so this is not
# jitter tolerance -- it is the window in which a restarted beat is not yet a
# failure, and it has to stay well below the shortest interval here (10 min) or
# the gate stops being able to see a row that has missed a whole run.
DEFAULT_GRACE_MINUTES = 15

# Tasks celery schedules for its own housekeeping. Their rows are re-saved from
# the in-memory defaults at every beat start, which is why one of them can hold
# `total_run_count=33` and `last_run_at=NULL` at the same time. See the module
# docstring.
CELERY_OWN_PREFIX = "celery."


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


def _short(period: timedelta) -> str:
    """An interval written the way the entry names it: 10m, 4h, 12h, 1d."""
    seconds = int(period.total_seconds())
    for unit, step in (("d", 86400), ("h", 3600), ("m", 60)):
        if seconds and seconds % step == 0:
            return f"{seconds // step}{unit}"
    return f"{seconds}s"


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
            # is one nobody reads. Refused rather than obeyed.
            raise CommandError(
                "--grace-minutes cannot be negative: it would make every "
                "enabled entry fail at once, which is a gate nobody can read."
            )
        grace = timedelta(minutes=grace_minutes)
        now = timezone.now()
        rows = list(PeriodicTask.objects.select_related("interval").order_by("name"))
        focus_mode_active = self._focus_mode_active()

        unmet = 0
        judged = 0
        stale = 0
        notes: list[str] = []
        celery_owned: list[str] = []
        switched_off: list[str] = []
        paused_by_focus_mode: list[str] = []
        odd_schedule: list[str] = []
        unreadable_interval: list[str] = []
        never_run: list[str] = []

        # The task registry is loaded at most once, and only once something has
        # already failed -- filling it costs a full task-module import, and the
        # sentence it produces is decoration on a verdict reached elsewhere.
        registry: set[str] | None = None
        registry_read = False

        def outlived(task: str) -> str:
            """A sentence for a row pointing at a task nothing implements."""
            nonlocal registry, registry_read
            if not registry_read:
                registry = self._registered_task_names()
                registry_read = True
            if registry is None or task in registry:
                return ""
            return (
                f" The task it names ({task}) is not registered in this app, so "
                f"it cannot run at all -- the entry has outlived the task."
            )

        self.stdout.write(
            f"  {'entry':<44} {'scheduled':<14} {'last run':<21} {'age':>8}  verdict"
        )
        if not rows:
            self.stdout.write("  (no periodic task rows exist at all)")

        for row in rows:
            period = self._period(row)
            last = row.last_run_at
            line = (
                f"  {row.name:<44} {self._schedule_label(row):<14} "
                f"{(last.strftime('%Y-%m-%d %H:%M:%S') if last else '-'):<21} "
                f"{(_humanize(now - last) if last else '-'):>8}  "
            )

            if row.task.startswith(CELERY_OWN_PREFIX):
                celery_owned.append(row.name)
                self.stdout.write(f"{line}--")
                continue

            if not row.enabled:
                if focus_mode_active and row.task not in FOCUS_KEEP_TASKS:
                    paused_by_focus_mode.append(row.name)
                else:
                    switched_off.append(row.name)
                self.stdout.write(f"{line}--")
                continue

            if period is None:
                # Two different reasons, kept apart: a schedule kind this
                # control does not read, and an interval it cannot read. One
                # line of explanation for both would have to be vague enough to
                # be nearly useless for each.
                if row.interval_id is not None:
                    unreadable_interval.append(f"{row.name} ({row.interval.period})")
                else:
                    odd_schedule.append(f"{row.name} ({self._schedule_label(row)})")
                self.stdout.write(f"{line}--")
                continue

            # `judged` counts rows that actually got a verdict, and is
            # incremented inside each of those arms rather than here: a
            # never-run row that is not yet provably late reaches this block and
            # still ends `--`, and counting it would let the "all judged entries
            # are stale" line fire on a schedule that is merely young.
            if last is None:
                # Never run. Judged only in the direction `date_changed` can
                # prove -- see the module docstring for why the other direction
                # is a hole this command states instead of papering over.
                existed = now - row.date_changed
                if existed > period + grace:
                    verdict = "FAIL"
                    judged += 1
                    unmet += 1
                    stale += 1
                    notes.append(
                        f"{row.name}: has never run (`last_run_at` is NULL) and "
                        f"the row itself is {_humanize(existed)} old -- longer "
                        f"than its {_short(period)} interval plus the "
                        f"{grace_minutes}m grace, so it has lived through a due "
                        f"date without dispatching.{outlived(row.task)}"
                    )
                else:
                    never_run.append(row.name)
                    verdict = "--"
            elif now - last > period + grace:
                verdict = "FAIL"
                judged += 1
                unmet += 1
                stale += 1
                notes.append(
                    f"{row.name}: last dispatched {_humanize(now - last)} ago "
                    f"against a {_short(period)} interval, so it is "
                    f"{_humanize(now - last - period)} past due. The entry is "
                    f"enabled, so nothing is standing it down -- it has simply "
                    f"stopped.{outlived(row.task)}"
                )
            else:
                verdict = "OK"
                judged += 1

            self.stdout.write(f"{line}{verdict}")

        # Each carve-out printed with its reason, so "not judged" cannot be read
        # as "not seen" -- the standard the sibling commands already hold to.
        if celery_owned:
            self.stdout.write(
                "  (celery's own housekeeping entries are not judged -- they are "
                "re-saved from the in-memory defaults at every beat start, so "
                "`last_run_at` stays NULL on one that has run 33 times and any "
                f"age read from it would be fiction: {', '.join(celery_owned)})"
            )
        if switched_off:
            self.stdout.write(
                "  (switched off, so not judged -- switched off is the only "
                "marker of a deliberate pause this table carries, and their last "
                "runs are in the table above, where a pause that has lasted "
                f"weeks shows as one: {', '.join(switched_off)})"
            )
        if paused_by_focus_mode:
            self.stdout.write(
                "  (Focus Mode is active, which switches every entry outside "
                "FOCUS_KEEP_TASKS off, so no run is meant while it lasts -- not "
                f"judged for: {', '.join(paused_by_focus_mode)})"
            )
        if odd_schedule:
            self.stdout.write(
                "  (not judged -- this control reads interval schedules, and a "
                "crontab's `remaining_estimate` does not mean the same thing as "
                f"an interval's, so no age is claimed for: {', '.join(odd_schedule)})"
            )
        if unreadable_interval:
            self.stdout.write(
                "  (not judged -- the interval on this row cannot be turned into "
                "a duration, because its `period` is not one of the model's "
                "choices, so there is nothing to compare the last run against: "
                f"{', '.join(unreadable_interval)})"
            )
        if never_run:
            self.stdout.write(
                "  (never run, and not provably late yet, so not judged. Read "
                "this as a hole and not as a pass: a never-run row is "
                "indistinguishable from a fresh one, because the scheduler "
                "substitutes `date_changed` for a missing `last_run_at` in "
                "memory and every beat start rewrites `date_changed` -- so a "
                "first run pushed out indefinitely by restarts is invisible "
                f"here: {', '.join(never_run)})"
            )
        # At least two, or the note claims a distinction it cannot make: with a
        # single judged row, "beat itself is not dispatching" and "this one task
        # stopped" are the same observation, and the sentence would be dressing
        # one FAIL row in a diagnosis. It is worth printing only when the
        # staleness is plural -- which is exactly when it stops being about a
        # task. (`judged` counts rows that got a verdict, so a never-run row
        # that ended `--` cannot pad it into firing.)
        if judged >= 2 and stale == judged:
            self.stdout.write(
                f"  (all {judged} judged entries are stale at once, which reads "
                "as beat itself not dispatching rather than that many tasks "
                "stopping independently)"
            )

        for note in notes:
            self.stdout.write(f"  ({note})")

        self.stdout.write("")
        self.stdout.write(f"Beat schedule: {unmet} unmet")

        if unmet:
            sys.exit(1)

    def _period(self, row: PeriodicTask) -> timedelta | None:
        """A row's own interval, or None when none can be read from it."""
        if row.interval_id is None:
            return None
        try:
            return row.interval.schedule.run_every
        except (TypeError, ValueError):
            # `IntervalSchedule.schedule` builds `timedelta(**{period: every})`,
            # so a `period` outside the model's choices raises here -- a row
            # written by hand, or by a version whose constants differed. It
            # routes into the same printed-not-judged bucket as a crontab row,
            # which is the honest answer rather than a swallowed error: no
            # interval can be read, so no age is claimed for the row.
            return None

    def _schedule_label(self, row: PeriodicTask) -> str:
        period = self._period(row)
        if period is not None:
            return _short(period)
        for field in ("crontab", "solar", "clocked"):
            if getattr(row, f"{field}_id") is not None:
                return field
        if row.interval_id is not None:
            return "interval?"
        return "-"

    def _focus_mode_active(self) -> bool:
        """Whether Focus Mode is on, read without creating the singleton row."""
        return bool(
            SyncFocusModeState.objects.filter(pk=1)
            .values_list("active", flat=True)
            .first()
        )

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
