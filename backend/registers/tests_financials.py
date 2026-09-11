from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import requests
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from companies.models import Company, CompanyFinancialResult
from registers.integrations.ruz_api import RuzApi, RuzUnreachable
from registers.models import CompanySyncStatus
from registers.services.ruz_financials_sync import (
    ANSWERED_RETRY_AFTER,
    FinancialsOutcome,
    RuzFinancialsSyncService,
    sync_company_and_record,
)


class RuzApiTransportErrorTests(SimpleTestCase):
    """An unreachable registry and an empty one must not arrive as one value.

    The default client has folded `RequestException` into `None` since it was
    written, and five callers depend on that -- so the default is pinned here
    as hard as the new behaviour. A change that made ordinary callers start
    raising would be a worse bug than the one being fixed.
    """

    def _client(self, *, failing_with, **kwargs):
        api = RuzApi(**kwargs)
        api.session = MagicMock()
        api.session.get.side_effect = failing_with
        return api

    def _connection_error(self):
        return requests.exceptions.ConnectionError("Failed to resolve www.registeruz.sk")

    def test_the_default_client_still_answers_none(self):
        api = self._client(failing_with=self._connection_error())

        self.assertIsNone(api.get_company_id_by_ico("12345678"))
        self.assertIsNone(api.get_company_details(1))
        self.assertIsNone(api.get_financial_statement_details(2))
        self.assertIsNone(api.get_financial_report_details(3))
        self.assertIsNone(api.get_report_template_details(4))

    def test_a_strict_client_raises_instead_of_answering_none(self):
        api = self._client(failing_with=self._connection_error(), raise_on_transport_error=True)

        for getter, argument in (
            (api.get_company_id_by_ico, "12345678"),
            (api.get_company_details, 1),
            (api.get_financial_statement_details, 2),
            (api.get_financial_report_details, 3),
            (api.get_report_template_details, 4),
        ):
            with self.subTest(getter=getter.__name__):
                with self.assertRaises(RuzUnreachable):
                    getter(argument)

    def test_a_404_is_an_answer_and_stays_none_even_when_strict(self):
        """The registry said "no such record". That is knowledge, not a failure."""
        response = MagicMock()
        response.status_code = 404
        api = self._client(
            failing_with=requests.exceptions.HTTPError(response=response),
            raise_on_transport_error=True,
        )

        self.assertIsNone(api.get_company_details(1))

    def test_a_server_error_is_not_an_answer_and_raises_when_strict(self):
        """A 5xx after the retry session gave up is not "this company has nothing"."""
        response = MagicMock()
        response.status_code = 503
        api = self._client(
            failing_with=requests.exceptions.HTTPError(response=response),
            raise_on_transport_error=True,
        )

        with self.assertRaises(RuzUnreachable):
            api.get_company_details(1)


class _ScriptedRuzApi:
    """Answers the financials getters from fixtures, or fails on demand."""

    def __init__(
        self, *, detail, statements=None, reports=None, templates=None, unreachable=False
    ):
        self.detail = detail
        self.statements = statements or {}
        self.reports = reports or {}
        self.templates = templates or {}
        self.unreachable = unreachable

    def _answer(self, value):
        if self.unreachable:
            raise RuzUnreachable("scripted transport failure")
        return value

    def get_company_details(self, company_id):
        return self._answer(self.detail)

    def get_company_by_ico(self, ico):
        return self._answer(self.detail)

    def get_financial_statement_details(self, statement_id):
        return self._answer(self.statements.get(statement_id))

    def get_financial_report_details(self, report_id):
        return self._answer(self.reports.get(report_id))

    def get_report_template_details(self, template_id):
        return self._answer(self.templates.get(template_id))


class FinancialsOutcomeTests(TestCase):
    """`rows=0` used to mean four different things. It now means one."""

    def setUp(self):
        self.company = Company.objects.create(
            ruz_id=4711,
            ico="47110000",
            nazov_UJ="Zavierka s.r.o.",
        )

    def _service(self, **kwargs):
        return RuzFinancialsSyncService(api=_ScriptedRuzApi(**kwargs))

    def _readable(self):
        """A company whose one statement yields one readable revenue row."""
        return dict(
            detail={"idUctovnychZavierok": [77]},
            statements={
                77: {"obdobieDo": "2023-12-31", "idUctovnychVykazov": [88], "idSablony": 1}
            },
            reports={
                88: {"idSablony": 1, "obsah": {"tabulky": [{"nazov": "Vynosy", "data": ["1000"]}]}}
            },
            templates={1: {"tabulky": []}},
        )

    def test_a_readable_statement_is_recorded(self):
        result = self._service(**self._readable()).sync_company_detailed(self.company)

        self.assertEqual(result.outcome, FinancialsOutcome.RECORDED)
        self.assertEqual(result.rows, 1)
        self.assertTrue(result.succeeded)
        self.assertEqual(
            CompanyFinancialResult.objects.get(company=self.company, year=2023).revenue,
            Decimal("1000"),
        )

    def test_a_company_with_no_statements_is_an_answer_not_a_failure(self):
        result = self._service(detail={"idUctovnychZavierok": []}).sync_company_detailed(
            self.company
        )

        self.assertEqual(result.outcome, FinancialsOutcome.NO_STATEMENTS)
        self.assertEqual(result.rows, 0)
        self.assertTrue(
            result.succeeded,
            "reaching the registry and reading it correctly is a successful sync; "
            "the statement being absent is a fact about the company",
        )

    def test_a_company_absent_from_ruz_is_an_answer_not_a_failure(self):
        result = self._service(detail=None).sync_company_detailed(self.company)

        self.assertEqual(result.outcome, FinancialsOutcome.NOT_IN_RUZ)
        self.assertTrue(result.succeeded)

    def test_an_unreachable_registry_is_not_reported_as_zero_rows(self):
        result = self._service(detail=None, unreachable=True).sync_company_detailed(
            self.company
        )

        self.assertEqual(result.outcome, FinancialsOutcome.UNREACHABLE)
        self.assertFalse(
            result.succeeded,
            "this is the whole increment: an unreachable registry must not arrive "
            "as the same value as a company that genuinely has no statements",
        )

    def test_sync_company_keeps_its_int_signature(self):
        service = self._service(**self._readable())

        self.assertEqual(service.sync_company(self.company), 1)


class SyncCompanyAndRecordTests(TestCase):
    """The single outcome -> CompanySyncStatus rule."""

    def setUp(self):
        self.company = Company.objects.create(
            ruz_id=4712, ico="47120000", nazov_UJ="Zaznam s.r.o."
        )

    def _run(self, **kwargs):
        service = RuzFinancialsSyncService(api=_ScriptedRuzApi(**kwargs))
        return sync_company_and_record(self.company, service=service)

    def _status(self):
        return CompanySyncStatus.objects.get(
            company=self.company, source=CompanySyncStatus.SOURCE_FINANCIALS
        )

    def test_an_answered_attempt_is_recorded_as_a_success(self):
        result = self._run(detail={"idUctovnychZavierok": []})

        self.assertTrue(result.succeeded)
        status = self._status()
        self.assertEqual(status.consecutive_failures, 0)
        self.assertIsNotNone(status.last_succeeded_at)

    def test_a_recorded_success_is_scheduled_far_out_not_left_due_now(self):
        """`next_retry_at = NULL` reads as "due now" and would starve the rotation.

        A success used to clear the field. Every company the due-query then read
        as due would be the ones just synced, so each batch would refill with
        the previous batch's companies and the never-attempted population would
        never be reached -- the original bug, reintroduced by its own fix.
        """
        self._run(detail={"idUctovnychZavierok": []})

        next_retry_at = self._status().next_retry_at
        self.assertIsNotNone(next_retry_at)
        self.assertGreater(next_retry_at, timezone.now() + timedelta(days=300))
        self.assertAlmostEqual(
            (next_retry_at - timezone.now()).days,
            ANSWERED_RETRY_AFTER.days,
            delta=1,
        )

    def test_an_unreachable_registry_is_recorded_as_a_failure(self):
        result = self._run(detail=None, unreachable=True)

        self.assertFalse(result.succeeded)
        status = self._status()
        self.assertEqual(status.consecutive_failures, 1)
        self.assertEqual(status.last_error_type, "network")
        self.assertIn("transport failure", status.last_error)
        self.assertIsNotNone(status.next_retry_at)
        self.assertLess(
            status.next_retry_at,
            timezone.now() + timedelta(days=1),
            "a failure should come back on the backoff schedule, not in a year",
        )

    def test_the_failure_does_not_propagate(self):
        """Raising here would break the chord in `orchestrate_full_company_sync`.

        `update_insurance_debt` is the chord callback, so an exception from this
        path stops a company's insurance debts from ever being refreshed again
        -- a second outage caused by the handling of the first.
        """
        result = self._run(detail=None, unreachable=True)

        self.assertEqual(result.outcome, FinancialsOutcome.UNREACHABLE)


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

        result = self.service._extract_with_template(table, template)

        self.assertEqual(result.get("revenue"), Decimal("150000"))
        self.assertEqual(result.get("costs"), Decimal("90000"))
        self.assertEqual(result.get("profit"), Decimal("60000"))

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

        result = self.service._extract_with_template(table, template)

        self.assertEqual(result.get("revenue"), Decimal("200000"))
        self.assertEqual(result.get("costs"), Decimal("150000"))
        self.assertEqual(result.get("profit"), Decimal("50000"))

    def test_extract_table_total_uses_last_numeric_value(self):
        table = {"data": ["abc", "1", "2.50"]}
        self.assertEqual(self.service._extract_table_total(table), Decimal("2.50"))
