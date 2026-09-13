"""The address grammar and the tier policy, both without a database.

Two things are being pinned here, and they fail differently.

**The grammar** (`street_key`, `parse_street`, `normalize_obec`) is what makes
the join happen at all, and every fold in it was found by watching a real row
fail to match. A fold that breaks is not an exception -- it is a company that
silently keeps its PSČ circle, which looks exactly like a company the register
cannot place.

**The policy** (`candidates`, `resolve`) is an order and a set of guards. Its
failure mode is worse than a missing pin: a tier that answers when it should
have been skipped puts a pin on the wrong village. So the guards are tested by
what they *refuse*, not only by what they return.

`resolve` takes its points through an injected `fetch`, so the entire decision --
every tier, in order, with every rejection -- is exercised here with no
database, no register file and no network. That is why the function is written
that way; these tests are the reason.
"""

import itertools

from django.test import SimpleTestCase

from companies.address import (
    MAX_KEY_SPREAD_M,
    MIN_STREET_RADIUS_M,
    centroid,
    is_one_place,
    normalize_obec,
    p90_radius_m,
    parse_street,
    street_key,
)
from companies.seat_matching import (
    BUILDING,
    POSTAL_CODE,
    STREET,
    T_OBEC_ULICA,
    T_OBEC_ULICA_ORIENT,
    T_OBEC_ULICA_SUPISNE,
    T_PSC_ULICA,
    T_PSC_ULICA_ORIENT,
    T_PSC_ULICA_SUPISNE,
    candidates,
    resolve,
)


class StreetKeyTests(SimpleTestCase):
    """Every fold in the docstring's table, one test each."""

    def test_it_drops_a_trailing_street_type_word(self):
        """Our `Bratislavská` and the register's `bratislavska ulica` are one street."""
        self.assertEqual(street_key('Bratislavská'), street_key('Bratislavská ulica'))
        self.assertEqual(street_key('Hlavná cesta'), 'hlavna')
        self.assertEqual(street_key('Mierové námestie'), 'mierove')

    def test_it_keeps_the_word_when_it_is_the_whole_name(self):
        """`Ulica` alone is a name, not a type word, and must not fold to nothing.

        The `or folded` in the function is what saves this, and without it the
        key would be `''` -- which the register reads as *rural*, so every such
        company would be looked up as if it had no street at all.
        """
        self.assertEqual(street_key('Ulica'), 'ulica')
        self.assertEqual(street_key('Cesta'), 'cesta')

    def test_it_does_not_strip_a_word_that_only_looks_like_one(self):
        """`Kúpeľná` ends in `na`; `Sadová` is not the plural `sady`.

        The pattern is anchored to whole words for exactly this reason: a
        substring rule would eat the ends of ordinary names.
        """
        self.assertEqual(street_key('Kúpeľná'), 'kupelna')
        self.assertEqual(street_key('Sadová'), 'sadova')

    def test_it_drops_the_space_after_a_full_stop(self):
        self.assertEqual(street_key('17. novembra'), street_key('17.novembra'))
        self.assertEqual(street_key('J. L. Bellu'), 'j.l.bellu')

    def test_it_treats_a_hyphen_as_the_same_break_as_a_space(self):
        self.assertEqual(
            street_key('M. Schneidra-Trnavského'),
            street_key('M. Schneidra Trnavského'),
        )

    def test_it_folds_diacritics_and_case(self):
        self.assertEqual(street_key('NÁMESTIE SNP'), 'namestie snp')
        self.assertEqual(street_key('Námestie  SNP'), street_key('namestie snp'))

    def test_it_drops_a_trailing_ul_abbreviation(self):
        self.assertEqual(street_key('Golianova ul.'), 'golianova')
        self.assertEqual(street_key('Golianova ul'), 'golianova')

    def test_nothing_folds_to_nothing(self):
        for value in (None, '', '   '):
            with self.subTest(value=value):
                self.assertEqual(street_key(value), '')


class ParseStreetTests(SimpleTestCase):
    """The table in the docstring, plus the ambiguity it deliberately keeps."""

    def test_it_reads_registration_first_and_orientation_second(self):
        """`1458/71` is registration 1458 at orientation 71, not the other way round.

        Slovak addresses write súpisné číslo first. Swapping them looks up a
        house that exists -- a real number on a real street -- so the mistake
        draws a plausible pin in the wrong place rather than failing.
        """
        street, lone, orientation, registration = parse_street('Bratislavská 1458/71')
        self.assertEqual(street, 'bratislavska')
        self.assertIsNone(lone)
        self.assertEqual(orientation, '71')
        self.assertEqual(registration, '1458')

    def test_a_lone_number_is_kept_apart_rather_than_guessed(self):
        """`Starohájska 3` is an orientation number in a town and a registration
        number in a village, and the field does not say which.

        So it is returned as `lone` and the caller tries both -- the register
        decides. Asserting it "is" one of the two here would be inventing the
        answer this function exists to withhold.
        """
        street, lone, orientation, registration = parse_street('Starohájska 3')
        self.assertEqual(street, 'starohajska')
        self.assertEqual(lone, '3')
        self.assertIsNone(orientation)
        self.assertIsNone(registration)

    def test_a_street_with_no_number_at_all(self):
        street, lone, orientation, registration = parse_street('Golianova ul.')
        self.assertEqual(street, 'golianova')
        self.assertIsNone(lone)
        self.assertIsNone(orientation)
        self.assertIsNone(registration)

    def test_a_letter_where_the_slash_would_be(self):
        """`Tomášiková 50/E`: registration 50, orientation `e`.

        The orientation reading is one the register cannot confirm -- its
        orientation column is digits with an optional trailing letter, never a
        bare one -- and that is fine, because the *registration* reading is
        asked separately and is what will match. Splitting the pair is what
        keeps a letter that means an entrance from costing us the building.
        """
        street, lone, orientation, registration = parse_street('Tomášiková 50/E')
        self.assertEqual(street, 'tomasikova')
        self.assertIsNone(lone)
        self.assertEqual(orientation, 'e')
        self.assertEqual(registration, '50')

    def test_a_trailing_letter_is_part_of_the_number(self):
        """`Kvetná 12A` -- the register's commonest shape: 2 427 rows read `1A`.

        Splitting the letter off would look up house 12 and place a company at
        its neighbour's door.
        """
        street, lone, _, _ = parse_street('Kvetná 12A')
        self.assertEqual(street, 'kvetna')
        self.assertEqual(lone, '12a')

    def test_a_letter_led_number_does_not_parse_as_one(self):
        """`Mlynská dolina F1` -- and the register has no such shape to match.

        Measured over all 1 739 536 register rows: not one house number leads
        with a letter. So a letter before the digits is not a number the
        register could answer with, and the parse takes the trailing `1` as the
        number with the `F` left on the street.

        Pinned because it is a real limitation rather than a decision: this
        company keeps its PSČ circle. Expressing it as a test is the difference
        between a known gap and an assumed one.
        """
        street, lone, orientation, registration = parse_street('Mlynská dolina F1')
        self.assertEqual(street, 'mlynska dolina f')
        self.assertEqual(lone, '1')
        self.assertIsNone(orientation)
        self.assertIsNone(registration)

    def test_a_village_written_where_the_street_goes(self):
        """`Krajné 52` -- the register's own rural shape: street and number."""
        street, lone, _, _ = parse_street('Krajné 52')
        self.assertEqual(street, 'krajne')
        self.assertEqual(lone, '52')

    def test_it_handles_nothing(self):
        self.assertEqual(parse_street(None), ('', None, None, None))


class NormalizeObecTests(SimpleTestCase):
    """The two spellings of a city part, and the collision that is accepted."""

    def test_our_spelling_and_the_registers_become_one_key(self):
        self.assertEqual(normalize_obec('Bratislava - mestská časť Ružinov'), 'bratislava')
        self.assertEqual(normalize_obec('Bratislava-Ružinov'), 'bratislava')

    def test_a_plain_municipality_is_untouched(self):
        self.assertEqual(normalize_obec('Košice'), 'kosice')
        self.assertEqual(normalize_obec('Nevidzany'), 'nevidzany')


class SpreadRuleTests(SimpleTestCase):
    """`is_one_place` and `p90_radius_m` -- the guards that refuse to guess."""

    def test_a_single_point_is_always_one_place(self):
        self.assertTrue(is_one_place([(48.15, 17.13)]))
        self.assertTrue(is_one_place([]))

    def test_two_entrances_of_one_building_average(self):
        """Measured on the register: median 0 m, maximum 51 m for accepted keys."""
        a = (48.1500, 17.1300)
        b = (48.1503, 17.1300)  # ~33 m north
        self.assertTrue(is_one_place([a, b], MAX_KEY_SPREAD_M))
        lat, lon = centroid([a, b])
        self.assertAlmostEqual(lat, 48.15015, places=5)

    def test_seventy_kilometres_is_two_places_and_is_refused(self):
        """`Nevidzany` exists in two districts, 62 km apart.

        This is the case the rule exists for: both points are real, both are on
        a street of that name, and picking either would pin a company to the
        wrong district with no way for a reader to tell.
        """
        self.assertFalse(is_one_place([(48.5, 17.9), (48.9, 18.6)], MAX_KEY_SPREAD_M))

    def test_the_limit_is_where_it_says_it_is(self):
        """Just inside is one place, just outside is two.

        Deliberately not sampled *at* the limit. The distance is computed in
        floating point and then compared to 150.0, so a pair constructed to be
        exactly 150 m apart can land a few ulps either side -- and a test that
        fails on the ulp is measuring the arithmetic, not the rule. A metre of
        slack on either side is far below anything this rule decides in
        practice: the keys it rejects span kilometres.
        """
        base = (48.15, 17.13)
        inside = (48.15 + 149.0 / 111_320, 17.13)
        outside = (48.15 + 151.0 / 111_320, 17.13)
        self.assertTrue(is_one_place([base, inside], MAX_KEY_SPREAD_M))
        self.assertFalse(is_one_place([base, outside], MAX_KEY_SPREAD_M))

    def test_a_huge_key_is_refused_without_measuring_every_pair(self):
        """The bounding box settles it, which is what bounds the cost.

        A key reaching 500 points is not one building under any reading, and the
        quadratic comparison is skipped rather than run to reach a foregone
        conclusion.
        """
        points = [(48.0 + i * 0.01, 17.0) for i in range(500)]
        self.assertFalse(is_one_place(points, MAX_KEY_SPREAD_M))

    def test_the_street_limit_is_wider_than_the_building_limit(self):
        """A street is meant to be long; that is not the same as being wrong."""
        points = [(48.15, 17.13), (48.17, 17.13)]  # ~2.2 km
        self.assertFalse(is_one_place(points, MAX_KEY_SPREAD_M))
        self.assertTrue(is_one_place(points, 5_000.0))

    def test_a_street_radius_never_falls_below_the_floor(self):
        """One known point on a street must not become a bare pin.

        Without the floor this returns 0 m, and 0 m is the value that means
        *building* everywhere else in this system -- so a single-point street
        would be drawn as a doorstep claim.
        """
        self.assertEqual(p90_radius_m([(48.15, 17.13)]), MIN_STREET_RADIUS_M)

    def test_one_far_outlier_does_not_widen_the_whole_street(self):
        """Nine buildings within 80 m, one register row 3 km away.

        Using the maximum would let that one row -- a mis-geocoded address, or a
        street name shared with another village -- stretch the circle for every
        company on the street. `COVERAGE` is the deliberate trade: drop the tail
        rather than inflate the claim.

        Asserted on the radius rather than by counting points inside it. The
        radius is rounded to whole metres, so a point sitting exactly at the
        90th percentile can land a metre outside the drawn ring -- real, and
        irrelevant at map scale, but enough to make a count-based assertion
        measure the rounding instead of the rule.
        """
        points = [(48.15 + (10.0 * i) / 111_320, 17.13) for i in range(9)]
        points.append((48.15 + 3_000.0 / 111_320, 17.13))

        radius = p90_radius_m(points)

        self.assertGreater(radius, MIN_STREET_RADIUS_M)
        self.assertLess(radius, 500, 'the 3 km outlier must not set the radius')


def _tiers(found):
    return [tier for tier, _ in found]


class CandidatesTests(SimpleTestCase):
    """The order *is* the policy, so the order is what is asserted."""

    def test_a_town_address_is_tried_narrow_scope_first(self):
        """For each number, the PSČ scope is asked before the municipal one.

        A PSČ that misses omits; a municipality that matches wrongly lies. For a
        pin, omission costs a circle and commission costs a false statement, so
        the narrow scope goes first -- which is why `psc_ulica_supisne` sits
        *above* `obec_ulica_orient` in the list below. That ordering is the
        policy, not an artefact of the loop: a registration number known to be
        in the right PSČ is a better answer than an orientation number known
        only to be in the right municipality.
        """
        found = candidates('82108', 'Bratislava', 'Tomášikova 50/E')
        self.assertEqual(
            _tiers(found),
            [
                T_PSC_ULICA_ORIENT,
                T_PSC_ULICA_SUPISNE,
                T_OBEC_ULICA_ORIENT,
                T_OBEC_ULICA_SUPISNE,
                T_PSC_ULICA,
                T_OBEC_ULICA,
            ],
        )

    def test_the_narrow_scope_is_asked_first_for_every_number(self):
        """Asserted as a property, so a reordering that keeps the promise passes
        and one that breaks it cannot."""
        narrow_of = {
            T_OBEC_ULICA_ORIENT: T_PSC_ULICA_ORIENT,
            T_OBEC_ULICA_SUPISNE: T_PSC_ULICA_SUPISNE,
            T_OBEC_ULICA: T_PSC_ULICA,
        }
        for ulica in ('Bratislavská 1458/71', 'Starohájska 3', 'Tomášikova 50/E'):
            with self.subTest(ulica=ulica):
                tiers = _tiers(candidates('82108', 'Bratislava', ulica))
                for wide, narrow in narrow_of.items():
                    if wide in tiers:
                        self.assertLess(tiers.index(narrow), tiers.index(wide))

    def test_the_street_centroid_is_always_last(self):
        """It is the only tier that draws a circle on purpose."""
        for ulica in ('Tomášikova 50/E', 'Starohájska 3', 'Golianova ul.'):
            with self.subTest(ulica=ulica):
                tiers = _tiers(candidates('82108', 'Bratislava', ulica))
                self.assertIn(tiers[-1], (T_PSC_ULICA, T_OBEC_ULICA))
                self.assertIn(tiers[-2], (T_PSC_ULICA, T_OBEC_ULICA))

    def test_a_lone_number_is_tried_as_both_and_the_register_decides(self):
        """One number, two possible columns, and the field cannot say which.

        So the same value is offered to both, once for each scope -- four
        building candidates, and the first one the register confirms wins.
        """
        found = candidates('82108', 'Bratislava', 'Starohájska 3')
        orient = [v for t, v in found if t is T_PSC_ULICA_ORIENT]
        supisne = [v for t, v in found if t is T_PSC_ULICA_SUPISNE]
        self.assertEqual(orient, [('82108', 'starohajska', '3')])
        self.assertEqual(supisne, [('82108', 'starohajska', '3')])
        self.assertEqual(len(_tiers(found)), 6, 'two scopes x two readings + both streets')

    def test_a_split_number_asks_each_column_once_with_its_own_value(self):
        """`1458/71` names both columns, so the lone fallback must not also fire.

        If it did, the same pair would be looked up four times per scope and a
        rejected key would be rejected four times over -- inflating the counts
        the report is read for.
        """
        found = candidates('82108', 'Bratislava', 'Bratislavská 1458/71')
        orient = [v for t, v in found if t is T_PSC_ULICA_ORIENT]
        supisne = [v for t, v in found if t is T_PSC_ULICA_SUPISNE]
        self.assertEqual(orient, [('82108', 'bratislavska', '71')])
        self.assertEqual(supisne, [('82108', 'bratislavska', '1458')])

    def test_a_rural_address_keys_on_the_number_with_an_empty_street(self):
        """A village writes the municipality where the street goes.

        The register marks the same rows with an empty `ULICA`, so the rural
        case is the *same key shape* -- not a second set of tiers to index.
        """
        found = candidates('95102', 'Krajné', 'Krajné 52')
        psc_values = [v for t, v in found if t in (T_PSC_ULICA_ORIENT, T_PSC_ULICA_SUPISNE)]
        self.assertTrue(psc_values)
        for _, values in found:
            if len(values) == 3:
                self.assertEqual(values[1], '', 'the street slot must stay empty')

    def test_a_street_equal_to_the_municipality_is_rural(self):
        """`Bratislava` in both fields is not a street named Bratislava."""
        found = candidates('82108', 'Bratislava', 'Bratislava 12')
        for _, values in found:
            if len(values) == 3:
                self.assertEqual(values[1], '')

    def test_no_psc_still_leaves_the_municipal_scope(self):
        """224 register rows and 3 of our companies carry no PSČ.

        The narrow scope is skipped rather than keyed on an empty string, which
        would match every PSČ-less register row in the country at once.
        """
        found = candidates('', 'Bratislava', 'Tomášikova 50/E')
        self.assertNotIn(T_PSC_ULICA_ORIENT, _tiers(found))
        self.assertNotIn(T_PSC_ULICA, _tiers(found))
        self.assertIn(T_OBEC_ULICA_ORIENT, _tiers(found))

    def test_nothing_at_all_yields_no_candidates(self):
        """A company with no address has nothing to look up, and asks nothing."""
        self.assertEqual(candidates('', '', ''), [])


class ResolveTests(SimpleTestCase):
    """Which tier wins, and -- more importantly -- which ones are refused."""

    def setUp(self):
        self._seq = itertools.count(1)

    def _fetch(self, table):
        """A `fetch` over `{(tier_name, values): points}`, empty elsewhere."""
        return lambda tier, values: table.get((tier.name, tuple(values)), ())

    def test_the_first_tier_that_answers_wins(self):
        """A building beats a street, and a street beats nothing."""
        found = candidates('82108', 'Bratislava', 'Starohájska 3')
        table = {
            (T_PSC_ULICA_ORIENT.name, ('82108', 'starohajska', '3')): [(48.15, 17.13)],
            (T_PSC_ULICA.name, ('82108', 'starohajska')): [(48.15, 17.13), (48.16, 17.13)],
        }
        hit = resolve(found, self._fetch(table))
        self.assertEqual(hit.precision, BUILDING)
        self.assertEqual(hit.tier, T_PSC_ULICA_ORIENT.name)
        self.assertEqual(hit.radius_m, 0, 'a building has no circle to draw')
        self.assertEqual(hit.point_count, 1)

    def test_a_scattered_building_key_falls_through_to_the_street(self):
        """The rejection is not an error -- it is a lower, true claim.

        This is the whole shape of the design: a merge or a collision shows up
        as a rejection to fall back from, never as a pin on the wrong building.
        """
        found = candidates('82108', 'Bratislava', 'Starohájska 3')
        table = {
            (T_PSC_ULICA_ORIENT.name, ('82108', 'starohajska', '3')): [
                (48.15, 17.13),
                (48.80, 17.13),  # ~72 km: two different places
            ],
            (T_PSC_ULICA.name, ('82108', 'starohajska')): [
                (48.15, 17.13),
                (48.152, 17.13),
            ],
        }
        hit = resolve(found, self._fetch(table))
        self.assertEqual(hit.precision, STREET)
        self.assertEqual(hit.tier, T_PSC_ULICA.name)

    def test_a_street_with_one_point_and_no_number_claims_nothing(self):
        """Both routes are closed, and the answer is `None` rather than a point.

        A lone register point is below the street floor, and with no house
        number there was never a building candidate -- so this company keeps its
        PSČ circle. Being unable to place it is the honest outcome; a single
        address point promoted to a building would be a doorstep claim built
        from one geocoded row.
        """
        found = candidates('82108', 'Bratislava', 'Golianova ul.')
        table = {(T_PSC_ULICA.name, ('82108', 'golianova')): [(48.15, 17.13)]}
        self.assertEqual(_tiers(found), [T_PSC_ULICA, T_OBEC_ULICA])
        self.assertIsNone(resolve(found, self._fetch(table)))

    def test_a_street_needs_more_than_one_point_to_have_a_shape(self):
        """Below `MIN_STREET_POINTS` there is no spread to average."""
        found = [(T_PSC_ULICA, ('82108', 'golianova'))]
        table = {(T_PSC_ULICA.name, ('82108', 'golianova')): [(48.15, 17.13)]}
        self.assertIsNone(resolve(found, self._fetch(table)))

    def test_a_street_longer_than_the_street_limit_is_refused(self):
        """A 205 km key is two villages sharing a name, not one street."""
        found = [(T_PSC_ULICA, ('82108', 'golianova'))]
        table = {
            (T_PSC_ULICA.name, ('82108', 'golianova')): [(48.15, 17.13), (49.5, 20.5)]
        }
        self.assertIsNone(resolve(found, self._fetch(table)))

    def test_nothing_answering_is_none_rather_than_a_guess(self):
        found = candidates('82108', 'Bratislava', 'Tomášikova 50/E')
        self.assertIsNone(resolve(found, self._fetch({})))

    def test_the_registers_own_precision_choices_are_the_three_on_the_map(self):
        """The values the matcher writes are the values the column allows.

        `SEAT_PRECISION_CHOICES` is imported by the model, so this asserts the
        set the map draws and the set the database accepts are the same set --
        they were written out twice before, which is how they drift.
        """
        from companies.seat_matching import SEAT_PRECISION_CHOICES

        self.assertEqual(
            {value for value, _ in SEAT_PRECISION_CHOICES},
            {BUILDING, STREET, POSTAL_CODE},
        )
