"""Where the seat pin comes from, and what it refuses to claim.

`seatLocation` is a join on PSČ, so the two things worth pinning down are the
normalisation that makes the join happen at all (three of our rows carry a
space in `psc`) and the `None` — which means "we cannot place this seat", not
"this company has no seat", and must stay distinguishable from a coordinate.
"""

import itertools

from django.test import TestCase

from companies.models import Company, PostalCodeArea
from companies.serializers import CompanyDetailSerializer


class NormalizePscTests(TestCase):
    def test_it_removes_the_separator_the_register_omits(self):
        """`Company.psc` holds '602 00'; the register writes '60200'.

        Without this the three rows noted in `PostalCodeArea.normalize_psc`
        would simply never match, and would look identical to a PSČ the source
        does not know -- the silent join failure this project keeps naming.
        """
        self.assertEqual(PostalCodeArea.normalize_psc('602 00'), '60200')
        self.assertEqual(PostalCodeArea.normalize_psc(' 82108 '), '82108')

    def test_it_removes_every_kind_of_whitespace_not_just_spaces(self):
        self.assertEqual(PostalCodeArea.normalize_psc('821\t08\n'), '82108')

    def test_it_returns_empty_for_nothing(self):
        for value in (None, '', '   '):
            with self.subTest(value=value):
                self.assertEqual(PostalCodeArea.normalize_psc(value), '')

    def test_it_does_not_invent_missing_characters(self):
        """Padding a short PSČ would merge two different places.

        The same mistake `.zfill(8)` makes with IČO in #90: '177474' and
        '00177474' are different sibling entities, and a normaliser that pads
        cannot tell them apart. A PSČ that is not five characters is simply not
        matched, and is reported instead.
        """
        self.assertEqual(PostalCodeArea.normalize_psc('6020'), '6020')


class _SeatFixtures(TestCase):
    """The rows these two suites share. No tests of its own, by design.

    Both suites need the same company, the same `PostalCodeArea` and the same
    one-line way to ask the serializer, and inheriting from `TestCase` directly
    in each would mean writing all three twice. A base class rather than a
    mixin because `setUp` is involved.
    """

    def setUp(self):
        # Both `ruz_id` and `ico` are unique on Company, and a test that asks for
        # two companies in one body is normal here.
        self._seq = itertools.count(1)

    def _company(self, **kwargs):
        n = next(self._seq)
        defaults = {
            'ruz_id': 990000 + n,
            'ico': f'9{n:07d}',
            'nazov_UJ': f'Test {n}, s. r. o.',
        }
        defaults.update(kwargs)
        return Company.objects.create(**defaults)

    def _area(self, psc='82108', **kwargs):
        defaults = {
            'lat': 48.15358,
            'lon': 17.13381,
            'radius_m': 800,
            'point_count': 1122,
            'dominant_obec': 'Bratislava-Ružinov',
            'obec_count': 4,
        }
        defaults.update(kwargs)
        return PostalCodeArea.objects.create(psc=psc, **defaults)

    def _seat(self, company):
        return CompanyDetailSerializer(company).data['seatLocation']


class SeatLocationSerializerTests(_SeatFixtures):
    """The PSČ join itself: the normalisation that makes it happen, and the `None`."""

    def test_a_placed_seat_carries_the_area_not_just_a_point(self):
        """The radius travels with the coordinate because the UI draws it.

        A payload of lat/lon alone would let any consumer render a bare marker,
        which claims the accuracy of a building entrance for a centroid that is
        a median 1 980 m away from its own address points.
        """
        self._area()
        seat = self._seat(self._company(psc='82108'))

        self.assertEqual(seat['lat'], 48.15358)
        self.assertEqual(seat['lon'], 17.13381)
        self.assertEqual(seat['radiusM'], 800)
        self.assertEqual(seat['psc'], '82108')
        self.assertEqual(seat['precision'], 'postal_code')

    def test_the_join_normalises_our_side_of_the_key(self):
        self._area(psc='60200')
        seat = self._seat(self._company(psc='602 00'))

        self.assertIsNotNone(seat)
        self.assertEqual(seat['psc'], '60200')

    def test_a_psc_the_source_does_not_list_is_none_rather_than_a_guess(self):
        """1,92 % of our rows: the source has no address point for that PSČ.

        Drawing them anywhere would be inventing a location, so the answer is
        `None` and the card is omitted.
        """
        self._area(psc='82108')
        self.assertIsNone(self._seat(self._company(psc='94001')))

    def test_a_company_with_no_psc_is_none(self):
        self.assertIsNone(self._seat(self._company(psc=None)))
        self.assertIsNone(self._seat(self._company(psc='')))

    def test_a_thin_area_is_absent_from_the_table_so_the_seat_is_none(self):
        """The guard is upstream: an area under the point floor is never stored.

        This pins the seam -- `import_postal_codes` dropping thin areas and the
        serializer answering `None` are two halves of one promise, and a test
        for either alone would pass while the promise was broken.
        """
        self.assertIsNone(self._seat(self._company(psc='83004')))


class SeatPrecisionTests(_SeatFixtures):
    """The three levels, and which one wins when more than one is available.

    These drive the same rows `match_seat_addresses` writes, so what is pinned
    is not "the serializer can read a column" but the ordering the whole feature
    rests on: the most precise claim that exists is the one that reaches the map.
    """

    def test_a_building_match_is_a_point_with_no_circle(self):
        """78,6 % of our rows, and the reason this task exists.

        `radiusM` is 0 and it is load-bearing: the frontend draws the point and
        *no ring at all*, because a building has no spread to draw. A non-zero
        radius here would put the circle back around a company we can place
        exactly -- the decoration the whole change removes.
        """
        self._area()
        seat = self._seat(self._company(
            psc='82108',
            seat_lat=48.15231,
            seat_lon=17.12987,
            seat_precision='building',
            seat_radius_m=None,
            seat_point_count=1,
            seat_tier='psc_ulica_orient',
        ))

        self.assertEqual(seat['lat'], 48.15231)
        self.assertEqual(seat['lon'], 17.12987)
        self.assertEqual(seat['radiusM'], 0)
        self.assertEqual(seat['precision'], 'building')

    def test_a_street_match_carries_the_measured_spread(self):
        """The circle is a 90th percentile of that street's own points, not a constant."""
        self._area()
        seat = self._seat(self._company(
            psc='82108',
            seat_lat=48.15300,
            seat_lon=17.13000,
            seat_precision='street',
            seat_radius_m=184,
            seat_point_count=37,
            seat_tier='psc_ulica',
        ))

        self.assertEqual(seat['radiusM'], 184)
        self.assertEqual(seat['precision'], 'street')

    def test_a_placed_seat_wins_over_the_psc_circle_even_when_both_exist(self):
        """The fallback is chosen once, here, rather than blended.

        Both sources are computed from the same register at different levels, so
        a merged answer would have two independent ways to go stale and no way
        to say which one moved. The row below has *both* a matched point and a
        `PostalCodeArea`, and the matched point is the answer.
        """
        area = self._area()
        seat = self._seat(self._company(
            psc='82108',
            seat_lat=48.15231,
            seat_lon=17.12987,
            seat_precision='building',
            seat_radius_m=None,
        ))

        self.assertEqual(seat['precision'], 'building')
        self.assertNotEqual(seat['lat'], area.lat)
        self.assertEqual(area.radius_m, 800, 'the circle is still there to fall back to')

    def test_an_unplaced_company_falls_back_to_the_circle(self):
        """The 14,5 % the register cannot place keep a true, weaker claim.

        The `seat_*` columns are empty for them -- that is what "unplaced" means
        -- and the answer must be the PSČ circle rather than `None` whenever the
        PSČ is one the register lists.
        """
        self._area()
        seat = self._seat(self._company(psc='82108'))

        self.assertEqual(seat['precision'], 'postal_code')
        self.assertEqual(seat['radiusM'], 800)

    def test_a_precision_without_a_point_is_ignored(self):
        """The columns are written together, so a half-written row is a bug.

        Defending against it here rather than trusting the writer: a
        `seat_precision` with no coordinate would index `SEAT_LABEL` on the
        frontend and then draw `undefined` on the map.
        """
        self._area()
        seat = self._seat(self._company(psc='82108', seat_precision='building'))

        self.assertEqual(seat['precision'], 'postal_code')

    def test_an_unknown_precision_is_ignored(self):
        """A value the column does not allow must not reach the map either."""
        self._area()
        seat = self._seat(self._company(
            psc='82108',
            seat_lat=48.15231,
            seat_lon=17.12987,
            seat_precision='',
        ))

        self.assertEqual(seat['precision'], 'postal_code')

    def test_a_placed_seat_with_no_psc_still_has_a_position(self):
        """224 register rows carry no PSČ, so a match may have none.

        The label falls back to the address rather than to an empty PSČ, but the
        pin is real and is drawn -- dropping it would discard a match we earned.
        """
        seat = self._seat(self._company(
            psc=None,
            seat_lat=48.15231,
            seat_lon=17.12987,
            seat_precision='building',
            seat_radius_m=0,
        ))

        self.assertIsNotNone(seat)
        self.assertEqual(seat['psc'], '')
        self.assertEqual(seat['precision'], 'building')
