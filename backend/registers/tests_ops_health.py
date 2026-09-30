"""The rules the gates share, and the exporter that publishes them.

`sync_health`, `source_health` and `beat_health` each had their own copy of
"is this thing fine", and the only consumer of that answer was a shell script
reading their stdout. `registers/services/ops_health.py` lifts the rules out and
`run_ops_exporter` publishes them as Prometheus metrics, so these tests come in
two halves:

- the **evaluators**, where the judgement itself is pinned: `not_judged` never
  counts as unmet, the newest attempt is the one that is judged, and the subject
  vocabulary comes from the model's choices rather than from the rows that
  happen to exist;
- the **exporter's series set**, where the failure this repository keeps making
  is pinned: a series that is *absent* reads as healthy. Every declared subject
  must have exactly one series even when nothing has ever run, and a domain whose
  evaluator raised must serve no series at all and say so in
  `cistafirma_ops_scrape_ok`.

The three commands' own test files are the byte-compat contract for their text
and are not touched here.
"""

import re
from datetime import timedelta
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from django_celery_beat.models import IntervalSchedule, PeriodicTask

from companies.models import Company
from registers.management.commands import run_ops_exporter
from registers.models import CompanySyncStatus, SyncJob, SyncProgress
from registers.services import ops_health
from registers.services.ops_health import (
    DOMAIN_BEAT,
    DOMAIN_SOURCE,
    DOMAIN_SYNC,
    STATUS_FAIL,
    STATUS_NOT_JUDGED,
    STATUS_OK,
    Report,
    Verdict,
)


def _series(body):
    """Parse the exposition text into {(metric, labels): value}.

    Labels are compared as a sorted tuple of pairs, so a test never depends on
    the order `prometheus_client` happens to write them in.
    """
    out = {}
    for line in body.decode().splitlines():
        if not line or line.startswith("#"):
            continue
        name, braces, rest = line.partition("{")
        if braces:
            label_text, _, value_text = rest.partition("}")
            labels = tuple(
                sorted(re.findall(r'(\w+)="((?:[^"\\]|\\.)*)"', label_text))
            )
            value = value_text.strip()
        else:
            name, _, value = name.rpartition(" ")
            labels = ()
        out[(name, labels)] = float(value)
    return out


class VerdictTests(SimpleTestCase):
    """The two rules the whole module rests on, neither of which needs a DB."""

    def test_unmet_counts_failures_and_nothing_else(self):
        report = Report(
            domain=DOMAIN_SYNC,
            verdicts=(
                Verdict(DOMAIN_SYNC, "a", STATUS_FAIL, "r"),
                Verdict(DOMAIN_SYNC, "b", STATUS_OK, "r"),
                Verdict(DOMAIN_SYNC, "c", STATUS_NOT_JUDGED, "r"),
                Verdict(DOMAIN_SYNC, "d", STATUS_NOT_JUDGED, "r"),
            ),
        )

        self.assertEqual(report.unmet, 1)
        self.assertEqual([v.subject for v in report.failed], ["a"])

    def test_not_judged_is_never_a_failure(self):
        """Focus Mode, a live full walk, a switched-off entry: none is unmet."""
        report = Report(
            domain=DOMAIN_BEAT,
            verdicts=tuple(
                Verdict(DOMAIN_BEAT, f"entry-{i}", STATUS_NOT_JUDGED, "carve_out")
                for i in range(5)
            ),
        )

        self.assertEqual(report.unmet, 0)

    def test_a_subject_collapses_to_its_worst_status(self):
        report = Report(
            domain=DOMAIN_SYNC,
            verdicts=(
                Verdict(DOMAIN_SYNC, "ruz_incremental", STATUS_OK, "running"),
                Verdict(DOMAIN_SYNC, "ruz_incremental", STATUS_FAIL, "stuck_running"),
                Verdict(DOMAIN_SYNC, "orsr_batch", STATUS_NOT_JUDGED, "not_judged"),
                Verdict(DOMAIN_SYNC, "orsr_batch", STATUS_OK, "queued_recent"),
            ),
        )

        statuses = report.status_by_subject()

        self.assertEqual(statuses["ruz_incremental"], STATUS_FAIL)
        # `unknown` outranks `ok`: with one series per subject, the pessimistic
        # reading is the only one that cannot hide the finding.
        self.assertEqual(statuses["orsr_batch"], STATUS_NOT_JUDGED)

    def test_an_unknown_status_is_refused_at_construction(self):
        with self.assertRaises(ValueError):
            Verdict(DOMAIN_SYNC, "a", "probably_fine", "r")

    def test_the_declared_vocabularies_are_the_models_own_choices(self):
        self.assertEqual(
            ops_health.declared_source_subjects(),
            [value for value, _ in ops_health.CompanySyncStatus.SOURCE_CHOICES],
        )
        self.assertEqual(
            ops_health.declared_sync_subjects(),
            [value for value, _ in SyncJob.JOB_TYPE_CHOICES],
        )


class EvaluateSyncHealthTests(TestCase):
    def _job(self, **kwargs):
        defaults = {
            "job_type": "ruz_incremental",
            "status": "completed",
            "triggered_via": "beat_schedule",
        }
        defaults.update(kwargs)
        return SyncJob.objects.create(**defaults)

    def _beat_attempt(self, job_type, status, *, completed_ago, queued_ago=None):
        job = self._job(
            job_type=job_type,
            status=status,
            completed_at=timezone.now() - completed_ago,
        )
        if queued_ago is not None:
            SyncJob.objects.filter(pk=job.pk).update(
                queued_at=timezone.now() - queued_ago
            )
            job.refresh_from_db()
        return job

    def test_a_stuck_running_job_is_the_only_failure_it_reports(self):
        self._job(
            status="running",
            triggered_via="system",
            last_heartbeat=timezone.now() - timedelta(days=15),
        )

        report = ops_health.evaluate_sync_health()

        self.assertEqual(report.unmet, 1)
        self.assertEqual(report.failed[0].reason, "stuck_running")
        self.assertEqual(report.failed[0].subject, "ruz_incremental")
        self.assertGreater(
            report.failed[0].values["heartbeat_age_seconds"], 14 * 86400
        )

    def test_a_newer_successful_attempt_clears_an_older_failure(self):
        """The newest attempt is judged, so a scar does not stay red."""
        self._beat_attempt("ruz_incremental", "failed", completed_ago=timedelta(hours=6))
        self._beat_attempt("ruz_incremental", "completed", completed_ago=timedelta(minutes=5))

        report = ops_health.evaluate_sync_health()

        self.assertEqual(report.unmet, 0)
        self.assertEqual(report.status_by_subject()["ruz_incremental"], STATUS_OK)

    def test_the_newest_attempt_failing_is_unmet(self):
        self._beat_attempt("ruz_incremental", "completed", completed_ago=timedelta(hours=6))
        self._beat_attempt("ruz_incremental", "failed", completed_ago=timedelta(minutes=5))

        report = ops_health.evaluate_sync_health()

        self.assertEqual(report.unmet, 1)
        self.assertEqual(report.failed[0].reason, "beat_attempt_failed")

    def test_the_window_is_anchored_on_when_an_attempt_ended(self):
        """A long run is still in scope on the day it finishes, not the day it started."""
        self._beat_attempt(
            "ruz_incremental",
            "failed",
            completed_ago=timedelta(minutes=10),
            queued_ago=timedelta(days=5),
        )

        report = ops_health.evaluate_sync_health()

        self.assertEqual(report.unmet, 1)

    def test_an_attempt_that_ended_outside_the_window_is_history(self):
        self._beat_attempt(
            "ruz_incremental",
            "failed",
            completed_ago=timedelta(days=3),
            queued_ago=timedelta(minutes=30),
        )

        report = ops_health.evaluate_sync_health()

        self.assertEqual(report.unmet, 0)
        self.assertNotIn("ruz_incremental", report.status_by_subject())

    def test_a_stalled_incremental_window_is_unmet(self):
        progress = SyncProgress.objects.create(
            sync_type="incremental", status="completed"
        )
        SyncProgress.objects.filter(pk=progress.pk).update(
            zmenene_od=(timezone.now() - timedelta(days=30)).date()
        )

        report = ops_health.evaluate_sync_health(window_max_age_days=3)

        self.assertEqual(report.unmet, 1)
        self.assertEqual(report.failed[0].reason, "window_stalled")

    def test_a_window_held_by_a_live_full_walk_is_not_judged(self):
        progress = SyncProgress.objects.create(
            sync_type="incremental", status="completed"
        )
        SyncProgress.objects.filter(pk=progress.pk).update(
            zmenene_od=(timezone.now() - timedelta(days=30)).date()
        )
        # The carve-out is a *live* full walk: `record_progress` writes
        # `last_activity` as it goes, and a walk that stopped writing is not
        # holding anything -- it is the staleness this command exists to catch.
        SyncProgress.objects.create(
            sync_type="full",
            status="running",
            last_activity=timezone.now(),
        )

        report = ops_health.evaluate_sync_health(window_max_age_days=3)

        self.assertEqual(report.unmet, 0)
        self.assertIn("incremental", report.context["held_by_full_walk"])


class EvaluateSourceHealthTests(TestCase):
    def test_every_declared_source_is_judged_exactly_once(self):
        """Including the ones with no rows at all -- an absent line is not health."""
        report = ops_health.evaluate_source_health()

        self.assertEqual(
            [verdict.subject for verdict in report.verdicts],
            ops_health.declared_source_subjects(),
        )

    def test_a_source_that_never_writes_attempt_rows_is_not_judged(self):
        """`fs` is a bulk ingest; a blank line here is a reading, not a gap."""
        report = ops_health.evaluate_source_health()

        self.assertEqual(report.status_by_subject()["fs"], STATUS_NOT_JUDGED)
        self.assertTrue(report.context["unmeasured"][0].startswith("source 'fs'"))
        self.assertNotIn("fs", [verdict.subject for verdict in report.failed])

    def test_a_source_under_its_attempt_threshold_is_not_unmet(self):
        company = Company.objects.create(
            ruz_id=800001, ico="90000001", nazov_UJ="Test s.r.o.", pravna_forma="112"
        )
        CompanySyncStatus.objects.create(
            company=company,
            source="orsr",
            last_attempted_at=timezone.now() - timedelta(hours=1),
        )

        report = ops_health.evaluate_source_health(min_attempts=200)

        self.assertEqual(report.status_by_subject()["orsr"], STATUS_NOT_JUDGED)
        self.assertNotIn("orsr", [verdict.subject for verdict in report.failed])
        self.assertIn(("orsr", 1), report.context["below_threshold"])

    def test_a_source_with_attempts_but_no_success_at_all_fails(self):
        now = timezone.now()
        companies = Company.objects.bulk_create([
            Company(
                ruz_id=810000 + i,
                ico=f"{91000000 + i}",
                nazov_UJ=f"Test {i}",
                pravna_forma="112",
            )
            for i in range(5)
        ])
        CompanySyncStatus.objects.bulk_create([
            CompanySyncStatus(
                company=company,
                source="orsr",
                last_attempted_at=now - timedelta(hours=1),
                last_error_type="parse_error",
            )
            for company in companies
        ])

        report = ops_health.evaluate_source_health(min_attempts=3)

        self.assertEqual(report.status_by_subject()["orsr"], STATUS_FAIL)
        self.assertIn("orsr", [verdict.subject for verdict in report.failed])


class EvaluateBeatHealthTests(TestCase):
    def _entry(
        self,
        name,
        *,
        every=10,
        last_run_at=None,
        task="registers.tasks.fetch_ruz_data_task",
        **kwargs,
    ):
        # `task` is a named parameter, not a default inside the `create()` call:
        # the caller that needs celery's own prefix (`celery.backend_cleanup`)
        # has to be able to override it, and passing it through `**kwargs` beside
        # a hardcoded `task=` there is a duplicate keyword, not an override.
        interval, _ = IntervalSchedule.objects.get_or_create(
            every=every, period=IntervalSchedule.MINUTES
        )
        return PeriodicTask.objects.create(
            name=name,
            task=task,
            interval=interval,
            last_run_at=last_run_at,
            **kwargs,
        )

    def test_a_stale_enabled_entry_is_the_control_this_exists_for(self):
        self._entry("compute-sector-benchmarks-daily", last_run_at=timezone.now() - timedelta(hours=32))

        report = ops_health.evaluate_beat_health(grace_minutes=15)

        self.assertEqual(report.unmet, 1)
        self.assertEqual(report.failed[0].subject, "compute-sector-benchmarks-daily")
        self.assertGreater(report.failed[0].values["age_seconds"], 31 * 3600)

    def test_a_disabled_entry_is_never_unmet(self):
        self._entry("paused-entry", enabled=False, last_run_at=timezone.now() - timedelta(days=30))

        report = ops_health.evaluate_beat_health(grace_minutes=15)

        self.assertEqual(report.unmet, 0)
        self.assertEqual(report.status_by_subject()["paused-entry"], STATUS_NOT_JUDGED)
        self.assertIn("paused-entry", report.context["switched_off"])

    def test_celerys_own_entries_are_excluded_by_prefix(self):
        self._entry(
            "celery.backend_cleanup",
            task="celery.backend_cleanup",
            last_run_at=None,
        )

        report = ops_health.evaluate_beat_health(grace_minutes=15)

        self.assertEqual(report.unmet, 0)
        self.assertIn("celery.backend_cleanup", report.context["celery_owned"])

    def test_a_never_run_entry_is_not_judged_until_the_row_is_provably_old(self):
        entry = self._entry("brand-new-entry", every=10)

        young = ops_health.evaluate_beat_health(grace_minutes=15)
        self.assertEqual(young.unmet, 0)
        self.assertIn("brand-new-entry", young.context["never_run"])

        # `date_changed` is auto_now, so it can only be moved after the row
        # exists -- and it is the only direction this control can prove.
        PeriodicTask.objects.filter(pk=entry.pk).update(
            date_changed=timezone.now() - timedelta(days=2)
        )

        old = ops_health.evaluate_beat_health(grace_minutes=15)
        self.assertEqual(old.unmet, 1)
        self.assertEqual(old.failed[0].reason, "never_run_late")

    def test_focus_mode_switching_an_entry_off_is_not_a_failure(self):
        self._entry("a-paused-entry", enabled=False, last_run_at=timezone.now() - timedelta(days=30))
        ops_health.SyncFocusModeState.objects.create(pk=1, active=True)

        report = ops_health.evaluate_beat_health(grace_minutes=15)

        self.assertEqual(report.unmet, 0)
        self.assertIn("a-paused-entry", report.context["paused_by_focus_mode"])
        self.assertNotIn("a-paused-entry", report.context["switched_off"])

    def test_the_registry_reader_is_not_called_when_nothing_has_failed(self):
        """It costs a task-module import; a healthy schedule must not pay it."""
        self._entry("a-healthy-entry", last_run_at=timezone.now())
        calls = []

        ops_health.evaluate_beat_health(
            grace_minutes=15, registry_loader=lambda: calls.append(1) or set()
        )

        self.assertEqual(calls, [])


class ExporterSeriesTests(TestCase):
    """What the exporter publishes, with no rows anywhere -- the failing case."""

    def _scrape(self, **kwargs):
        cache = run_ops_exporter.OpsReportCache()
        body, ok = run_ops_exporter.collect_metrics(cache=cache, **kwargs)
        return _series(body), ok

    def test_every_declared_source_gets_a_series_with_no_rows_at_all(self):
        series, ok = self._scrape()

        self.assertTrue(ok)
        for source in ops_health.declared_source_subjects():
            found = [
                value
                for (name, labels), value in series.items()
                if name == run_ops_exporter.METRIC_SUBJECT
                and ("domain", DOMAIN_SOURCE) in labels
                and ("subject", source) in labels
            ]
            self.assertEqual(
                len(found),
                1,
                f"source {source!r} must have exactly one subject series",
            )
            self.assertEqual(found[0], 1.0)

    def test_every_declared_job_type_gets_a_series_with_no_rows_at_all(self):
        series, _ = self._scrape()

        subjects = {
            dict(labels)["subject"]
            for (name, labels) in series
            if name == run_ops_exporter.METRIC_SUBJECT
            and ("domain", DOMAIN_SYNC) in labels
        }

        self.assertEqual(subjects, set(ops_health.declared_sync_subjects()))

    def test_the_subject_metric_has_one_series_per_subject_and_no_more(self):
        series, _ = self._scrape()

        counts = {}
        for (name, labels) in series:
            if name != run_ops_exporter.METRIC_SUBJECT:
                continue
            pair = (dict(labels)["domain"], dict(labels)["subject"])
            counts[pair] = counts.get(pair, 0) + 1

        self.assertTrue(counts)
        self.assertTrue(all(count == 1 for count in counts.values()), counts)

    def test_both_source_states_are_emitted_for_every_source(self):
        series, _ = self._scrape()

        for source in ops_health.declared_source_subjects():
            for state in ("attempted", "succeeded"):
                self.assertIn(
                    (
                        run_ops_exporter.METRIC_SOURCE_COMPANIES,
                        (("source", source), ("state", state)),
                    ),
                    series,
                )

    def test_each_domain_publishes_its_own_unmet_and_evaluation_time(self):
        series, _ = self._scrape()

        for domain in (DOMAIN_SYNC, DOMAIN_SOURCE, DOMAIN_BEAT):
            self.assertIn(
                (run_ops_exporter.METRIC_UNMET, (("domain", domain),)), series
            )
            self.assertIn(
                (run_ops_exporter.METRIC_EVALUATED, (("domain", domain),)), series
            )
        self.assertEqual(
            series[(run_ops_exporter.METRIC_SCRAPE_OK, ())], 1.0
        )

    def test_a_raising_evaluator_takes_its_own_domain_down_and_nothing_else(self):
        def broken():
            raise RuntimeError("the database went away")

        def loaders(thresholds):
            return (
                (DOMAIN_SYNC, broken, 0),
                (
                    DOMAIN_SOURCE,
                    lambda: run_ops_exporter._load_source(thresholds),
                    None,
                ),
                (DOMAIN_BEAT, lambda: run_ops_exporter._load_beat(thresholds), 0),
            )

        with patch.object(run_ops_exporter, "_loaders", loaders):
            series, ok = self._scrape()

        self.assertFalse(ok)
        self.assertEqual(series[(run_ops_exporter.METRIC_SCRAPE_OK, ())], 0.0)
        # Reported as absent, never as ok: a domain that raised serves nothing.
        self.assertFalse(
            [
                labels
                for (name, labels) in series
                if name == run_ops_exporter.METRIC_SUBJECT
                and ("domain", DOMAIN_SYNC) in labels
            ]
        )
        self.assertNotIn(
            (run_ops_exporter.METRIC_UNMET, (("domain", DOMAIN_SYNC),)), series
        )
        # The other two domains are still served.
        self.assertIn(
            (run_ops_exporter.METRIC_UNMET, (("domain", DOMAIN_SOURCE),)), series
        )
        self.assertIn(
            (run_ops_exporter.METRIC_UNMET, (("domain", DOMAIN_BEAT),)), series
        )

    def test_the_source_cache_serves_a_second_scrape_without_re_evaluating(self):
        calls = []

        def loader():
            calls.append(1)
            return Report(domain=DOMAIN_SOURCE, verdicts=()), ("ruz",)

        def loaders(thresholds):
            return ((DOMAIN_SOURCE, loader, None),)

        cache = run_ops_exporter.OpsReportCache()
        with patch.object(run_ops_exporter, "_loaders", loaders):
            first, _ = run_ops_exporter.collect_metrics(
                cache=cache, cache_seconds=60, thresholds={}
            )
            second, _ = run_ops_exporter.collect_metrics(
                cache=cache, cache_seconds=60, thresholds={}
            )
            third, _ = run_ops_exporter.collect_metrics(
                cache=cache, cache_seconds=0, thresholds={}
            )

        self.assertEqual(len(calls), 2, "60s cache must serve the second scrape")
        a = _series(first)[(run_ops_exporter.METRIC_EVALUATED, (("domain", DOMAIN_SOURCE),))]
        b = _series(second)[(run_ops_exporter.METRIC_EVALUATED, (("domain", DOMAIN_SOURCE),))]
        self.assertEqual(a, b, "a cached scrape must not claim a fresh evaluation")
        self.assertNotEqual(
            a,
            _series(third)[
                (run_ops_exporter.METRIC_EVALUATED, (("domain", DOMAIN_SOURCE),))
            ],
        )

    def test_a_stuck_job_publishes_its_heartbeat_age_and_an_unmet_sync_domain(self):
        job = SyncJob.objects.create(
            job_type="ruz_incremental",
            status="running",
            triggered_via="system",
            started_at=timezone.now() - timedelta(days=15),
            last_heartbeat=timezone.now() - timedelta(days=14),
        )
        self.assertIsNotNone(job.pk)

        series, _ = self._scrape()

        self.assertEqual(
            series[
                (
                    run_ops_exporter.METRIC_SUBJECT,
                    (
                        ("domain", DOMAIN_SYNC),
                        ("status", STATUS_FAIL),
                        ("subject", "ruz_incremental"),
                    ),
                )
            ],
            1.0,
        )
        self.assertGreater(
            series[
                (
                    run_ops_exporter.METRIC_HEARTBEAT_AGE,
                    (("job_type", "ruz_incremental"),),
                )
            ],
            13 * 86400,
        )
        self.assertGreater(
            series[(run_ops_exporter.METRIC_UNMET, (("domain", DOMAIN_SYNC),))], 0
        )

    def test_a_stale_beat_entry_publishes_its_age(self):
        interval, _ = IntervalSchedule.objects.get_or_create(
            every=10, period=IntervalSchedule.MINUTES
        )
        PeriodicTask.objects.create(
            name="compute-sector-benchmarks-daily",
            task="registers.tasks.compute_sector_benchmarks",
            interval=interval,
            last_run_at=timezone.now() - timedelta(hours=32),
        )

        series, _ = self._scrape()

        self.assertGreater(
            series[
                (
                    run_ops_exporter.METRIC_BEAT_AGE,
                    (("task", "compute-sector-benchmarks-daily"),),
                )
            ],
            31 * 3600,
        )
        self.assertEqual(
            series[
                (
                    run_ops_exporter.METRIC_SUBJECT,
                    (
                        ("domain", DOMAIN_BEAT),
                        ("status", STATUS_FAIL),
                        ("subject", "compute-sector-benchmarks-daily"),
                    ),
                )
            ],
            1.0,
        )
