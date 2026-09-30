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

Four conditions fail a job, and each is a control that looks alive but is not:

- `running` with a heartbeat past the watchdog's staleness threshold -- the
  worker is gone and nothing will ever finish the work;
- `queued` far past any plausible wait and never claimed -- work was accepted
  and then silently dropped;
- the newest attempt of a **beat-scheduled** job type ended `failed` -- the
  schedule is unattended, so a run that dies has nobody watching it;
- an incremental sync window that has stopped moving -- the run that is meant
  to advance it completes, so nothing looks wrong, and the source is read
  through a window that grows older every day. Two states make that age
  *meaningless* rather than stale -- Focus Mode, which switches the run off,
  and a running unrestricted full walk, which reads every change itself -- and
  both are named on screen with `--` instead of judged. Each carve-out lasts
  exactly as long as the state that justifies it.

The third is judged on the newest attempt, not on any failed one: a failing run
that the next run supersedes is history, and a gate that stays red for it would
be reporting a scar rather than a state. A later successful run clears it.

**The window runs from when an attempt ended, and a run still in flight is
always in scope.** Both halves matter for the same reason: the walk this stack
now runs takes five days. Anchored on `queued_at`, a run that long leaves the
window on its first day and its failure is never reported; anchored on
`completed_at`, the failure stays visible for the whole window after it
happens. And judging only *ended* runs would drop the walk out of the gate
entirely, leaving the newest attempt of `ruz_full` to be whichever short run
was queued last. See the comment above the query.

**On the `triggered_via='beat_schedule'` scope.** It was measured on 2026-09-10
as selecting exactly one job type (`ruz_incremental`), and that reading is now
stale in a way that changes what a FAIL means. `_run_ruz_command` stamps
`triggered_via='beat_schedule'` on **every** job it auto-enqueues -- the beat
schedule, the keeper's resume, the Django-admin buttons, and the repair
dispatches -- so the value does not mean "unattended". Measured on the
production table 2026-09-19, the three values in use are:

- `beat_schedule`: the beat schedule, the keeper, the Django-admin sync buttons,
  and every repair dispatch;
- `admin_ui`: the DRF admin API (`POST /api/admin/sync/jobs/`) and the legacy
  endpoints in `registers/views.py`, both of which enqueue the row themselves
  and pass its id on, so the stamp survives;
- `cli`: the management command run by hand.

So the filter does separate the auto-enqueued runs from two genuinely
operator-initiated paths -- which is most of what the rule wants -- but a FAIL
on a type an operator started from the Django admin is this gate reporting a run
nobody replaced, not a run nobody was watching. The filter is kept because it
still selects every unattended run. Narrowing it means giving the Django-admin
buttons an honest trigger, which is a change to the dispatch path rather than to
this gate.

Judged on `failed` only. A `paused` run is resumable and was stopped by an
operator who knows; a `cancelled` one cannot happen to a RUZ job at all, since
the admin API refuses both cancel and resume for them. Both are printed with
their status, so the boundary is visible rather than silent -- which is what
keeps "not judged" from being the same thing as "not seen".

The counters of recent jobs are printed but never judged: how many items a job
*should* process depends on the run, not on its type, so there is no honest
threshold to apply.

**The fourth condition is the answer to that gap, and it is not a counter
threshold either.** `SyncProgress.zmenene_od` is the start of the window an
incremental sync reads through, and `fetch_ruz_data` moves it forward on every
walk that reaches the end -- so its *age* is a state, not a volume. A window
older than a few days on a row whose last walk completed means the walks are
not reaching the end, whatever the job rows say the counters were.

This is the one that was missing. From 2026-09-11 the RUZ incremental resumed
from a cursor a previous run had left at the end of its own window, asked for
changes past that point, read an empty page, and stored `completed` with zero
items -- ten runs over three days, while `zmenene_od` sat on 2026-08-04 and the
register's changes went unread. Every condition above was green, and correctly
so: nothing had failed. The window was the only place the truth was written
down, and nothing was reading it.

**Except while Focus Mode is on**, which switches the RUZ beat entry off
(`fetch_ruz_data_task` is deliberately absent from `FOCUS_KEEP_TASKS`). Then no
run is meant to move the window, its age is a fact about the operator rather
than about the sync, and the condition is skipped with the reason printed --
the same carve-out `source_health` already makes for the sources Focus Mode
silences. Without it, entering Focus Mode and leaving it running for a few days
would redden the gate for a documented action and explain it with a sentence
that is false: there were no runs to report success.

Read-only: it issues SELECTs and writes nothing.

**The decision now lives in `registers.services.ops_health`** and this command
renders it, so that an exporter or an admin endpoint can read the same verdict
without re-implementing the rule. The text below is unchanged; the words `OK`,
`FAIL` and `--`, the notes, the order of the sections and the summary line are
what `scripts/local/ops_check.sh` parses.
"""

from __future__ import annotations

import sys

from django.core.management.base import BaseCommand

from registers.services.ops_health import (
    DEFAULT_FAILED_JOB_HOURS,
    DEFAULT_QUEUED_MINUTES,
    DEFAULT_WINDOW_MAX_AGE_DAYS,
    BEAT_TRIGGER,  # re-exported: the module's constants used to live here
    RECENT_LIMIT,
    WINDOW_JUDGED_STATUSES,
    env_int as _env_int,
    evaluate_sync_health,
)


class Command(BaseCommand):
    help = (
        "Report active sync jobs and fail when one is still `running` after its "
        "heartbeat went stale, has sat `queued` far past any plausible wait, is "
        "the newest run of a beat-scheduled job type and failed, or has left an "
        "incremental sync window that stopped moving."
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
        parser.add_argument(
            "--failed-job-hours",
            type=int,
            default=_env_int(
                "CISTAFIRMA_FAILED_JOB_HOURS", DEFAULT_FAILED_JOB_HOURS
            ),
            help=(
                "How far back a beat-scheduled run's failure is still the current "
                "state of that schedule (default: CISTAFIRMA_FAILED_JOB_HOURS or "
                "24). It bounds the complaint as well as opening it: past the "
                "window the job is history, and a control that cannot clear "
                "stops being read."
            ),
        )
        parser.add_argument(
            "--window-max-age-days",
            type=int,
            default=_env_int(
                "CISTAFIRMA_SYNC_WINDOW_DAYS", DEFAULT_WINDOW_MAX_AGE_DAYS
            ),
            help=(
                "How old an incremental sync's window may be before it counts as "
                "stalled (default: CISTAFIRMA_SYNC_WINDOW_DAYS or 3). Generous "
                "on purpose: the window advances on every finished walk, the "
                "fastest beat interval here is 6h, and even a million changed "
                "companies take about a day at the sync's own rate."
            ),
        )

    def handle(self, *args, **options):
        queued_minutes = options["queued_minutes"]
        failed_job_hours = options["failed_job_hours"]
        window_max_age_days = options["window_max_age_days"]

        report = evaluate_sync_health(
            queued_minutes=queued_minutes,
            failed_job_hours=failed_job_hours,
            window_max_age_days=window_max_age_days,
        )
        ctx = report.context

        self.stdout.write(
            f"  {'id':>5}  {'job_type':<18} {'status':<10} {'last sign of life':<21} "
            f"{'idle':>8}  {'processed':>9}  verdict"
        )

        for item in ctx["running"]:
            job = item["job"]
            marker = job.last_heartbeat or job.started_at
            self.stdout.write(
                f"  {job.pk:>5}  {job.job_type:<18} {job.status:<10} "
                f"{(marker.strftime('%Y-%m-%d %H:%M:%S') if marker else '-'):<21} "
                f"{item['idle']:>8}  {job.processed_items:>9}  {item['verdict']}"
            )

        for item in ctx["queued"]:
            job = item["job"]
            self.stdout.write(
                f"  {job.pk:>5}  {job.job_type:<18} {job.status:<10} "
                f"{job.queued_at.strftime('%Y-%m-%d %H:%M:%S'):<21} "
                f"{item['idle']:>8}  {'-':>9}  {item['verdict']}"
            )

        for job in ctx["recent"]:
            marker = job.completed_at or job.started_at
            self.stdout.write(
                f"  {job.pk:>5}  {job.job_type:<18} {job.status:<10} "
                f"{(marker.strftime('%Y-%m-%d %H:%M:%S') if marker else '-'):<21} "
                f"{'-':>8}  {job.processed_items:>9}  --"
            )

        if not ctx["running"] and not ctx["queued"] and not ctx["recent"]:
            self.stdout.write("  (no sync jobs have ever been recorded)")

        # Printed, never judged -- see the module docstring.
        self.stdout.write(
            "  (counters shown, not judged: how many items a job should process "
            "depends on the run, so no threshold would be honest)"
        )

        # --- The unattended schedule -------------------------------------
        self.stdout.write("")
        self.stdout.write(
            f"  beat-scheduled job types, newest attempt within "
            f"{failed_job_hours}h"
        )
        if not ctx["beat"]:
            self.stdout.write(
                "    (none recorded in the window -- the schedule is dispatching "
                "nothing, or no run is reaching the job table. Not judged here: "
                "an absence is not evidence of failure, and this control would "
                "be lying if it said it was.)"
            )
        for item in ctx["beat"]:
            job = item["job"]
            self.stdout.write(
                f"    {item['job_type']:<18} job #{job.pk:<5} {job.status:<10} "
                f"{item['age']:>8} ago  {item['verdict']}"
            )

        # --- The incremental windows -------------------------------------
        self.stdout.write("")
        self.stdout.write(
            f"  incremental sync windows (judged: window may be at most "
            f"{window_max_age_days}d old)"
        )
        if not ctx["windows"]:
            self.stdout.write(
                "    (no incremental sync has ever been recorded -- not judged, "
                "because an absence is not evidence of a stall)"
            )
        for item in ctx["windows"]:
            progress = item["progress"]
            if item["zmenene_od"] is None:
                self.stdout.write(
                    f"    {progress.sync_type:<22} {progress.status:<10} "
                    f"{'no window set':<12}  --"
                )
                continue
            self.stdout.write(
                f"    {progress.sync_type:<22} {progress.status:<10} "
                f"{str(item['zmenene_od']):<12}  {item['age_days']}d old  "
                f"{item['verdict']}"
            )

        if ctx["paused_by_focus_mode"]:
            self.stdout.write(
                "  (Focus Mode is active, which switches the RUZ beat entry "
                "off, so no run is meant to move this window -- not judged for: "
                f"{', '.join(ctx['paused_by_focus_mode'])})"
            )

        if ctx["held_by_full_walk"]:
            self.stdout.write(
                "  (a full RUZ walk is running and reads every change itself, "
                "so no incremental run is meant to move this window while it "
                f"lasts -- not judged for: {', '.join(ctx['held_by_full_walk'])})"
            )

        for note in report.notes:
            self.stdout.write(f"  ({note})")

        self.stdout.write("")
        self.stdout.write(f"Sync jobs: {report.unmet} unmet")

        if report.unmet:
            sys.exit(1)
