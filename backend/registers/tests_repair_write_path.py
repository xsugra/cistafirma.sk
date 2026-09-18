"""A repair run must not take over a row that belongs to another entity.

All three repair commands (`repair_ruz_sync`, `repair_ruz_sync_v2`,
`repair_ruz_gaps`) restricted themselves to RUZ ids the database did not already
hold, and then upserted with `Company.objects.update_or_create(ico=...)`.

`ico` is `unique`, so when the register answers one IČO with a second entity the
lookup finds the **incumbent** row, and the defaults re-stamp its `ruz_id` to the
new entity. That is not an update, it is an identity swap: the incumbent entity
disappears from the database, the row now claims to be its sibling, and the run
counts it as `skipped` / `repaired` rather than as a problem. The register really
does answer one IČO with more than one entity -- `00177474` comes back as three
distinct ones (`ruz_id` 1677, 1049449, 1070716) -- so this is reachable, not
theoretical.

`ruz_id` is the register's own key and the one the walk keys on
(`fetch_ruz_data.update_or_create_company`), whose comment states the contract
plainly: "What the walk writes is keyed on `ruz_id` ... so a duplicate IČO can
never silently swap two entities' identities." These tests hold the repair
commands to it.

They are written against the *outcome* -- which entity a row claims to be, and
what the run says it did -- rather than against the lookup keyword, so they keep
their meaning if the fix is written differently.

The third command is here for the opposite reason. `repair_ruz_sync` (v1) is a
half-finished rewrite that cannot run at all, and the test asserts it keeps
refusing rather than quietly becoming reachable again; see its module docstring.

Two of these tests are about the *work list* rather than the write, and they are
in this file because it is the same mistake one level up: `Company` alone was
the whole of "already held", while the register's natural persons live in
`IndividualEntity` and are absent from `Company` by design.
"""

from datetime import date
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from companies.models import Company
from registers.models import IndividualEntity, SyncGapAnalysis, SyncProgress
from registers.services.ruz_repair_writer import CREATED, UPDATED, RepairWriter


class _InlineExecutor:
    """Runs the batch on the calling thread instead of a worker pool.

    A worker thread opens its own database connection that outlives the test --
    enough for `DROP DATABASE test_cistafirma` to fail at teardown. Nothing here
    is about concurrency; see `tests_repair_job_tracking.py`.
    """

    def __init__(self, max_workers=None):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def map(self, func, iterable):
        return [func(item) for item in iterable]


_INLINE_CONCURRENCY = SimpleNamespace(
    futures=SimpleNamespace(ThreadPoolExecutor=_InlineExecutor)
)

# The register's own example: one IČO, three distinct entities. The walk can only
# ever hold one of them, because `ico` is unique -- and whichever it holds is the
# row a repair must not re-stamp.
SHARED_ICO = '00177474'
INCUMBENT_RUZ_ID = 1677
SIBLING_RUZ_ID = 1049449


class _FakeRuzApi:
    """Pages of ids, and one canned record per id."""

    def __init__(self, pages, records):
        self._pages = list(pages)
        self._records = records
        self.detail_calls = []

    def get_changed_company_ids(self, zmenene_od=None, pokracovat_za_id=None, max_zaznamov=None):
        if not self._pages:
            return {"id": [], "existujeDalsieId": False}
        page = self._pages.pop(0)
        return {"id": page, "existujeDalsieId": bool(self._pages)}

    def get_company_details(self, company_id):
        self.detail_calls.append(company_id)
        record = self._records.get(company_id)
        if record is None:
            return None
        return {"id": company_id, **record}


def _incumbent():
    """The entity the database holds under the shared IČO."""
    return Company.objects.create(
        ruz_id=INCUMBENT_RUZ_ID,
        ico=SHARED_ICO,
        nazov_UJ='DHZ Sološnica',
        mesto='Sološnica',
        datum_zalozenia=date(1998, 5, 4),
    )


class RepairSyncV2IdentityTests(TestCase):
    """`repair_ruz_sync_v2`, the command `start_repair_sync` dispatches."""

    def _run(self, pages, records, **options):
        api = _FakeRuzApi(pages, records)
        with patch(
            "registers.management.commands.repair_ruz_sync_v2.RuzApi",
            return_value=api,
        ), patch(
            "registers.management.commands.repair_ruz_sync_v2.concurrent",
            _INLINE_CONCURRENCY,
        ):
            call_command(
                "repair_ruz_sync_v2",
                stdout=StringIO(),
                stderr=StringIO(),
                **options,
            )
        return api

    def test_a_second_entity_under_a_held_ico_does_not_take_over_the_row(self):
        """The register answers the incumbent's IČO with a second entity, whose
        `ruz_id` the database does not hold -- so the command fetches it, and the
        IČO-keyed upsert finds the incumbent.

        The incumbent must still be the incumbent afterwards. Re-stamping its
        `ruz_id` would make the row claim to be an entity it is not, and would
        delete the entity it was: one row silently becomes another, with nothing
        in the run's own counters to say so.
        """
        incumbent = _incumbent()

        self._run(
            [[SIBLING_RUZ_ID]],
            {SIBLING_RUZ_ID: {'ico': SHARED_ICO, 'nazovUJ': 'DHZ Nová Kelča'}},
        )

        incumbent.refresh_from_db()
        self.assertEqual(incumbent.ruz_id, INCUMBENT_RUZ_ID)
        self.assertEqual(incumbent.nazov_UJ, 'DHZ Sološnica')
        self.assertEqual(incumbent.mesto, 'Sološnica')
        self.assertEqual(incumbent.datum_zalozenia, date(1998, 5, 4))

    def test_the_sibling_is_not_silently_stored_as_the_incumbent(self):
        """The other half of the same write: the row must not end up holding the
        sibling's `ruz_id` either. One IČO is one row, and `ruz_id` is unique, so
        the register's second entity has nowhere to go -- which is a fact to
        report, not to resolve by overwriting whoever holds the IČO.
        """
        _incumbent()

        self._run(
            [[SIBLING_RUZ_ID]],
            {SIBLING_RUZ_ID: {'ico': SHARED_ICO, 'nazovUJ': 'DHZ Nová Kelča'}},
        )

        self.assertFalse(Company.objects.filter(ruz_id=SIBLING_RUZ_ID).exists())

    def test_the_run_does_not_report_a_takeover_as_ordinary_work(self):
        """A refused write is not a skipped record and not a repaired one. It is
        the one outcome an operator has to look at, so it has to land in the
        error counter -- the counter that is read, rather than the stdout nobody
        tails for hours.
        """
        _incumbent()

        self._run(
            [[SIBLING_RUZ_ID]],
            {SIBLING_RUZ_ID: {'ico': SHARED_ICO, 'nazovUJ': 'DHZ Nová Kelča'}},
        )

        progress = SyncProgress.objects.get(sync_type='repair')
        self.assertEqual(progress.total_errors, 1)
        self.assertEqual(progress.total_created, 0)

    def test_the_reason_is_on_the_row_after_the_run_ends(self):
        """A count is not a reason. The old handler bound the exception and never
        read it, so a run whose every write was refused ended `completed`, with a
        number and no cause anywhere -- not on the row, not in a log, not on
        stderr. The command now keeps the last 20 reasons on `last_error`, and
        the point of that column is that it outlives the process that wrote it.
        """
        _incumbent()

        self._run(
            [[SIBLING_RUZ_ID]],
            {SIBLING_RUZ_ID: {'ico': SHARED_ICO, 'nazovUJ': 'DHZ Nová Kelča'}},
        )

        progress = SyncProgress.objects.get(sync_type='repair')
        self.assertTrue(progress.last_error)
        self.assertIn(str(SIBLING_RUZ_ID), progress.last_error)

    def test_an_id_the_individual_table_holds_is_not_re_fetched(self):
        """The work list has to mean "the database does not hold this record",
        and the database is two tables.

        `IndividualEntity` is where the register's natural persons live; every
        one of its `ruz_id`s is absent from `Company` by design (measured on dell
        2026-09-18: 35 339 rows and not one of them in `Company` -- the count is a
        snapshot that only grows while the walk runs, the zero overlap is what
        does not change). While the work list asked `Company` alone, that whole
        population was permanently "missing": every run re-fetched all 35k detail
        pages, re-upserted rows that were already correct, and counted each one as
        new work -- so a repair could never report that it had converged.

        The assertion is on the fetch, not the write: not being fetched is what
        makes the list finite, and it holds however the record would have been
        stored.
        """
        IndividualEntity.objects.create(
            ruz_id=4000001, ico='22222222', nazov_UJ='Ján Živnostník',
        )

        api = self._run(
            [[4000001]],
            {4000001: {'ico': '22222222', 'nazovUJ': 'Ján Živnostník'}},
        )

        self.assertEqual(api.detail_calls, [])
        self.assertFalse(Company.objects.filter(ruz_id=4000001).exists())

    def test_a_genuinely_new_record_is_still_created(self):
        """The positive control. A repair that refuses everything is not a fix,
        and a test that only ever asserts absence would pass against one.
        """
        _incumbent()

        self._run(
            [[2000001]],
            {2000001: {'ico': '54572495', 'nazovUJ': 'poctivé sirupy s. r. o.'}},
        )

        created = Company.objects.get(ruz_id=2000001)
        self.assertEqual(created.ico, '54572495')
        self.assertEqual(created.nazov_UJ, 'poctivé sirupy s. r. o.')


class GapRepairIdentityTests(TestCase):
    """`repair_ruz_gaps`, the command the admin's gap-repair button dispatches.

    Its `_fetch_and_save` carries the swap as a comment -- "Existujúca firma s
    iným RUZ ID - aktualizujeme" -- which is the defect stated as if it were the
    design.
    """

    def _analysis(self, gap_ranges):
        return SyncGapAnalysis.objects.create(
            status='ready',
            analyzed_min_id=gap_ranges[0][0],
            analyzed_max_id=gap_ranges[-1][1],
            total_missing=sum(b - a + 1 for a, b in gap_ranges),
            total_gaps=len(gap_ranges),
            gap_ranges=gap_ranges,
        )

    def _run(self, analysis, records):
        api = _FakeRuzApi([], records)
        with patch(
            "registers.management.commands.repair_ruz_gaps.RuzApi",
            return_value=api,
        ), patch(
            "registers.management.commands.repair_ruz_gaps.concurrent",
            _INLINE_CONCURRENCY,
        ):
            call_command(
                "repair_ruz_gaps",
                analysis_id=analysis.pk,
                stdout=StringIO(),
                stderr=StringIO(),
            )
        return api

    def test_the_gap_repair_does_not_take_over_the_holder(self):
        incumbent = _incumbent()
        analysis = self._analysis([[SIBLING_RUZ_ID, SIBLING_RUZ_ID]])

        self._run(
            analysis,
            {SIBLING_RUZ_ID: {'ico': SHARED_ICO, 'nazovUJ': 'DHZ Nová Kelča'}},
        )

        incumbent.refresh_from_db()
        self.assertEqual(incumbent.ruz_id, INCUMBENT_RUZ_ID)
        self.assertEqual(incumbent.nazov_UJ, 'DHZ Sološnica')

    def test_the_gap_repair_does_not_count_it_as_repaired(self):
        _incumbent()
        analysis = self._analysis([[SIBLING_RUZ_ID, SIBLING_RUZ_ID]])

        self._run(
            analysis,
            {SIBLING_RUZ_ID: {'ico': SHARED_ICO, 'nazovUJ': 'DHZ Nová Kelča'}},
        )

        analysis.refresh_from_db()
        self.assertEqual(analysis.error_count, 1)
        self.assertEqual(analysis.repaired_count, 0)

    def test_a_genuinely_missing_record_is_still_repaired(self):
        """Positive control, as above: the gap repair's whole purpose is to fill
        a hole, and it must still fill one.
        """
        analysis = self._analysis([[2000001, 2000001]])

        self._run(analysis, {2000001: {'ico': '54572495', 'nazovUJ': 'poctivé sirupy'}})

        self.assertEqual(Company.objects.get(ruz_id=2000001).ico, '54572495')


class RepairWriterDelegationTests(TestCase):
    """A repair must store what the walk would have stored.

    The three commands each carried their own `defaults` dict, and it was a
    *different* mapping from the walk's: it omitted the SZCO routing of legal
    forms 100-110 and 422, it read the dates with a bare `parse_date`, and it did
    not strip the IČO. A repair that stores a record differently from the walk is
    a repair whose result depends on which command happened to see the record
    first, which is not a property anyone can reason about.

    These tests go to the writer directly rather than through a command: the
    delegation is the thing being asserted, and it is the same object in all
    three.
    """

    def _writer(self):
        return RepairWriter(StringIO(), StringIO())

    def test_a_natural_person_goes_to_the_individual_table(self):
        """Legal forms 100-110 and 422 are natural persons. Stored as a
        `Company`, each one is a row in the table the public search reads, for a
        person the register never described as an organisation -- and the admin
        then lists them as companies.
        """
        outcome, _ = self._writer().store(
            5000001,
            {'id': 5000001, 'ico': '33333333', 'nazovUJ': 'Mária Živnostníčka',
             'pravnaForma': '101'},
        )

        self.assertEqual(outcome, CREATED)
        self.assertTrue(IndividualEntity.objects.filter(ruz_id=5000001).exists())
        self.assertFalse(Company.objects.filter(ruz_id=5000001).exists())

    def test_an_unreadable_date_does_not_clear_a_stored_one(self):
        """The date half of the same write.

        `parse_date` answers `None` for a value it cannot read, and `None` in
        `defaults` is what `update_or_create` writes -- so a payload whose date
        format changed would erase every stored date it touched, silently, and
        the sync after the fix would restore them as false dissolution
        notifications. `apply_ruz_dates` tells an *absent* value (a statement:
        not dissolved) from *noise* (no statement at all) and omits the field for
        the second, which leaves the stored value alone.
        """
        Company.objects.create(
            ruz_id=5000002, ico='44444444', nazov_UJ='Stará Firma',
            datum_zrusenia=date(2020, 1, 1),
        )

        outcome, _ = self._writer().store(
            5000002,
            {'id': 5000002, 'ico': '44444444', 'nazovUJ': 'Stará Firma',
             'datumZrusenia': 'zrušená kdysi'},
        )

        self.assertEqual(outcome, UPDATED)
        self.assertEqual(
            Company.objects.get(ruz_id=5000002).datum_zrusenia, date(2020, 1, 1)
        )

    def test_the_same_payload_still_clears_a_date_it_states_is_absent(self):
        """The positive control for the test above, and the reason the guard
        cannot simply refuse every missing date: omitting the key is the only way
        RUZ says "this company is not dissolved". A writer that treated absence
        as noise too would never record a resurrection.
        """
        Company.objects.create(
            ruz_id=5000003, ico='55555555', nazov_UJ='Obnovená Firma',
            datum_zrusenia=date(2020, 1, 1),
        )

        self._writer().store(
            5000003,
            {'id': 5000003, 'ico': '55555555', 'nazovUJ': 'Obnovená Firma'},
        )

        self.assertIsNone(Company.objects.get(ruz_id=5000003).datum_zrusenia)

    def test_the_ico_is_stored_stripped(self):
        """The register pads old 6- and 7-digit IČO to eight characters with
        spaces, so an unstripped value never matches a lookup. `.strip()` and
        only `.strip()`: `.zfill(8)` would merge `'177474  '` and `'00177474'`,
        which are two different organisational units.
        """
        self._writer().store(
            5000004,
            {'id': 5000004, 'ico': '  54381151  ', 'nazovUJ': 'Poctivé Sirupy'},
        )

        self.assertEqual(Company.objects.get(ruz_id=5000004).ico, '54381151')


class RepairSyncV1IsRefusedTests(TestCase):
    """The superseded first command refuses, and touches nothing on the way out.

    `repair_ruz_sync` is a half-finished rewrite: it calls an undefined
    `self._fetch_and_save_company`, reads `api`, `total_missing` and three
    counters before they are ever assigned, and fetches every page twice. It
    cannot run, and it is not invoked by anything -- but its name is the obvious
    one, so an operator reaches for it.

    It used to raise `AttributeError` from inside a thread pool, and the
    `except Exception` around the loop then wrote `failed` onto the
    `sync_type='repair'` progress row -- the row `repair_ruz_sync_v2` uses as its
    own cursor. So the failure was not contained to a command nobody calls.

    These tests are a guard, not a description of behaviour worth having: if the
    command is made runnable again it must be by someone who has read its
    docstring, and it must come with a job row, a heartbeat and the global lock
    the way #186 gave them to its replacement.
    """

    def test_it_refuses_and_names_the_command_that_replaced_it(self):
        with self.assertRaises(CommandError) as caught:
            call_command('repair_ruz_sync', stdout=StringIO(), stderr=StringIO())

        self.assertIn('repair_ruz_sync_v2', str(caught.exception))

    def test_it_refuses_before_it_can_touch_the_shared_progress_row(self):
        with self.assertRaises(CommandError):
            call_command('repair_ruz_sync', stdout=StringIO(), stderr=StringIO())

        self.assertFalse(SyncProgress.objects.filter(sync_type='repair').exists())
