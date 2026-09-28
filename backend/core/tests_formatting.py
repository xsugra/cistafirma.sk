"""The two Slovak counting helpers.

Tested here rather than only through their callers because they are shared: the
risk indicators are the first users, not the owners, and a regression in the
count of one would show up as a wording change in somebody else's section.
"""

from django.test import SimpleTestCase

from core.formatting import plural_oblique_sk, plural_sk


class PluralTests(SimpleTestCase):
    """`1 firma`, `3 firmy`, `5 firiem` -- the house rule, at every boundary."""

    def test_one_is_singular(self):
        self.assertEqual(plural_sk(1, 'firma', 'firmy', 'firiem'), '1 firma')

    def test_two_to_four_take_the_plural_form(self):
        for count in (2, 3, 4):
            with self.subTest(count=count):
                self.assertEqual(
                    plural_sk(count, 'firma', 'firmy', 'firiem'), f'{count} firmy'
                )

    def test_five_and_above_take_the_genitive_plural(self):
        for count in (5, 20, 1000):
            with self.subTest(count=count):
                self.assertEqual(
                    plural_sk(count, 'firma', 'firmy', 'firiem'), f'{count} firiem'
                )

    def test_zero_counts_as_many(self):
        # Slovak says "0 firiem", not "0 firma" -- and zero is a count the
        # rules do produce, e.g. companies with no NACE code.
        self.assertEqual(plural_sk(0, 'firma', 'firmy', 'firiem'), '0 firiem')


class PluralObliqueTests(SimpleTestCase):
    """`1 firme`, `5 firmách` -- two forms, because only two exist."""

    def test_one_is_singular(self):
        self.assertEqual(plural_oblique_sk(1, 'firme', 'firmách'), '1 firme')

    def test_everything_above_one_is_the_same_form(self):
        # The boundary that differs from `plural_sk`: two takes the plural here,
        # which is why the two helpers cannot be one.
        for count in (2, 3, 4, 5, 1000):
            with self.subTest(count=count):
                self.assertEqual(
                    plural_oblique_sk(count, 'firme', 'firmách'), f'{count} firmách'
                )

    def test_zero_is_the_plural_form(self):
        self.assertEqual(plural_oblique_sk(0, 'osoby', 'osôb'), '0 osôb')
