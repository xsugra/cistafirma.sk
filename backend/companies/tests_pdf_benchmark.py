"""What the PDF's benchmark block actually prints, row by row.

The PDF renders through a template, so a row whose inputs silently resolve to
`None` looks exactly like a row for a company that filed nothing: both draw
"—". Three of the six lookups here asked the ratio dict for `current_ratio`,
`self_financing_ratio` and `debt_to_equity`, while `to_dict` emits camelCase --
so those rows showed a dash on the company side for every company that has ever
had a report generated, and nothing anywhere reported a problem.

These tests read the context the report hands the template, which is the last
point before rendering where that can be checked without a PDF parser.
"""

import sys
import types
from unittest.mock import MagicMock, patch

from django.test import TestCase

from companies.models import Company, CompanyFinancialResult, SectorBenchmark
from companies.services import pdf_report


def benchmark_context(company):
    """The template context `generate_company_report` builds for `company`.

    Called directly rather than through `get_company_report`: the cache wrapper
    around it is `CompanyReportCacheTests`' subject, and going through it would
    have these tests write report keys into the shared Redis on every run.
    """
    captured = {}

    def fake_render(template, context, *args, **kwargs):
        captured['context'] = context
        return '<html></html>'

    # `HTML` is imported inside the function, so it has to be stubbed in
    # `sys.modules` rather than patched onto the module.
    weasyprint = types.ModuleType('weasyprint')
    weasyprint.HTML = MagicMock()
    weasyprint.HTML.return_value.write_pdf.return_value = b'%PDF-1.4'
    with patch.object(pdf_report, 'render_to_string', fake_render), \
            patch.dict(sys.modules, {'weasyprint': weasyprint}):
        pdf_report.generate_company_report(company)

    return captured['context']


class PdfBenchmarkRowsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            ruz_id=999201, ico='00999201', nazov_UJ='Maržová, s.r.o.', sk_NACE='4610'
        )
        CompanyFinancialResult.objects.create(
            company=self.company,
            year=2025,
            revenue=1000,
            added_value=250,
            total_revenue=1000,
            profit=100,
            assets_total=2000,
            equity=800,
            liabilities_total=1100,
            assets_inventory=200,
            assets_receivables_short=300,
            assets_financial_accounts=100,
            liabilities_short=400,
        )
        SectorBenchmark.objects.create(
            nace_section='G',
            year=2025,
            company_count=30,
            median_assets_total=1800,
            median_equity=700,
            median_debt_ratio=55,
            median_gross_margin=8,
            median_current_ratio=1.5,
            median_self_financing_ratio=40,
            median_roa=2,
            median_roe=5,
            median_ros=3,
        )

    def rows(self):
        context = benchmark_context(self.company)
        return {row['label']: row for row in context['benchmark_rows']}

    def test_the_gross_margin_row_is_present(self):
        # It was absent from the export while the company page carried it.
        self.assertIn('Hrubá marža', self.rows())

    def test_the_two_size_medians_are_printed(self):
        # Both were stored and never shown, so the table listed nine ratios
        # with no hint of the balance sheet they came from.
        rows = self.rows()

        # `_fmt_eur` separates thousands with a non-breaking space and joins
        # the currency with no space at all.
        self.assertEqual(rows['Aktíva']['company_val'], '2 000€')
        self.assertEqual(rows['Aktíva']['sector_val'], '1 800€')
        self.assertEqual(rows['Vlastný kapitál']['company_val'], '800€')
        self.assertEqual(rows['Vlastný kapitál']['sector_val'], '700€')
        # They are euro amounts, not bare ratios: `_fmt` had no `€` branch and
        # printed "1 800.00" beside medians that carry their unit.
        self.assertNotIn('1800.00', rows['Aktíva']['sector_val'])

    def test_the_size_rows_lead_the_table(self):
        # Order is the only thing that says these two set up every ratio below.
        context = benchmark_context(self.company)
        labels = [row['label'] for row in context['benchmark_rows']]

        self.assertEqual(labels[:2], ['Aktíva', 'Vlastný kapitál'])

    def test_a_median_no_one_computed_is_a_dash_not_a_zero(self):
        SectorBenchmark.objects.filter(nace_section='G', year=2025).update(
            median_assets_total=None, median_equity=None
        )

        rows = self.rows()

        self.assertEqual(rows['Aktíva']['sector_val'], '—')
        self.assertEqual(rows['Vlastný kapitál']['sector_val'], '—')
        # The company side is unaffected -- it comes from the filing.
        self.assertEqual(rows['Aktíva']['company_val'], '2 000€')

    def test_every_row_carries_a_company_figure_not_a_dash(self):
        # The filed statement supports all nine: a dash here means a lookup
        # that never resolved, which is what the snake_case keys did.
        rows = self.rows()
        self.assertEqual(len(rows), 9)

        for label, row in rows.items():
            with self.subTest(label=label):
                self.assertNotEqual(row['company_val'], '—', f'{label} lost its figure')
                self.assertNotEqual(row['sector_val'], '—', f'{label} lost its median')

    def test_the_figures_are_the_ones_the_formulas_give(self):
        rows = self.rows()

        # added_value / revenue, the same expression as `Financials.grossMargin`.
        self.assertEqual(rows['Hrubá marža']['company_val'], '25.0 %')
        # (liabilities_total + accruals) / assets_total.
        self.assertEqual(rows['Zadĺženosť']['company_val'], '55.0 %')
        # Current assets 200 + 300 + 100 over short liabilities 400.
        self.assertEqual(rows['L3 Likvidita']['company_val'], '1.50')
        self.assertEqual(rows['Samofinancovanie']['company_val'], '40.0 %')

    def test_a_line_the_statement_lacked_is_a_dash_not_a_zero(self):
        # Same company, no income statement lines at all.
        CompanyFinancialResult.objects.filter(company=self.company).delete()
        CompanyFinancialResult.objects.create(
            company=self.company, year=2025, assets_total=2000, equity=800,
            liabilities_total=1100,
        )

        rows = self.rows()

        self.assertEqual(rows['Hrubá marža']['company_val'], '—')
        self.assertEqual(rows['Zadĺženosť']['company_val'], '55.0 %')
        self.assertNotIn('0.0 %', [r['company_val'] for r in rows.values()])


class PdfFinancialHistoryTests(TestCase):
    """The history table's rows, cell by cell.

    Every amount here went through `float(fr.revenue or 0)`, so a line the
    filing did not carry printed "0 €" -- a confident figure in place of an
    absent one, on the document a reader is most likely to take at face value.
    The sign was decided in the template, where `_fmt_eur`'s string met a `> 0`
    comparison, and Django swallows the `TypeError` that raises and calls the
    comparison False -- so every profit cell rendered red, dashes included.
    """

    def setUp(self):
        self.company = Company.objects.create(
            ruz_id=999203, ico='00999203', nazov_UJ='Historická, s.r.o.',
        )

    def history(self):
        return benchmark_context(self.company)['financial_history']

    def test_a_line_the_filing_lacked_is_a_dash_not_a_zero(self):
        # A balance sheet with no income statement: the shape 00681393 has.
        CompanyFinancialResult.objects.create(
            company=self.company, year=2025, assets_total=328, equity=328,
        )

        row = self.history()[0]

        self.assertEqual(row['revenue'], '—')
        self.assertEqual(row['profit'], '—')
        self.assertEqual(row['profit_after_tax'], '—')
        self.assertEqual(row['assets'], '328€')
        self.assertNotIn('0€', [row['revenue'], row['profit'], row['profit_after_tax']])

    def test_a_filed_zero_still_prints_as_a_zero(self):
        # The other half of the distinction: a statement can genuinely file
        # zeros, and a dash there would be its own lie.
        CompanyFinancialResult.objects.create(
            company=self.company, year=2025, revenue=0, profit=0, total_revenue=0,
        )

        row = self.history()[0]

        self.assertEqual(row['revenue'], '0€')
        self.assertTrue(row['profit_is_filed'])

    def test_the_two_profit_rows_are_different_quantities(self):
        CompanyFinancialResult.objects.create(
            company=self.company, year=2025, revenue=5000, profit=300,
            profit_after_tax=240,
        )

        row = self.history()[0]

        self.assertEqual(row['profit'], '300€')
        self.assertEqual(row['profit_after_tax'], '240€')

    def test_the_sign_is_decided_on_the_raw_value_not_on_the_rendered_string(self):
        CompanyFinancialResult.objects.create(
            company=self.company, year=2024, revenue=1000, profit=-50,
            profit_after_tax=-80,
        )
        CompanyFinancialResult.objects.create(
            company=self.company, year=2025, revenue=1000, profit=90,
            profit_after_tax=70,
        )

        loss, gain = self.history()

        self.assertTrue(loss['profit_is_filed'])
        self.assertFalse(loss['profit_is_positive'])
        self.assertFalse(loss['profit_after_tax_is_positive'])
        self.assertTrue(gain['profit_is_positive'])
        self.assertTrue(gain['profit_after_tax_is_positive'])

    def test_an_absent_profit_is_not_flagged_as_filed_at_all(self):
        CompanyFinancialResult.objects.create(
            company=self.company, year=2025, assets_total=328, equity=328,
        )

        row = self.history()[0]

        # Both flags False is what tells the template to leave the cell
        # uncoloured. `is_positive` alone cannot: "not positive" and "not
        # filed" are the same answer, and a dash would have gone red.
        self.assertFalse(row['profit_is_filed'])
        self.assertFalse(row['profit_is_positive'])
        self.assertFalse(row['profit_after_tax_is_filed'])
        self.assertFalse(row['profit_after_tax_is_positive'])


class PdfRatioRowsTests(TestCase):
    """The financial-analysis table prints every row it declares.

    `RATIO_ROWS` names ten ratios and `ratio_rows` skips any whose value is
    `None`. The lookup asked the camelCase `ratios` dict for snake_case names,
    so seven rows were dropped for every company -- and a dropped row and a row
    the company could not support look identical from outside. This is the same
    failure as the benchmark block's, in the table directly above it.
    """

    def setUp(self):
        self.company = Company.objects.create(
            ruz_id=999202, ico='00999202', nazov_UJ='Ukazovateľová, a.s.',
            sk_NACE='4610',
        )
        # A statement that supports all ten: both liquidity pairs, both
        # activity rows and both debt rows need their own inputs.
        CompanyFinancialResult.objects.create(
            company=self.company,
            year=2025,
            revenue=2000,
            added_value=500,
            total_revenue=2000,
            profit=150,
            assets_total=1000,
            equity=600,
            liabilities_total=400,
            assets_inventory=100,
            assets_receivables_short=100,
            assets_financial_accounts=50,
            liabilities_short=200,
        )

    def rows(self):
        context = benchmark_context(self.company)
        return {row['label']: row for row in context['ratio_rows']}

    def test_every_declared_row_is_rendered(self):
        self.assertEqual(len(self.rows()), len(pdf_report.RATIO_ROWS))

    def test_the_rows_a_missing_key_used_to_swallow_are_there(self):
        # Named individually: these are the seven that never appeared, and a
        # count alone would not say which one came back.
        rows = self.rows()

        for label in (
            'L3 — Bežná likvidita',
            'L2 — Pohotová likvidita',
            'L1 — Okamžitá likvidita',
            'Obrat aktív',
            'Doba inkasa pohľadávok',
            'Zadĺženosť (D/E)',
            'Miera samofinancovania',
        ):
            with self.subTest(row=label):
                self.assertIn(label, rows)

    def test_each_row_carries_both_a_figure_and_a_verdict(self):
        for label, row in self.rows().items():
            with self.subTest(row=label):
                self.assertNotEqual(row['display'], '—')
                self.assertIn(
                    row['interpretation'], ('good', 'warning', 'bad', 'unknown')
                )

    def test_a_ratio_the_statement_cannot_support_is_omitted_not_faked(self):
        # No asset detail at all, so the three liquidity rows have no value.
        # They are left out rather than drawn as zero -- and the rows that do
        # have inputs are unaffected.
        CompanyFinancialResult.objects.filter(company=self.company).delete()
        CompanyFinancialResult.objects.create(
            company=self.company, year=2025, revenue=2000, total_revenue=2000,
            profit=150, assets_total=1000, equity=600, liabilities_total=400,
        )

        rows = self.rows()

        self.assertNotIn('L3 — Bežná likvidita', rows)
        self.assertIn('ROA (Rentabilita aktív)', rows)
        self.assertEqual(rows['ROA (Rentabilita aktív)']['display'], '15.0 %')
