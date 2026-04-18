import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Tuple

from companies.models import Company, CompanyFinancialResult
from registers.integrations.ruz_api import RuzApi


logger = logging.getLogger(__name__)


class RuzFinancialsSyncService:
    """Synchronizuje hospodarske vysledky firmy z RUZ API (uctovne zavierky/vykazy)."""

    REVENUE_KEYS = ("vynosy", "trzby", "trzba")
    COST_KEYS = ("naklady", "naklad")
    PROFIT_KEYS = ("vysledok hospodarenia", "hospodarsky vysledok", "vysledok")

    def __init__(self, api: Optional[RuzApi] = None):
        self.api = api or RuzApi()
        self._template_cache: Dict[int, Dict] = {}

    def sync_company(self, company: Company, max_statements: int = 20) -> int:
        """Fetch and upsert yearly financial data for one company. Returns number of upserts."""
        if not company.ruz_id:
            detail = self.api.get_company_by_ico(company.ico)
        else:
            detail = self.api.get_company_details(company.ruz_id)

        if not detail:
            logger.warning("RUZ financial sync: company %s (%s) not found in RUZ", company.id, company.ico)
            return 0

        statement_ids = detail.get("idUctovnychZavierok", []) or []
        if not statement_ids:
            return 0

        upserts = 0
        for statement_id in statement_ids[:max_statements]:
            statement = self.api.get_financial_statement_details(statement_id)
            if not statement:
                continue

            year = self._extract_year(statement)
            if not year:
                continue

            report_ids = statement.get("idUctovnychVykazov", []) or []
            if not report_ids:
                continue

            revenue, profit = self._extract_financials_from_reports(report_ids)
            if revenue is None and profit is None:
                continue

            CompanyFinancialResult.objects.update_or_create(
                company=company,
                year=year,
                defaults={
                    "revenue": revenue,
                    "profit": profit,
                    "source": "ruz_api",
                },
            )
            upserts += 1

        return upserts

    def _extract_year(self, statement: Dict) -> Optional[int]:
        # Prefer obdobieDo (YYYY-MM), fallback to obdobieOd.
        for key in ("obdobieDo", "obdobieOd"):
            value = statement.get(key)
            if not value:
                continue
            match = re.match(r"^(\d{4})", str(value))
            if match:
                return int(match.group(1))
        return None

    def _extract_financials_from_reports(self, report_ids: List[int]) -> Tuple[Optional[Decimal], Optional[Decimal]]:
        best_revenue = None
        best_cost = None
        best_profit = None

        for report_id in report_ids:
            report = self.api.get_financial_report_details(report_id)
            if not report:
                continue

            tables = ((report.get("obsah") or {}).get("tabulky") or [])
            template_tables = self._get_template_tables(report.get("idSablony"))

            for idx, table in enumerate(tables):
                template_table = template_tables[idx] if idx < len(template_tables) else None
                rev, cost, prof = self._extract_with_template(table, template_table)
                if rev is not None:
                    best_revenue = self._pick_better(best_revenue, rev)
                if cost is not None:
                    best_cost = self._pick_better(best_cost, cost)
                if prof is not None:
                    best_profit = self._pick_better(best_profit, prof)

            for table in tables:
                name = self._normalize_text(self._table_name(table))
                if not name:
                    continue

                total = self._extract_table_total(table)
                if total is None:
                    continue

                if any(k in name for k in self.REVENUE_KEYS):
                    best_revenue = self._pick_better(best_revenue, total)
                elif any(k in name for k in self.COST_KEYS):
                    best_cost = self._pick_better(best_cost, total)
                elif any(k in name for k in self.PROFIT_KEYS):
                    best_profit = self._pick_better(best_profit, total)

        if best_profit is None and best_revenue is not None and best_cost is not None:
            best_profit = best_revenue - best_cost

        return best_revenue, best_profit

    def _get_template_tables(self, template_id: Optional[int]) -> List[Dict]:
        if not template_id:
            return []
        if template_id not in self._template_cache:
            template = self.api.get_report_template_details(template_id) or {}
            self._template_cache[template_id] = template
        return self._template_cache[template_id].get("tabulky", []) or []

    def _extract_with_template(self, table: Dict, template_table: Optional[Dict]) -> Tuple[Optional[Decimal], Optional[Decimal], Optional[Decimal]]:
        if not template_table:
            return None, None, None

        data = table.get("data") or []
        rows = template_table.get("riadky") or []
        if not data or not rows:
            return None, None, None

        if len(data) >= len(rows) * 2:
            # Most reports carry current + previous period in alternating columns.
            get_row_value = lambda idx: self._to_decimal(data[idx * 2])
        else:
            get_row_value = lambda idx: self._to_decimal(data[idx]) if idx < len(data) else None

        revenue = None
        cost = None
        profit = None

        for idx, row in enumerate(rows):
            row_label = self._normalize_text(((row.get("text") or {}).get("sk") or ""))
            if not row_label:
                continue
            value = get_row_value(idx)
            if value is None:
                continue

            if ("vynosy z hospodarskej cinnosti spolu" in row_label) or ("trzby z predaja" in row_label and revenue is None):
                revenue = self._pick_better(revenue, value)
            if "naklady na hospodarsku cinnost spolu" in row_label:
                cost = self._pick_better(cost, value)
            if (
                "vysledok hospodarenia z hospodarskej cinnosti" in row_label
                or "vysledok hospodarenia za uctovne obdobie po zdaneni" in row_label
            ):
                profit = self._pick_better(profit, value)

        if profit is None and revenue is not None and cost is not None:
            profit = revenue - cost

        return revenue, cost, profit

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
        # In RUZ tables the total is usually at the end.
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

