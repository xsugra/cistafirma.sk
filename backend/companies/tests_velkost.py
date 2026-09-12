"""The size codebook, and the one value in it that is not a size.

`SIZE_BANDS` is transcribed from
`https://www.registeruz.sk/cruz-public/api/velkosti-organizacie` (ŠÚ SR
číselník 0073/KATP97). These tests do not re-check it against the register --
that would make the suite depend on a third party being up -- they pin the
properties the rest of the project relies on, so that an edit to the table has
to be deliberate:

* the table is *complete* against the codes the live column actually holds, and
* `00` is separated from the bands everywhere, because it is the modal value in
  the table (63,3 % of active companies) and the one code that must never be
  presented as a size.
"""

from django.test import TestCase

from companies.services.velkost import (
    SIZE_BAND_CODES,
    SIZE_BANDS,
    SIZE_UNKNOWN,
    has_size_band,
    is_known_size_code,
    normalise_size_code,
    size_band_label,
)


class SizeCodebookTests(TestCase):
    def test_every_code_the_live_column_holds_is_in_the_table(self):
        # Measured 2026-09-12 over `"Companies and SZCO"`: the distinct
        # non-null values in `Veľkosť` are exactly `00` and `01`-`38` as listed,
        # with 409 nulls and no empty strings or padded values. A code appearing
        # here that the table lacks is the signal that it needs re-reading.
        for code in ('00', '01', '02', '03', '04', '05', '06', '07', '11', '12',
                     '21', '22', '23', '24', '25', '31', '32', '33', '34', '35',
                     '36', '37', '38'):
            with self.subTest(code=code):
                self.assertIn(code, SIZE_BANDS)

    def test_the_table_is_the_size_the_register_publishes(self):
        # 23 entries. A smaller table means a band was dropped and companies in
        # it would silently lose their section.
        self.assertEqual(len(SIZE_BANDS), 23)

    def test_the_bands_are_the_registers_own_wording(self):
        # Three spellings a tidy-up would "fix" and thereby break: the lowest
        # band is an explicit count of zero, the top one carries a plus, and the
        # unknown one is lowercase. All three are rendered to readers verbatim.
        self.assertEqual(SIZE_BANDS['00'], 'nezistený')
        self.assertEqual(SIZE_BANDS['01'], '0 zamestnancov')
        self.assertEqual(SIZE_BANDS['38'], '30000+ zamestnancov')

    def test_unknown_is_not_offered_as_a_band(self):
        # The whole reason the module exists: `00` is a real code with a real
        # meaning, and that meaning is that there is no size. It is in the
        # table (so `is_known_size_code` can tell it from a code we have never
        # seen) and out of `SIZE_BAND_CODES` (so nothing can group 205 840
        # companies under a heading that reads like a size).
        self.assertIn(SIZE_UNKNOWN, SIZE_BANDS)
        self.assertNotIn(SIZE_UNKNOWN, SIZE_BAND_CODES)
        self.assertIsNone(size_band_label(SIZE_UNKNOWN))
        self.assertFalse(has_size_band(SIZE_UNKNOWN))
        self.assertTrue(is_known_size_code(SIZE_UNKNOWN))

    def test_a_band_label_is_returned_for_a_band_and_only_for_a_band(self):
        self.assertEqual(size_band_label('04'), '3-4 zamestnanci')
        self.assertEqual(size_band_label('38'), '30000+ zamestnancov')
        self.assertTrue(has_size_band('04'))
        # Absent, blank and unrecognised all leave the company unplaceable --
        # but only the last of the three is news, which is what separates this
        # from `is_known_size_code`.
        for nothing in (None, '', '   ', '99'):
            with self.subTest(value=nothing):
                self.assertIsNone(size_band_label(nothing))
                self.assertFalse(has_size_band(nothing))
                self.assertFalse(is_known_size_code(nothing))

    def test_a_padded_or_spaced_code_is_read_as_the_code_it_is(self):
        # Four import paths write this column, so the value is normalised before
        # it is trusted rather than compared raw.
        self.assertEqual(normalise_size_code(' 04 '), '04')
        self.assertEqual(size_band_label(' 04 '), '3-4 zamestnanci')
        self.assertEqual(normalise_size_code(''), None)
        self.assertEqual(normalise_size_code('   '), None)
        self.assertEqual(normalise_size_code(None), None)

    def test_the_code_is_compared_case_sensitively_because_it_is_a_number(self):
        # Not a style choice: the column holds two digits, so there is no case
        # to fold, and `iexact` would produce an `UPPER()` comparison that
        # cannot use the `(velkost_organizacie, datum_zrusenia)` index.
        self.assertIsNone(size_band_label('aa'))
        self.assertFalse(is_known_size_code('04x'))
