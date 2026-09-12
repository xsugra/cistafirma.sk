"""`CompanyDetailSerializer.get_financials` / `get_financialsState`.

Two rules are held here.

Absent is not zero: the write gate stores a balance sheet on its own now, so a
row may legitimately carry no `revenue` and no `profit`. Every figure the
statement did not carry has to arrive as `None`, which the screen draws as a
dash -- `0 €` is a claim about the company, and we would be making it up.

The two ratios are computed by the same expressions the sector medians use
(`companies/services/benchmarking.py`), because the benchmark table prints them
side by side. A company that filed no liabilities line has an unknown debt
ratio, not a debt-free one.
"""

from django.test import TestCase

from companies.models import Company, CompanyFinancialResult
from companies.serializers import CompanyDetailSerializer
from registers.models import CompanySyncStatus


class FinancialsSerializerTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            ruz_id=999101, ico='00999101', nazov_UJ='Súvahová, s.r.o.'
        )

    def read(self):
        return CompanyDetailSerializer(self.company).data['financials']

    def test_a_balance_sheet_with_no_income_statement_reads_as_absent(self):
        CompanyFinancialResult.objects.create(
            company=self.company,
            year=2024,
            assets_total=1000,
            equity=400,
            liabilities_total=500,
            liabilities_accruals=100,
        )

        financials = self.read()

        self.assertEqual(len(financials), 1)
        self.assertIsNone(financials[0]['revenue'])
        self.assertIsNone(financials[0]['profit'])
        # ...while the lines that were filed survive as figures.
        self.assertEqual(financials[0]['assetsTotal'], 1000.0)

    def test_the_debt_ratio_needs_a_filed_liability_line(self):
        # Assets 1 000 and nothing said about what financed them.
        CompanyFinancialResult.objects.create(
            company=self.company, year=2024, assets_total=1000, equity=1000
        )

        self.assertIsNone(self.read()[0]['debtRatio'])

    def test_a_filed_zero_debt_is_a_measured_zero(self):
        CompanyFinancialResult.objects.create(
            company=self.company, year=2024, assets_total=1000, liabilities_total=0
        )

        self.assertEqual(self.read()[0]['debtRatio'], 0.0)

    def test_the_gross_margin_needs_both_of_its_lines(self):
        CompanyFinancialResult.objects.create(
            company=self.company, year=2024, revenue=1000, added_value=250
        )
        CompanyFinancialResult.objects.create(
            company=self.company, year=2023, added_value=250
        )

        by_year = {f['year']: f['grossMargin'] for f in self.read()}

        self.assertEqual(by_year[2024], 25.0)
        # No revenue filed for 2023: `added_value / max(revenue, 1)` would have
        # called that a 25 000 % margin.
        self.assertIsNone(by_year[2023])


class FinancialsStateTests(TestCase):
    """The vocabulary the company page turns into a sentence."""

    def setUp(self):
        self.company = Company.objects.create(
            ruz_id=999102, ico='00999102', nazov_UJ='Stavová, s.r.o.'
        )

    def state(self):
        return CompanyDetailSerializer(self.company).data['financialsState']

    def test_a_stored_statement_wins_over_every_failure_beside_it(self):
        CompanyFinancialResult.objects.create(
            company=self.company, year=2024, assets_total=1000
        )
        CompanySyncStatus.objects.create(
            company=self.company,
            source=CompanySyncStatus.SOURCE_FINANCIALS,
            consecutive_failures=7,
            is_blocked=True,
        )

        self.assertEqual(self.state(), 'ready')

    def test_never_attempted(self):
        self.assertEqual(self.state(), 'not_fetched')

    def test_a_manual_block_names_itself_ahead_of_the_failure_count(self):
        # A blocked source and a failing one are different operator stories:
        # one needs a decision, the other may yet succeed on its own.
        CompanySyncStatus.objects.create(
            company=self.company,
            source=CompanySyncStatus.SOURCE_FINANCIALS,
            consecutive_failures=3,
            is_blocked=True,
        )

        self.assertEqual(self.state(), 'blocked')

    def test_failed_attempt(self):
        CompanySyncStatus.objects.create(
            company=self.company,
            source=CompanySyncStatus.SOURCE_FINANCIALS,
            consecutive_failures=1,
        )

        self.assertEqual(self.state(), 'failed')

    def test_answered_but_nothing_recorded(self):
        CompanySyncStatus.objects.create(
            company=self.company,
            source=CompanySyncStatus.SOURCE_FINANCIALS,
            consecutive_failures=0,
            last_detail='no statements',
        )

        self.assertEqual(self.state(), 'nothing_recorded')

    def test_another_source_status_does_not_answer_for_financials(self):
        CompanySyncStatus.objects.create(
            company=self.company,
            source=CompanySyncStatus.SOURCE_RUZ,
            consecutive_failures=5,
        )

        self.assertEqual(self.state(), 'not_fetched')
