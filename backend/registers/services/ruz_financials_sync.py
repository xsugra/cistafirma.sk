import logging
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Dict, List, NamedTuple, Optional

from companies.models import Company, CompanyFinancialResult
from registers.integrations.ruz_api import RuzApi, RuzUnreachable
from registers.models import CompanySyncStatus
from registers.services.sync_engine import (
    ANSWERED_RETRY_AFTER,
    _classify_error,
    update_company_status,
)

logger = logging.getLogger(__name__)


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


class ExtractionOutcome(NamedTuple):
    """What reading one statement's reports produced, and what it had to work with.

    `financials` alone cannot say whether an empty result means the registry
    filed nothing or this code could not map what was filed. Measured 2026-09-12
    over the 79 companies the rotation answered with nothing: four different
    facts arrived as one sentence, and the sentence named the wrong one. Holding
    the two counts next to the fields is what lets the caller say which.

    `filled_cells` counts cells holding a number this reader could have used
    (`_to_decimal`), not merely non-blank text -- a cell of prose is not a figure
    the parser lost.
    """

    financials: Dict[str, Optional[Decimal]]
    is_ifrs: bool
    tables_seen: int
    filled_cells: int


_TRAILING_PARENTHETICAL = re.compile(r"\s*\([^()]*\)\s*$")

BALANCE_SHEET_KEYS = (
    "suvaha",
    "bilancia",
    "balance sheet",
    "strana aktiv",
    "strana pasiv",
    "assets",
    "liabilities",
    # The non-profit / municipal statement (šablóna 1163/1164, measured on
    # `00681393` 2026-09-12) names its two sides `Majetok` and `Záväzky` instead
    # of `Strana aktív` / `Strana pasív`. Both tables resolve their column shape
    # and yielded nothing, because neither name reached this tuple and the whole
    # balance-sheet block below is gated on `is_balance_sheet`.
    #
    # `zavazky` also prefixes note tables such as "Záväzky po lehote
    # splatnosti", which now enter that block; `_is_summary_row`'s anchoring is
    # what keeps them from producing a total (its remainder is neither empty nor
    # `sucet`/`spolu`). Same mechanism the existing `assets` / `liabilities`
    # keys already rely on.
    "majetok",
    "zavazky",
)

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

# The three totals, as prefixes for `_is_summary_row`, which anchors at the
# start of the label and then accepts an empty remainder or `r.` / `sucet` /
# `spolu`. "Majetok celkom" and "Záväzky celkom" therefore need their own entry:
# the bare `zavazky` prefix cannot match a `celkom` remainder, and `celkom` is
# the form this app uses everywhere else (`frontend/utils/pdfExport.ts`,
# `components/company/LiabilitiesPieChart.tsx`) -- which is why
# `LIABILITIES_TOTAL_LABELS` has always listed it.
ASSETS_TOTAL_LABELS = ("majetok spolu", "aktiva celkom", "spolu majetok", "majetok celkom")

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

# Bare prefixes, not the full labels: `_is_summary_row` already accepts the
# `sucet` and `spolu` remainders, so "vlastne imanie" covers "Vlastné imanie",
# "Vlastné imanie súčet" and "Vlastné imanie spolu" at once.
EQUITY_TOTAL_LABELS = ("vlastne imanie", "vlastny kapital")
LIABILITIES_TOTAL_LABELS = ("zavazky", "cudzie zdroje", "zavazky celkom")

# Which fields make a statement worth a row: the five headline aggregates.
# Explicit rather than "any mapped field", and the difference is not academic.
# `financials` only ever receives non-`None` values, so a gate of "anything at
# all" would store a row whose sole content is `income_tax` or `added_value` --
# details *of* a year's accounts, never a year on their own. Such a row renders
# as a chart of zeros with one number in it, and it answers `has_financials` =
# true. It would also make the `gated` counter in `_read_company` unreachable,
# deleting the only clause that names a decision this code makes rather than a
# fact about the registry. `costs` and `total_revenue` are deliberately out: a
# statement whose "Náklady" total resolves while "Výnosy" does not is a
# fragment, and the gate has always discarded it.
STATEMENT_HEADLINE_FIELDS = (
    "revenue",
    "profit",
    "assets_total",
    "equity",
    "liabilities_total",
)

PL_EXTENDED_LABELS = {
    "pridana hodnota": "added_value",
}


_template_cache: Dict[int, Dict] = {}

# The templates name the two accounting periods in one of two vocabularies,
# both read live from RUZ on 2026-09-12: the words ("Bezprostredne predchádzajúce
# účtovné obdobie", šablóny 687 and 699) or the form's own placeholder pair
# ("20xx" against "20xx-1", šablóny 690, 696 and 727). Whichever appears, the
# cell carrying it marks where the current period's columns stop.
_PREVIOUS_PERIOD_MARKERS = ("predchadzajuc", "preceding")
_PREVIOUS_PERIOD_PLACEHOLDER = re.compile(r"(?:20xx|\d{4})-1")

# Inside the current period's block, the column the rest of the app means is the
# aggregate one: "Netto" on the balance sheet (a gross value, or the correction
# column beside it, does not satisfy assets = equity + liabilities) and "Spolu"
# on the cost and revenue tables (against "Hlavná činnosť" and "Podnikateľská
# činnosť"). Where neither is present the block's last column is the aggregate,
# which is where every measured template puts it.
_PERIOD_TOTAL_MARKERS = ("netto", "spolu")


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
        # Why a statement contributed nothing, counted rather than summed: the
        # four reasons below mean different things and used to arrive as one
        # sentence, which then named the wrong one.
        unreadable = 0     # the statement itself could not be used
        no_tables = 0      # the report bodies carry no tables
        empty_tables = 0   # tables exist and hold no number
        unmapped = 0       # tables hold numbers, and no key or column rule reads them
        gated = 0          # read fine, discarded for carrying no headline figure
        found_ifrs = False
        for statement_id in statement_ids[:max_statements]:
            statement = self.api.get_financial_statement_details(statement_id)
            if not statement:
                unreadable += 1
                continue

            year = self._extract_year(statement)
            if not year:
                unreadable += 1
                continue

            report_ids = statement.get("idUctovnychVykazov", []) or []
            if not report_ids:
                unreadable += 1
                continue

            extraction = self._extract_financials_from_reports(report_ids)
            if extraction.is_ifrs:
                found_ifrs = True
            financials = extraction.financials
            if not any(
                financials.get(field) is not None
                for field in STATEMENT_HEADLINE_FIELDS
            ):
                if extraction.tables_seen == 0:
                    no_tables += 1
                elif extraction.filled_cells == 0:
                    empty_tables += 1
                elif not financials:
                    unmapped += 1
                else:
                    gated += 1
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

        reasons = self._reason_clauses(
            unreadable=unreadable,
            no_tables=no_tables,
            empty_tables=empty_tables,
            unmapped=unmapped,
            gated=gated,
        )

        if upserts == 0:
            # Statements exist and none was recorded. Still an answer -- and
            # worth being able to count, because a population that is all this
            # and no `RECORDED` is a signal. Which signal, though, depends on
            # why: `gated` is a decision this code makes, `unmapped` is a gap in
            # it, and the other three are the registry having nothing to give.
            # The single sentence that used to stand here said "none readable"
            # about all of them, and for a company the gate had discarded it was
            # false -- measured 2026-09-12 on the 79 companies the rotation
            # answered with nothing. A reader told the wrong reason looks in the
            # wrong place, which is how that investigation took two wrong turns.
            return FinancialsSyncResult(
                FinancialsOutcome.NO_STATEMENTS,
                detail=(
                    f"{len(statement_ids)} statement(s) present, none recorded "
                    f"({', '.join(reasons) if reasons else 'none readable'})"
                ),
            )

        # A statement we could not read is worth naming even when others were
        # fine. `RECORDED` alone cannot show the difference between "all 13
        # statements read" and "12 of 13 did, and the parser is drifting" --
        # and the second is the early warning that the first is about to stop
        # being true. The count is the signal; the trend across runs is the
        # alarm. Measured 2026-09-11 on the pilot: 12-13 statements per company,
        # all read. The reasons ride along for the same purpose: a run that
        # starts discarding statements says so before the count moves.
        readable = f"{upserts} of {len(statement_ids)} statement(s) readable"
        return FinancialsSyncResult(
            FinancialsOutcome.RECORDED,
            rows=upserts,
            detail=f"{readable} ({', '.join(reasons)})" if reasons else "",
        )

    @staticmethod
    def _reason_clauses(
        *,
        unreadable: int,
        no_tables: int,
        empty_tables: int,
        unmapped: int,
        gated: int,
    ) -> List[str]:
        """Why statements contributed nothing, ordered by what a reader should check first.

        `gated` and `unmapped` lead because both are this code's doing -- one a
        decision, one a gap -- and a reader who meets them first looks here. The
        rest are facts about the registry: an empty template and a body without
        tables are the company having nothing to file, not something to repair.
        """
        clauses = []
        if gated:
            clauses.append(
                f"{gated} readable but carrying none of a revenue, a profit "
                f"or a balance-sheet total"
            )
        if unmapped:
            clauses.append(f"{unmapped} carrying values that yielded no field")
        if empty_tables:
            clauses.append(f"{empty_tables} with tables but no filled cell")
        if no_tables:
            clauses.append(f"{no_tables} with no tables in the report bodies")
        if unreadable:
            clauses.append(f"{unreadable} unusable")
        return clauses

    def _extract_year(self, statement: Dict) -> Optional[int]:
        for key in ("obdobieDo", "obdobieOd"):
            value = statement.get(key)
            if not value:
                continue
            match = re.match(r"^(\d{4})", str(value))
            if match:
                return int(match.group(1))
        return None

    def _extract_financials_from_reports(self, report_ids: List[int]) -> ExtractionOutcome:
        """Read a statement's reports, and report what there was to read.

        The counts are gathered here rather than by the caller because the
        reports are already fetched here: walking them a second time would mean
        a second round of requests to a registry that times out.
        """
        result: Dict[str, Optional[Decimal]] = {}
        is_ifrs = False
        tables_seen = 0
        filled_cells = 0

        for report_id in report_ids:
            report = self.api.get_financial_report_details(report_id)
            if not report:
                continue

            if report.get("idSablony") == self.IFRS_TEMPLATE_ID:
                is_ifrs = True

            tables = ((report.get("obsah") or {}).get("tabulky") or [])
            template_tables = self._get_template_tables(report.get("idSablony"))

            tables_seen += len(tables)
            for table in tables:
                filled_cells += sum(
                    1
                    for value in (table.get("data") or [])
                    if self._to_decimal(value) is not None
                )

            for idx, table in enumerate(tables):
                template_table = template_tables[idx] if idx < len(template_tables) else None
                extracted = self._extract_with_template(table, template_table)
                for key, value in extracted.items():
                    if value is not None:
                        result[key] = self._pick_better(result.get(key), value)

            for idx, table in enumerate(tables):
                name = self._normalize_text(self._table_name(table))
                if not name:
                    continue

                total = self._extract_table_total(
                    table,
                    template_tables[idx] if idx < len(template_tables) else None,
                )
                if total is None:
                    # Only a table whose *name* promises one of these figures is
                    # worth a word when it delivers nothing -- the others are
                    # simply not totals. Silence here would be the same defect
                    # in miniature: a company quietly losing its revenue with
                    # nothing in the log to count.
                    if any(
                        k in name
                        for k in self.REVENUE_KEYS + self.COST_KEYS + self.PROFIT_KEYS
                    ):
                        logger.warning(
                            "RUZ financials: table %r names a revenue, cost or "
                            "profit figure, but no total could be read in the "
                            "current period's column; contributing nothing",
                            self._table_name(table),
                        )
                    continue

                if any(k in name for k in self.REVENUE_KEYS):
                    result["revenue"] = self._pick_better(result.get("revenue"), total)
                elif any(k in name for k in self.COST_KEYS):
                    result["costs"] = self._pick_better(result.get("costs"), total)
                elif any(k in name for k in self.PROFIT_KEYS):
                    result["profit"] = self._pick_better(result.get("profit"), total)

        if result.get("profit") is None and result.get("revenue") is not None and result.get("costs") is not None:
            result["profit"] = result["revenue"] - result["costs"]

        return ExtractionOutcome(result, is_ifrs, tables_seen, filled_cells)

    def _data_column_shape(
        self, template_table: Dict, rows: List[Dict], data: List
    ) -> Optional[tuple]:
        """`(columns per row, index of the current period's column)`, or None.

        The width is arithmetic here, not an inference. `data` is the values of
        the table flattened row by row, so it is `rows x columns` long, and the
        template declares `pocetDatovychStlpcov`. Measured 2026-09-12 across 38
        tables of 25 companies: the two agree exactly every time, which is what
        makes the old `len(data) >= len(rows) * 2` test unnecessary as well as
        unsafe -- it held for the four-column asset side too, and reading it as
        "two columns" is the defect this replaces.

        A template that omits the declared width still gives the shape when the
        values divide evenly by the row count; that division is a fact about the
        data, not a guess about it. When neither holds, or when the current
        period cannot be located in the header, the answer is None: the caller
        refuses the table rather than picking a column.
        """
        cols = template_table.get("pocetDatovychStlpcov")
        if not isinstance(cols, int) or cols < 1:
            if not rows or len(data) % len(rows):
                return None
            cols = len(data) // len(rows)

        if len(data) < len(rows) * cols:
            return None

        current = self._current_period_column(template_table, cols)
        if current is None:
            return None
        return cols, current

    def _current_period_column(self, template_table: Dict, cols: int) -> Optional[int]:
        """Which of a row's data columns holds the current period, 0-based.

        The current period is always the first block of data columns -- that is
        the form's own layout, in every template measured -- and the header says
        where the block ends, because the cell naming the *preceding* period is
        the first column after it. That single fact covers all three shapes seen
        so far: two plain columns (šablóna 699 "Strana pasív"), four carrying a
        gross/correction/net figure (šablóna 699 "Strana aktív"), and the
        cost-and-revenue tables whose three columns are main activity, business
        activity and their sum (šablóny 696 and 727).

        A block one column wide has nothing to choose between. A wider one does,
        and the choice matters: on the asset side, "Brutto" and "Korekcia" are
        both the current period and both wrong as a balance-sheet total.

        None means the header does not say, including the case where the
        preceding period comes first -- an order this code has never seen and
        will not assume away.
        """
        cells = template_table.get("hlavicka") or []
        columns = [
            cell.get("stlpec") for cell in cells if isinstance(cell.get("stlpec"), int)
        ]
        if not columns:
            # No header at all to disagree with: a one-column table can only
            # mean one thing. Anything wider is left to the caller's refusal.
            return 0 if cols == 1 else None

        first = max(columns) - cols + 1

        preceding = [
            cell["stlpec"]
            for cell in cells
            if isinstance(cell.get("stlpec"), int)
            and self._names_previous_period(self._header_text(cell))
        ]
        if not preceding:
            return 0 if cols == 1 else None

        block = min(preceding) - first
        if not 0 < block <= cols:
            return None

        # The deepest header row at each data column is the most specific label
        # for it ("Netto 2" rather than the period name spanning over it).
        deepest: Dict[int, tuple] = {}
        for cell in cells:
            column = cell.get("stlpec")
            if not isinstance(column, int):
                continue
            rank = cell.get("riadok")
            rank = rank if isinstance(rank, int) else 0
            if column not in deepest or rank > deepest[column][0]:
                deepest[column] = (rank, self._header_text(cell))

        for index in range(block - 1, -1, -1):
            label = deepest.get(first + index, (0, ""))[1]
            if any(marker in label for marker in _PERIOD_TOTAL_MARKERS):
                return index
        return block - 1

    def _names_previous_period(self, text: str) -> bool:
        """Whether a header label names the period *before* the current one."""
        if any(marker in text for marker in _PREVIOUS_PERIOD_MARKERS):
            return True
        # Per word, because `_header_text` hands over both languages at once and
        # a cell carrying "20xx-1" in each would otherwise never match whole.
        return any(
            _PREVIOUS_PERIOD_PLACEHOLDER.fullmatch(word) for word in text.split()
        )

    def _header_text(self, cell: Dict) -> str:
        """A header cell's label in either language, normalised for matching."""
        text = cell.get("text")
        if isinstance(text, dict):
            text = " ".join(str(text.get(key) or "") for key in ("sk", "en"))
        return self._normalize_text(text)

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

        shape = self._data_column_shape(template_table, rows, data)
        if shape is None:
            # Refusing is the point, not a failure to handle. The width used to
            # be guessed from `len(data) >= len(rows) * 2`, which for the
            # four-column asset side is true and wrong at once: template row i
            # read sheet row i // 2, so `assets_total` held the GROSS
            # current-period assets of a different line and every asset line
            # below it was another row's value. A number that looks right and
            # is not is worse than an absent one, so an unreadable template
            # contributes nothing rather than something invented -- and says so
            # out loud, because a refusal nobody can count is its own silence.
            logger.warning(
                "RUZ financials: no readable data-column shape for table %r "
                "(cols=%s, rows=%s, values=%s); refusing to guess which column "
                "is the current period",
                self._table_name(template_table),
                template_table.get("pocetDatovychStlpcov"),
                len(rows),
                len(data),
            )
            return extracted

        cols, current = shape

        def get_row_value(idx):
            position = idx * cols + current
            if position >= len(data):
                return None
            return self._to_decimal(data[position])

        table_name = self._normalize_text(
            self._table_name(template_table) or self._table_name(table)
        )
        is_balance_sheet = any(k in table_name for k in BALANCE_SHEET_KEYS) if table_name else False

        # `in_liabilities_section` starts the row loop on the right side. The
        # per-row check further down corrects it, but only once it has seen a
        # row containing `zavazky` -- so a `Záväzky` table whose first row is
        # `Rezervy súčet` would read that row as an asset. The blast radius is
        # bounded (`ASSETS_LABELS` and `LIABILITIES_LABELS` are disjoint, so a
        # wrong flag yields no field rather than a wrong one), but the flag
        # should still be right.
        is_liabilities_table = (
            any(k in table_name for k in ("strana pasiv", "liabilities", "zavazky"))
            if table_name
            else False
        )

        in_liabilities_section = is_liabilities_table

        for idx, row in enumerate(rows):
            row_label = self._normalize_text(((row.get("text") or {}).get("sk") or ""))
            if not row_label:
                continue
            value = get_row_value(idx)

            # P&L extraction (revenue, cost, profit)
            #
            # Note what is absent: `Príjmy` and `Výdavky`, the non-profit and
            # municipal statement's two sides. They are *not* mapped to
            # `revenue`/`costs`, and that is a decision rather than an oversight
            # (docs/SOURCE_DATA_INTEGRITY.md). A municipality's grant income is
            # not a company's turnover, and `revenue` is a denominator across
            # this codebase -- the sector benchmark's median revenue and gross
            # margin, `latest_revenue`, the admin's "Má tržby" facet, the lead
            # score's growth points. One village in a NACE section would move
            # that section's benchmark for every ordinary firm in it.
            #
            # Mapping them would also require *guessing*: `Príjmy`/`Výdavky`
            # carry no readable data-column shape, so `_current_period_column`
            # refuses before any vocabulary question is asked -- the same
            # refusal, for the same reason, as the four-column asset side.
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

            if self._is_summary_row(row_label, ASSETS_TOTAL_LABELS):
                if value is not None:
                    extracted["assets_total"] = self._pick_better(extracted.get("assets_total"), value)
                continue

            if self._is_summary_row(row_label, EQUITY_TOTAL_LABELS):
                if value is not None:
                    extracted["equity"] = self._pick_better(extracted.get("equity"), value)
                continue

            if self._is_summary_row(row_label, LIABILITIES_TOTAL_LABELS):
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
        """Whether a normalised row label is the total for one of `prefixes`.

        A trailing parenthetical is dropped first, and that is the whole reason
        the non-profit totals were being lost. Šablóna 1164 writes its totals as
        `Majetok celkom (súčet r. 01 až r. 10)` and
        `Záväzky celkom (súčet r. 12 a r.15)`: the parenthesis is a note about
        how the row was arrived at, so the label's identity is everything before
        it. Read literally the remainder is `(sucet r. 01 az r. 10)`, which is
        none of the accepted forms, so both totals were discarded with their
        values sitting in the table -- measured on `00681393` and `00699349`
        2026-09-12, after the table names themselves were already recognised.

        Only this predicate strips it. The `ASSETS_LABELS` / `LIABILITIES_LABELS`
        lookups below still match against the full label, so a note row cannot
        start producing a line item.
        """
        label = _TRAILING_PARENTHETICAL.sub("", label).strip()
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

    def _extract_table_total(
        self, table: Dict, template_table: Optional[Dict] = None
    ) -> Optional[Decimal]:
        """The last row that carries a figure, in the current period's column.

        This is the other half of the same defect. It used to return
        `numbers[-1]` -- the last numeric value anywhere in the flattened table,
        in whatever column it happened to sit. The tables it serves are the ones
        whose *name* matches the revenue, cost and profit keys: "Výnosy" and
        "Náklady", four data columns wide (šablóny 696 and 727), where the
        current period occupies the first three and the fourth repeats the
        previous period. Since those tables end in empty "Kontrolné číslo súčet"
        rows, the last value found was the last filled data row's fourth column
        -- last year's figure, read as this year's. For the companies that use
        these templates those two tables are the *only* source of `revenue` and
        `costs`, so the wrong number had nothing beside it to contradict it.

        Reading down from the bottom for the last non-empty value *in the
        current period's column* keeps the original intent -- the table's own
        total row, which is the last filled one -- and drops the part that made
        the column arbitrary.

        A table with **no template at all** keeps the old reading, deliberately.
        That is a different population from the one that was measured -- every
        table in the 38-table sample had its template, so nothing here says how
        wide a template-less table is -- and refusing would move a documented
        outcome as a side effect: a statement whose every table is unreadable
        contributes no field, so it counts as zero rows, and a template fetch
        that failed would arrive as "this company has no statements". That is
        the conflation `UNREACHABLE` was introduced to undo. Left as it was and
        reported separately rather than decided quietly.
        """
        data = table.get("data") or []

        if not template_table:
            numbers = [
                parsed
                for parsed in (self._to_decimal(value) for value in data)
                if parsed is not None
            ]
            return numbers[-1] if numbers else None

        rows = template_table.get("riadky") or []
        if not rows:
            return None

        shape = self._data_column_shape(template_table, rows, data)
        if shape is None:
            return None

        cols, current = shape
        for idx in range(len(rows) - 1, -1, -1):
            position = idx * cols + current
            if position >= len(data):
                continue
            value = self._to_decimal(data[position])
            if value is not None:
                return value
        return None

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
        # On **both** branches. The answered path is the one that needs it:
        # `error` is blanked there, so this is the only place the sentence
        # survives past the task's log line.
        detail=result.detail,
    )
    return result
