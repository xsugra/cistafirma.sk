"""What the company payload says about the statements RUZ holds.

The "Účtovné závierky" section shows the years *we* read. On its own that is a
sentence about this database wearing the clothes of a sentence about the
company: Volkswagen Slovakia has 37 statement IDs in RUZ and zero rows here, and
without the count it is indistinguishable from a firm that files nothing.

These tests cover the count and the shape it travels in -- the two raw ID lists
are counts to every consumer this project has, and publishing 372 integers per
company to be `len`-ed by the client was the whole of what `fields = '__all__'`
was doing with them.
"""

from django.test import TestCase

from companies.models import Company
from companies.serializers import CompanyDetailSerializer


def make_company(ico, **kwargs):
    return Company.objects.create(
        ruz_id=kwargs.pop('ruz_id', 700001),
        ico=ico,
        nazov_UJ=kwargs.pop('nazov_UJ', 'Testovacia, s. r. o.'),
        **kwargs,
    )


class RuzStatementCountTests(TestCase):
    def test_the_two_counts_are_published(self):
        company = make_company(
            '40000001',
            id_uctovnych_zavierok=[111, 222, 333],
            id_vyrocnych_sprav=[444],
        )

        data = CompanyDetailSerializer(company).data

        self.assertEqual(data['ruz_statements'], 3)
        self.assertEqual(data['ruz_annual_reports'], 1)

    def test_a_company_ruz_holds_nothing_for_counts_zero_rather_than_missing(self):
        # The section has to be able to tell "RUZ lists none" from "nobody
        # asked"; a missing key would collapse the two.
        data = CompanyDetailSerializer(make_company('40000002')).data

        self.assertEqual(data['ruz_statements'], 0)
        self.assertEqual(data['ruz_annual_reports'], 0)

    def test_the_id_lists_themselves_no_longer_travel(self):
        # The change this file exists for. The arrays are up to 372 integers
        # (Tatra Asset Management) and nothing reads them; a client that wants
        # the number has `ruz_statements`.
        company = make_company('40000003', id_uctovnych_zavierok=[9] * 372)

        data = CompanyDetailSerializer(company).data

        self.assertNotIn('id_uctovnych_zavierok', data)
        self.assertNotIn('id_vyrocnych_sprav', data)
        self.assertEqual(data['ruz_statements'], 372)

    def test_everything_else_still_travels(self):
        # `exclude` and not `fields`, so dropping two keys cannot silently drop
        # the rest -- the failure that would break every section at once.
        data = CompanyDetailSerializer(make_company('40000004', kraj='SK010')).data

        for key in ('ico', 'nazov_UJ', 'kraj', 'sk_NACE', 'financials', 'riskScore',
                    'executives', 'connections', 'financialsState', 'ruz_portal_url'):
            with self.subTest(key=key):
                self.assertIn(key, data)
