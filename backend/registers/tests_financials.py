from decimal import Decimal

from django.test import SimpleTestCase

from registers.services.ruz_financials_sync import RuzFinancialsSyncService


class RuzFinancialsSyncServiceTests(SimpleTestCase):
    def setUp(self):
        self.service = RuzFinancialsSyncService(api=None)

    def test_extract_year_prefers_obdobie_do(self):
        statement = {"obdobieOd": "2018-01", "obdobieDo": "2019-12"}
        self.assertEqual(self.service._extract_year(statement), 2019)

    def test_extract_with_template_maps_revenue_cost_profit(self):
        table = {
            "data": [
                "150000", "140000",  # revenue row current/previous
                "90000", "85000",    # cost row current/previous
                "60000", "55000",    # profit row current/previous
            ]
        }
        template = {
            "riadky": [
                {"text": {"sk": "Výnosy z hospodárskej činnosti spolu súčet (r. 02 až r. 07)"}},
                {"text": {"sk": "Náklady na hospodársku činnosť spolu súčet (r. 09 až r. 17)"}},
                {"text": {"sk": "Výsledok hospodárenia z hospodárskej činnosti (+/-)"}},
            ]
        }

        revenue, cost, profit = self.service._extract_with_template(table, template)

        self.assertEqual(revenue, Decimal("150000"))
        self.assertEqual(cost, Decimal("90000"))
        self.assertEqual(profit, Decimal("60000"))

    def test_extract_with_template_calculates_profit_when_missing(self):
        table = {
            "data": [
                "200000", "190000",
                "150000", "140000",
            ]
        }
        template = {
            "riadky": [
                {"text": {"sk": "Výnosy z hospodárskej činnosti spolu súčet (r. 02 až r. 07)"}},
                {"text": {"sk": "Náklady na hospodársku činnosť spolu súčet (r. 09 až r. 17)"}},
            ]
        }

        revenue, cost, profit = self.service._extract_with_template(table, template)

        self.assertEqual(revenue, Decimal("200000"))
        self.assertEqual(cost, Decimal("150000"))
        self.assertEqual(profit, Decimal("50000"))

    def test_extract_table_total_uses_last_numeric_value(self):
        table = {"data": ["abc", "1", "2.50"]}
        self.assertEqual(self.service._extract_table_total(table), Decimal("2.50"))

