"""The insurance batch must be bounded by what the drain can absorb.

The scheduler enqueued the entire due population every tick -- 439 817
companies on 2026-09-12 -- against an `update_insurance_debt` that drains
14 400 per 12 h. Measured that day the `insurance` queue held 5 108 434
messages (~5 GB of Redis), and the scheduler itself -- running on the same queue
it floods -- waited behind its own backlog and then fired repeatedly: beat
dispatched it at 07:50, a worker first ran it after 11:00, and it then executed
at 03:11, 04:17, 11:14, 11:49, 12:04, 13:55, 14:15, 14:19, 14:34, 14:39 and
14:53, roughly 8.4 million messages in one day.

None of that failed, logged an error, or moved any counter a human watches.
These tests pin the three things that keep it from coming back: the cap, the
order the batch is drawn in, and the queue it runs on.

The routing assertions read `settings`, but be aware the live routing lives in
the `PeriodicTask` row -- see the comment above `INSURANCE_BATCH_PER_TICK`.
"""

from datetime import timedelta
from unittest import mock

from django.conf import settings
from django.test import TestCase
from django.utils import timezone

from companies.models import Company, Watchlist
from registers.tasks import (
    INSURANCE_BATCH_PER_TICK,
    INSURANCE_TICK_HOURS,
    schedule_insurance_debt_checks,
    update_insurance_debt,
)
from users.models import User


def _companies(count: int, *, start: int = 1, checked: str = "never") -> list[Company]:
    """`count` companies, all due for an insurance check.

    `checked` is either "never" (`last_insurance_debt` NULL) or "stale"
    (13 hours ago, past the 12-hour threshold). `start` keeps `ruz_id` disjoint
    between two groups in one test.
    """
    when = None
    if checked == "stale":
        when = timezone.now() - timedelta(hours=13)

    return [
        Company.objects.create(
            ruz_id=start + index,
            ico=f"{start + index:08d}",
            nazov_UJ=f"Firma {start + index}",
            pravna_forma="112",
            last_insurance_debt=when,
        )
        for index in range(count)
    ]


class InsuranceBatchBoundTests(TestCase):
    """The cap itself."""

    def test_the_batch_is_capped_at_the_limit(self):
        # 30 companies are due; the cap is what stops the queue growing.
        _companies(30)

        with mock.patch("registers.tasks.update_insurance_debt.delay") as delay:
            schedule_insurance_debt_checks(limit=10)

        self.assertEqual(delay.call_count, 10)

    def test_the_default_limit_is_what_one_tick_can_drain(self):
        """The cap is derived from `rate_limit`, so the two cannot drift apart.

        If `update_insurance_debt` is ever given a different rate, this fails
        and `INSURANCE_BATCH_PER_TICK` has to be revisited rather than silently
        describing a drain that no longer exists.
        """
        per_minute = int(str(update_insurance_debt.rate_limit).split("/")[0])

        self.assertEqual(
            INSURANCE_BATCH_PER_TICK, per_minute * 60 * INSURANCE_TICK_HOURS
        )

    def test_a_batch_larger_than_the_population_returns_everything(self):
        _companies(3)

        with mock.patch("registers.tasks.update_insurance_debt.delay") as delay:
            schedule_insurance_debt_checks(limit=1000)

        self.assertEqual(delay.call_count, 3)


class InsuranceBatchOrderTests(TestCase):
    """The order the batch is drawn in -- the subtle half of the fix."""

    def test_never_checked_companies_come_before_stale_ones(self):
        """Postgres sorts NULLs *last* under a plain ascending order.

        Without an explicit `nulls_first` the 25 398 companies whose timestamp
        is merely stale would be re-chosen every tick while the 414 419
        never-checked ones waited behind them for ever -- the same "a scheduled
        job that looks alive and never advances" defect this repository keeps
        finding, reached through a sort order rather than a missing cursor.
        """
        stale = _companies(5, start=1, checked="stale")
        never = _companies(5, start=101)

        with mock.patch("registers.tasks.update_insurance_debt.delay") as delay:
            schedule_insurance_debt_checks(limit=5)

        chosen = [call.args[0] for call in delay.call_args_list]
        self.assertEqual(set(chosen), {company.id for company in never})
        for company in stale:
            self.assertNotIn(company.id, chosen)

    def test_the_oldest_check_is_chosen_first_among_stale_companies(self):
        companies = _companies(5, checked="stale")
        oldest, newest = companies[0], companies[-1]
        Company.objects.filter(pk=oldest.pk).update(
            last_insurance_debt=timezone.now() - timedelta(days=9)
        )
        Company.objects.filter(pk=newest.pk).update(
            last_insurance_debt=timezone.now() - timedelta(hours=13)
        )

        with mock.patch("registers.tasks.update_insurance_debt.delay") as delay:
            schedule_insurance_debt_checks(limit=1)

        self.assertEqual(delay.call_args.args[0], oldest.id)


class InsuranceWatchPriorityTests(TestCase):
    """A watched company is drawn ahead of the never-checked crowd.

    The rotation absorbs 14 400 of ~414 000 never-checked companies per tick, so
    an unwatched company waits about a week for its first check. A watched one
    waited exactly as long, which is what made this a defect rather than a slow
    feature: `create_debt_change_event` needs two checks to have something to
    compare, so "Udalosti vo firme" could not fill for a company a reader had
    actually asked about. Measured 2026-09-13: 6 companies watched, 0 ever
    checked, 0 events.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            email="watcher@example.com", password="testpass123"
        )

    def test_a_watched_company_is_chosen_before_never_checked_ones(self):
        unwatched = _companies(5, start=1)
        watched = _companies(1, start=101)[0]
        Watchlist.objects.create(user=self.user, company=watched)

        with mock.patch("registers.tasks.update_insurance_debt.delay") as delay:
            schedule_insurance_debt_checks(limit=3)

        chosen = [call.args[0] for call in delay.call_args_list]
        self.assertEqual(chosen[0], watched.id)
        # The rest of the batch still goes to new ground.
        self.assertEqual(len(chosen), 3)
        self.assertTrue(set(chosen[1:]) <= {c.id for c in unwatched})

    def test_a_watched_company_is_found_even_at_a_limit_of_one(self):
        """`limit // 2` is 0 there, so the cap has a floor of one.

        Without it the smallest possible batch would be drawn entirely from the
        unwatched half and watching a company would do nothing exactly when the
        system is under the most pressure.
        """
        _companies(5, start=1)
        watched = _companies(1, start=101)[0]
        Watchlist.objects.create(user=self.user, company=watched)

        with mock.patch("registers.tasks.update_insurance_debt.delay") as delay:
            schedule_insurance_debt_checks(limit=1)

        self.assertEqual(delay.call_args.args[0], watched.id)

    def test_watched_companies_cannot_take_the_whole_batch(self):
        """The cap that keeps priority from becoming starvation.

        Watched companies are the *front* of the order, so without a cap a
        watchlist larger than `limit` would take every slot and the 414 419
        never-checked companies the rotation exists to reach would stop
        advancing -- a scheduled job that looks alive and never progresses,
        reached through priority rather than a missing cursor.
        """
        watched = _companies(10, start=1)
        unwatched = _companies(10, start=101)
        for company in watched:
            Watchlist.objects.create(user=self.user, company=company)

        with mock.patch("registers.tasks.update_insurance_debt.delay") as delay:
            schedule_insurance_debt_checks(limit=10)

        chosen = [call.args[0] for call in delay.call_args_list]
        self.assertEqual(len(chosen), 10)
        # Half the batch is new ground, so the general population keeps moving.
        self.assertEqual(len(set(chosen) & {c.id for c in unwatched}), 5)
        self.assertEqual(len(set(chosen) & {c.id for c in watched}), 5)

    def test_staleness_still_orders_companies_within_each_half(self):
        """Priority reorders the two halves; it does not replace the order."""
        watched_old = _companies(1, start=1)[0]
        watched_new = _companies(1, start=2)[0]
        for company in (watched_old, watched_new):
            Watchlist.objects.create(user=self.user, company=company)
        Company.objects.filter(pk=watched_old.pk).update(
            last_insurance_debt=timezone.now() - timedelta(days=9)
        )
        Company.objects.filter(pk=watched_new.pk).update(
            last_insurance_debt=timezone.now() - timedelta(hours=13)
        )

        with mock.patch("registers.tasks.update_insurance_debt.delay") as delay:
            schedule_insurance_debt_checks(limit=2)

        chosen = [call.args[0] for call in delay.call_args_list]
        self.assertEqual(chosen, [watched_old.id, watched_new.id])

    def test_the_watched_half_is_topped_up_when_there_is_nothing_else_due(self):
        """The cap is a ceiling, not a reservation -- a short batch is waste.

        With only watched companies due, capping the watched half at
        `limit // 2` would dispatch half a batch and idle the other half of the
        drain, which `rate_limit` does not give back. That state is not exotic:
        a caught-up rotation is the goal, and then the unwatched due set really
        does run dry.
        """
        watched = _companies(4, start=1)
        for company in watched:
            Watchlist.objects.create(user=self.user, company=company)

        with mock.patch("registers.tasks.update_insurance_debt.delay") as delay:
            schedule_insurance_debt_checks(limit=4)

        chosen = [call.args[0] for call in delay.call_args_list]
        self.assertEqual(len(chosen), 4)
        self.assertEqual(set(chosen), {c.id for c in watched})

    def test_a_recently_checked_watched_company_is_not_resurrected(self):
        """Priority is a reordering of the due set, not an exemption from it.

        A company whose debt was answered an hour ago is not due, watched or
        not -- otherwise watching a company would park it permanently in every
        batch and the queue would stop advancing.
        """
        watched = _companies(1, start=1)[0]
        Watchlist.objects.create(user=self.user, company=watched)
        Company.objects.filter(pk=watched.pk).update(
            last_insurance_debt=timezone.now() - timedelta(hours=1)
        )
        never_checked = _companies(1, start=2)[0]

        with mock.patch("registers.tasks.update_insurance_debt.delay") as delay:
            schedule_insurance_debt_checks(limit=5)

        self.assertEqual(delay.call_args.args[0], never_checked.id)


class InsuranceBatchSelectionTests(TestCase):
    """What is due -- unchanged by the cap, and worth pinning anyway."""

    def test_a_company_checked_recently_is_left_alone(self):
        companies = _companies(3)
        Company.objects.filter(pk=companies[0].pk).update(
            last_insurance_debt=timezone.now() - timedelta(hours=1)
        )

        with mock.patch("registers.tasks.update_insurance_debt.delay") as delay:
            schedule_insurance_debt_checks(limit=10)

        chosen = [call.args[0] for call in delay.call_args_list]
        self.assertNotIn(companies[0].id, chosen)
        self.assertEqual(len(chosen), 2)

    def test_nothing_due_means_nothing_enqueued(self):
        _companies(3)
        Company.objects.all().update(last_insurance_debt=timezone.now())

        with mock.patch("registers.tasks.update_insurance_debt.delay") as delay:
            schedule_insurance_debt_checks(limit=10)

        self.assertEqual(delay.call_count, 0)


class InsuranceSchedulerRoutingTests(TestCase):
    """The scheduler must not run on the queue it floods."""

    def test_the_scheduler_is_not_routed_to_the_insurance_queue(self):
        """It waited behind its own backlog and then fired repeatedly.

        Beat dispatched it at 07:50 on 2026-09-12; a worker first ran it after
        11:00, and it then executed at 03:11, 04:17, 11:14, 11:49, 12:04, 13:55,
        14:15, 14:19, 14:34, 14:39 and 14:53 -- each run enqueuing the whole due
        population.
        """
        task_name = "registers.tasks.schedule_insurance_debt_checks"

        self.assertNotEqual(
            settings.CELERY_TASK_ROUTES[task_name]["queue"], "insurance"
        )
        self.assertNotEqual(
            settings.CELERY_BEAT_SCHEDULE[
                "schedule-insurance-debt-checks-every-12-hours"
            ]["options"]["queue"],
            "insurance",
        )

    def test_the_beat_entry_carries_the_batch_size(self):
        """So the cap can be retuned from the scheduler row without a deploy."""
        entry = settings.CELERY_BEAT_SCHEDULE[
            "schedule-insurance-debt-checks-every-12-hours"
        ]

        self.assertEqual(entry["args"], [INSURANCE_BATCH_PER_TICK])

    def test_the_insurance_worker_is_still_the_only_consumer_of_its_queue(self):
        """`update_insurance_debt` keeps its rate limit and its own queue."""
        self.assertEqual(update_insurance_debt.rate_limit, "20/m")
        self.assertEqual(
            settings.CELERY_TASK_ROUTES["registers.tasks.update_insurance_debt"][
                "queue"
            ],
            "insurance",
        )
