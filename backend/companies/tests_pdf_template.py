"""What the report template renders, read as text.

`render_to_string` has no dependency on weasyprint -- only the PDF conversion
does -- so the template can be rendered and read in the test venv, which is
where weasyprint is deliberately absent. Every test in this module therefore
asserts on rendered HTML rather than on the context handed to it.

That gap mattered. The Z-score card asked for `z_score` and `z_score_label`
against the camelCase dict `to_dict` publishes, so each lookup resolved to the
empty string; a Django comparison against `''` raises a TypeError that the
template engine swallows as False, and `'' != None` is True -- so the card's
guard passed for *every* company, both `>` comparisons failed, and it fell to
its `else` branch. The registry's whole population was printed a red badge
reading "Zvýšené riziko bankrotu" over an empty score.

The context tests in `tests_pdf_benchmark` could not have caught that: the
context was correct. Only the rendering was wrong, and it is exactly the kind
of wrongness that leaves no trace -- a template lookup that misses is not an
error in Django, it is a blank.
"""

import sys
import types
from unittest.mock import MagicMock, patch

from django.template.loader import render_to_string as real_render_to_string
from django.test import TestCase

from companies.models import Company, CompanyFinancialResult
from companies.services import pdf_report


def rendered_html(company):
    """The real HTML `generate_company_report` renders for `company`.

    `render_to_string` is wrapped rather than replaced: the point is to keep
    the real rendering and capture it. Only `weasyprint` is stubbed, in
    `sys.modules`, because it is imported inside the function.
    """
    captured = {}

    def spy(template, context, *args, **kwargs):
        html = real_render_to_string(template, context, *args, **kwargs)
        captured['html'] = html
        return html

    weasyprint = types.ModuleType('weasyprint')
    weasyprint.HTML = MagicMock()
    weasyprint.HTML.return_value.write_pdf.return_value = b'%PDF-1.4'
    with patch.object(pdf_report, 'render_to_string', spy), \
            patch.dict(sys.modules, {'weasyprint': weasyprint}):
        pdf_report.generate_company_report(company)

    return captured['html']


class PdfZScoreCardTests(TestCase):
    """The card prints a zone the company is actually in, or nothing at all."""

    def setUp(self):
        self.company = Company.objects.create(
            ruz_id=999301, ico='00999301', nazov_UJ='Skóre, s.r.o.',
        )

    def _with_statement(self, **fields):
        CompanyFinancialResult.objects.create(
            company=self.company, year=2025, **fields
        )
        return rendered_html(self.company)

    def test_a_company_with_no_score_is_not_given_a_bankruptcy_verdict(self):
        # The regression this module exists for. A statement with no assets
        # line cannot produce a Z-score, and the card must not appear at all.
        html = self._with_statement(revenue=1000, profit=100)

        self.assertNotIn('Zvýšené riziko bankrotu', html)
        self.assertNotIn('Nízke riziko bankrotu', html)
        self.assertNotIn('Nejednoznačná situácia', html)
        self.assertNotIn('Altman Z-score', html)

    def test_a_distressed_company_is_told_so_and_shown_its_score(self):
        # x3 negative and x5 small: comfortably inside the distress band.
        html = self._with_statement(
            assets_total=1000, equity=100, liabilities_total=900,
            profit=-300, revenue=100, equity_retained=-500,
        )

        self.assertIn('Zvýšené riziko bankrotu', html)
        self.assertIn('Pásmo bankrotu', html)
        self.assertIn('zscore-bad', html)
        self.assertNotIn('Nízke riziko bankrotu', html)

    def test_a_safe_company_is_told_so_and_shown_its_score(self):
        html = self._with_statement(
            assets_total=1000, equity=900, liabilities_total=100,
            profit=400, revenue=1400, equity_retained=800,
            assets_inventory=300, liabilities_short=200,
        )

        self.assertIn('Nízke riziko bankrotu', html)
        self.assertIn('Bezpečná zóna', html)
        self.assertIn('zscore-good', html)
        self.assertNotIn('Zvýšené riziko bankrotu', html)


class PdfHistoryTableTests(TestCase):
    """The history table's cells, as rendered."""

    def setUp(self):
        self.company = Company.objects.create(
            ruz_id=999302, ico='00999302', nazov_UJ='História, s.r.o.',
        )

    def test_an_unfiled_line_renders_a_dash_and_never_a_double_currency(self):
        CompanyFinancialResult.objects.create(
            company=self.company, year=2025, assets_total=328, equity=328,
        )

        html = rendered_html(self.company)

        # `_fmt_eur` ends an amount with its currency, and the cell used to
        # append another one: every figure in this table printed "1 234 € €".
        self.assertNotIn('€€', html)
        self.assertNotIn('€ €', html)
        # The balance sheet was filed; the income statement was not.
        self.assertIn('328€', html)

    def test_no_template_comment_leaks_into_the_document(self):
        # `{# #}` is a *single-line* tag in Django. A comment written across
        # lines is therefore not a comment: it is body text, and the three
        # explanatory blocks in this template printed themselves into the PDF,
        # "1 234 € €" among them. `{% comment %}` is the multi-line form, and
        # this is the assertion that keeps them apart -- a reader of the
        # rendered report should never meet the template's own prose.
        CompanyFinancialResult.objects.create(
            company=self.company, year=2025, revenue=1000, profit=100,
        )

        html = rendered_html(self.company)

        for fragment in (
            '_fmt_eur',
            'camelCase',
            'to_dict',
            'unequal-to-None',
            'the figure is `revenue`',
        ):
            with self.subTest(fragment=fragment):
                self.assertNotIn(fragment, html)

    def test_both_profit_columns_are_present(self):
        CompanyFinancialResult.objects.create(
            company=self.company, year=2025, revenue=1000, profit=300,
            profit_after_tax=240,
        )

        html = rendered_html(self.company)

        self.assertIn('VH z hosp. č.', html)
        self.assertIn('Zisk po zd.', html)
        self.assertIn('300€', html)
        self.assertIn('240€', html)

    def test_the_revenue_column_is_named_vynosy_not_trzby(self):
        # The figure is `revenue`, which is "Výnosy z hospodárskej činnosti
        # spolu" -- not tržby. The header said "Tržby".
        CompanyFinancialResult.objects.create(
            company=self.company, year=2025, revenue=1000, profit=100,
        )

        self.assertIn('Výnosy', rendered_html(self.company))


class PdfNoStatementTests(TestCase):
    """A company with nothing on file still produces a report."""

    def test_a_company_with_no_financial_results_renders_without_a_ratio_block(self):
        company = Company.objects.create(
            ruz_id=999303, ico='00999303', nazov_UJ='Prázdna, s.r.o.',
        )

        html = rendered_html(company)

        self.assertIn('Prázdna, s.r.o.', html)
        self.assertNotIn('Finančná analýza', html)
        self.assertNotIn('Prehľad hospodárskych výsledkov', html)
        # The disclaimer is the one block that must always be there.
        self.assertIn('CistaFirma nenesie zodpovednosť', html)
