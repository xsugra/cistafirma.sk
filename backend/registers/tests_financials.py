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


class NoStatementsReasonTests(TestCase):
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
