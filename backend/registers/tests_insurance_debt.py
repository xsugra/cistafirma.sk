from unittest.mock import Mock

from django.test import SimpleTestCase

from registers.scrapers.debt_result import DebtCheckState
from registers.scrapers.soc_poist_debt import check_socpoist_debt
from registers.scrapers.vszp_debt import check_vszp_debt_get


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
