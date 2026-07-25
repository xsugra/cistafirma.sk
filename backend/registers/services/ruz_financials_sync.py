import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional

from companies.models import Company, CompanyFinancialResult
from registers.integrations.ruz_api import RuzApi

logger = logging.getLogger(__name__)


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
        self.api = api or RuzApi()

    IFRS_TEMPLATE_ID = 709

    def sync_company(self, company: Company, max_statements: int = 30) -> int:
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
        found_ifrs = False
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

            financials, is_ifrs = self._extract_financials_from_reports(report_ids)
            if is_ifrs:
                found_ifrs = True
            if financials.get("revenue") is None and financials.get("profit") is None:
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

        return upserts

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
