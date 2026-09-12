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
    clear_template_cache,
    sync_company_and_record,
)
from registers.services.sync_engine import update_company_status


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


class TemplateCacheTestCase(TestCase):
    """Base for every test here that scripts a report template.

    `_get_template_tables` memoises templates in a module-level dict for the
    life of the process, and `_ScriptedRuzApi` answers a template id with
    whatever a *test* scripted under it. Two tests that script the same id
    therefore share one answer: the first to run wins and the second reads a
    template it never wrote -- silently, because a template that yields no
    tables is not an error here, it is an empty list.

    Cleared in `_pre_setup`, which Django calls before every test, and not in a
    mixin's `setUp`: a subclass that defines its own `setUp` would skip a
    mixin's without a word, and a guard against silent state has to hold
    whether or not the next test remembers it exists. This is the same hook
    Django uses for its own per-test setup, so it cannot be skipped by
    accident. It costs one dict clear per test.
    """

    def _pre_setup(self):
        super()._pre_setup()
        clear_template_cache()


class FinancialsOutcomeTests(TemplateCacheTestCase):
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

    def test_both_profit_rows_reach_the_row_they_belong_to(self):
        # End to end through the write path: the split is only real if
        # `profit_after_tax` survives `_extract_financials_from_reports`, the
        # write gate and `update_or_create(defaults=...)` to land in its column.
        #
        # Šablóna 699, not 1, because `_get_template_tables` memoises templates
        # in a module-level dict for the life of the process: a template id
        # another test has already fetched comes back as whatever that test
        # scripted. That is no longer a hazard for the empty templates the rest
        # of this file scripts -- an answer with no tables is not cached at all
        # now -- but this one carries real rows, so it would be, and it keeps
        # its own id. `TemplateCacheTestCase` clears the cache between tests
        # for the same reason.
        service = self._service(
            detail={"idUctovnychZavierok": [77]},
            statements={77: {"obdobieDo": "2023-12-31", "idUctovnychVykazov": [88], "idSablony": 699}},
            reports={
                88: {
                    "idSablony": 699,
                    "obsah": {
                        "tabulky": [
                            {
                                "nazov": "Výkaz ziskov a strát",
                                "data": ["60000", "55000", "48000", "44000"],
                            }
                        ]
                    },
                }
            },
            templates={
                699: {
                    "tabulky": [
                        {
                            "hlavicka": _income_statement_header(),
                            "riadky": [
                                {"text": {"sk": "Výsledok hospodárenia z hospodárskej činnosti (+/-)"}},
                                {"text": {"sk": "Výsledok hospodárenia za účtovné obdobie po zdanení (+/-)"}},
                            ],
                        }
                    ]
                }
            },
        )

        service.sync_company_detailed(self.company)

        row = CompanyFinancialResult.objects.get(company=self.company, year=2023)
        self.assertEqual(row.profit, Decimal("60000"))
        self.assertEqual(row.profit_after_tax, Decimal("48000"))

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

    def test_a_partly_readable_company_says_how_much_it_could_read(self):
        """`RECORDED` alone cannot show a parser starting to drift.

        All thirteen statements read and twelve of thirteen read both report
        `RECORDED` with rows > 0, and only the second one is the early warning
        that the first is about to stop being true. The count belongs in the
        result so a run can see the trend before it becomes a total failure.
        """
        result = self._service(
            detail={"idUctovnychZavierok": [77, 79]},
            statements={
                77: {"obdobieDo": "2023-12-31", "idUctovnychVykazov": [88], "idSablony": 1},
                # 79 is answered with nothing, as an unreadable statement is.
            },
            reports={
                88: {"idSablony": 1, "obsah": {"tabulky": [{"nazov": "Vynosy", "data": ["1000"]}]}}
            },
            templates={1: {"tabulky": []}},
        ).sync_company_detailed(self.company)

        self.assertEqual(result.outcome, FinancialsOutcome.RECORDED)
        self.assertEqual(result.rows, 1)
        self.assertIn("1 of 2", result.detail)

    def test_a_fully_readable_company_does_not_carry_a_skipped_count(self):
        """No silent branch is being reported, so the detail stays empty."""
        result = self._service(**self._readable()).sync_company_detailed(self.company)

        self.assertEqual(result.detail, "")


class NoStatementsReasonTests(TemplateCacheTestCase):
    """One sentence covered four different facts, and named the wrong one.

    Measured 2026-09-12 over the 79 companies the rotation answered with nothing:
    `NO_STATEMENTS` with "N statement(s) present, none readable" stood for an
    empty registry, an empty template, a gap in the parser, and a statement the
    write gate discarded -- and for the last one the sentence was simply false,
    which sent that investigation down two wrong paths. Each cause now says
    which it is, because the reader cannot tell them apart from outside.
    """

    def setUp(self):
        self.company = Company.objects.create(
            ruz_id=4713, ico="47130000", nazov_UJ="Dovod s.r.o."
        )

    def _service(self, **kwargs):
        return RuzFinancialsSyncService(api=_ScriptedRuzApi(**kwargs))

    def _one_statement(self, report):
        return dict(
            detail={"idUctovnychZavierok": [77]},
            statements={
                77: {"obdobieDo": "2023-12-31", "idUctovnychVykazov": [88], "idSablony": 1}
            },
            reports={88: report},
        )

    def test_a_body_without_tables_says_so(self):
        result = self._service(
            **self._one_statement({"idSablony": 1, "obsah": {"tabulky": []}}),
            templates={1: {"tabulky": []}},
        ).sync_company_detailed(self.company)

        self.assertEqual(result.outcome, FinancialsOutcome.NO_STATEMENTS)
        self.assertIn("1 statement(s) present, none recorded", result.detail)
        self.assertIn("1 with no tables in the report bodies", result.detail)

    def test_a_template_with_every_cell_empty_says_so(self):
        result = self._service(
            **self._one_statement(
                {"idSablony": 1, "obsah": {"tabulky": [{"nazov": "Vynosy", "data": ["", ""]}]}}
            ),
            templates={1: {"tabulky": []}},
        ).sync_company_detailed(self.company)

        self.assertEqual(result.outcome, FinancialsOutcome.NO_STATEMENTS)
        self.assertIn("1 with tables but no filled cell", result.detail)

    def test_tables_carrying_values_that_yield_no_field_say_so(self):
        """The gap that is this code's doing, as opposed to the registry's.

        A table with **no template at all** is not scanned for any label: the
        report holds a figure and nothing reads it. Only `filled_cells > 0` with
        an empty result separates this from the two cases above.

        The `Majetok` name here is incidental -- this test does *not* exercise
        the balance-sheet vocabulary, because `templates={1: {"tabulky": []}}`
        means no template table is ever matched and `_extract_with_template`
        returns immediately. (Before the vocabulary change the name made the
        docstring read as evidence that `Majetok` was still unmapped, which it
        no longer is -- see `test_a_majetok_table_is_read_as_a_balance_sheet`.)
        """
        result = self._service(
            **self._one_statement(
                {"idSablony": 1, "obsah": {"tabulky": [{"nazov": "Majetok", "data": ["16.23"]}]}}
            ),
            templates={1: {"tabulky": []}},
        ).sync_company_detailed(self.company)

        self.assertEqual(result.outcome, FinancialsOutcome.NO_STATEMENTS)
        self.assertIn("1 carrying values that yielded no field", result.detail)

    def test_a_statement_carrying_only_a_balance_sheet_is_now_recorded(self):
        """The measured falsehood: `00591653` filed four balance sheets.

        The parser read assets and equity out of each of them and the write gate
        dropped all four for carrying neither a revenue nor a profit. Inkrement D
        named that as this code's own decision rather than the registry's filing;
        this is the increment that stopped making it. A balance sheet on its own
        is now a row -- with `revenue` and `profit` left NULL rather than
        invented, which is what the frontend's `—` renders.
        """
        template = {
            "tabulky": [
                {
                    "nazov": "Strana aktív",
                    "pocetDatovychStlpcov": 1,
                    "hlavicka": [],
                    "riadky": [
                        {"text": {"sk": "Majetok spolu"}},
                        {"text": {"sk": "Vlastné imanie"}},
                    ],
                }
            ]
        }
        result = self._service(
            **self._one_statement(
                {"idSablony": 555, "obsah": {"tabulky": [{"nazov": "Strana aktív", "data": ["328", "328"]}]}}
            ),
            templates={555: template},
        ).sync_company_detailed(self.company)

        self.assertEqual(result.outcome, FinancialsOutcome.RECORDED)
        self.assertEqual(result.rows, 1)
        self.assertEqual(result.detail, "", "nothing was skipped, so nothing to explain")

        row = CompanyFinancialResult.objects.get(company=self.company, year=2023)
        self.assertEqual(row.assets_total, Decimal("328"))
        self.assertEqual(row.equity, Decimal("328"))
        self.assertIsNone(row.revenue)
        self.assertIsNone(row.profit)

    def test_a_statement_whose_only_fields_are_details_is_still_gated(self):
        """The gate keeps a witness: the headline fields, not "any field at all".

        A row whose sole content is `assets_inventory` or `income_tax` is a
        detail *of* a year's accounts, never a year on its own -- it would render
        as a chart of zeros with one number in it, and answer `has_financials` =
        true. Keeping the allow-list explicit is also what keeps this branch
        reachable at all, and with it the only clause naming a decision this code
        makes rather than a fact about the registry.
        """
        template = {
            "tabulky": [
                {
                    "nazov": "Strana aktív",
                    "pocetDatovychStlpcov": 1,
                    "hlavicka": [],
                    "riadky": [
                        {"text": {"sk": "Zásoby súčet"}},
                        {"text": {"sk": "Daň z príjmov"}},
                    ],
                }
            ]
        }
        result = self._service(
            **self._one_statement(
                {"idSablony": 556, "obsah": {"tabulky": [{"nazov": "Strana aktív", "data": ["16", "3"]}]}}
            ),
            templates={556: template},
        ).sync_company_detailed(self.company)

        self.assertEqual(result.outcome, FinancialsOutcome.NO_STATEMENTS)
        self.assertIn("1 readable but carrying none of a revenue", result.detail)
        self.assertFalse(CompanyFinancialResult.objects.exists())

    def test_a_majetok_table_is_read_as_a_balance_sheet(self):
        """The non-profit vocabulary: `Majetok` and `Záväzky` are the two sides.

        Šablóna 1163/1164 names them that way instead of `Strana aktív` /
        `Strana pasív`, so neither name reached `BALANCE_SHEET_KEYS` and the
        whole balance-sheet block -- which is gated on `is_balance_sheet` -- was
        skipped. Measured on `00681393`.
        """
        template = {
            "tabulky": [
                {
                    "nazov": "Majetok",
                    "pocetDatovychStlpcov": 2,
                    "hlavicka": [
                        {"text": {"sk": "Bežné účtovné obdobie"}, "riadok": 1, "stlpec": 1},
                        {
                            "text": {"sk": "Bezprostredne predchádzajúce účtovné obdobie"},
                            "riadok": 1,
                            "stlpec": 2,
                        },
                    ],
                    "riadky": [
                        {"text": {"sk": "Majetok spolu"}},
                        {"text": {"sk": "Dlhodobý hmotný majetok súčet"}},
                    ],
                }
            ]
        }
        result = self._service(
            **self._one_statement(
                {"idSablony": 557, "obsah": {"tabulky": [{"nazov": "Majetok", "data": ["500", "400", "300", "200"]}]}}
            ),
            templates={557: template},
        ).sync_company_detailed(self.company)

        self.assertEqual(result.outcome, FinancialsOutcome.RECORDED)
        row = CompanyFinancialResult.objects.get(company=self.company, year=2023)
        self.assertEqual(row.assets_total, Decimal("500"))
        self.assertEqual(row.assets_tangible, Decimal("300"))

    def test_a_total_with_a_parenthetical_note_is_still_a_total(self):
        """Šablóna 1164 writes its totals as `Majetok celkom (súčet r. 01 až r. 10)`.

        Measured on `00681393` and `00699349` 2026-09-12, after the table names
        were already recognised: read literally the remainder is
        `(sucet r. 01 az r. 10)`, which is none of the accepted forms, so both
        totals were dropped with their values sitting in the table. The
        parenthesis is a note about how the row was arrived at, not part of the
        label's identity.
        """
        template = {
            "tabulky": [
                {
                    "nazov": "Majetok",
                    "pocetDatovychStlpcov": 2,
                    "hlavicka": [
                        {"text": {"sk": "Bežné účtovné obdobie"}, "riadok": 1, "stlpec": 1},
                        {
                            "text": {"sk": "Bezprostredne predchádzajúce účtovné obdobie"},
                            "riadok": 1,
                            "stlpec": 2,
                        },
                    ],
                    "riadky": [
                        {"text": {"sk": "Peniaze"}},
                        {"text": {"sk": "Majetok celkom (súčet r. 01 až r. 10)"}},
                    ],
                }
            ]
        }
        result = self._service(
            **self._one_statement(
                {
                    "idSablony": 560,
                    "obsah": {
                        "tabulky": [
                            {
                                "nazov": "Majetok",
                                "data": ["", "", "25.88", "559.95"],
                            }
                        ]
                    },
                }
            ),
            templates={560: template},
        ).sync_company_detailed(self.company)

        self.assertEqual(result.outcome, FinancialsOutcome.RECORDED)
        row = CompanyFinancialResult.objects.get(company=self.company, year=2023)
        self.assertEqual(row.assets_total, Decimal("25.88"))

    def test_a_zavazky_table_reaches_its_total_through_the_celkom_form(self):
        """`Záväzky celkom` needs its own entry: `_is_summary_row` is anchored.

        The bare `zavazky` prefix matches the label but rejects the remainder
        (`celkom` is neither empty nor `súčet`/`spolu`), and `celkom` is the form
        this app uses everywhere else. It is why the dead `LIABILITIES_TOTAL_
        LABELS` has always listed it -- the constant was written for this call
        site and never wired to it.
        """
        template = {
            "tabulky": [
                {
                    "nazov": "Záväzky",
                    "pocetDatovychStlpcov": 1,
                    "hlavicka": [],
                    "riadky": [
                        {"text": {"sk": "Záväzky celkom"}},
                        {"text": {"sk": "Rezervy súčet"}},
                    ],
                }
            ]
        }
        result = self._service(
            **self._one_statement(
                {"idSablony": 558, "obsah": {"tabulky": [{"nazov": "Záväzky", "data": ["700", "50"]}]}}
            ),
            templates={558: template},
        ).sync_company_detailed(self.company)

        self.assertEqual(result.outcome, FinancialsOutcome.RECORDED)
        row = CompanyFinancialResult.objects.get(company=self.company, year=2023)
        self.assertEqual(row.liabilities_total, Decimal("700"))
        self.assertEqual(row.liabilities_reserves, Decimal("50"))


class SyncCompanyAndRecordTests(TemplateCacheTestCase):
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

    def test_an_answered_attempt_keeps_its_sentence(self):
        """The reason `last_detail` exists: `last_error` is blanked on success.

        The population this is for is the one that *succeeded* -- the registry
        answered, the statements were there, and none of them produced a row.
        `error` is written only on failure, so that sentence used to survive only
        in the task's log line, and `ANSWERED_RETRY_AFTER` pushes the next
        attempt out a year. Nothing could recover it.
        """
        result = self._run(
            detail={"idUctovnychZavierok": [77]},
            statements={
                77: {"obdobieDo": "2023-12-31", "idUctovnychVykazov": [88], "idSablony": 1}
            },
            reports={88: {"idSablony": 1, "obsah": {"tabulky": []}}},
            templates={1: {"tabulky": []}},
        )

        self.assertTrue(result.succeeded)
        status = self._status()
        self.assertEqual(status.last_error, "", "an answered attempt has no error")
        self.assertIn("1 statement(s) present, none recorded", status.last_detail)
        self.assertIn("1 with no tables in the report bodies", status.last_detail)

    def test_a_partly_readable_company_records_both_halves(self):
        """A partly-readable company says how much was read, not only what was not.

        One readable statement and one with no tables at all: the sentence has to
        carry the count *and* the reason, which is what makes it worth storing.
        (A company where nothing was skipped gets `detail=""` on purpose -- there
        is no silent branch to report.)
        """
        template = {
            "tabulky": [
                {
                    "nazov": "Výnosy",
                    "pocetDatovychStlpcov": 1,
                    "hlavicka": [],
                    "riadky": [
                        {"text": {"sk": "Výnosy z hospodárskej činnosti spolu súčet"}},
                    ],
                }
            ]
        }
        result = self._run(
            detail={"idUctovnychZavierok": [77, 78]},
            statements={
                77: {"obdobieDo": "2023-12-31", "idUctovnychVykazov": [88], "idSablony": 559},
                78: {"obdobieDo": "2022-12-31", "idUctovnychVykazov": [89], "idSablony": 559},
            },
            reports={
                88: {
                    "idSablony": 559,
                    "obsah": {"tabulky": [{"nazov": "Výnosy", "data": ["1200"]}]},
                },
                89: {"idSablony": 559, "obsah": {"tabulky": []}},
            },
            templates={559: template},
        )

        self.assertEqual(result.outcome, FinancialsOutcome.RECORDED)
        status = self._status()
        self.assertEqual(status.last_error, "")
        self.assertIn("1 of 2 statement(s) readable", status.last_detail)
        self.assertIn("1 with no tables in the report bodies", status.last_detail)

    def test_a_caller_with_nothing_to_say_leaves_the_column_alone(self):
        """`detail=None` means "nothing to say", not "the reason is empty".

        That distinction is the whole reason the parameter defaults to `None`
        rather than `""`: the four sources that pass nothing (ORSR, VZP,
        Sociálna poisťovňa, RUZ dates) would otherwise blank a sentence they
        never had an opinion about. Asserted on the *same* row, because two
        sources are two rows and comparing across them would pass regardless.
        """
        common = dict(company_id=self.company.id, source=CompanySyncStatus.SOURCE_FINANCIALS)

        update_company_status(**common, success=True, detail="1 statement(s) present")
        self.assertEqual(self._status().last_detail, "1 statement(s) present")

        update_company_status(**common, success=True)

        self.assertEqual(
            self._status().last_detail,
            "1 statement(s) present",
            "a caller that said nothing must not erase what one that spoke left",
        )


def _income_statement_header():
    """Šablóna 699 "Výkaz ziskov a strát": current period, then the previous one."""
    return [
        {"text": {"sk": "Označenie"}, "riadok": 1, "stlpec": 1},
        {"text": {"sk": "Text"}, "riadok": 1, "stlpec": 2},
        {"text": {"sk": "Číslo riadku"}, "riadok": 1, "stlpec": 3},
        {"text": {"sk": "Skutočnosť", "en": "Actual data"}, "riadok": 1, "stlpec": 4, "sirkaStlpca": 2},
        {"text": {"sk": "Bežné účtovné obdobie"}, "riadok": 2, "stlpec": 4},
        {"text": {"sk": "Bezprostredne predchádzajúce účtovné obdobie"}, "riadok": 2, "stlpec": 5},
    ]


def _assets_header():
    """Šablóna 699 "Strana aktív": four data columns, gross/correction/net, then netto previous."""
    return [
        {"text": {"sk": "Označenie"}, "riadok": 1, "stlpec": 1},
        {"text": {"sk": "STRANA AKTÍV"}, "riadok": 1, "stlpec": 2},
        {"text": {"sk": "Číslo riadku"}, "riadok": 1, "stlpec": 3},
        {"text": {"sk": "Bežné účtovné obdobie"}, "riadok": 1, "stlpec": 4, "sirkaStlpca": 3},
        {"text": {"sk": "Bezprostredne predchádzajúce účtovné obdobie"}, "riadok": 1, "stlpec": 7},
        {"text": {"sk": "Brutto - časť 1"}, "riadok": 2, "stlpec": 4},
        {"text": {"sk": "Korekcia - časť 2"}, "riadok": 2, "stlpec": 5},
        {"text": {"sk": "Netto 2"}, "riadok": 2, "stlpec": 6},
        {"text": {"sk": "Netto 3"}, "riadok": 2, "stlpec": 7},
    ]


def _cost_revenue_header():
    """Šablóny 696/727 "Náklady"/"Výnosy": the periods are named "20xx" and "20xx-1"."""
    return [
        {"text": {"sk": "Číslo účtu alebo skupiny"}, "riadok": 1, "stlpec": 1},
        {"text": {"sk": "Náklady"}, "riadok": 1, "stlpec": 2},
        {"text": {"sk": "Číslo riadku"}, "riadok": 1, "stlpec": 3},
        {"text": {"sk": "20xx"}, "riadok": 1, "stlpec": 4, "sirkaStlpca": 3},
        {"text": {"sk": "20xx-1"}, "riadok": 1, "stlpec": 7},
        {"text": {"sk": "Hlavná činnosť"}, "riadok": 2, "stlpec": 4},
        {"text": {"sk": "Podnikateľská činnosť"}, "riadok": 2, "stlpec": 5},
        {"text": {"sk": "Spolu"}, "riadok": 2, "stlpec": 6},
    ]


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
            "hlavicka": _income_statement_header(),
            "riadky": [
                {"text": {"sk": "Výnosy z hospodárskej činnosti spolu súčet (r. 02 až r. 07)"}},
                {"text": {"sk": "Náklady na hospodársku činnosť spolu súčet (r. 09 až r. 17)"}},
                {"text": {"sk": "Výsledok hospodárenia z hospodárskej činnosti (+/-)"}},
            ],
        }

        result = self.service._extract_with_template(table, template)

        self.assertEqual(result.get("revenue"), Decimal("150000"))
        self.assertEqual(result.get("costs"), Decimal("90000"))
        self.assertEqual(result.get("profit"), Decimal("60000"))

    def test_the_two_profit_rows_land_in_two_fields(self):
        # Both rows used to feed `profit`, chosen between by larger absolute
        # value. They are different accounting quantities and now have a field
        # each: `profit` is the operating result, `profit_after_tax` the bottom
        # line.
        table = {
            "data": [
                "150000", "140000",  # revenue row current/previous
                "90000", "85000",    # cost row current/previous
                "60000", "55000",    # operating result
                "48000", "44000",    # after-tax result
            ]
        }
        template = {
            "hlavicka": _income_statement_header(),
            "riadky": [
                {"text": {"sk": "Výnosy z hospodárskej činnosti spolu súčet (r. 02 až r. 07)"}},
                {"text": {"sk": "Náklady na hospodársku činnosť spolu súčet (r. 09 až r. 17)"}},
                {"text": {"sk": "Výsledok hospodárenia z hospodárskej činnosti (+/-)"}},
                {"text": {"sk": "Výsledok hospodárenia za účtovné obdobie po zdanení (+/-)"}},
            ],
        }

        result = self.service._extract_with_template(table, template)

        self.assertEqual(result.get("profit"), Decimal("60000"))
        self.assertEqual(result.get("profit_after_tax"), Decimal("48000"))

    def test_a_loss_does_not_promote_the_after_tax_row_into_profit(self):
        # The exact shape of the old defect. A loss *grows* once tax is
        # deducted, so `_pick_better` -- which kept the larger absolute value --
        # chose the after-tax row precisely on the loss-makers, while the field
        # was displayed as "Zisk po zdanení". All 23 rows measured live on
        # 2026-09-12 that held the after-tax figure were loss-making, which is
        # this rule and nothing else.
        table = {
            "data": [
                "-1000", "-900",   # operating result, a loss
                "-1150", "-1000",  # after-tax result, a bigger loss
            ]
        }
        template = {
            "hlavicka": _income_statement_header(),
            "riadky": [
                {"text": {"sk": "Výsledok hospodárenia z hospodárskej činnosti (+/-)"}},
                {"text": {"sk": "Výsledok hospodárenia za účtovné obdobie po zdanení (+/-)"}},
            ],
        }

        result = self.service._extract_with_template(table, template)

        self.assertEqual(result.get("profit"), Decimal("-1000"))
        self.assertEqual(result.get("profit_after_tax"), Decimal("-1150"))

    def test_an_after_tax_row_alone_does_not_fill_profit(self):
        # A statement that the parser could only read down to the bottom line
        # has no operating result, and `profit` must stay empty rather than
        # take the after-tax figure -- a dash is the honest answer.
        table = {"data": ["48000", "44000"]}
        template = {
            "hlavicka": _income_statement_header(),
            "riadky": [
                {"text": {"sk": "Výsledok hospodárenia za účtovné obdobie po zdanení (+/-)"}},
            ],
        }

        result = self.service._extract_with_template(table, template)

        self.assertIsNone(result.get("profit"))
        self.assertEqual(result.get("profit_after_tax"), Decimal("48000"))

    def test_the_computed_fallback_fills_profit_only(self):
        # `revenue - costs` is the operating result -- that identity is what
        # makes the fallback correct -- and it is not a tax-adjusted figure, so
        # it must never be written to `profit_after_tax`.
        table = {"data": ["200000", "190000", "150000", "140000"]}
        template = {
            "hlavicka": _income_statement_header(),
            "riadky": [
                {"text": {"sk": "Výnosy z hospodárskej činnosti spolu súčet (r. 02 až r. 07)"}},
                {"text": {"sk": "Náklady na hospodársku činnosť spolu súčet (r. 09 až r. 17)"}},
            ],
        }

        result = self.service._extract_with_template(table, template)

        self.assertEqual(result.get("profit"), Decimal("50000"))
        self.assertIsNone(result.get("profit_after_tax"))

    def test_extract_with_template_calculates_profit_when_missing(self):
        table = {
            "data": [
                "200000", "190000",
                "150000", "140000",
            ]
        }
        template = {
            "hlavicka": _income_statement_header(),
            "riadky": [
                {"text": {"sk": "Výnosy z hospodárskej činnosti spolu súčet (r. 02 až r. 07)"}},
                {"text": {"sk": "Náklady na hospodársku činnosť spolu súčet (r. 09 až r. 17)"}},
            ],
        }

        result = self.service._extract_with_template(table, template)

        self.assertEqual(result.get("revenue"), Decimal("200000"))
        self.assertEqual(result.get("costs"), Decimal("150000"))
        self.assertEqual(result.get("profit"), Decimal("50000"))

    def test_the_asset_side_reads_the_netto_column_of_each_row(self):
        # The defect this replaces: `len(data) >= len(rows) * 2` also held for
        # the four-column asset side, so the code read it as if a row were two
        # values wide and took template row i from sheet row i // 2 and column
        # 2 * (i % 2). `assets_total` came out as the GROSS current-period
        # figure of the row above, and every line below it was another row's
        # value -- with nothing to contradict it, because the total row is the
        # first row of this table and its label matched.
        table = {
            "data": [
                "1000", "200", "800", "700",   # SPOLU MAJETOK
                "400", "100", "300", "250",    # Dlhodobý hmotný majetok súčet
                "500", "50", "450", "400",     # Zásoby súčet
            ]
        }
        template = {
            "nazov": {"sk": "Strana aktív"},
            "pocetDatovychStlpcov": 4,
            "hlavicka": _assets_header(),
            "riadky": [
                {"text": {"sk": "SPOLU MAJETOK r. 02 + r. 33 + r. 74"}},
                {"text": {"sk": "Dlhodobý hmotný majetok súčet (r. 12 až r. 20)"}},
                {"text": {"sk": "Zásoby súčet (r. 34 až r. 38)"}},
            ],
        }

        result = self.service._extract_with_template(table, template)

        self.assertEqual(result.get("assets_total"), Decimal("800"))
        self.assertEqual(result.get("assets_tangible"), Decimal("300"))
        self.assertEqual(result.get("assets_inventory"), Decimal("450"))

    def test_a_two_column_statement_is_read_exactly_as_before(self):
        # The fix must not touch the tables that were already right. "Strana
        # pasív" has two data columns and the first is the current period, under
        # both the old width test and the new one -- so the parsed values have
        # to be identical, or this is trading one silent error for another.
        table = {
            "data": [
                "2000", "1800",   # Vlastné imanie súčet
                "1200", "1100",   # Cudzie zdroje
            ]
        }
        template = {
            "nazov": {"sk": "Strana pasív"},
            "pocetDatovychStlpcov": 2,
            "hlavicka": [
                {"text": {"sk": "Označenie"}, "riadok": 1, "stlpec": 1},
                {"text": {"sk": "Bežné účtovné obdobie"}, "riadok": 1, "stlpec": 4},
                {"text": {"sk": "Bezprostredne predchádzajúce účtovné obdobie"}, "riadok": 1, "stlpec": 5},
                {"text": {"sk": "4"}, "riadok": 2, "stlpec": 4},
                {"text": {"sk": "5"}, "riadok": 2, "stlpec": 5},
            ],
            "riadky": [
                {"text": {"sk": "Vlastné imanie r. 80 + r. 81 + r. 82 + r. 83 + r. 84"}},
                {"text": {"sk": "Cudzie zdroje r. 101 + r. 102 + r. 103"}},
            ],
        }

        result = self.service._extract_with_template(table, template)

        self.assertEqual(result.get("equity"), Decimal("2000"))
        self.assertEqual(result.get("liabilities_total"), Decimal("1200"))

    def test_the_placeholder_period_header_is_read_as_a_period_header(self):
        # Šablóny 690, 696 and 727 do not spell the periods out; they use the
        # form's own "20xx" against "20xx-1". Measured live on 2026-09-12, and
        # without this the whole vocabulary of three templates would be refused.
        table = {
            "data": [
                "10", "20", "30", "25",   # the total row, current period sums to 30
            ]
        }
        template = {
            "nazov": {"sk": "Náklady"},
            "pocetDatovychStlpcov": 4,
            "hlavicka": _cost_revenue_header(),
            "riadky": [{"text": {"sk": "Účtové skupiny 50 - 58 súčet"}}],
        }

        self.assertEqual(self.service._extract_table_total(table, template), Decimal("30"))

    def test_extract_table_total_reads_this_period_not_the_previous_one(self):
        # "Náklady" (šablóna 696) is four columns wide -- main activity, business
        # activity, their sum, then the previous period -- and it ends in empty
        # "Kontrolné číslo súčet" rows. `numbers[-1]` walked the flattened table
        # and returned the last value it could find, which is the last filled
        # row's FOURTH column: last year's total, stored as this year's costs,
        # and for these templates the only source of `costs` there is.
        table = {
            "data": [
                "100", "200", "300", "280",   # a line, current period sums to 300
                "150", "250", "400", "390",   # the total row
                "", "", "", "",               # Kontrolné číslo súčet (empty)
            ]
        }
        template = {
            "nazov": {"sk": "Náklady"},
            "pocetDatovychStlpcov": 4,
            "hlavicka": _cost_revenue_header(),
            "riadky": [
                {"text": {"sk": "Spotrebované nákupy (r. 002 až r. 005)"}},
                {"text": {"sk": "Účtové skupiny 50 - 58 súčet (r. 001 + r. 006)"}},
                {"text": {"sk": "Kontrolné číslo súčet (r. 001 až r. 064)"}},
            ],
        }

        self.assertEqual(self.service._extract_table_total(table, template), Decimal("400"))

    def test_a_table_with_no_template_keeps_the_reading_it_had(self):
        # Deliberately unchanged, and the reason is a population this fix did
        # NOT measure: every table in the 38-table sample had its template, so
        # nothing here says how wide a template-less table is. Re-reading it as
        # "unreadable" would make a statement whose every table is unreadable
        # contribute no field at all -- which counts as zero rows, so a template
        # fetch that failed would arrive as "this company has no statements".
        # That is the conflation `UNREACHABLE` was introduced to undo, and it is
        # not moved as a side effect of a stride fix.
        self.assertEqual(
            self.service._extract_table_total({"data": ["1000"]}), Decimal("1000")
        )
        self.assertEqual(self.service._extract_table_total({"data": []}), None)

    def test_a_table_whose_period_cannot_be_located_contributes_nothing(self):
        # Four columns and no header saying which is the current period. Every
        # column would be a guess, and the guess is what produced the wrong
        # numbers in the first place -- so the table contributes nothing, and
        # the caller stores no field rather than an invented one.
        table = {"data": ["1000", "200", "800", "700"]}
        template = {
            "nazov": {"sk": "Strana aktív"},
            "pocetDatovychStlpcov": 4,
            "riadky": [{"text": {"sk": "SPOLU MAJETOK r. 02 + r. 33 + r. 74"}}],
        }

        self.assertEqual(self.service._extract_with_template(table, template), {})

    def test_values_that_do_not_fill_whole_rows_are_refused(self):
        # The shape has to be arithmetic before it is trusted: 7 values over 4
        # rows is neither four columns nor one, so no column index means
        # anything and the table is left alone.
        table = {"data": ["1", "2", "3", "4", "5", "6", "7"]}
        template = {
            "nazov": {"sk": "Strana aktív"},
            "hlavicka": _assets_header(),
            "riadky": [{"text": {"sk": "SPOLU MAJETOK"}} for _ in range(4)],
        }

        self.assertEqual(self.service._extract_with_template(table, template), {})


class _BalanceTableMixin:
    """`_assets_table` for the two classes that build a filed table by hand.

    Lifted out of `CurrentAssetsTests` when the tests below needed it too: the
    four-column shape (`gross`, `correction`, `netto`, `netto prior`) is the
    same whichever question is being asked of it, and a second copy of it is a
    second thing to keep in step with `_current_period_column`.
    """

    def _assets_table(self, labels, values, name="Strana aktív"):
        """One four-column asset table: gross, correction, netto, netto prior."""
        rows = [{"text": {"sk": label}} for label in labels]
        data = []
        for value in values:
            data.extend([value, "", value, ""])
        return (
            {"data": data},
            {
                "nazov": {"sk": name},
                "pocetDatovychStlpcov": 4,
                "hlavicka": _assets_header(),
                "riadky": rows,
            },
        )


class CurrentAssetsTests(_BalanceTableMixin, SimpleTestCase):
    """The five lines of `Obežný majetok`, and the total the statement reports.

    ŠÚ SR template 699 (MF/18009/2014-74, platné od 2014-01-01) reformulated
    r.71 as "Finančné účty r. 72 + r. 73". The parser's key was
    `financne ucty sucet`, which is not a substring of that, so the cash line
    stopped being read at the template change and nothing said so. Measured on
    the live corpus 2026-09-12: `assets_financial_accounts` holds a value for
    547 of the 2 576 filings of 2013 and for **0 of every year from 2015 on**.

    The tests below pin the labels of *every* template family, because a fix
    that matches only the new one trades a 2014+ hole for a pre-2014 one -- and
    because the first attempt at this fix replaced the key with a *bare*
    `financne ucty`, which šablóna 687's r.23 "Ostatné finančné účty" contains.
    That put one line's figure in another line's field, under that field's
    label: the same defect, one template further along.

    The two rows 687 still left unread were closed the same way, and the third
    attempt shows the pattern is not about 687 at all: for both rows the
    *natural* short key names a different line somewhere else in the corpus --
    `zasoby (` is contained in nine templates' advances on inventory, and
    `dlhodobe pohladavky (` in templates 29 and 1141's `Ostatné dlhodobé
    pohľadávky`. A key here is not a name; it is a claim that the phrase occurs
    once, and the corpus is what checks it.
    """

    def setUp(self):
        self.service = RuzFinancialsSyncService()

    def test_the_obezny_majetok_total_is_read_and_neobezny_is_not(self):
        # `Obežný majetok` is a substring of `Neobežný majetok`, and the
        # non-current row comes FIRST in the template -- so the plain `in` test
        # every other key uses would have read 2 004 309 into the current-assets
        # total and stopped there. The largest single misstatement available in
        # this table, and it is one character wide.
        table, template = self._assets_table(
            [
                "Neobežný majetok r. 03 + r. 11 + r. 21",
                "Obežný majetok r. 34 + r. 41 + r. 53 + r. 66 + r. 71",
            ],
            ["2004309", "3194728"],
        )

        result = self.service._extract_with_template(table, template)

        self.assertEqual(result.get("assets_current"), Decimal("3194728"))

    def test_the_2013_template_total_is_read_too(self):
        # Šablóna 21 writes the same total over four terms, not five: the
        # pre-2014 statement has no separate short-term-financial-assets row.
        # The prefix match has to be indifferent to which.
        table, template = self._assets_table(
            [
                "Neobežný majetok r. 003 + r. 011 + r. 021",
                "Obežný majetok r. 031 + r. 038 + r. 046 + r. 055",
            ],
            ["2004309", "3194728"],
        )

        result = self.service._extract_with_template(table, template)

        self.assertEqual(result.get("assets_current"), Decimal("3194728"))

    def test_financne_ucty_survives_every_spelling_of_the_row(self):
        # Every spelling the corpus uses, in one test, because the whole defect
        # was that only some of them matched: "súčet" before 2014, a bare
        # formula from 2014 on, and the `r. 052 až r. 056` form in the
        # non-business statement (templates 17, 385, 1180).
        for label, value in (
            ("Finančné účty súčet (r. 056 až r. 060)", "158700"),
            ("Finančné účty r. 72 + r. 73", "176879"),
            ("Finančné účty r. 052 až r. 056", "91234"),
        ):
            with self.subTest(label=label):
                table, template = self._assets_table([label], [value])

                result = self.service._extract_with_template(table, template)

                self.assertEqual(result.get("assets_financial_accounts"), Decimal(value))

    def test_the_short_term_financial_assets_row_lands_in_its_own_field(self):
        # r.66, the fifth term. It used to be listed as
        # `"krabezny financny majetok"` -- a typo matching nothing -- pointing at
        # `assets_financial_accounts`, which r.71 already owns. Two lines, one
        # destination: one of the five terms of the total was never read.
        table, template = self._assets_table(
            [
                "Krátkodobý finančný majetok súčet (r. 67 až r. 70)",
                "Finančné účty r. 72 + r. 73",
            ],
            ["30000", "176879"],
        )

        result = self.service._extract_with_template(table, template)

        self.assertEqual(result.get("assets_financial_short"), Decimal("30000"))
        self.assertEqual(result.get("assets_financial_accounts"), Decimal("176879"))

    def test_an_itemised_row_without_sucet_is_not_the_total(self):
        # r.67-r.70 are the components of r.66, and their labels all begin with
        # the same words. Only the `súčet` row is the total; the others are
        # lines inside it, and reading one as the total would understate it.
        table, template = self._assets_table(
            [
                "Krátkodobý finančný majetok v prepojených účtovných jednotkách "
                "(251A, 253A, 256A, 257A, 25XA) - /291A, 29XA/",
                "Obstarávaný krátkodobý finančný majetok (259, 314A) - /291A/",
            ],
            ["30000", "5000"],
        )

        result = self.service._extract_with_template(table, template)

        self.assertIsNone(result.get("assets_financial_short"))

    def test_a_note_row_does_not_shadow_the_cash_line(self):
        # "Náklady na krátkodobý finančný majetok (566)" is a profit-and-loss
        # row that shares the phrase. The key is the `súčet` row, so it must
        # not reach this one.
        table, template = self._assets_table(
            ["Náklady na krátkodobý finančný majetok (566)"], ["15933"]
        )

        result = self.service._extract_with_template(table, template)

        self.assertIsNone(result.get("assets_financial_accounts"))
        self.assertIsNone(result.get("assets_financial_short"))

    def test_an_other_row_is_not_the_row_whose_name_it_contains(self):
        # Šablóna 687 names r.23 "Ostatné finančné účty (251, 252, 253, 256,
        # 257, 25X, 259, 314A)". A *bare* `financne ucty` key is a substring of
        # that, so it read the short-term-financial-assets line into r.71's
        # field -- a figure printed under a label that claims it is the cash
        # total. "Ostatné" is not decoration: it is what makes this a different
        # line, and 687 keeps them apart on purpose, r.21 "Finančný majetok"
        # being r.22 "Peniaze a účty v bankách" + r.23.
        table, template = self._assets_table(
            ["Ostatné finančné účty (251, 252, 253, 256, 257, 25X, 259, 314A) - /291, 29X/"],
            ["480000"],
        )

        result = self.service._extract_with_template(table, template)

        self.assertEqual(result.get("assets_financial_short"), Decimal("480000"))
        self.assertIsNone(result.get("assets_financial_accounts"))

    def test_the_687_cash_row_is_read(self):
        # The same merged line 699 splits in two: "Peniaze a účty v bankách"
        # carries r.72's accounts (211, 213, 21X) and r.73's (221A, 22XA,
        # +/- 261) in one row, so it is r.71's figure under one label.
        table, template = self._assets_table(
            ["Peniaze a účty v bankách (211, 213, 21X, 221A, 22XA, +/- 261)"],
            ["52482"],
        )

        result = self.service._extract_with_template(table, template)

        self.assertEqual(result.get("assets_financial_accounts"), Decimal("52482"))

    def test_the_687_current_assets_total_is_read(self):
        # Four terms, and the first of them is the row 687 leaves without a
        # `súčet`: "Zásoby (112, 119, 11X, …)". The total is read from the
        # statement's own row, so the unread component cannot shrink it.
        table, template = self._assets_table(
            [
                "Neobežný majetok r. 03 + r. 04 + r. 09",
                "Obežný majetok r. 15 + r. 16 + r. 17 + r. 21",
                "Zásoby (112, 119, 11X, 121, 122, 123, 124, 12X, 132, 133, 13X, 139, 314A)",
                "Dlhodobé pohľadávky (311A, 312A, 313A, 314A, 315A, 316A, 31XA)",
                "Krátkodobé pohľadávky súčet (r. 18 až r. 20)",
                "Finančný majetok r. 22 + r. 23",
                "Peniaze a účty v bankách (211, 213, 21X, 221A, 22XA, +/- 261)",
                "Ostatné finančné účty (251, 252, 253, 256, 257, 25X, 259, 314A) - /291, 29X/",
            ],
            [
                "900000",
                "1310000",
                "200000",
                "30000",
                "230000",
                "850000",
                "52482",
                "480000",
            ],
        )

        result = self.service._extract_with_template(table, template)

        self.assertEqual(result.get("assets_current"), Decimal("1310000"))
        self.assertEqual(result.get("assets_financial_accounts"), Decimal("52482"))
        self.assertEqual(result.get("assets_financial_short"), Decimal("480000"))
        self.assertEqual(result.get("assets_receivables_short"), Decimal("230000"))
        # The two rows 687 writes without a `súčet`, now read. Their keys carry
        # the start of the row's account list -- see the test below for the
        # shorter spellings that would have matched a different line.
        self.assertEqual(result.get("assets_inventory"), Decimal("200000"))
        self.assertEqual(result.get("assets_receivables_long"), Decimal("30000"))

    def test_a_line_item_that_mentions_payables_does_not_end_the_asset_side(self):
        # `Pohľadávky a záväzky z pevných termínových operácií (373AÚ)` is a
        # receivable, on the asset side, that happens to name payables. The
        # section flag used to flip on any label *containing* `zavazky`, so in
        # templates 2, 9, 11, 522, 684 and 690 -- the ROPO / municipal and
        # consolidated statements, which all carry this row -- every asset line
        # below it was matched against the liabilities vocabulary and the last
        # two were lost. One of them is the cash total.
        table, template = self._assets_table(
            [
                "Pohľadávky a záväzky z pevných termínových operácií (373AÚ) - (391AÚ)",
                "Krátkodobé pohľadávky súčet (r. 061 až 084)",
                "Finančné účty súčet (r. 086 až 097)",
            ],
            ["", "8863715.58", "2439764.97"],
        )

        result = self.service._extract_with_template(table, template)

        self.assertEqual(result.get("assets_receivables_short"), Decimal("8863715.58"))
        self.assertEqual(result.get("assets_financial_accounts"), Decimal("2439764.97"))

    def test_a_combined_table_still_switches_at_a_liabilities_header(self):
        # The other direction, and the reason the per-row check was anchored
        # rather than deleted: a table named only `Súvaha` identifies no side,
        # so the liabilities rows in it are reachable only through this switch.
        # Every one of the 245 templates names its sides, which is why the check
        # has never been load-bearing -- but a future combined statement is the
        # case it exists for.
        table, template = self._assets_table(
            [
                "Zásoby súčet (r. 05 až 07)",
                "Vlastné imanie a záväzky spolu",
                "Základné imanie súčet (r. 069 až 072)",
            ],
            ["100000", "", "500000"],
            name="Súvaha",
        )

        result = self.service._extract_with_template(table, template)

        self.assertEqual(result.get("assets_inventory"), Decimal("100000"))
        self.assertEqual(result.get("equity_basic"), Decimal("500000"))

    def test_an_advance_on_inventory_is_not_inventory(self):
        # Why `zasoby (112` and not `zasoby (`: nine templates write a
        # "Poskytnuté (prevádzkové) preddavky na zásoby (314A)" row. In 699 that
        # is r.41, the *second* term of `Obežný majetok` -- a sibling of r.34
        # Zásoby, not part of it. Two directions, both wrong: alone, the
        # advance would be read as the inventory line (the first case below);
        # beside a filed Zásoby row it would replace it whenever it is larger,
        # because that is what `_pick_better` keeps (the second).
        alone, template = self._assets_table(
            ["Poskytnuté preddavky na zásoby (314A) - /391A/"],
            ["250000"],
        )

        self.assertIsNone(
            self.service._extract_with_template(alone, template).get("assets_inventory")
        )

        # 250 000 against a filed 100 000, deliberately inverted from anything a
        # real filing would carry: `_pick_better` keeps the larger, so only a
        # decoy that is larger can tell the two keys apart at all.
        both, template = self._assets_table(
            [
                "Zásoby súčet (r. 35 až r. 40)",
                "Poskytnuté preddavky na zásoby (314A) - /391A/",
            ],
            ["100000", "250000"],
        )

        self.assertEqual(
            self.service._extract_with_template(both, template).get("assets_inventory"),
            Decimal("100000"),
        )

    def test_an_asset_side_accrual_is_not_a_liability_accrual(self):
        # The one row the section flag routes to two *different fields*, which is
        # why this defect was not merely a missing value. In templates 2, 9, 11,
        # 522, 684 and 690 the `Pohľadávky a záväzky z pevných termínových
        # operácií` row flipped the flag mid-asset-table, and every row after it
        # -- including `Časové rozlíšenie súčet`, which is the asset side's own
        # accrual -- was then read as a liability. So the filing's asset accrual
        # was stored under `liabilities_accruals` and `assets_accruals` was left
        # empty: a wrong number and a missing one, from the same line.
        table, template = self._assets_table(
            [
                "Pohľadávky a záväzky z pevných termínových operácií (373AÚ) - (391AÚ)",
                "Časové rozlíšenie súčet (r. 111 až r. 113)",
            ],
            ["", "123456.78"],
        )

        result = self.service._extract_with_template(table, template)

        self.assertEqual(result.get("assets_accruals"), Decimal("123456.78"))
        self.assertIsNone(result.get("liabilities_accruals"))

    def test_a_table_named_pasiva_is_the_liabilities_side(self):
        # Ten templates (29, 662, 663, 711, 723, 738, 941, 1121, 1141, 5181)
        # name the table exactly `Pasíva`, and the name-side test looked for
        # `strana pasiv` -- so it called all ten asset tables. The per-row
        # trigger covered the mistake by accident in eight of them, on row 0;
        # in 29 and 1141 the first row beginning with one of its markers is row
        # 24, so everything above it was read against the asset vocabulary and
        # `Dlhodobé záväzky súčet` -- a row the shipped rule *did* read -- was
        # dropped.
        #
        # The row order below is what makes this a test rather than a
        # restatement: the payable total comes before any row that begins with a
        # marker, so only the table's own name can put it on the right side.
        table, template = self._assets_table(
            [
                "A. Vlastné zdroje krytia majetku súčet (r. 057 + r. 062 + r. 072)",
                "Dlhodobé záväzky súčet (r.079 až r.084)",
                "Záväzky z nájmu (954AÚ)",
            ],
            ["", "418375.00", "12000"],
            name="Pasíva",
        )

        result = self.service._extract_with_template(table, template)

        self.assertEqual(result.get("liabilities_long"), Decimal("418375.00"))

    def test_a_sub_line_of_long_term_receivables_is_not_the_total(self):
        # The same trap on the other row. Templates 29 and 1141 write
        # "Ostatné dlhodobé pohľadávky (…)" as a component; their total is
        # "Dlhodobé pohľadávky súčet (r. 031 až r. 034)". `dlhodobe pohladavky
        # (` matches both, which is why the key carries `(311a` -- 687's
        # account list, the only spelling of it in the corpus.
        alone, template = self._assets_table(
            ["Ostatné dlhodobé pohľadávky (373 AU + 375AU + 378AU + 396AU) - (391AU)"],
            ["120000"],
        )

        self.assertIsNone(
            self.service._extract_with_template(alone, template).get(
                "assets_receivables_long"
            )
        )

        both, template = self._assets_table(
            [
                "Dlhodobé pohľadávky súčet (r. 031 až r. 034)",
                "Ostatné dlhodobé pohľadávky (373 AU + 375AU + 378AU + 396AU) - (391AU)",
            ],
            ["70000", "120000"],
        )

        self.assertEqual(
            self.service._extract_with_template(both, template).get(
                "assets_receivables_long"
            ),
            Decimal("70000"),
        )


class BalanceSheetGateTests(_BalanceTableMixin, SimpleTestCase):
    """Which tables the balance-sheet block opens at all.

    `is_balance_sheet` gates the whole block, so a table whose name it does not
    recognise contributes *nothing*: not a total, not a line, not a refusal. The
    tuple held `strana aktiv` / `strana pasiv` and two more spellings, and
    sixteen templates name their sides `Aktíva` / `Pasíva` -- ten of them
    letter-spaced as `A K T Í V A`, which is a typographic layout rather than a
    different word. Measured over the corpus 2026-09-13: 32 tables, 1 048 filed
    rows, never opened. Every insurer in the app is in that set.
    """

    def setUp(self):
        self.service = RuzFinancialsSyncService()

    def test_a_table_named_aktiva_is_opened_and_its_total_read(self):
        # `Aktíva spolu` is the last row of the insurers' asset table, and the
        # only row label in the whole corpus that begins with those words. The
        # gate and the total are two separate misses on one table: opening it
        # without the label reads the rows and still reports no assets total,
        # which is the figure the identity control needs.
        table, template = self._assets_table(
            [
                "Pohľadávky z poistenia a zaistenia",
                "Pokladničné hodnoty a peňažné ekvivalenty",
                "Aktíva spolu",
            ],
            ["1200", "3400", "4600"],
            name="AKTÍVA",
        )

        result = self.service._extract_with_template(table, template)

        self.assertEqual(result.get("assets_total"), Decimal("4600"))

    def test_a_letter_spaced_side_name_is_the_same_side(self):
        # Six templates write `P A S Í V A`. A substring test reads that as
        # neither side; collapsing spaces on both sides reads it as the side it
        # is. The row order below is the point of the test. `Dlhodobé záväzky
        # súčet` sits *above* every section marker, so nothing but the table's
        # own name can say which side it is on -- open the table and leave the
        # side undecided and that row is looked up in the asset vocabulary,
        # which has no key for it, and dropped. Asserting only `equity` here
        # would not catch that: `Vlastné imanie spolu` is itself a marker and
        # would set the flag on its own.
        table, template = self._assets_table(
            [
                "Dlhodobé záväzky súčet (r.079 až r.084)",
                "Vlastné imanie spolu",
                "Pasíva spolu",
            ],
            ["418375.00", "8000", "8000"],
            name="P A S Í V A",
        )

        result = self.service._extract_with_template(table, template)

        self.assertEqual(result.get("liabilities_long"), Decimal("418375.00"))
        self.assertEqual(result.get("equity"), Decimal("8000"))
        # And `Pasíva spolu` must *not* become the liabilities total. It is the
        # whole pasíva side -- equity plus liabilities -- so reading it here
        # would file the grand total as a liability and let the identity control
        # pass by comparing a number with itself. Measured on `30807484`
        # (Sociálna poisťovňa, šablóna 29, 2015): the row carries 1 104 603
        # 246.61, which is 1 062 050 495.44 equity plus 42 552 751.17
        # liabilities, not either of them.
        self.assertIsNone(result.get("liabilities_total"))

    def test_a_total_prefixed_by_its_section_letter_is_still_the_total(self):
        # The insurance and social-insurance forms number their sides `a.` and
        # `b.`, and both figures the identity control needs sit behind one. The
        # letter is the form's numbering, not part of the name.
        table, template = self._assets_table(
            [
                "a. Vlastné zdroje krytia majetku súčet (r. 057 + r. 062 + r. 072)",
                "b. Cudzie zdroje súčet (r.077 + r.078 + r.085 + r.099 + r.103)",
                "Pasíva spolu súčet (r. 056 + r. 076)",
            ],
            ["1062050495.44", "42552751.17", "1104603246.61"],
            name="Pasíva",
        )

        result = self.service._extract_with_template(table, template)

        self.assertEqual(result.get("equity"), Decimal("1062050495.44"))
        self.assertEqual(result.get("liabilities_total"), Decimal("42552751.17"))
        # The arithmetic the identity control checks, from the filing itself.
        self.assertEqual(
            result["equity"] + result["liabilities_total"],
            Decimal("1104603246.61"),
        )

    def test_the_whole_pasiva_side_is_not_a_liability(self):
        # `Vlastné zdroje a cudzie zdroje spolu` names both sides at once. Every
        # total vocabulary has to leave it alone: a figure that is already the
        # sum of the other two cannot also be a term in that sum.
        table, template = self._assets_table(
            [
                "Vlastné zdroje a cudzie zdroje spolu r.061+ r.074 + r.101",
                "Pasíva spolu",
            ],
            ["5000000", "5000000"],
            name="Strana pasív",
        )

        result = self.service._extract_with_template(table, template)

        self.assertIsNone(result.get("liabilities_total"))
        self.assertIsNone(result.get("assets_total"))
        self.assertIsNone(result.get("equity"))

    def test_the_social_insurance_asset_side_is_read(self):
        # Šablóny 29 and 1141 -- the social-insurance and health-insurance
        # statements -- use the ordinary company vocabulary, so opening their
        # table recovers the whole asset side rather than a total. Eight lines
        # here, and before the gate fix every one of them was unreachable.
        table, template = self._assets_table(
            [
                "Dlhodobý nehmotný majetok súčet (r.003 až r.007)",
                "Dlhodobý hmotný majetok súčet (r.009 až r.017)",
                "Zásoby súčet (r.027 až r. 029)",
                "Dlhodobé pohľadávky súčet (r.031 až r.034)",
                "Krátkodobé pohľadávky súčet (r.036 až r.044)",
                "Majetok spolu súčet (r. 001 + r. 025)",
            ],
            ["500", "7000", "300", "1200", "900", "9900"],
            name="Aktíva",
        )

        result = self.service._extract_with_template(table, template)

        self.assertEqual(result.get("assets_intangible"), Decimal("500"))
        self.assertEqual(result.get("assets_tangible"), Decimal("7000"))
        self.assertEqual(result.get("assets_inventory"), Decimal("300"))
        self.assertEqual(result.get("assets_receivables_long"), Decimal("1200"))
        self.assertEqual(result.get("assets_receivables_short"), Decimal("900"))
        self.assertEqual(result.get("assets_total"), Decimal("9900"))

    def test_the_insurers_own_asset_vocabulary_stays_unread(self):
        # The deliberate half. Eight commercial-insurance templates keep no key
        # for `Majetkové podiely`, `Finančné nástroje v reálnej hodnote`,
        # `Podiel zaisteného na technických rezervách` and the rest -- a
        # different chart of accounts, and one this app has no filing-verified
        # mapping for. They must contribute nothing rather than something
        # plausible: a wrong number under a real label is the failure this whole
        # file is arranged against.
        table, template = self._assets_table(
            [
                "Majetkové podiely",
                "Finančné nástroje v reálnej hodnote proti zisku a strate",
                "Podiel zaistiteľov na technických rezervách",
                "Hmotný hnuteľný majetok",
                "Aktíva spolu",
            ],
            ["900000", "400000", "250000", "120000", "1670000"],
            name="AKTÍVA",
        )

        result = self.service._extract_with_template(table, template)

        # The total is asserted first so this cannot pass by the table never
        # being opened -- a shut gate also reads nothing, and it would be the
        # wrong reason to be green here.
        self.assertEqual(result.get("assets_total"), Decimal("1670000"))
        self.assertEqual(
            {k: v for k, v in result.items() if k.startswith("assets_") and v is not None},
            {"assets_total": Decimal("1670000")},
        )


class _CountingRuzApi(_ScriptedRuzApi):
    """`_ScriptedRuzApi` that remembers which templates it was asked for.

    The template cache is a module-level dict, so "did this read hit the cache"
    is only visible from outside as "did the api get asked". Counting is
    therefore not a proxy for the behaviour under test -- it *is* the
    behaviour, and it needs no private name imported to observe it.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.template_ids = []

    def get_report_template_details(self, template_id):
        self.template_ids.append(template_id)
        return super().get_report_template_details(template_id)


class TemplateCacheTests(TemplateCacheTestCase):
    """A template is remembered only once RUZ has answered with one."""

    def setUp(self):
        self.company = Company.objects.create(
            ruz_id=4821,
            ico="48210000",
            nazov_UJ="Šablóna s.r.o.",
        )

    def _company_with_two_reports_of_one_form(self, api):
        """One statement carrying two reports that share a template id."""
        api.detail = {"idUctovnychZavierok": [77]}
        api.statements = {
            77: {"obdobieDo": "2023-12-31", "idUctovnychVykazov": [88, 89]}
        }
        api.reports = {
            88: {"idSablony": 7, "obsah": {"tabulky": [{"nazov": "Vynosy", "data": ["1000"]}]}},
            89: {"idSablony": 7, "obsah": {"tabulky": [{"nazov": "Vynosy", "data": ["2000"]}]}},
        }
        return api

    def test_a_template_that_answers_nothing_is_asked_again(self):
        # The failed fetch must not become the remembered answer. `templates={}`
        # makes the getter answer None -- one transport blip, or a form the
        # registry has not got. Caching that pins "no tables" for this form for
        # the life of the worker process: every later company using it reads
        # nothing, and the run reports a clean success, because a statement
        # whose tables yield nothing is a legitimate outcome. The api is asked
        # once per report, and asked again next time.
        api = self._company_with_two_reports_of_one_form(
            _CountingRuzApi(detail=None, templates={})
        )

        RuzFinancialsSyncService(api=api).sync_company_detailed(self.company)

        self.assertEqual(api.template_ids, [7, 7])

    def test_a_template_with_no_tables_is_asked_again(self):
        # The shape every scripted test in this file uses for its templates.
        # An empty `tabulky` is also what a form with no rows looks like, so
        # there is nothing here worth remembering either.
        api = self._company_with_two_reports_of_one_form(
            _CountingRuzApi(detail=None, templates={7: {"tabulky": []}})
        )

        RuzFinancialsSyncService(api=api).sync_company_detailed(self.company)

        self.assertEqual(api.template_ids, [7, 7])

    def test_two_reports_of_one_form_read_the_template_once(self):
        # The other half of the contract, and the reason the cache exists: a
        # company filing up to thirteen reports of the same form must not mean
        # thirteen requests to a registry that times out. A fix that stopped
        # caching anything would pass the two tests above and fail this one.
        api = self._company_with_two_reports_of_one_form(
            _CountingRuzApi(
                detail=None, templates={7: {"tabulky": [{"nazov": "Vynosy"}]}}
            )
        )

        RuzFinancialsSyncService(api=api).sync_company_detailed(self.company)

        self.assertEqual(api.template_ids, [7])

    def test_z_a_later_test_starts_from_an_empty_cache(self):
        """Runs last in this class, after the test above cached template 7.

        Template 7 is scripted here with *no* tables, and the previous test
        scripted it with one. If the cache survived between tests, this read
        returns the earlier test's tables and never asks the api -- which is
        the leak, reproduced. Read through the private method rather than a
        whole sync because the cache is the unit under test and a sync would
        bury the distinction in a parsed row.

        The name is sorted to run last on purpose; the assertion is about what
        the *previous* test left behind, so it cannot be order-independent.
        """
        api = _CountingRuzApi(detail=None, templates={7: {"tabulky": []}})

        self.assertEqual(RuzFinancialsSyncService(api=api)._get_template_tables(7), [])
        self.assertEqual(api.template_ids, [7])
