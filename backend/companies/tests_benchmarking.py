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

from unittest.mock import patch

from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext

from companies.models import Company, CompanyFinancialResult, SectorBenchmark
from companies.services import benchmarking
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


class EveryQualifyingYearTests(TestCase):
    """`year=None` computes every year worth computing, not the newest alone.

    Both readers -- `companies/serializers.py` and
    `companies/services/pdf_report.py` -- look a benchmark up by the **company's**
    latest filed year, so a table holding one year serves only the companies
    whose last filing is still in it. On production on 2026-09-17 the table held
    19 rows, all of them 2025, and 1 703 of 15 467 companies rendered with no
    benchmark at all (2024: 469, 2023: 179, 2013-2022: 1 055).
    """

    @staticmethod
    def _file(year: int, count: int, *, first: int) -> None:
        """`count` companies of one NACE section, each with a `year` filing."""
        for n in range(first, first + count):
            company = Company.objects.create(
                ruz_id=910000 + n,
                ico=f'{91000000 + n:08d}',
                nazov_UJ=f'Firma {year}/{n}',
                sk_NACE='4610',  # section G
            )
            CompanyFinancialResult.objects.create(
                company=company, year=year, revenue=1000, profit=100,
                assets_total=2000, equity=800, liabilities_total=1100,
            )

    def setUp(self):
        self._file(2024, 6, first=0)
        self._file(2025, 6, first=6)

    def test_a_run_without_a_year_stores_every_qualifying_year(self):
        with patch.object(benchmarking, 'MIN_RESULTS_PER_YEAR', 1), \
                patch.object(benchmarking, 'MIN_COMPANIES_PER_SECTION', 1):
            summary = benchmarking.compute_sector_benchmarks()

        self.assertEqual(sorted(summary), [2024, 2025])
        self.assertEqual(
            sorted(set(SectorBenchmark.objects.values_list('year', flat=True))),
            [2024, 2025],
        )

    def test_an_explicit_year_still_computes_only_that_one(self):
        with patch.object(benchmarking, 'MIN_COMPANIES_PER_SECTION', 1):
            summary = benchmarking.compute_sector_benchmarks(2024)

        self.assertEqual(list(summary), [2024])
        self.assertEqual(
            list(SectorBenchmark.objects.values_list('year', flat=True)), [2024]
        )

    def test_a_year_under_the_sample_threshold_is_left_out(self):
        # 2026 on production: 98 filings against 13 999-14 790 for every year
        # 2013-2025. The threshold is not what held the table to a single year
        # -- a `break` was, and it cost every year but one -- but it still has
        # to bind where it is meant to.
        self._file(2026, 3, first=20)
        with patch.object(benchmarking, 'MIN_RESULTS_PER_YEAR', 5), \
                patch.object(benchmarking, 'MIN_COMPANIES_PER_SECTION', 1):
            summary = benchmarking.compute_sector_benchmarks()

        self.assertEqual(sorted(summary), [2024, 2025])

    def _queries_to_compute(self, year: int) -> CaptureQueriesContext:
        """The queries one year costs, always on the same branch.

        `update_or_create` takes two: its create half wraps the INSERT in its own
        `atomic`, so it pays a SAVEPOINT/RELEASE pair the update half does not.
        Clearing the table first puts both measurements on the create half --
        otherwise the second run is compared against a different code path and
        reads as an improvement it did not make.
        """
        SectorBenchmark.objects.all().delete()
        with CaptureQueriesContext(connection) as ctx:
            benchmarking.compute_sector_benchmarks(year)
        return ctx

    def test_the_cost_per_year_does_not_grow_with_the_rows_in_it(self):
        # A field left out of `only()` is not absent, it is *deferred*: reading
        # it issues one more query, per row. `liabilities_accruals` was missing
        # from that list while `_compute_section_metrics` read it for every row,
        # so a single year cost one round trip per filing -- 13 999 of them on
        # production -- and computing thirteen years would have multiplied it.
        #
        # Equal counts for 6 rows and for 12 is the whole assertion. The fetch
        # itself is one server-side cursor either way (`iterator()`), so any
        # per-row query makes the second number larger by exactly six.
        with patch.object(benchmarking, 'MIN_COMPANIES_PER_SECTION', 1):
            few = self._queries_to_compute(2025)
            self._file(2025, 6, first=40)
            many = self._queries_to_compute(2025)

        self.assertEqual(
            len(few), len(many),
            'computing a year must not cost a query per filing:\n'
            + '\n'.join(f'  6 rows: {q["sql"][:90]}' for q in few.captured_queries)
            + '\n'
            + '\n'.join(f' 12 rows: {q["sql"][:90]}' for q in many.captured_queries),
        )
