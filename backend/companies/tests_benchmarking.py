"""Sector medians, and what an unfiled line is allowed to contribute to one.

The medians are what the benchmark table puts beside a company's own figures,
so a row that filed nothing must leave the median alone rather than vote for
zero. Measured on the live book before this was fixed, the median gross margin
of a whole NACE section read 0.0 % because more than half of its rows had no
`added_value`, and section H's read -13.18 % where the filed values median at
25.82 % (`max(revenue, 1)` in the denominator turns an absent revenue into an
`added_value`-times-100 outlier).

The other half of the rule matters just as much: a line that *was* filed as
zero is a measurement, and excluding it would be the same error mirrored.
"""

from django.test import SimpleTestCase

from companies.models import CompanyFinancialResult
from companies.services.benchmarking import _compute_section_metrics


def row(year: int = 2025, **fields) -> CompanyFinancialResult:
    """An unsaved result row -- the median computation never touches the DB."""
    return CompanyFinancialResult(year=year, **fields)


class MedianOfFiledLinesTests(SimpleTestCase):
    """`_compute_section_metrics` counts filings, not absences."""

    def test_an_unfiled_margin_leaves_the_median_alone(self):
        # Three companies filed a margin of 10, 20 and 30 %. A fourth filed an
        # added value but no revenue at all. Before: its margin was computed as
        # `added_value / max(revenue, 1) * 100` = 50 000 %, and the median of
        # four values is the mean of the middle two -- 25 % became 10 015 %.
        metrics = _compute_section_metrics(
            [
                row(revenue=100, added_value=10),
                row(revenue=100, added_value=20),
                row(revenue=100, added_value=30),
                row(added_value=500),
            ],
            'G',
        )

        self.assertEqual(metrics['median_gross_margin'], 20)

    def test_a_section_that_filed_no_margin_has_no_median(self):
        # Section O in the live book: 643 rows, the median came out 0.0 %.
        # "Nobody filed it" and "the sector runs at zero margin" are different
        # facts and only one of them is printable.
        metrics = _compute_section_metrics(
            [row(assets_total=1000, profit=10) for _ in range(6)],
            'O',
        )

        self.assertIsNone(metrics['median_gross_margin'])

    def test_a_balance_sheet_without_liabilities_is_not_debt_free(self):
        # Two companies filed a debt ratio of 40 % and 60 %. A third filed a
        # balance sheet but neither liabilities line -- reading that as 0 %
        # would claim we measured something the filing never carried.
        metrics = _compute_section_metrics(
            [
                row(assets_total=1000, liabilities_total=400),
                row(assets_total=1000, liabilities_total=600),
                row(assets_total=1000, equity=500),
            ],
            'G',
        )

        self.assertEqual(metrics['median_debt_ratio'], 50)

    def test_an_unfiled_profit_does_not_read_as_break_even(self):
        # `_safe_float` turned an absent profit into 0.0, which entered the ROA
        # median as a measured break-even year and pulled it toward zero.
        metrics = _compute_section_metrics(
            [
                row(assets_total=1000, profit=100),
                row(assets_total=1000, profit=300),
                row(assets_total=1000),
            ],
            'G',
        )

        self.assertEqual(metrics['median_roa'], 20)

    def test_a_filed_zero_is_still_a_measurement(self):
        # The mirror image, and the reason the rule is "was it filed", not "is
        # it truthy": a company that really did file no debt, or no added
        # value, must stay in the median.
        metrics = _compute_section_metrics(
            [
                row(revenue=1000, added_value=0, assets_total=1000, liabilities_total=0),
                row(revenue=1000, added_value=200, assets_total=1000, liabilities_total=500),
            ],
            'G',
        )

        self.assertEqual(metrics['median_gross_margin'], 10)
        self.assertEqual(metrics['median_debt_ratio'], 25)

    def test_accruals_alone_are_enough_to_measure_debt(self):
        # Either liabilities line being present makes the sum a measurement;
        # only both being absent leaves it unknown.
        metrics = _compute_section_metrics(
            [row(assets_total=1000, liabilities_accruals=250)],
            'G',
        )

        self.assertEqual(metrics['median_debt_ratio'], 25)

    def test_the_median_current_ratio_is_built_from_the_reported_total(self):
        # The median is printed beside the company's own current ratio, so the
        # two have to be the same figure. This module used to hold its own copy
        # of the rule, and the copy kept summing the components after the
        # statement was found to report the total at r.33 -- the median would
        # have excluded cash from every filing since 2015 while the ratios next
        # to it included it.
        #
        # Each company's components sum to 100 and its reported total is 300,
        # so a median built by summing reads 10 % and one built from the
        # statement reads 30 %. Both are far from the other; neither can pass
        # for the other by rounding.
        rows = [
            row(
                assets_total=1000,
                liabilities_short=1000,
                assets_current=300,
                assets_inventory=100,
                assets_receivables_short=0,
                assets_financial_accounts=0,
            )
            for _ in range(3)
        ]

        metrics = _compute_section_metrics(rows, 'G')

        self.assertEqual(metrics['median_current_ratio'], 30.0)
