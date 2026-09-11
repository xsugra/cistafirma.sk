import logging
import re
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Dict, List, Optional

from companies.models import Company, CompanyFinancialResult
from registers.integrations.ruz_api import RuzApi, RuzUnreachable
from registers.models import CompanySyncStatus
from registers.services.sync_engine import _classify_error, update_company_status

logger = logging.getLogger(__name__)

# A company the registry answered about is not due again for a year. This is
# not a retry delay -- the retry delay is `compute_next_retry`'s exponential
# backoff, and it applies to failures. This is what "we asked, and the answer
# is not going to change this week" costs: without it a successful attempt
# leaves `next_retry_at = NULL`, which the due-query reads as "due now", so the
# whole freshly-synced batch would refill the next batch and starve every
# company that has never been attempted.
ANSWERED_RETRY_AFTER = timedelta(days=365)


class FinancialsOutcome(str, Enum):
    """What one financials attempt actually established.

    `sync_company() -> int` returned `0` for every one of these at once, and the
    first three do not belong with the last one. The first three are *knowledge
    about the company*; the last is *ignorance about the registry*. A caller
    that cannot tell them apart records "checked, nothing there" for a company
    it never reached -- which is how this import read as healthy while covering
    309 of 251 598 companies, and why the Trnava preset returned an empty table
    for months without anything looking broken.
    """

    RECORDED = "recorded"            # registry answered; statements stored
    NO_STATEMENTS = "no_statements"  # registry answered; nothing to store
    NOT_IN_RUZ = "not_in_ruz"        # registry answered; no such company
    UNREACHABLE = "unreachable"      # registry never answered

    @property
    def answered(self) -> bool:
        """Whether the registry told us something, as opposed to us failing to ask."""
        return self is not FinancialsOutcome.UNREACHABLE


@dataclass(frozen=True)
class FinancialsSyncResult:
    """The outcome of one company's financials attempt, with the rows it stored."""

    outcome: FinancialsOutcome
    rows: int = 0
    detail: str = ""

    @property
    def succeeded(self) -> bool:
        """Whether this attempt should be recorded as a success.

        True for all three answered outcomes, including the two that stored
        nothing. A sync that reached the registry and read it correctly *did*
        succeed; the data being absent is a fact about the company, and
        recording it as a success is what makes "checked and empty" visible as
        something different from "never checked".
        """
        return self.outcome.answered


BALANCE_SHEET_KEYS = ("suvaha", "bilancia", "balance sheet", "strana aktiv", "strana pasiv", "assets", "liabilities")

ASSETS_LABELS = {
    "dlhodoby nehmotny majetok sucet": "assets_intangible",
    "dlhodoby hmotny majetok sucet": "assets_tangible",
    "dlhodoby financny majetok sucet": "assets_financial",
    "zasoby sucet": "assets_inventory",
    "zasoby spolu": "assets_inventory",
    "dlhodobe pohladavky sucet": "assets_receivables_long",
    "dlhodobe pohladavky spolu": "assets_receivables_long",
    "kratkodobe pohladavky sucet": "assets_receivables_short",
    "kratkodobe pohladavky spolu": "assets_receivables_short",
    "financne ucty sucet": "assets_financial_accounts",
    "financne ucty spolu": "assets_financial_accounts",
    "krabezny financny majetok": "assets_financial_accounts",
}

ASSETS_TOTAL_LABELS = ("majetok spolu", "aktiva celkom", "spolu majetok")

LIABILITIES_LABELS = {
    "zakladne imanie sucet": "equity_basic",
    "zakladne imanie": "equity_basic",
    "kapitalove fondy sucet": "equity_capital_funds",
    "kapitalove fondy spolu": "equity_capital_funds",
    "fondy zo zisku": "equity_profit_funds",
    "zakonne rezervne fondy": "equity_profit_funds",
    "vysledok hospodarenia minulych rokov": "equity_retained",
    "rezervy sucet": "liabilities_reserves",
    "rezervy spolu": "liabilities_reserves",
    "dlhodobe rezervy": "liabilities_reserves",
    "dlhodobe zavazky sucet": "liabilities_long",
    "dlhodobe zavazky spolu": "liabilities_long",
    "kratkodobe zavazky sucet": "liabilities_short",
    "kratkodobe zavazky spolu": "liabilities_short",
}

EQUITY_TOTAL_LABELS = ("vlastne imanie sucet", "vlastne imanie spolu", "vlastny kapital")
LIABILITIES_TOTAL_LABELS = ("cudzie zdroje", "zavazky celkom", "cudzie zdroje spolu")

PL_EXTENDED_LABELS = {
    "pridana hodnota": "added_value",
}


_template_cache: Dict[int, Dict] = {}


class RuzFinancialsSyncService:
    """Synchronizuje hospodarske vysledky firmy z RUZ API (uctovne zavierky/vykazy)."""

    REVENUE_KEYS = ("vynosy", "trzby", "trzba")
    COST_KEYS = ("naklady", "naklad")
    PROFIT_KEYS = ("vysledok hospodarenia", "hospodarsky vysledok", "vysledok")

    def __init__(self, api: Optional[RuzApi] = None):
        # The strict client is what makes this service's outcome meaningful. The
        # other five `RuzApi()` construction sites keep the permissive default,
        # so their behaviour is untouched, while this path can no longer answer
        # "0 rows" for a registry it never reached.
        self.api = api or RuzApi(raise_on_transport_error=True)

    IFRS_TEMPLATE_ID = 709

    def sync_company(self, company: Company, max_statements: int = 30) -> int:
        """Number of upserts. Prefer `sync_company_detailed`: `0` does not say why.

        Kept as a one-line delegate so existing callers and tests keep the
        signature they had, without the ambiguity that made this increment
        necessary.
        """
        return self.sync_company_detailed(company, max_statements).rows

    def sync_company_detailed(
        self, company: Company, max_statements: int = 30
    ) -> FinancialsSyncResult:
        """Fetch and upsert yearly financial data, and say what that established.

        An unreachable registry comes back as `UNREACHABLE` rather than as
        `rows=0`, which is the difference this whole increment turns on. Any
        other exception is a bug in the reading code and is left to propagate --
        it is not a statement about the registry, and folding it into an outcome
        would recreate exactly the ambiguity being removed here.
        """
        try:
            return self._read_company(company, max_statements)
        except RuzUnreachable as exc:
            logger.error(
                "RUZ financial sync: registry unreachable for company %s (%s): %s",
                company.id, company.ico, exc,
            )
            return FinancialsSyncResult(FinancialsOutcome.UNREACHABLE, detail=str(exc))

    def _read_company(self, company: Company, max_statements: int) -> FinancialsSyncResult:
        if not company.ruz_id:
            detail = self.api.get_company_by_ico(company.ico)
        else:
            detail = self.api.get_company_details(company.ruz_id)

        if not detail:
            logger.info(
                "RUZ financial sync: company %s (%s) has no record in RUZ", company.id, company.ico
            )
            return FinancialsSyncResult(
                FinancialsOutcome.NOT_IN_RUZ, detail="company has no RUZ record"
            )

        statement_ids = detail.get("idUctovnychZavierok", []) or []
        if not statement_ids:
            return FinancialsSyncResult(
                FinancialsOutcome.NO_STATEMENTS, detail="company has no statements in RUZ"
            )

        upserts = 0
        skipped = 0
        found_ifrs = False
        for statement_id in statement_ids[:max_statements]:
            statement = self.api.get_financial_statement_details(statement_id)
            if not statement:
                skipped += 1
                continue

            year = self._extract_year(statement)
            if not year:
                skipped += 1
                continue

            report_ids = statement.get("idUctovnychVykazov", []) or []
            if not report_ids:
                skipped += 1
                continue

            financials, is_ifrs = self._extract_financials_from_reports(report_ids)
            if is_ifrs:
                found_ifrs = True
            if financials.get("revenue") is None and financials.get("profit") is None:
                skipped += 1
                continue

            CompanyFinancialResult.objects.update_or_create(
                company=company,
                year=year,
                defaults={
                    "source": "ruz_api",
                    **{k: v for k, v in financials.items() if v is not None},
                },
            )
            upserts += 1

        if found_ifrs != company.uses_ifrs:
            company.uses_ifrs = found_ifrs
            company.save(update_fields=["uses_ifrs"])

        if upserts == 0:
            # Statements exist but none yielded a revenue or a profit we could
            # read. Still an answer -- and worth being able to count, because a
            # population that is all this and no `RECORDED` is a parser signal.
            return FinancialsSyncResult(
                FinancialsOutcome.NO_STATEMENTS,
                detail=f"{len(statement_ids)} statement(s) present, none readable",
            )

        # A statement we could not read is worth naming even when others were
        # fine. `RECORDED` alone cannot show the difference between "all 13
        # statements read" and "12 of 13 did, and the parser is drifting" --
        # and the second is the early warning that the first is about to stop
        # being true. The count is the signal; the trend across runs is the
        # alarm. Measured 2026-09-11 on the pilot: 12-13 statements per company,
        # all read.
        readable = f"{upserts} of {len(statement_ids)} statement(s) readable"
        return FinancialsSyncResult(
            FinancialsOutcome.RECORDED,
            rows=upserts,
            detail=readable if skipped else "",
        )

    def _extract_year(self, statement: Dict) -> Optional[int]:
        for key in ("obdobieDo", "obdobieOd"):
            value = statement.get(key)
            if not value:
                continue
            match = re.match(r"^(\d{4})", str(value))
            if match:
                return int(match.group(1))
        return None

    def _extract_financials_from_reports(self, report_ids: List[int]) -> tuple:
        """Returns (financials_dict, is_ifrs)."""
        result: Dict[str, Optional[Decimal]] = {}
        is_ifrs = False

        for report_id in report_ids:
            report = self.api.get_financial_report_details(report_id)
            if not report:
                continue

            if report.get("idSablony") == self.IFRS_TEMPLATE_ID:
                is_ifrs = True

            tables = ((report.get("obsah") or {}).get("tabulky") or [])
            template_tables = self._get_template_tables(report.get("idSablony"))

            for idx, table in enumerate(tables):
                template_table = template_tables[idx] if idx < len(template_tables) else None
                extracted = self._extract_with_template(table, template_table)
                for key, value in extracted.items():
                    if value is not None:
                        result[key] = self._pick_better(result.get(key), value)

            for table in tables:
                name = self._normalize_text(self._table_name(table))
                if not name:
                    continue

                total = self._extract_table_total(table)
                if total is None:
                    continue

                if any(k in name for k in self.REVENUE_KEYS):
                    result["revenue"] = self._pick_better(result.get("revenue"), total)
                elif any(k in name for k in self.COST_KEYS):
                    result["costs"] = self._pick_better(result.get("costs"), total)
                elif any(k in name for k in self.PROFIT_KEYS):
                    result["profit"] = self._pick_better(result.get("profit"), total)

        if result.get("profit") is None and result.get("revenue") is not None and result.get("costs") is not None:
            result["profit"] = result["revenue"] - result["costs"]

        return result, is_ifrs

    def _get_template_tables(self, template_id: Optional[int]) -> List[Dict]:
        if not template_id:
            return []
        if template_id not in _template_cache:
            template = self.api.get_report_template_details(template_id) or {}
            _template_cache[template_id] = template
        return _template_cache[template_id].get("tabulky", []) or []

    def _extract_with_template(self, table: Dict, template_table: Optional[Dict]) -> Dict[str, Optional[Decimal]]:
        extracted: Dict[str, Optional[Decimal]] = {}

        if not template_table:
            return extracted

        data = table.get("data") or []
        rows = template_table.get("riadky") or []
        if not data or not rows:
            return extracted

        if len(data) >= len(rows) * 2:
            get_row_value = lambda idx: self._to_decimal(data[idx * 2])
        else:
            get_row_value = lambda idx: self._to_decimal(data[idx]) if idx < len(data) else None

        table_name = self._normalize_text(
            self._table_name(template_table) or self._table_name(table)
        )
        is_balance_sheet = any(k in table_name for k in BALANCE_SHEET_KEYS) if table_name else False

        is_assets_table = any(k in table_name for k in ("strana aktiv", "assets")) if table_name else False
        is_liabilities_table = any(k in table_name for k in ("strana pasiv", "liabilities")) if table_name else False

        in_liabilities_section = is_liabilities_table

        for idx, row in enumerate(rows):
            row_label = self._normalize_text(((row.get("text") or {}).get("sk") or ""))
            if not row_label:
                continue
            value = get_row_value(idx)

            # P&L extraction (revenue, cost, profit)
            if ("vynosy z hospodarskej cinnosti spolu" in row_label) or ("trzby z predaja" in row_label and "revenue" not in extracted):
                if value is not None:
                    extracted["revenue"] = self._pick_better(extracted.get("revenue"), value)

            if "vynosy z financnej cinnosti spolu" in row_label or "financne vynosy spolu" in row_label or "financne vynosy sucet" in row_label:
                if value is not None:
                    rev = extracted.get("revenue")
                    base = rev if rev is not None else Decimal(0)
                    extracted["total_revenue"] = base + value

            if "vynosy z hospodarskej cinnosti spolu" in row_label:
                if value is not None and "total_revenue" not in extracted:
                    extracted["total_revenue"] = value

            if "naklady na hospodarsku cinnost spolu" in row_label:
                if value is not None:
                    extracted["costs"] = self._pick_better(extracted.get("costs"), value)

            if (
                "vysledok hospodarenia z hospodarskej cinnosti" in row_label
                or "vysledok hospodarenia za uctovne obdobie po zdaneni" in row_label
            ):
                if value is not None:
                    extracted["profit"] = self._pick_better(extracted.get("profit"), value)

            # P&L extended
            if "dan z prijmov" in row_label and "odlozena" not in row_label:
                if "splatna" in row_label:
                    if value is not None:
                        extracted["income_tax_paid"] = value
                elif value is not None:
                    extracted["income_tax"] = value

            for label_key, field_name in PL_EXTENDED_LABELS.items():
                if label_key in row_label and value is not None:
                    extracted[field_name] = self._pick_better(extracted.get(field_name), value)

            # Balance sheet extraction
            if not is_balance_sheet:
                continue

            if any(k in row_label for k in ("vlastne imanie", "vlastny kapital", "pasiva", "zavazky")):
                in_liabilities_section = True

            if self._is_summary_row(row_label, ("spolu majetok", "aktiva celkom", "majetok spolu")):
                if value is not None:
                    extracted["assets_total"] = self._pick_better(extracted.get("assets_total"), value)
                continue

            if self._is_summary_row(row_label, ("vlastne imanie", "vlastny kapital")):
                if value is not None:
                    extracted["equity"] = self._pick_better(extracted.get("equity"), value)
                continue

            if self._is_summary_row(row_label, ("zavazky", "cudzie zdroje")):
                if value is not None:
                    extracted["liabilities_total"] = self._pick_better(extracted.get("liabilities_total"), value)
                continue

            if "casove rozlisenie" in row_label and value is not None:
                if in_liabilities_section:
                    extracted["liabilities_accruals"] = value
                else:
                    extracted["assets_accruals"] = value
                continue

            if not in_liabilities_section:
                for label_key, field_name in ASSETS_LABELS.items():
                    if label_key in row_label and value is not None:
                        extracted[field_name] = self._pick_better(extracted.get(field_name), value)
                        break
            else:
                for label_key, field_name in LIABILITIES_LABELS.items():
                    if label_key in row_label and value is not None:
                        extracted[field_name] = self._pick_better(extracted.get(field_name), value)
                        break

        if extracted.get("profit") is None and extracted.get("revenue") is not None and extracted.get("costs") is not None:
            extracted["profit"] = extracted["revenue"] - extracted["costs"]

        return extracted

    def _is_summary_row(self, label: str, prefixes: tuple) -> bool:
        for prefix in prefixes:
            if not label.startswith(prefix):
                continue
            rest = label[len(prefix):].strip()
            if not rest or rest.startswith("r.") or rest.startswith("sucet") or rest.startswith("spolu"):
                return True
        return False

    def _table_name(self, table: Dict) -> str:
        name = table.get("nazov")
        if isinstance(name, dict):
            return name.get("sk") or name.get("en") or ""
        return str(name or "")

    def _extract_table_total(self, table: Dict) -> Optional[Decimal]:
        data = table.get("data") or []
        numbers = []
        for value in data:
            parsed = self._to_decimal(value)
            if parsed is not None:
                numbers.append(parsed)
        if not numbers:
            return None
        return numbers[-1]

    def _to_decimal(self, value) -> Optional[Decimal]:
        if value is None:
            return None
        text = str(value).strip().replace(" ", "")
        if not text:
            return None
        text = text.replace(",", ".")
        try:
            return Decimal(text)
        except (InvalidOperation, ValueError):
            return None

    def _pick_better(self, current: Optional[Decimal], candidate: Decimal) -> Decimal:
        if current is None:
            return candidate
        if abs(candidate) > abs(current):
            return candidate
        return current

    def _normalize_text(self, value: str) -> str:
        ascii_map = str.maketrans(
            "áäčďéěíĺľňóôŕřšťúýžÁÄČĎÉĚÍĹĽŇÓÔŔŘŠŤÚÝŽ",
            "aacdeeillnoorrstuyzAACDEEILLNOORRSTUYZ",
        )
        return (value or "").translate(ascii_map).lower()


def sync_company_and_record(
    company: Company, *, service: Optional[RuzFinancialsSyncService] = None
) -> FinancialsSyncResult:
    """Sync one company's financials and record the attempt against the source.

    The single owner of the outcome -> `CompanySyncStatus` rule, so the Celery
    task, the management command and the batch scheduler cannot each decide
    differently what `rows=0` means. That divergence is the bug being fixed: the
    API could not tell "checked, nothing there" from "never reached", and every
    caller quietly resolved the ambiguity its own way.

    The transport failure does **not** propagate. `orchestrate_full_company_sync`
    builds its `group(...)` with `update_insurance_debt` as the chord callback,
    so an exception raised here would stop that callback from ever running and a
    company would silently stop having its insurance debts refreshed -- a second
    outage caused by the handling of the first. Repetition is therefore owned
    entirely by `next_retry_at` (exponential backoff, capped at 24 h), not by
    Celery autoretry.

    Any *other* exception is recorded and re-raised: it is a bug in the reading
    code, not a statement about the registry, and it belongs in the worker's
    error rate rather than in an outcome.
    """
    service = service or RuzFinancialsSyncService()

    try:
        result = service.sync_company_detailed(company)
    except Exception as exc:  # noqa: BLE001 -- recorded, then re-raised
        update_company_status(
            company_id=company.id,
            source=CompanySyncStatus.SOURCE_FINANCIALS,
            success=False,
            error=f"{type(exc).__name__}: {exc}",
            error_type=_classify_error(exc),
        )
        raise

    update_company_status(
        company_id=company.id,
        source=CompanySyncStatus.SOURCE_FINANCIALS,
        success=result.succeeded,
        # `error_type` stays "network" and not `_classify_error`'s verdict: the
        # one thing we know about an `UNREACHABLE` is that the registry was not
        # read, and `_classify_error` matches substrings -- a company id
        # containing "500" would be filed as a server error.
        error="" if result.succeeded else result.detail,
        error_type="" if result.succeeded else "network",
        retry_after=ANSWERED_RETRY_AFTER if result.succeeded else None,
    )
    return result
