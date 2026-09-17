"""Sídlo je odvodené z adresy — a odvodenina musí vedieť, že adresa sa zmenila.

`seat_*` spočítal `match_seat_addresses` raz, nad adresou, ktorá bola vtedy
v riadku. Do #148 neexistovala cesta, ktorá by ho zneplatnila: firma sa
presťahovala, synchronizácia prepísala `ulica`/`mesto`/`psc`, a pin zostal stáť
na starom adresnom bode — a to navždy, lebo matcher nebol naplánovaný.

Obe polovice opravy sú tu zastúpené. Zneplatnenie: `SeatInvalidationTests`
(zápis mení adresu), `UnplacedStateTests` (čím sa vyčistený riadok líši od
neumiestniteľného) a `PendingSeatTests` (čo z toho vidí API). Plán, ktorý
umiestnenie vráti: `SeatScheduleTests`.

Prostredie je zámerne presne toľko, koľko treba: `update_or_create` (cesta
synchronizácie), DRF `PATCH` (admin API) a holý `save()`. Tri diery, ktoré test
**neprikrýva**, sú pomenované pri testoch, ktoré na ne narazili — `bulk_update`,
`QuerySet.update()` a čiastočný `refresh_from_db`; diera, o ktorej test mlčí,
vyzerá ako pokrytie. Všetky tri sú dnes nedosiahnuteľné a všetky tri majú od
naplánovania matchera rovnakú hranicu: zmeškané zneplatnenie znamená pin na
starej adrese najviac šesť hodín, nie navždy.
"""

import importlib

from django.conf import settings
from django.test import TestCase
from django.utils import timezone

from adminapi.serializers.companies import AdminCompanyDetailSerializer
from companies.models import Company
from companies.tests_seat_location import _SeatFixtures
from registers.management.commands.match_seat_addresses import _wanted

# The register's own address point for the building below, so a pin that
# survives a test is recognisable as *this* pin and not as a coincidence.
PIN_LAT = 48.15231
PIN_LON = 17.12987


class _PlacedFixtures(_SeatFixtures):
    """A company the register has already placed on a building. No tests of its own."""

    def _placed(self, **kwargs):
        """The state a move has to invalidate: all six `seat_*` values and the stamp."""
        defaults = {
            'psc': '82108',
            'mesto': 'Bratislava',
            'ulica': 'Mlynské nivy 5',
            'seat_lat': PIN_LAT,
            'seat_lon': PIN_LON,
            'seat_precision': 'building',
            'seat_radius_m': 0,
            'seat_point_count': 1,
            'seat_tier': 'psc_ulica_orient',
            'seat_matched_at': timezone.now(),
        }
        defaults.update(kwargs)
        return self._company(**defaults)

    def _assert_pin_gone(self, company):
        """Reloads first, and that reload is the whole point.

        A fix that cleared the columns in memory but left them out of
        `update_fields` would pass an assertion made on the object in hand,
        because that object is not what the database holds. Reading the row
        back is the only version of this check that can fail for the right
        reason.
        """
        company.refresh_from_db()
        self.assertIsNone(company.seat_lat)
        self.assertIsNone(company.seat_lon)
        self.assertEqual(company.seat_precision, '')
        self.assertIsNone(company.seat_radius_m)
        self.assertIsNone(company.seat_point_count)
        self.assertEqual(company.seat_tier, '')
        self.assertIsNone(company.seat_matched_at)


class SeatInvalidationTests(_PlacedFixtures):
    """When the address moves, the pin must not stay behind."""

    def test_the_sync_path_clears_the_pin_when_the_company_moves(self):
        """`update_or_create`, which is how every RUZ sync writes an address.

        This is the path the whole fix is about, and the one that would fail
        silently: `update_or_create` calls `save(update_fields=set(defaults))`,
        so clearing `seat_*` on the object is not enough — unless the names are
        added to `update_fields`, the UPDATE never mentions those columns and
        the database keeps the old pin while the log says the company was
        imported.

        The fallback area is created too, so that what the reader gets instead
        of the pin is the PSČ circle rather than nothing at all.
        """
        company = self._placed()
        self._area(psc='04001')

        Company.objects.update_or_create(
            ruz_id=company.ruz_id,
            defaults={'psc': '04001', 'mesto': 'Košice', 'ulica': 'Hlavná 1'},
        )

        self._assert_pin_gone(company)
        self.assertEqual(company.psc, '04001', 'the new address is the stored one')
        seat = self._seat(company)
        self.assertEqual(seat['precision'], 'postal_code')
        self.assertTrue(seat['pending'])

    def test_the_admin_api_path_clears_the_pin_too(self):
        """The DRF update path: `setattr` then a bare `instance.save()`.

        Different from the sync path in exactly the way that matters here — no
        `update_fields` at all, so every column is written. Worth its own test
        because a fix that only handled `update_fields` would pass the test
        above and fail this one, and `AdminCompanyDetailSerializer` is what
        serves `PATCH` on the admin company detail endpoint.
        """
        company = self._placed()

        serializer = AdminCompanyDetailSerializer(
            company, data={'ulica': 'Hlavná 1'}, partial=True
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        self._assert_pin_gone(company)

    def test_a_plain_save_clears_the_pin(self):
        """The third shape: an object edited in hand and saved whole."""
        company = self._placed()

        company.ulica = 'Hlavná 1'
        company.save()

        self._assert_pin_gone(company)

    def test_an_object_created_in_memory_is_not_a_blind_spot(self):
        """`Company(...)` never passes through `from_db`, and that nearly hid a gap.

        The fixture is built by `create()`, so this is the ordinary shape of a
        row that was *written* rather than *read*: the first `save()` has no
        stored address to compare against, and unless it records one, every
        later `save()` on that object is blind — the second write would move
        the address and keep the pin. Found by this suite failing on the test
        above, which is why the assertion is here and not only in a comment.
        """
        company = self._placed()
        self.assertEqual(
            company._stored_address,
            ('82108', 'Bratislava', 'Mlynské nivy 5'),
            'the write recorded what the row now holds',
        )

        company.ulica = 'Hlavná 1'
        company.save()

        self._assert_pin_gone(company)

    def test_a_sync_that_writes_the_same_address_keeps_the_pin(self):
        """The other direction, and the reason `from_db` exists at all.

        Every 6 h the RUZ sync rewrites the address of every company it reads.
        If a write counted as a change, the pin of every company in the book
        would be dropped on every pass, and the map would say "still computing"
        for a population nobody moved — the failure that would make this fix
        worse than the bug it repairs.
        """
        company = self._placed()

        Company.objects.update_or_create(
            ruz_id=company.ruz_id,
            defaults={'psc': '82108', 'mesto': 'Bratislava', 'ulica': 'Mlynské nivy 5'},
        )

        company.refresh_from_db()
        self.assertEqual(company.seat_lat, PIN_LAT)
        self.assertEqual(company.seat_precision, 'building')
        self.assertIsNotNone(company.seat_matched_at)

    def test_a_save_that_does_not_touch_the_address_keeps_the_pin(self):
        """`save(update_fields=...)` without the address must not invalidate.

        The address in memory may already differ from the row while the column
        it names is not being written. Invalidating there would clear a pin for
        a company whose stored address is still the one the pin was computed
        from.
        """
        company = self._placed()

        company.ulica = 'Hlavná 1'
        company.nazov_UJ = 'Premenovaná, s. r. o.'
        company.save(update_fields=['nazov_UJ'])

        company.refresh_from_db()
        self.assertEqual(company.ulica, 'Mlynské nivy 5', 'the address column was not written')
        self.assertEqual(company.seat_lat, PIN_LAT)

    def test_a_sync_that_sends_no_address_does_not_wipe_the_pin(self):
        """`defaults` is built with `data.get(...)`, so a missing key writes `None`.

        A naive "the address changed" test — comparing key presence instead of
        values, or counting a drop to empty as a move — would read that as a
        relocation and clear the pin. The company did not move; the payload was
        incomplete. And this is the direction that cannot be undone: the pin is
        gone until the next matching run, and the matcher is the only thing
        that can put it back.
        """
        company = self._placed()

        Company.objects.update_or_create(
            ruz_id=company.ruz_id, defaults={'mesto': '', 'ulica': None}
        )

        company.refresh_from_db()
        self.assertEqual(company.seat_precision, 'building')
        self.assertEqual(company.seat_lat, PIN_LAT)

    def test_a_company_that_never_moves_keeps_its_pin_across_many_writes(self):
        """Repeated writes, because the 6-hourly sync is not a single pass.

        The failure mode this rules out is cumulative: an invalidation that
        fires on the second write of the same address would leave the pin gone
        for good, since nothing re-runs the matcher until the next scheduled
        pass.
        """
        company = self._placed()

        for _ in range(3):
            Company.objects.update_or_create(
                ruz_id=company.ruz_id,
                defaults={
                    'psc': '82108',
                    'mesto': 'Bratislava',
                    'ulica': 'Mlynské nivy 5',
                    'nazov_UJ': 'Test, s. r. o.',
                },
            )

        company.refresh_from_db()
        self.assertEqual(company.seat_lat, PIN_LAT)
        self.assertEqual(company.seat_precision, 'building')

    def test_bulk_update_of_the_address_leaves_a_stale_pin_behind(self):
        """A known gap, pinned as a gap so it cannot be mistaken for coverage.

        `bulk_update` compiles to one `UPDATE ... CASE` per field and never
        calls `save()`, so the hook does not see it. Nothing in this repository
        writes the address that way — `match_seat_addresses` is the only
        `bulk_update` here and it writes `seat_*`, which is the derived half
        and is fine to write directly — so the gap is real but unreachable
        today.

        The assertion is on the *stale* outcome on purpose: whoever adds such a
        call gets a failure that names this docstring, instead of a pin that
        quietly stays on the old address. The alternative — asserting the
        correct outcome — would fail today and could only be satisfied by
        catching `bulk_update`, which Django gives no hook for.

        What a missed invalidation costs is bounded by the schedule and not by
        this hook: `match-seat-addresses-every-6-hours` recomputes every row
        from the address it holds, so a pin left behind here is wrong for at
        most six hours. Before the matcher was scheduled the same gap was
        permanent, which is why this one is a recorded edge rather than a
        blocker.
        """
        company = self._placed()

        company.ulica = 'Hlavná 1'
        company.mesto = 'Košice'
        company.psc = '04001'
        Company.objects.bulk_update([company], ['ulica', 'mesto', 'psc'])

        company.refresh_from_db()
        self.assertEqual(company.psc, '04001', 'the address really did move')
        self.assertEqual(company.seat_lat, PIN_LAT, 'and the pin did not follow')

    def test_a_queryset_update_of_the_address_leaves_a_stale_pin_behind(self):
        """The same gap, by the other door Django leaves open.

        `QuerySet.update()` never loads an object, so there is no `save()` and
        no `from_db` to hook either. Also unused for the address in this
        repository — recorded for the same reason as the test above, because
        "we handle the address change" is a claim that should name its edges.
        Bounded by the six-hour matcher in the same way.
        """
        company = self._placed()

        Company.objects.filter(pk=company.pk).update(psc='04001', mesto='Košice', ulica='Hlavná 1')

        company.refresh_from_db()
        self.assertEqual(company.psc, '04001')
        self.assertEqual(company.seat_lat, PIN_LAT)

    def test_a_partial_refresh_after_a_move_leaves_a_stale_pin_behind(self):
        """The third door, and the only one this repository could still close.

        `refresh_from_db(fields=[...])` over a subset leaves the address in
        memory a mix of the old load and the new one, so the hook deliberately
        forgets the stored address rather than compare against a half-loaded
        row -- see `refresh_from_db`. That is the safe direction, since it
        declines to invalidate instead of invalidating blindly, but it does mean
        a write on that object afterwards cannot see a move.

        Unlike `bulk_update` and `QuerySet.update()`, Django does give a hook
        here, so this gap could be closed by re-reading the three address
        columns when `fields` omits them. It is left open because that costs an
        extra query on a path nothing in this repository takes -- no caller
        passes `fields` -- and because the scheduled matcher now recomputes the
        placement from the stored address within six hours anyway. Recorded so
        the first `refresh_from_db(fields=[...])` on a `Company` meets this
        docstring rather than a pin that quietly stays on the old address.
        """
        company = self._placed()

        company.refresh_from_db(fields=['nazov_UJ'])
        company.ulica = 'Hlavná 1'
        company.save()

        company.refresh_from_db()
        self.assertEqual(company.ulica, 'Hlavná 1', 'the address really did move')
        self.assertEqual(company.seat_lat, PIN_LAT, 'and the pin did not follow')


class UnplacedStateTests(_PlacedFixtures):
    """The two "no pin" states differ in exactly one column, and that is the API."""

    def test_a_cleared_seat_is_what_the_matcher_writes_for_an_unplaced_row(self):
        """The cleared values must equal `_wanted(None)`, minus the stamp.

        `_wanted(None)` is what `match_seat_addresses` writes for a company the
        register cannot place, and it stamps `seat_matched_at` on the way out —
        for unplaced rows too, which is the fact the whole distinction rests
        on. A cleared seat has to be those same six values with **no** stamp.
        If the two drifted, "we have not computed this yet" and "the register
        cannot place this" would collapse back into one row and the card would
        have nothing left to tell apart.
        """
        company = self._placed()

        Company.objects.update_or_create(
            ruz_id=company.ruz_id, defaults={'ulica': 'Hlavná 1'}
        )
        company.refresh_from_db()

        self.assertEqual(
            tuple(getattr(company, f) for f in Company.SEAT_FIELDS),
            _wanted(None),
        )
        self.assertIsNone(company.seat_matched_at)

    def test_every_seat_column_is_in_the_invalidation_set(self):
        """A seventh `seat_*` column must not be silently left out of the clear.

        The set is written by hand once, in the model; this is what makes
        forgetting it a failed test rather than a column that keeps a stale
        value on every company that moves. `SEAT_FIELDS` is also what
        `match_seat_addresses` reads and writes, so this pins both halves.
        """
        on_model = {f.name for f in Company._meta.get_fields() if f.name.startswith('seat_')}

        self.assertEqual(on_model, set(Company.SEAT_INVALIDATION_FIELDS))
        self.assertEqual(
            set(Company.SEAT_FIELDS) | {'seat_matched_at'},
            set(Company.SEAT_INVALIDATION_FIELDS),
        )


class PendingSeatTests(_PlacedFixtures):
    """`pending` is the sentence the card needs, so it has to be right at the source."""

    def test_a_moved_company_reads_as_pending_not_as_unplaceable(self):
        """The point of the whole change, seen from the API.

        Before the address moved the row was a building pin. After it, the pin
        is gone and the PSČ circle is what is left — and the circle alone does
        not say *why*. `pending` is that why, and it is the difference between
        a card that says "the register knows only the PSČ centre" (a claim
        about a database nobody queried for this address) and one that says we
        have not computed it yet.
        """
        self._area(psc='82108')
        company = self._placed()
        self.assertFalse(self._seat(company)['pending'])

        Company.objects.update_or_create(
            ruz_id=company.ruz_id, defaults={'ulica': 'Hlavná 1'}
        )
        company.refresh_from_db()

        seat = self._seat(company)
        self.assertEqual(seat['precision'], 'postal_code')
        self.assertTrue(seat['pending'])

    def test_an_unplaced_company_the_matcher_reached_is_not_pending(self):
        """14,5 % of rows: asked and answered. The circle is the answer."""
        self._area(psc='82108')
        company = self._company(psc='82108', seat_matched_at=timezone.now())

        seat = self._seat(company)
        self.assertEqual(seat['precision'], 'postal_code')
        self.assertFalse(seat['pending'])

    def test_a_company_the_matcher_has_not_reached_is_pending(self):
        """A row imported after the last run has no stamp, and that is not a fault.

        It also covers the rows matched before migration 0022 added
        `seat_matched_at` — the column was never backfilled, so an old unplaced
        row reads as pending until the matcher next touches it, which the 6 h
        schedule now does. Erring this way is the safe direction: the card
        promises less, and the next pass makes it true.
        """
        self._area(psc='82108')
        company = self._company(psc='82108')

        self.assertIsNone(company.seat_matched_at)
        self.assertTrue(self._seat(company)['pending'])

    def test_a_placed_seat_is_never_pending(self):
        """There is no fallback to explain, so there is nothing to be pending about.

        Including the pre-0022 pins, whose stamp is missing while the pin
        itself is not: the row below has no `seat_matched_at` at all, and the
        map still gets its building.
        """
        self._area()
        company = self._company(
            psc='82108',
            seat_lat=PIN_LAT,
            seat_lon=PIN_LON,
            seat_precision='building',
            seat_radius_m=0,
        )

        seat = self._seat(company)
        self.assertEqual(seat['precision'], 'building')
        self.assertFalse(seat['pending'])

    def test_a_psc_the_register_does_not_list_is_still_none(self):
        """`pending` must not turn an unanswerable PSČ into a drawn one.

        The circle is looked up from the address the row carries *now*, so a
        moved company whose new PSČ is unknown has nothing honest to draw —
        and that stays `None` whether or not a match is pending.
        """
        self._area(psc='82108')
        company = self._placed()

        Company.objects.update_or_create(
            ruz_id=company.ruz_id, defaults={'psc': '94001', 'mesto': 'Nové Zámky'}
        )
        company.refresh_from_db()

        self.assertIsNone(self._seat(company))


class SeatScheduleTests(TestCase):
    """The invalidation is only half the fix; the pass that undoes it must run.

    Clearing `seat_*` is immediate, but the placement only comes back when
    `match_seat_addresses` runs again. Nothing scheduled it before #148 — the
    command had only ever been run by hand — so a cleared pin stayed cleared,
    which would have made the invalidation worse than the stale pin it replaced.
    """

    ENTRY = 'match-seat-addresses-every-6-hours'

    def _entry(self):
        return settings.CELERY_BEAT_SCHEDULE[self.ENTRY]

    def _task(self):
        module_path, _, attribute = self._entry()['task'].rpartition('.')
        module = importlib.import_module(module_path)
        return getattr(module, attribute)

    def test_the_entry_names_a_task_that_exists(self):
        """A misspelled task name is a schedule that never runs and never says so.

        Celery logs `Received unregistered task` and discards the message; the
        beat row keeps its `last_run_at` moving, so every layer looks healthy
        while no pass ever happens. Importing the name from the entry is the
        only check that can fail for that reason.
        """
        task = self._task()

        self.assertTrue(callable(task), self._entry()['task'])
        self.assertTrue(hasattr(task, 'delay'), 'not a Celery task: no .delay')

    def test_the_matcher_is_not_scheduled_onto_a_lane_it_would_block(self):
        """Same reason `detect_stuck_sync_jobs` and the insurance dispatcher are not.

        `ruz_full` holds the incremental sync's cursor, so a minutes-long
        full-table sweep queued there would delay a data import behind work that
        is not an import; `orsr` and `insurance` are rate-limited against
        somebody else's server, and this command reads only our own database.
        """
        queue = self._entry()['options']['queue']

        self.assertEqual(queue, 'celery')
        for blocked in ('ruz_full', 'orsr', 'insurance'):
            self.assertNotEqual(queue, blocked)
        self.assertNotEqual(
            settings.CELERY_TASK_ROUTES.get(self._entry()['task'], {}).get('queue'),
            'ruz_full',
        )

    def test_the_matcher_never_runs_less_often_than_the_sync_that_moves_addresses(self):
        """The invariant behind the interval, rather than the number itself.

        `fetch-ruz-data` is what writes a new address, and every such write
        clears the seat. If the matcher ran less often than that sync, a company
        that moved would be left with no seat for longer than the window that
        moved it -- and the debt would accumulate instead of being cleared.
        Tying the two together means retuning the sync cannot silently break
        this, which a hard-coded `21600` would not catch.
        """
        entry = self._entry()
        ruz_sync = settings.CELERY_BEAT_SCHEDULE['fetch-ruz-data-every-6-hours']

        self.assertLessEqual(entry['schedule'], ruz_sync['schedule'])
        self.assertGreater(entry['options']['expires'], 0)
        self.assertLess(entry['options']['expires'], entry['schedule'])
