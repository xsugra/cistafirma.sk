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
