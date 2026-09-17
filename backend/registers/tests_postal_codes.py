"""The MV SR address import: the two traps, and the radius it promises.

The traps are the reason this file exists rather than trusting a one-off run.
Both are silent: a naive import produces a plausible-looking table either way,
and the damage only shows up as pins in the wrong place.
"""

import math
import os
import tempfile
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from companies.models import MIN_ADDRESS_POINTS, Company, PostalCodeArea

HEADER = (
    'IDENTIFIKATOR;KRAJ;OKRES;OBEC;CAST_OBCE;ULICA;SUPISNE_CISLO;'
    'ORIENTACNE_CISLO_CELE;PSC;ADRBOD_X;ADRBOD_Y'
)


def _row(index, psc, lon, lat, obec='Obec', okres='Okres', kraj='Kraj'):
    # The real file writes decimal *commas*; keeping that here means the parse
    # is exercised rather than assumed.
    def num(value):
        return f'{value}'.replace('.', ',')

    return f'{index};{kraj};{okres};{obec};;Ulica;1;;{psc};{num(lon)};{num(lat)}'


def _metres(lon1, lat1, lon2, lat2):
    dx = (lon1 - lon2) * 111_320 * math.cos(math.radians(lat1))
    dy = (lat1 - lat2) * 111_320
    return math.hypot(dx, dy)


class PostalCodeImportTests(TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)

    def _write(self, lines, name='adresy.csv'):
        path = os.path.join(self._dir.name, name)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(HEADER + '\n')
            for line in lines:
                fh.write(line + '\n')
        return path

    def _spread(self, psc, n, lon0=19.0, lat0=48.6, step=0.001):
        """`n` address points in a line, so the radius is a real number."""
        return [
            _row(i, psc, round(lon0 + i * step, 6), lat0) for i in range(n)
        ]

    def _run(self, path, **options):
        out = StringIO()
        call_command('import_postal_codes', path, stdout=out, **options)
        return out.getvalue()

    def test_a_healthy_psc_is_stored_with_a_radius_that_really_covers_90_percent(self):
        """The promise in the docstring, checked as a property.

        Asserted as "at least 90 % of the source's own points fall inside the
        stored radius" rather than against a re-implementation of the
        percentile: a test that recomputes the formula would agree with a wrong
        formula.
        """
        self._run(self._write(self._spread('97632', 25)))

        area = PostalCodeArea.objects.get(psc='97632')
        distances = [
            _metres(19.0 + i * 0.001, 48.6, area.lon, area.lat) for i in range(25)
        ]
        inside = [d for d in distances if d <= area.radius_m]
        self.assertGreaterEqual(len(inside) / len(distances), 0.90)

    def test_the_radius_is_a_percentile_not_the_furthest_point(self):
        """Otherwise it would be a bounding circle and the word would be a lie."""
        self._run(self._write(self._spread('97632', 25)))

        area = PostalCodeArea.objects.get(psc='97632')
        furthest = _metres(19.0 + 24 * 0.001, 48.6, area.lon, area.lat)
        self.assertLess(area.radius_m, furthest)

    def test_an_area_below_the_point_floor_is_not_stored(self):
        """A one-point PSČ yields a 0 m radius -- a pin claiming a doorstep.

        Not storing it is the whole guard: the seat then answers `None` and no
        map is drawn, which is a smaller claim than a wrong one.
        """
        lines = self._spread('83004', MIN_ADDRESS_POINTS - 1) + self._spread('97632', 25)

        out = self._run(self._write(lines))

        self.assertFalse(PostalCodeArea.objects.filter(psc='83004').exists())
        self.assertTrue(PostalCodeArea.objects.filter(psc='97632').exists())
        self.assertIn('below 20 address points', out)
        self.assertIn('83004', out)

    def test_rows_without_a_psc_are_not_aggregated_into_an_area(self):
        """The 224 rows whose coordinates are scattered across the country.

        Grouped by their (empty) PSČ they would produce a centroid somewhere in
        central Slovakia, and every PSČ-less company would be pinned to it.
        """
        lines = [_row(1, '  ', 19.1, 48.6), _row(2, '', 21.2, 48.7)] + self._spread(
            '97632', 25
        )

        out = self._run(self._write(lines))

        self.assertEqual(PostalCodeArea.objects.filter(psc='').count(), 0)
        self.assertEqual(PostalCodeArea.objects.count(), 1)
        self.assertIn('no PSČ', out)

    def test_it_says_why_a_psc_could_not_be_placed_instead_of_blaming_the_source(self):
        """Two different reasons, and only one of them is the source's doing.

        An unplaced PSČ used to be reported as "the source does not list them",
        which is false for the five under the point floor -- we dropped those,
        and they are the only unplaced rows an operator could do anything about
        (lower the floor, or accept that 26 companies get no pin). A report that
        states the wrong cause is worse than no report, because it is the one
        anyone would act on.
        """
        lines = self._spread('83004', MIN_ADDRESS_POINTS - 1) + self._spread('97632', 25)
        Company.objects.create(
            ruz_id=1, ico='11111111', nazov_UJ='Tenká, s. r. o.', psc='83004'
        )
        Company.objects.create(
            ruz_id=2, ico='22222222', nazov_UJ='Neznáma, s. r. o.', psc='94001'
        )

        out = self._run(self._write(lines), source_version='2026-08-21')

        self.assertIn('2 distinct PSČ unplaced, 2 rows:', out)
        self.assertIn('1 PSČ · 1 rows — listed, but under the 20-point floor', out)
        self.assertIn('1 PSČ · 1 rows — the register does not list it at all', out)

    def test_an_area_that_left_the_source_is_removed(self):
        """The table is entirely derived from the source, so it must reconcile.

        A PSČ that stops being published would otherwise keep putting a pin on
        a place the source no longer supports, with nothing on screen to say so.
        """
        PostalCodeArea.objects.create(
            psc='99999', lat=48.0, lon=19.0, radius_m=500, point_count=100
        )

        out = self._run(self._write(self._spread('97632', 25)))

        self.assertFalse(PostalCodeArea.objects.filter(psc='99999').exists())
        self.assertIn('left the source', out)

    def test_the_source_version_is_recorded_on_every_row(self):
        self._run(self._write(self._spread('97632', 25)), source_version='2026-08-21')

        self.assertEqual(
            PostalCodeArea.objects.get(psc='97632').source_version, '2026-08-21'
        )

    def test_a_dry_run_writes_nothing(self):
        out = self._run(self._write(self._spread('97632', 25)), dry_run=True)

        self.assertEqual(PostalCodeArea.objects.count(), 0)
        self.assertIn('would cover', out)

    def test_it_refuses_a_file_that_is_not_the_address_register(self):
        """A wrong file must fail loudly, not import zeros.

        The command's whole output is derived from columns that would simply be
        absent; silently reading a different CSV would store nothing and report
        a low coverage number that looks like a data problem rather than a
        wrong-file problem.
        """
        path = os.path.join(self._dir.name, 'other.csv')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write('a;b;c\n1;2;3\n')

        with self.assertRaises(CommandError) as ctx:
            self._run(path)

        self.assertIn('not the MV SR address CSV', str(ctx.exception))

    def test_a_missing_file_is_an_error_not_an_empty_import(self):
        with self.assertRaises(CommandError):
            self._run(os.path.join(self._dir.name, 'nope.csv'))

    def test_it_says_when_the_source_version_is_missing(self):
        """The value cannot be derived from the CSV, so its absence is stated.

        Otherwise the table would look complete while being untraceable to any
        release of the dataset it came from.
        """
        out = self._run(self._write(self._spread('97632', 25)))

        self.assertIn('cannot be traced to a release', out)
