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

    def test_every_row_carries_a_company_figure_not_a_dash(self):
        # The filed statement supports all seven: a dash here means a lookup
        # that never resolved, which is what the snake_case keys did.
        rows = self.rows()
        self.assertEqual(len(rows), 7)

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
