from unittest.mock import Mock

from django.test import SimpleTestCase

from registers.scrapers.debt_result import DebtCheckState
from registers.scrapers.soc_poist_debt import check_socpoist_debt
from registers.scrapers.vszp_debt import check_vszp_debt_get

# Trimmed copies of the two responses the live site actually returns, so the
# parser is pinned to the real markup rather than to an idea of it.
VSZP_NO_RECORD_PAGE = """
<html><body>
<form><input type="hidden" name="nazov" value="31700764"/></form>
<table class="table table-striped tabulkaStandard">
    <thead>
        <tr>
            <th>Obchodné meno</th><th>Obec</th><th>Ulica</th><th>PSČ</th>
            <th>Pohľadávka</th><th>Typ platiteľa</th><th>Rozsah</th>
        </tr>
    </thead>
    </tbody>
        </tbody>
    </table>
Nenašli sa žiadne záznamy.
</body></html>
"""

# Note what this response does *not* contain: any "€". The claim column is a
# bare number, right-aligned.
VSZP_DEBTOR_ROW_PAGE = """
<html><body>
<table class="table table-striped tabulkaStandard">
    <thead>
        <tr>
            <th>Obchodné meno</th><th>Obec</th><th>Ulica</th><th>PSČ</th>
            <th>Pohľadávka</th><th>Typ platiteľa</th><th>Rozsah</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td>A - TEAM SECURITY, A.S.<br />IČO: 34136088</td>
            <td>BRATISLAVA-RUŽINOV</td>
            <td>MILETIČOVA 23</td>
            <td>82109</td>
            <td style="text-align: right;">6 641,86</td>
            <td>Zamestnávateľ</td>
            <td style="text-align: center;"> </td>
        </tr>
    </tbody>
</table>
</body></html>
"""


class InsuranceDebtScraperTests(SimpleTestCase):
    def test_vszp_missing_result_row_is_unknown_not_zero(self):
        session = Mock()
        session.get.return_value = Mock(
            text="<html><body><p>Unexpected page structure</p></body></html>",
        )

        with self._patch_session("registers.scrapers.vszp_debt.get_session_with_retry", session):
            result = check_vszp_debt_get("12345678")

        self.assertEqual(result.state, DebtCheckState.UNKNOWN)
        self.assertIsNone(result.amount)
        self.assertEqual(result.error_type, "parse_error")

    def test_vszp_explicit_no_record_is_authoritative_zero(self):
        """The site's own "no records" message is the absence signal.

        Without this branch every company that is not a VSZP debtor reads as
        `unknown`, which tasks.update_insurance_debt refuses to count as a
        completed check -- so last_insurance_debt never advances and the whole
        table is re-queued forever.
        """
        session = Mock()
        session.get.return_value = Mock(text=VSZP_NO_RECORD_PAGE)

        with self._patch_session("registers.scrapers.vszp_debt.get_session_with_retry", session):
            result = check_vszp_debt_get("31700764")

        self.assertEqual(result.state, DebtCheckState.NOT_FOUND)
        self.assertEqual(result.amount, 0.0)
        self.assertTrue(result.is_authoritative)

    def test_vszp_debtor_row_is_found_without_a_currency_symbol(self):
        """The claim column carries no "€", so is_money() cannot gate it."""
        session = Mock()
        session.get.return_value = Mock(text=VSZP_DEBTOR_ROW_PAGE)

        with self._patch_session("registers.scrapers.vszp_debt.get_session_with_retry", session):
            result = check_vszp_debt_get("34136088")

        self.assertEqual(result.state, DebtCheckState.FOUND)
        self.assertAlmostEqual(result.amount, 6641.86, places=2)

    def test_vszp_row_for_another_ico_is_not_matched(self):
        """A bare substring match would confuse IČO 3413608 with 34136088."""
        session = Mock()
        session.get.return_value = Mock(text=VSZP_DEBTOR_ROW_PAGE)

        with self._patch_session("registers.scrapers.vszp_debt.get_session_with_retry", session):
            result = check_vszp_debt_get("3413608")

        self.assertEqual(result.state, DebtCheckState.UNKNOWN)
        self.assertIsNone(result.amount)

    def test_vszp_unparseable_amount_is_unknown_not_zero(self):
        """A row we cannot read is not a row that says "no debt"."""
        page = VSZP_DEBTOR_ROW_PAGE.replace("6 641,86", "neuvedené")
        session = Mock()
        session.get.return_value = Mock(text=page)

        with self._patch_session("registers.scrapers.vszp_debt.get_session_with_retry", session):
            result = check_vszp_debt_get("34136088")

        self.assertEqual(result.state, DebtCheckState.UNKNOWN)
        self.assertIsNone(result.amount)
        self.assertEqual(result.error_type, "parse_error")

    def test_social_explicit_no_record_is_authoritative_zero(self):
        session = Mock()
        session.get.return_value = Mock(
            text="<html><body>Zadaným kritériám nevyhovuje žiaden záznam</body></html>",
        )

        with self._patch_session("registers.scrapers.soc_poist_debt.get_session_with_retry", session):
            result = check_socpoist_debt("12345678")

        self.assertEqual(result.state, DebtCheckState.NOT_FOUND)
        self.assertEqual(result.amount, 0.0)

    def _patch_session(self, target, session):
        from unittest.mock import patch

        return patch(target, return_value=session)
