"""Machine-readable operational health verdicts, shared by the gates.

Three management commands answer three operational questions and each of them
already owns a rule that must not exist twice:

- `sync_health`   -- is an active sync job really active, and is the
  incremental window still moving?
- `source_health` -- is each external source still producing usable results?
- `beat_health`   -- is every celery-beat entry still dispatching?

Until now each answer lived inside a `BaseCommand.handle()` (or an instance
method beside it) and ended in `sys.exit(1)`, so the only thing that could
consume a verdict was a shell script reading the command's stdout. That is fine
for `make ops-check` and useless for anything else: an exporter, an admin
endpoint or a test could not ask "is this unmet" without re-implementing the
rule -- which is exactly the defect this repository keeps paying for.

So the decision is lifted here and the commands become renderers. **The
verdicts are the contract; the text is the renderer's business.** Two rules:

- `not_judged` is not `ok`. Focus Mode switching a source off, a live full RUZ
  walk superseding an incremental window, a switched-off beat entry, a source
  below its attempt threshold: none of those is evidence of health, and
  collapsing any of them into `ok` makes a control that reddens on a documented
  operator action. Every `Verdict` therefore carries one of three states and
  `Report.unmet` counts only `fail`.
- The subject vocabulary is the *declared* one. `source_health` iterates
  `CompanySyncStatus.SOURCE_CHOICES` and `beat_health` iterates the
  `PeriodicTask` rows so that a source with no rows is a line saying zero
  rather than a line that is not there; a metric built from `values("source")`
  would read a writer that never ran as a healthy source. The same principle is
  what the exporter's `cistafirma_ops_subject` metric needs.

Nothing here writes: every query is a SELECT, and Focus Mode is read through a
filtered `values_list` (never `SyncFocusModeState.load()`, which is a
`get_or_create`) so that asking a question cannot create a row.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Callable, Mapping

from django.db.models import Count, Q
from django.utils import timezone
from django_celery_beat.models import PeriodicTask

from registers.models import (
    CompanySyncStatus,
    SyncFocusModeState,
    SyncJob,
    SyncProgress,
)
from registers.services.focus_mode import FOCUS_KEEP_TASKS
from registers.services.sync_engine import is_stuck, stuck_heartbeat_threshold

# ---------------------------------------------------------------------------
# Domains and verdict states
# ---------------------------------------------------------------------------

# The three questions, named after the commands that ask them. They are metric
# label values, so they are short and stable rather than derived from a class
# name that could move.
DOMAIN_SYNC = "sync"
DOMAIN_SOURCE = "source"
DOMAIN_BEAT = "beat"

STATUS_OK = "ok"
STATUS_FAIL = "fail"
STATUS_NOT_JUDGED = "not_judged"

STATUSES = (STATUS_OK, STATUS_FAIL, STATUS_NOT_JUDGED)

# Worst-of ordering, used when several verdicts share one subject (a job type
# with both a stuck and a healthy run) and only one series may be emitted. A
# `fail` outranks an unknown, which outranks a pass: the collapsed series has to
# be the pessimistic reading, or the collapse would hide the very finding the
# verdict carries.
_STATUS_RANK = {STATUS_OK: 0, STATUS_NOT_JUDGED: 1, STATUS_FAIL: 2}


def worst_status(statuses) -> str:
    """The pessimistic reading of several statuses, or `not_judged` for none."""
    best = None
    for status in statuses:
        if best is None or _STATUS_RANK[status] > _STATUS_RANK[best]:
            best = status
    return best if best is not None else STATUS_NOT_JUDGED


# ---------------------------------------------------------------------------
# Shared vocabulary and thresholds
# ---------------------------------------------------------------------------

DEFAULT_QUEUED_MINUTES = 720
DEFAULT_FAILED_JOB_HOURS = 24
DEFAULT_WINDOW_MAX_AGE_DAYS = 3
RECENT_LIMIT = 8

# The statuses in which an incremental window is expected to be moving. A
# `paused` row was stopped by an operator who knows, and a `running` one is a
# walk in progress -- both legitimately hold an old window, and judging either
# would be reporting on the operator rather than on the sync.
WINDOW_JUDGED_STATUSES = ("completed", "idle")

# The one trigger whose runs nobody is watching. See `sync_health`'s docstring
# for what the value does and does not mean on this stack.
BEAT_TRIGGER = "beat_schedule"

DEFAULT_WINDOW_HOURS = 24
DEFAULT_MIN_ATTEMPTS = 200
DEFAULT_MIN_SUCCESSES = 20

DEFAULT_GRACE_MINUTES = 15

# Tasks celery schedules for its own housekeeping. Their rows are re-saved from
# the in-memory defaults at every beat start, which is why one of them can hold
# `total_run_count=33` and `last_run_at=NULL` at the same time.
CELERY_OWN_PREFIX = "celery."

# Sources whose answer carries an amount, mapped to the company field that
# stores it. `tasks.update_insurance_debt` writes the source's amount there for
# every authoritative answer, zero included.
AMOUNT_FIELDS = {
    CompanySyncStatus.SOURCE_VSZP: "debt_vszp",
    CompanySyncStatus.SOURCE_SOCIAL: "debt_soc_poist",
}

# Sources whose answer can be a listing *without* an amount, mapped to the
# company field that records it. See `source_health`'s docstring.
LISTING_FIELDS = {
    CompanySyncStatus.SOURCE_SOCIAL: "social_listed_without_amount",
}

# Sources that can also *refuse* a field, mapped to what it is they could not
# read. A refusal is a second, distinct failure mode and needs its own line; a
# source that fails both lines is one event, counted once.
FIELD_REFUSAL_SOURCES = {
    CompanySyncStatus.SOURCE_RUZ: "date field",
}

# Sources that never write per-company attempt rows, with the reason. They are
# rendered as a line of their own rather than omitted, because an absence in
# this table is read as health and this is the opposite.
SOURCES_WITHOUT_ATTEMPT_ROWS = {
    CompanySyncStatus.SOURCE_FS: (
        "bulk file ingest, matched by ICO -- it never visits a company, so it "
        "records no per-company attempt and nothing here measures its freshness"
    ),
}

# Sources whose silence in the window is a legitimate reading, with the reason.
SOURCES_THAT_MAY_BE_SILENT = {
    CompanySyncStatus.SOURCE_RUZ: (
        "it records only the companies the registry reported as changed, so a "
        "quiet window means nothing changed upstream"
    ),
}

# Sources whose periodic task Focus Mode switches off. Silence from these is not
# judged *while Focus Mode is active*.
SOURCES_PAUSED_BY_FOCUS_MODE = frozenset({
    CompanySyncStatus.SOURCE_VSZP,
    CompanySyncStatus.SOURCE_SOCIAL,
})


# ---------------------------------------------------------------------------
# Small shared helpers
# ---------------------------------------------------------------------------


def env_int(name: str, default: int) -> int:
    """An integer from the environment, or `default` when absent or unusable."""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def humanize(delta: timedelta) -> str:
    """A short age, coarse enough to read at a glance in a gate's output."""
    seconds = max(int(delta.total_seconds()), 0)
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h {(seconds % 3600) // 60}m"
    return f"{seconds // 86400}d {(seconds % 86400) // 3600}h"


def short_period(period: timedelta) -> str:
    """An interval written the way the entry names it: 10m, 4h, 12h, 1d."""
    seconds = int(period.total_seconds())
    for unit, step in (("d", 86400), ("h", 3600), ("m", 60)):
        if seconds and seconds % step == 0:
            return f"{seconds // step}{unit}"
    return f"{seconds}s"


def focus_mode_active_readonly() -> bool:
    """Whether Focus Mode is on, read without creating the singleton row.

    `SyncFocusModeState.load()` is a `get_or_create`, so calling it from a
    read-only control would make that control write on a fresh database. All
    three gates need the same reading, so it lives here once rather than three
    times; the three copies are what this helper replaced.
    """
    return bool(
        SyncFocusModeState.objects.filter(pk=1)
        .values_list("active", flat=True)
        .first()
    )


# ---------------------------------------------------------------------------
# Verdicts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Verdict:
    """One judged thing, in the shape a metric can be built from.

    `subject` is a *stable, low-cardinality* label -- a source name, a job type,
    a beat entry -- never a `SyncJob.pk` or a company id. `reason` is a short
    machine code for the branch that produced the status, so an alert can
    distinguish "no attempt at all" from "attempts but no success" without
    parsing `detail`.
    """

    domain: str
    subject: str
    status: str
    reason: str
    detail: str = ""
    values: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ValueError(
                f"Verdict.status must be one of {STATUSES}, got {self.status!r}"
            )


@dataclass(frozen=True)
class Report:
    """One domain's verdicts plus everything its renderer needs.

    `notes`, `counters` and `context` exist for the commands: they hold exactly
    what the previous `handle()` built inline (the notes in the order they were
    appended, the rendered-table rows, the carve-out lists), so the tables,
    notes and counters on screen are unchanged. The machine-readable part is
    `verdicts`.
    """

    domain: str
    verdicts: tuple[Verdict, ...] = ()
    notes: tuple[str, ...] = ()
    counters: Mapping[str, int] = field(default_factory=dict)
    context: Mapping[str, Any] = field(default_factory=dict)

    @property
    def unmet(self) -> int:
        """How many verdicts failed -- the number the gate's exit code uses."""
        return sum(1 for verdict in self.verdicts if verdict.status == STATUS_FAIL)

    @property
    def failed(self) -> tuple[Verdict, ...]:
        return tuple(v for v in self.verdicts if v.status == STATUS_FAIL)

    def status_by_subject(self) -> dict[str, str]:
        """One status per subject: the pessimistic reading when several apply."""
        grouped: dict[str, list[str]] = {}
        for verdict in self.verdicts:
            grouped.setdefault(verdict.subject, []).append(verdict.status)
        return {
            subject: worst_status(statuses)
            for subject, statuses in grouped.items()
        }


def declared_sync_subjects() -> list[str]:
    """Every job type the `SyncJob` vocabulary declares.

    Taken from the model's choices rather than from the rows that exist, for the
    same reason `source_health` iterates `SOURCE_CHOICES`: a job type with no
    rows must be a series saying "nothing to judge", not a series that is absent.
    """
    return [value for value, _label in SyncJob.JOB_TYPE_CHOICES]


def declared_source_subjects() -> list[str]:
    """Every source the `CompanySyncStatus` vocabulary declares."""
    return [value for value, _label in CompanySyncStatus.SOURCE_CHOICES]


# ---------------------------------------------------------------------------
# sync_health
# ---------------------------------------------------------------------------


def _full_walk_holding_windows(now) -> SyncProgress | None:
    """The live unrestricted full walk, which supersedes the windows.

    While it runs, no incremental run is meant to move the window: every RUZ job
    shares the one `ruz:global` slot, so `enqueue_ruz_job` makes the 6-hourly
    `fetch_ruz_data_task` bounce off it and the task waits in its worker's
    reserve instead of running. Its age is therefore not staleness.

    **Only `full`, not every full-ish walk.** `full_companies` reads companies
    alone, and an incremental window covers SZCO too, so it does *not* supersede
    the window; suppressing there would hide real staleness.

    **The walk has to be alive.** `record_progress` writes `last_activity` every
    hundredth record, so requiring it inside the watchdog's staleness threshold
    is what stops this carve-out outliving the walk it describes -- and a gate
    that has gone quiet for ever is the very defect `sync_health` exists to
    catch.
    """
    walk = (
        SyncProgress.objects.filter(sync_type="full", status="running")
        .order_by("-last_activity")
        .first()
    )
    if walk is None or walk.last_activity is None:
        return None
    if now - walk.last_activity > stuck_heartbeat_threshold():
        return None
    return walk


def evaluate_sync_health(
    *,
    queued_minutes: int = DEFAULT_QUEUED_MINUTES,
    failed_job_hours: int = DEFAULT_FAILED_JOB_HOURS,
    window_max_age_days: int = DEFAULT_WINDOW_MAX_AGE_DAYS,
    now=None,
) -> Report:
    """Judge active sync jobs, the unattended schedule and the sync windows."""
    if now is None:
        now = timezone.now()
    stuck_minutes = int(stuck_heartbeat_threshold().total_seconds() // 60)
    queued_cutoff = now - timedelta(minutes=queued_minutes)
    failed_cutoff = now - timedelta(hours=failed_job_hours)

    running = list(SyncJob.objects.filter(status="running").order_by("started_at"))
    queued = list(SyncJob.objects.filter(status="queued").order_by("queued_at"))
    recent = list(
        SyncJob.objects.exclude(status__in=["running", "queued"]).order_by(
            "-queued_at"
        )[:RECENT_LIMIT]
    )

    verdicts: list[Verdict] = []
    notes: list[str] = []

    running_rows = []
    for job in running:
        marker = job.last_heartbeat or job.started_at
        idle = humanize(now - marker) if marker else "-"
        # Asked, not re-derived: the gate must agree with the reaper, or it
        # reports a job as healthy that the watchdog is about to fail.
        stale = is_stuck(job, cutoff=now - timedelta(minutes=stuck_minutes))
        values: dict[str, float] = {}
        if marker is not None:
            values["heartbeat_age_seconds"] = (now - marker).total_seconds()
        if stale:
            verdict_text = "FAIL"
            detail = (
                f"job #{job.pk} ({job.job_type}): running with no heartbeat for "
                f"{idle} -- the worker is gone and nothing will finish it. The "
                f"watchdog reaps this; the API will not cancel or resume it."
            )
            notes.append(detail)
            verdicts.append(
                Verdict(
                    domain=DOMAIN_SYNC,
                    subject=job.job_type,
                    status=STATUS_FAIL,
                    reason="stuck_running",
                    detail=detail,
                    values=values,
                )
            )
        else:
            verdict_text = "OK"
            verdicts.append(
                Verdict(
                    domain=DOMAIN_SYNC,
                    subject=job.job_type,
                    status=STATUS_OK,
                    reason="running",
                    detail=f"job #{job.pk} ({job.job_type}) is running and beating",
                    values=values,
                )
            )
        running_rows.append({"job": job, "idle": idle, "verdict": verdict_text})

    queued_rows = []
    for job in queued:
        idle = humanize(now - job.queued_at)
        values = {"queued_age_seconds": (now - job.queued_at).total_seconds()}
        if job.queued_at < queued_cutoff:
            verdict_text = "FAIL"
            detail = (
                f"job #{job.pk} ({job.job_type}): queued {idle} and never claimed "
                f"-- accepted, then silently dropped (no worker is picking it up)."
            )
            notes.append(detail)
            verdicts.append(
                Verdict(
                    domain=DOMAIN_SYNC,
                    subject=job.job_type,
                    status=STATUS_FAIL,
                    reason="queued_unclaimed",
                    detail=detail,
                    values=values,
                )
            )
        else:
            verdict_text = "OK"
            verdicts.append(
                Verdict(
                    domain=DOMAIN_SYNC,
                    subject=job.job_type,
                    status=STATUS_OK,
                    reason="queued_recent",
                    detail=f"job #{job.pk} ({job.job_type}) is queued and recent",
                    values=values,
                )
            )
        queued_rows.append({"job": job, "idle": idle, "verdict": verdict_text})

    # --- The unattended schedule -----------------------------------------
    # Every type the beat dispatches, judged on its newest attempt inside the
    # window. Ordered by `-queued_at` and de-duplicated in Python rather than
    # with a `Max()` subquery: the table holds tens of rows, and reading it
    # whole keeps the rule legible.
    #
    # The window is anchored on when an attempt *ended*, not on when it was
    # queued, and a run that has not ended is always in scope. A `queued_at`
    # anchor put the five-day full walk out of reach of this control for all but
    # its first day -- the one run this gate most needs to see, invisible exactly
    # when it matters.
    beat_attempts = list(
        SyncJob.objects.filter(
            Q(triggered_via=BEAT_TRIGGER),
            Q(completed_at__gte=failed_cutoff) | Q(completed_at__isnull=True),
        ).order_by("-queued_at")
    )
    newest_beat: dict[str, SyncJob] = {}
    for job in beat_attempts:
        newest_beat.setdefault(job.job_type, job)

    beat_rows = []
    for job_type, job in sorted(newest_beat.items()):
        marker = job.completed_at or job.started_at or job.queued_at
        age = humanize(now - marker)
        values = {"beat_age_seconds": (now - marker).total_seconds()}
        if job.status == "failed":
            verdict_text = "FAIL"
            # Collapsed to one line: the gate's output is read a line at a time,
            # and an error with newlines in it would read as several notes, only
            # the first of which is attached to the verdict.
            error = " ".join((job.last_error or "").split())[:300]
            detail = (
                f"job #{job.pk} ({job_type}): the newest beat-scheduled run "
                f"failed {age} ago, so nothing has replaced the data it was "
                f"meant to fetch. Last error: {error or '(none recorded)'}"
            )
            notes.append(detail)
            verdicts.append(
                Verdict(
                    domain=DOMAIN_SYNC,
                    subject=job_type,
                    status=STATUS_FAIL,
                    reason="beat_attempt_failed",
                    detail=detail,
                    values=values,
                )
            )
        else:
            verdict_text = "OK"
            verdicts.append(
                Verdict(
                    domain=DOMAIN_SYNC,
                    subject=job_type,
                    status=STATUS_OK,
                    reason="beat_attempt_recent",
                    detail=(
                        f"job #{job.pk} ({job_type}) is the newest beat-scheduled "
                        f"attempt and did not fail"
                    ),
                    values=values,
                )
            )
        beat_rows.append(
            {"job_type": job_type, "job": job, "age": age, "verdict": verdict_text}
        )

    # --- The incremental windows -------------------------------------
    windows = list(
        SyncProgress.objects.filter(sync_type__startswith="incremental").order_by(
            "sync_type"
        )
    )
    focus_mode_active = focus_mode_active_readonly()
    paused_by_focus_mode: list[str] = []
    full_walk = _full_walk_holding_windows(now)
    held_by_full_walk: list[str] = []

    window_rows = []
    for progress in windows:
        if progress.zmenene_od is None:
            # Written by a run that never got as far as choosing a window.
            # Nothing to age, so nothing to judge.
            window_rows.append(
                {
                    "progress": progress,
                    "zmenene_od": None,
                    "age_days": None,
                    "verdict": "--",
                }
            )
            verdicts.append(
                Verdict(
                    domain=DOMAIN_SYNC,
                    subject=progress.sync_type,
                    status=STATUS_NOT_JUDGED,
                    reason="no_window_set",
                    detail=(
                        f"sync window '{progress.sync_type}' has no window set, so "
                        f"there is no age to judge"
                    ),
                )
            )
            continue

        age_days = (now.date() - progress.zmenene_od).days
        judged = progress.status in WINDOW_JUDGED_STATUSES
        detail = ""
        if judged and focus_mode_active:
            verdict_text = "--"
            status = STATUS_NOT_JUDGED
            reason = "focus_mode"
            paused_by_focus_mode.append(progress.sync_type)
        elif judged and full_walk is not None:
            verdict_text = "--"
            status = STATUS_NOT_JUDGED
            reason = "full_walk"
            held_by_full_walk.append(progress.sync_type)
        elif judged and age_days > window_max_age_days:
            verdict_text = "FAIL"
            status = STATUS_FAIL
            reason = "window_stalled"
            # Two different states look identical from the date alone, and the
            # sentence has to be true for the one it describes:
            #
            # - the walk completes over nothing (the original bug), or
            # - the walk deliberately holds the window because items are failing.
            #
            # Both mean the source's changes go unread, so both fail. But saying
            # "every run since has reported success" about the second would be
            # false -- it reported errors, on purpose, and stopped.
            if progress.total_errors:
                error = " ".join((progress.last_error or "").split())[:200]
                cause = (
                    f"and the walks are finishing with {progress.total_errors} "
                    f"item error(s), so the window is being held on purpose "
                    f"rather than silently stalled"
                    + (f". Last recorded error: {error}" if error else "")
                )
            else:
                cause = (
                    "and every run since has reported success without moving "
                    "it -- so the source is being read through a window that "
                    "no longer covers its changes. The runs themselves are "
                    "green; this is the only row that records it"
                )
            detail = (
                f"sync window '{progress.sync_type}': the last completed walk "
                f"left the window starting {progress.zmenene_od} ({age_days}d "
                f"old) {cause}."
            )
            notes.append(detail)
        elif not judged:
            verdict_text = "--"
            status = STATUS_NOT_JUDGED
            reason = "window_status_not_judged"
        else:
            verdict_text = "OK"
            status = STATUS_OK
            reason = "window_moving"

        if not detail:
            detail = (
                f"sync window '{progress.sync_type}' is {age_days}d old "
                f"(status {progress.status})"
            )
        window_rows.append(
            {
                "progress": progress,
                "zmenene_od": progress.zmenene_od,
                "age_days": age_days,
                "verdict": verdict_text,
            }
        )
        verdicts.append(
            Verdict(
                domain=DOMAIN_SYNC,
                subject=progress.sync_type,
                status=status,
                reason=reason,
                detail=detail,
                values={"window_age_days": age_days},
            )
        )

    report = Report(
        domain=DOMAIN_SYNC,
        verdicts=tuple(verdicts),
        notes=tuple(notes),
        counters={
            "running": len(running),
            "queued": len(queued),
            "recent": len(recent),
            "beat_types": len(newest_beat),
            "windows": len(windows),
        },
        context={
            "running": running_rows,
            "queued": queued_rows,
            "recent": recent,
            "beat": beat_rows,
            "windows": window_rows,
            "focus_mode_active": focus_mode_active,
            "paused_by_focus_mode": paused_by_focus_mode,
            "held_by_full_walk": held_by_full_walk,
            "queued_minutes": queued_minutes,
            "failed_job_hours": failed_job_hours,
            "window_max_age_days": window_max_age_days,
        },
    )
    return report


# ---------------------------------------------------------------------------
# source_health
# ---------------------------------------------------------------------------


def _found_count(source: str, window_start) -> int | None:
    """How many of this source's in-window successes recognised a company.

    None for a source whose answer carries no amount: that source cannot be read
    this way, and is left unjudged rather than guessed at.

    "Recognised" is the amount column *or* the listing flag, because for
    Socialna poistovna a company the register lists without a sum is a company
    the parser read correctly. See `LISTING_FIELDS`.
    """
    field = AMOUNT_FIELDS.get(source)
    if field is None:
        return None
    found = Q(**{f"company__{field}__gt": 0})
    listed_field = LISTING_FIELDS.get(source)
    if listed_field:
        found |= Q(**{f"company__{listed_field}": True})
    return (
        CompanySyncStatus.objects.filter(
            source=source, last_succeeded_at__gte=window_start
        )
        .filter(found)
        .count()
    )


def _recorded_errors(source: str, window_start) -> str:
    """The error types actually recorded in the window, as a suffix.

    "The parser recognises nothing" is the reading a source with no successes
    invites, and it is only one of the ways to get there: a source whose every
    attempt timed out, or was refused, reaches the same verdict while its parser
    is fine. Naming what was actually recorded is what stops the note sending an
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


def _silence_reason(source: str, *, focus_mode_active: bool) -> str | None:
    """Why this source may legitimately have attempted nothing, or None.

    `None` is the judgement, not a missing value: a source whose task draws from
    a due-list that is never empty has no way to be idle by accident, so silence
    there is a finding rather than a reading. Everything that can be quiet for an
    ordinary reason is named in one of the two mappings above, so the distinction
    is a fact written down rather than a guess made per run.
    """
    if source in SOURCES_THAT_MAY_BE_SILENT:
        return SOURCES_THAT_MAY_BE_SILENT[source]
    if focus_mode_active and source in SOURCES_PAUSED_BY_FOCUS_MODE:
        return (
            "Focus Mode is active, which switches this source's periodic "
            "task off until it is exited"
        )
    return None


def evaluate_source_health(
    *,
    window_hours: int = DEFAULT_WINDOW_HOURS,
    min_attempts: int = DEFAULT_MIN_ATTEMPTS,
    min_successes: int = DEFAULT_MIN_SUCCESSES,
    now=None,
) -> Report:
    """Judge each declared source on what it achieved inside the window."""
    if now is None:
        now = timezone.now()
    window_start = now - timedelta(hours=window_hours)

    rows_by_source = {
        row["source"]: row
        for row in CompanySyncStatus.objects.values("source")
        .annotate(
            attempts=Count("id", filter=Q(last_attempted_at__gte=window_start)),
            succeeded=Count("id", filter=Q(last_succeeded_at__gte=window_start)),
            # A refusal is a company *currently* refusing, not a row that once
            # refused: the row records the latest attempt, so a company whose
            # next sync read its dates cleanly is back to
            # `consecutive_failures = 0` and drops out of this count. That is
            # what keeps the column self-clearing instead of a permanent scar.
            refusing=Count(
                "id",
                filter=Q(
                    last_attempted_at__gte=window_start,
                    consecutive_failures__gt=0,
                ),
            ),
        )
    }

    # Both tables are driven by the declared vocabulary rather than by the rows
    # that came back, so a source with nothing to report is a line saying zero
    # instead of a line that is not there.
    declared_sources = declared_source_subjects()
    attempt_rows = [
        rows_by_source.get(source)
        or {"source": source, "attempts": 0, "succeeded": 0, "refusing": 0}
        for source in declared_sources
    ]
    refusal_rows_raw = [
        row for row in attempt_rows if row["source"] in FIELD_REFUSAL_SOURCES
    ]

    focus_mode_active = focus_mode_active_readonly()

    notes: list[str] = []
    unmeasured: list[str] = []
    below_threshold: list[tuple[str, int]] = []
    failed_sources: set[str] = set()

    render_attempt_rows = []
    source_states: dict[str, str] = {}
    source_reasons: dict[str, str] = {}
    source_details: dict[str, str] = {}
    source_values: dict[str, dict[str, float]] = {}

    for row in attempt_rows:
        source = row["source"]
        attempts = row["attempts"]
        succeeded = row["succeeded"]
        reported = _found_count(source, window_start) if succeeded else None

        # A split is only worth judging once there are enough successes for
        # "none of them" to mean the branch is gone rather than merely unlucky.
        split_is_judgeable = reported is not None and succeeded >= min_successes

        detail = ""
        if source in SOURCES_WITHOUT_ATTEMPT_ROWS:
            # Nothing here is a reading about the source. Saying "OK" would
            # claim a check that this command cannot make, so it says so.
            verdict = "not measured"
            status = STATUS_NOT_JUDGED
            reason = "not_measured"
            unmeasured.append(
                f"source '{source}': {SOURCES_WITHOUT_ATTEMPT_ROWS[source]}"
            )
        elif attempts == 0:
            silence = _silence_reason(source, focus_mode_active=focus_mode_active)
            if silence is None:
                verdict = "FAIL"
                status = STATUS_FAIL
                reason = "no_attempt"
                detail = (
                    f"source '{source}': no attempt at all in the last "
                    f"{window_hours}h -- its task draws from a due-list that "
                    f"is not empty, so silence means it did not run or did "
                    f"not write"
                )
                notes.append(detail)
            else:
                # A reading, not a lack of evidence -- and named, so a reader
                # cannot mistake it for one.
                verdict = "OK"
                status = STATUS_OK
                reason = (
                    "silent_focus_mode"
                    if focus_mode_active
                    and source in SOURCES_PAUSED_BY_FOCUS_MODE
                    else "silent_expected"
                )
                detail = (
                    f"source '{source}': no attempt in the last "
                    f"{window_hours}h, which is expected -- {silence}"
                )
                notes.append(detail)
        elif attempts < min_attempts:
            below_threshold.append((source, attempts))
            verdict = "OK"
            status = STATUS_NOT_JUDGED
            reason = "below_attempt_threshold"
            detail = (
                f"source '{source}': {attempts} attempt(s), below the "
                f"{min_attempts} threshold -- not judged"
            )
        elif succeeded == 0:
            verdict = "FAIL"
            status = STATUS_FAIL
            reason = "no_success"
            detail = (
                f"source '{source}': {attempts} attempt(s) and no successful "
                f"check at all -- the parser recognises nothing"
                f"{_recorded_errors(source, window_start)}"
            )
            notes.append(detail)
        elif split_is_judgeable and reported == 0:
            verdict = "FAIL"
            status = STATUS_FAIL
            reason = "no_debt_reported"
            detail = (
                f"source '{source}': {succeeded} check(s) succeeded and not one "
                f"reported a debt -- a company that owes would be recorded as "
                f"debt-free"
            )
            notes.append(detail)
        elif split_is_judgeable and succeeded - reported == 0:
            verdict = "FAIL"
            status = STATUS_FAIL
            reason = "no_no_record_answer"
            detail = (
                f"source '{source}': {succeeded} check(s) succeeded and not one "
                f"reported the source's no-record answer -- a company that owes "
                f"nothing can never be marked checked, so it stays due forever"
            )
            notes.append(detail)
        else:
            verdict = "OK"
            status = STATUS_OK
            reason = "ok"

        if status == STATUS_FAIL:
            failed_sources.add(source)

        source_states[source] = status
        source_reasons[source] = reason
        source_details[source] = detail
        source_values[source] = {"attempted": attempts, "succeeded": succeeded}
        if reported is not None:
            source_values[source]["found"] = reported
        source_values[source]["refusing"] = row["refusing"]

        render_attempt_rows.append(
            {
                "source": source,
                "attempts": attempts,
                "succeeded": succeeded,
                "reported": reported,
                "verdict": verdict,
            }
        )

    # The second table: a source that *refuses* a field it cannot read, rather
    # than failing a company outright. A source failing both lines is one event
    # and is counted once -- the double-count guard below.
    render_refusal_rows = []
    for row in refusal_rows_raw:
        source = row["source"]
        refusals = row["refusing"]
        if refusals == 0:
            # Not silence: the source answered in the window and refused
            # nothing. Zero here is a reading, not a lack of evidence.
            verdict = "OK"
        elif refusals < min_attempts:
            verdict = f"OK (below the {min_attempts} threshold -- not judged)"
        else:
            verdict = "FAIL"
            if source not in failed_sources:
                # The double-count guard: when the attempts line already failed
                # this source it has already been counted, and "no successes"
                # and "N companies refusing" are one event -- reporting it twice
                # would make the gate's own count of unmet controls wrong.
                failed_sources.add(source)
                source_states[source] = STATUS_FAIL
                source_reasons[source] = "refusing_fields"
                source_details[source] = (
                    f"source '{source}': {refusals} "
                    f"compan{'y' if refusals == 1 else 'ies'} refuse a "
                    f"{FIELD_REFUSAL_SOURCES[source]} that cannot be read"
                )
        render_refusal_rows.append(
            {
                "source": source,
                "refusals": refusals,
                "plural": "company" if refusals == 1 else "companies",
                "what": FIELD_REFUSAL_SOURCES[source],
                "verdict": verdict,
            }
        )

    verdicts = tuple(
        Verdict(
            domain=DOMAIN_SOURCE,
            subject=source,
            status=source_states.get(source, STATUS_NOT_JUDGED),
            reason=source_reasons.get(source, "not_judged"),
            detail=source_details.get(source, ""),
            values=source_values.get(source, {}),
        )
        for source in declared_sources
    )

    return Report(
        domain=DOMAIN_SOURCE,
        verdicts=verdicts,
        notes=tuple(notes),
        counters={
            "below_threshold": len(below_threshold),
            "refusal_lines": len(render_refusal_rows),
        },
        context={
            "attempt_rows": render_attempt_rows,
            "refusal_rows": render_refusal_rows,
            "unmeasured": unmeasured,
            "below_threshold": below_threshold,
            "window_hours": window_hours,
            "min_attempts": min_attempts,
            "focus_mode_active": focus_mode_active,
        },
    )


# ---------------------------------------------------------------------------
# beat_health
# ---------------------------------------------------------------------------


def beat_period(row) -> timedelta | None:
    """A beat row's own interval, or None when none can be read from it."""
    if row.interval_id is None:
        return None
    try:
        return row.interval.schedule.run_every
    except (TypeError, ValueError):
        # `IntervalSchedule.schedule` builds `timedelta(**{period: every})`, so
        # a `period` outside the model's choices raises here -- a row written by
        # hand, or by a version whose constants differed. It routes into the
        # printed-not-judged bucket, which is the honest answer rather than a
        # swallowed error: no interval can be read, so no age is claimed.
        return None


def beat_schedule_label(row) -> str:
    """How the entry's schedule reads in the table's second column."""
    period = beat_period(row)
    if period is not None:
        return short_period(period)
    for field_name in ("crontab", "solar", "clocked"):
        if getattr(row, f"{field_name}_id") is not None:
            return field_name
    if row.interval_id is not None:
        return "interval?"
    return "-"


def evaluate_beat_health(
    *,
    grace_minutes: int = DEFAULT_GRACE_MINUTES,
    now=None,
    registry_loader: Callable[[], "set[str] | None"] | None = None,
) -> Report:
    """Judge every `PeriodicTask` row against its own interval.

    `registry_loader` is the caller's reader for the set of task names this app
    implements (`beat_health.Command._registered_task_names`). It is a callable
    rather than a set because filling it costs a full task-module import, and it
    is only ever needed to decorate a verdict reached from `last_run_at` -- so
    it is called at most once, and only once something has already failed.
    """
    if now is None:
        now = timezone.now()
    grace = timedelta(minutes=grace_minutes)

    rows = list(PeriodicTask.objects.select_related("interval").order_by("name"))
    focus_mode_active = focus_mode_active_readonly()

    notes: list[str] = []
    celery_owned: list[str] = []
    switched_off: list[str] = []
    paused_by_focus_mode: list[str] = []
    odd_schedule: list[str] = []
    unreadable_interval: list[str] = []
    never_run: list[str] = []

    judged = 0
    stale = 0

    registry: set[str] | None = None
    registry_read = False

    def outlived(task: str) -> str:
        """A sentence for a row pointing at a task nothing implements."""
        nonlocal registry, registry_read
        if registry_loader is None:
            return ""
        if not registry_read:
            registry = registry_loader()
            registry_read = True
        if registry is None or task in registry:
            return ""
        return (
            f" The task it names ({task}) is not registered in this app, so "
            f"it cannot run at all -- the entry has outlived the task."
        )

    verdicts: list[Verdict] = []
    render_rows = []

    for row in rows:
        period = beat_period(row)
        last = row.last_run_at
        schedule_label = beat_schedule_label(row)
        age_text = humanize(now - last) if last else "-"
        values: dict[str, float] = {}
        if last is not None:
            values["age_seconds"] = (now - last).total_seconds()

        if row.task.startswith(CELERY_OWN_PREFIX):
            celery_owned.append(row.name)
            verdicts.append(
                Verdict(
                    domain=DOMAIN_BEAT,
                    subject=row.name,
                    status=STATUS_NOT_JUDGED,
                    reason="celery_owned",
                    detail=(
                        f"{row.name}: celery's own housekeeping entry, not judged"
                    ),
                    values=values,
                )
            )
        elif not row.enabled:
            if focus_mode_active and row.task not in FOCUS_KEEP_TASKS:
                paused_by_focus_mode.append(row.name)
                reason = "focus_mode"
            else:
                switched_off.append(row.name)
                reason = "switched_off"
            verdicts.append(
                Verdict(
                    domain=DOMAIN_BEAT,
                    subject=row.name,
                    status=STATUS_NOT_JUDGED,
                    reason=reason,
                    detail=f"{row.name}: switched off, so not judged",
                    values=values,
                )
            )
        elif period is None:
            # Two different reasons, kept apart: a schedule kind this control
            # does not read, and an interval it cannot read.
            if row.interval_id is not None:
                unreadable_interval.append(f"{row.name} ({row.interval.period})")
            else:
                odd_schedule.append(f"{row.name} ({schedule_label})")
            verdicts.append(
                Verdict(
                    domain=DOMAIN_BEAT,
                    subject=row.name,
                    status=STATUS_NOT_JUDGED,
                    reason="unreadable_schedule",
                    detail=f"{row.name}: no interval can be read from its schedule",
                    values=values,
                )
            )
        elif last is None:
            # Never run. Judged only in the direction `date_changed` can prove.
            existed = now - row.date_changed
            if existed > period + grace:
                judged += 1
                stale += 1
                detail = (
                    f"{row.name}: has never run (`last_run_at` is NULL) and "
                    f"the row itself is {humanize(existed)} old -- longer "
                    f"than its {short_period(period)} interval plus the "
                    f"{grace_minutes}m grace, so it has lived through a due "
                    f"date without dispatching.{outlived(row.task)}"
                )
                notes.append(detail)
                verdicts.append(
                    Verdict(
                        domain=DOMAIN_BEAT,
                        subject=row.name,
                        status=STATUS_FAIL,
                        reason="never_run_late",
                        detail=detail,
                        values={
                            "row_age_seconds": existed.total_seconds(),
                            "interval_seconds": period.total_seconds(),
                            "grace_seconds": grace.total_seconds(),
                        },
                    )
                )
            else:
                never_run.append(row.name)
                verdicts.append(
                    Verdict(
                        domain=DOMAIN_BEAT,
                        subject=row.name,
                        status=STATUS_NOT_JUDGED,
                        reason="never_run_young",
                        detail=(
                            f"{row.name}: has never run and is not provably late yet"
                        ),
                        values={"row_age_seconds": existed.total_seconds()},
                    )
                )
        elif now - last > period + grace:
            judged += 1
            stale += 1
            detail = (
                f"{row.name}: last dispatched {humanize(now - last)} ago "
                f"against a {short_period(period)} interval, so it is "
                f"{humanize(now - last - period)} past due. The entry is "
                f"enabled, so nothing is standing it down -- it has simply "
                f"stopped.{outlived(row.task)}"
            )
            notes.append(detail)
            verdicts.append(
                Verdict(
                    domain=DOMAIN_BEAT,
                    subject=row.name,
                    status=STATUS_FAIL,
                    reason="stale",
                    detail=detail,
                    values={
                        "age_seconds": (now - last).total_seconds(),
                        "interval_seconds": period.total_seconds(),
                        "grace_seconds": grace.total_seconds(),
                    },
                )
            )
        else:
            judged += 1
            verdicts.append(
                Verdict(
                    domain=DOMAIN_BEAT,
                    subject=row.name,
                    status=STATUS_OK,
                    reason="ok",
                    detail=f"{row.name}: dispatched inside its interval",
                    values={
                        "age_seconds": (now - last).total_seconds(),
                        "interval_seconds": period.total_seconds(),
                        "grace_seconds": grace.total_seconds(),
                    },
                )
            )

        text = _render_verdict_text(verdicts[-1].status)
        render_rows.append(
            {
                "row": row,
                "schedule_label": schedule_label,
                "last": last,
                "age_text": age_text,
                "verdict": text,
            }
        )

    return Report(
        domain=DOMAIN_BEAT,
        verdicts=tuple(verdicts),
        notes=tuple(notes),
        counters={"judged": judged, "stale": stale, "rows": len(rows)},
        context={
            "rows": render_rows,
            "celery_owned": celery_owned,
            "switched_off": switched_off,
            "paused_by_focus_mode": paused_by_focus_mode,
            "odd_schedule": odd_schedule,
            "unreadable_interval": unreadable_interval,
            "never_run": never_run,
            "focus_mode_active": focus_mode_active,
            "grace_minutes": grace_minutes,
        },
    )


def _render_verdict_text(status: str) -> str:
    """The word `beat_health` prints for a row: OK, FAIL or `--`.

    The renderer's vocabulary, kept beside the statuses it maps from so the two
    cannot drift; `not_judged` is `--`, which is what every carve-out in that
    table prints.
    """
    if status == STATUS_FAIL:
        return "FAIL"
    if status == STATUS_OK:
        return "OK"
    return "--"
