"""Reusable combined filtering for admin company listings."""

from __future__ import annotations

import json

from django.db.models import Exists, OuterRef, Q, QuerySet

from companies.models import Company, CompanyFinancialResult
from registers.models import CompanySyncStatus, OrsrCompanyProfile


class CompanyFilterService:
    """Apply combined filters to company querysets.

    Designed for the admin companies table and other admin-facing consumers.
    All filters are optional and combine with AND semantics across fields.
    """

    BOOL_TRUE = {"1", "true", "True", "yes", "on"}
    BOOL_FALSE = {"0", "false", "False", "no", "off"}

    PRESETS = [
        {
            # This preset asked for `has_financials` and `has_orsr` on top of the
            # four conditions its own description names, and returned nothing at
            # all: 0 of the 136 matching companies had a financial statement and
            # only 4 had an ORSR profile. Both were dropped rather than the
            # description reworded, because the description is what the operator
            # reads and the two conditions were a description of the *data we
            # wish we had*, not of the filter the preset claims to be. Measured
            # 2026-09-11: 0 results before, 136 after.
            #
            # The general shape is worth keeping in view: a filter that requires
            # a dataset we do not hold fails *silently* -- an empty table is
            # indistinguishable from "we have no such data", and the operator has
            # no way to tell which. See docs/SOURCE_DATA_INTEGRITY.md.
            "key": "it_trnava_no_debt",
            "name": "IT firmy v Trnave bez dlhov",
            "description": "Aktívne firmy v Trnave, s IT NACE a bez dlhov.",
            "filters": {
                "mesto": "Trnava",
                "psc": "917",
                "active": "1",
                "debt_state": "no_debt",
                "sk_nace": "62",
            },
        },
        {
            "key": "profitable_it",
            "name": "IT firmy v zisku",
            "description": "Firmy s IT NACE, ktoré majú zisk a platné finančné údaje.",
            "filters": {
                "sk_nace": "62",
                "profit_state": "profit",
                "has_financials": "1",
            },
        },
        {
            "key": "clean_and_healthy",
            "name": "Bez dlhov a zdravé syncy",
            "description": "Firmy bez dlhov s dobrým sync health a aktívnym profilom.",
            "filters": {
                "debt_state": "no_debt",
                "sync_state": "healthy",
                "active": "1",
            },
        },
    ]

    def apply(self, queryset: QuerySet[Company], params) -> QuerySet[Company]:
        qs = queryset
        annotation_names = set(getattr(getattr(qs, "query", None), "annotations", {}).keys())

        if q := params.get("q"):
            qs = qs.filter(
                Q(ico__icontains=q)
                | Q(nazov_UJ__icontains=q)
                | Q(dic__icontains=q)
                | Q(ic_dph__icontains=q)
                | Q(ulica__icontains=q)
                | Q(mesto__icontains=q)
                | Q(psc__icontains=q)
                | Q(ruz_id__icontains=q)
            )

        if pravna_forma := params.get("pravna_forma"):
            if isinstance(pravna_forma, (list, tuple)):
                qs = qs.filter(pravna_forma__in=[p for p in pravna_forma if p])
            else:
                values = [p.strip() for p in str(pravna_forma).split(",") if p.strip()]
                if values:
                    qs = qs.filter(pravna_forma__in=values)

        if sk_nace := params.get("sk_nace"):
            qs = qs.filter(sk_NACE__istartswith=sk_nace)

        if kraj := params.get("kraj"):
            qs = qs.filter(kraj__iexact=kraj)

        if okres := params.get("okres"):
            qs = qs.filter(okres__iexact=okres)

        if mesto := params.get("mesto"):
            qs = qs.filter(mesto__iexact=mesto)

        if psc := params.get("psc"):
            qs = qs.filter(psc__istartswith=psc)

        if sidlo := params.get("sidlo"):
            qs = qs.filter(sidlo__iexact=sidlo)

        if active := params.get("active"):
            active_str = str(active)
            if active_str in self.BOOL_TRUE:
                qs = qs.filter(datum_zrusenia__isnull=True)
            elif active_str in self.BOOL_FALSE:
                qs = qs.filter(datum_zrusenia__isnull=False)

        # Optimized: Use annotated flags if available, else use Exists subqueries (never use __isnull joins)
        if has_orsr := params.get("has_orsr"):
            if str(has_orsr) in self.BOOL_TRUE:
                if "has_orsr_flag" in annotation_names:
                    qs = qs.filter(has_orsr_flag=True)
                else:
                    # Use Exists subquery instead of join
                    qs = qs.filter(Exists(OrsrCompanyProfile.objects.filter(company_id=OuterRef("pk"))))
            elif str(has_orsr) in self.BOOL_FALSE:
                if "has_orsr_flag" in annotation_names:
                    qs = qs.filter(has_orsr_flag=False)
                else:
                    # Use negated Exists subquery instead of join
                    qs = qs.exclude(Exists(OrsrCompanyProfile.objects.filter(company_id=OuterRef("pk"))))

        if has_financials := params.get("has_financials"):
            if str(has_financials) in self.BOOL_TRUE:
                if "has_financials_flag" in annotation_names:
                    qs = qs.filter(has_financials_flag=True)
                else:
                    # Use Exists subquery instead of join
                    qs = qs.filter(Exists(CompanyFinancialResult.objects.filter(company_id=OuterRef("pk"))))
            elif str(has_financials) in self.BOOL_FALSE:
                if "has_financials_flag" in annotation_names:
                    qs = qs.filter(has_financials_flag=False)
                else:
                    # Use negated Exists subquery instead of join
                    qs = qs.exclude(Exists(CompanyFinancialResult.objects.filter(company_id=OuterRef("pk"))))

        debt_filter = params.get("debt_state")
        if debt_filter:
            debt_q = Q(debt_vszp__gt=0) | Q(debt_soc_poist__gt=0) | Q(tax_debt__gt=0)
            if debt_filter == "has_debt":
                qs = qs.filter(debt_q)
            elif debt_filter == "no_debt":
                qs = qs.exclude(debt_q)

        if vat_payer := params.get("vat_payer"):
            if str(vat_payer) in self.BOOL_TRUE:
                qs = qs.filter(vat_payer=True)
            elif str(vat_payer) in self.BOOL_FALSE:
                qs = qs.filter(vat_payer=False)

        if tax_reliability := params.get("tax_reliability"):
            qs = qs.filter(tax_reliability__iexact=tax_reliability)

        if size := params.get("velkost_organizacie"):
            qs = qs.filter(velkost_organizacie__iexact=size)

        if region := params.get("region"):
            qs = qs.filter(kraj__iexact=region)

        lead_score_min = self._to_int(params.get("lead_score_min"))
        if lead_score_min is not None:
            qs = qs.filter(lead_score__score__gte=lead_score_min)

        lead_score_max = self._to_int(params.get("lead_score_max"))
        if lead_score_max is not None:
            qs = qs.filter(lead_score__score__lte=lead_score_max)

        confidence_min = self._to_int(params.get("confidence_min"))
        if confidence_min is not None:
            qs = qs.filter(enrichment__confidence_score__gte=confidence_min)

        if profit_state := params.get("profit_state"):
            qs = self._apply_profit_state(qs, profit_state, annotation_names)

        if revenue_state := params.get("revenue_state"):
            qs = self._apply_revenue_state(qs, revenue_state, annotation_names)

        if debt_amount_state := params.get("debt_amount_state"):
            qs = self._apply_debt_amount_state(qs, debt_amount_state)

        if sync_state := params.get("sync_state"):
            qs = self._apply_sync_state(qs, sync_state, annotation_names)

        latest_financial_year = self._to_int(params.get("financial_year"))
        if latest_financial_year is not None:
            if "latest_financial_year" in annotation_names:
                qs = qs.filter(latest_financial_year=latest_financial_year)
            else:
                # Use Exists subquery instead of join to avoid cartesian product
                qs = qs.filter(Exists(CompanyFinancialResult.objects.filter(company_id=OuterRef("pk"), year=latest_financial_year)))

        builder = self._parse_builder(params.get("filter_builder"))
        if builder:
            builder_q = self._builder_to_q(builder, annotation_names)
            if builder_q is not None:
                qs = qs.filter(builder_q)

        # No DISTINCT needed anymore - all joins use Exists() or annotated flags
        return qs.order_by("-id")

    def _apply_profit_state(self, queryset: QuerySet[Company], value: str, annotation_names: set[str] | None = None) -> QuerySet[Company]:
        annotation_names = annotation_names or set()
        if value == "profit":
            if "latest_profit" in annotation_names:
                return queryset.filter(latest_profit__gt=0)
            if "has_profit" in annotation_names:
                return queryset.filter(has_profit=True)
            # Use Exists subquery to avoid join
            return queryset.filter(Exists(CompanyFinancialResult.objects.filter(company_id=OuterRef("pk"), profit__gt=0)))
        if value == "loss":
            if "latest_profit" in annotation_names:
                return queryset.filter(latest_profit__lt=0)
            if "has_loss" in annotation_names:
                return queryset.filter(has_loss=True)
            # Use Exists subquery to avoid join
            return queryset.filter(Exists(CompanyFinancialResult.objects.filter(company_id=OuterRef("pk"), profit__lt=0)))
        if value == "break_even":
            if "latest_profit" in annotation_names:
                return queryset.filter(latest_profit=0)
            # Use Exists subquery to avoid join
            return queryset.filter(Exists(CompanyFinancialResult.objects.filter(company_id=OuterRef("pk"), profit=0)))
        if value == "unknown":
            if "latest_profit" in annotation_names:
                return queryset.filter(latest_profit__isnull=True)
            # Use Exists subquery to avoid join
            return queryset.exclude(Exists(CompanyFinancialResult.objects.filter(company_id=OuterRef("pk"), profit__isnull=False)))
        return queryset

    def _apply_revenue_state(self, queryset: QuerySet[Company], value: str, annotation_names: set[str] | None = None) -> QuerySet[Company]:
        annotation_names = annotation_names or set()
        if value == "revenue":
            if "latest_revenue" in annotation_names:
                return queryset.filter(latest_revenue__gt=0)
            if "has_revenue" in annotation_names:
                return queryset.filter(has_revenue=True)
            # Use Exists subquery to avoid join
            return queryset.filter(Exists(CompanyFinancialResult.objects.filter(company_id=OuterRef("pk"), revenue__gt=0)))
        if value == "no_revenue":
            if "latest_revenue" in annotation_names:
                return queryset.filter(Q(latest_revenue__lte=0) | Q(latest_revenue__isnull=True))
            # Use Exists subquery to avoid join
            return queryset.exclude(Exists(CompanyFinancialResult.objects.filter(company_id=OuterRef("pk"), revenue__gt=0)))
        return queryset

    def _apply_debt_amount_state(self, queryset: QuerySet[Company], value: str) -> QuerySet[Company]:
        debt_q = Q(debt_vszp__gt=0) | Q(debt_soc_poist__gt=0) | Q(tax_debt__gt=0)
        if value == "debt_free":
            return queryset.exclude(debt_q)
        if value == "has_debt":
            return queryset.filter(debt_q)
        return queryset

    def _apply_sync_state(self, queryset: QuerySet[Company], value: str, annotation_names: set[str] | None = None) -> QuerySet[Company]:
        annotation_names = annotation_names or set()
        if value == "healthy":
            if "sync_failures" in annotation_names:
                return queryset.filter(sync_failures=0)
            # Use Exists subquery with negation instead of join
            return queryset.exclude(Exists(CompanySyncStatus.objects.filter(company_id=OuterRef("pk"), consecutive_failures__gt=0)))
        if value == "failing":
            if "sync_failures" in annotation_names:
                return queryset.filter(sync_failures__gt=0)
            # Use Exists subquery instead of join
            return queryset.filter(Exists(CompanySyncStatus.objects.filter(company_id=OuterRef("pk"), consecutive_failures__gt=0)))
        if value == "blocked":
            if "is_blocked_flag" in annotation_names:
                return queryset.filter(is_blocked_flag=True)
            # Use Exists subquery instead of join
            return queryset.filter(Exists(CompanySyncStatus.objects.filter(company_id=OuterRef("pk"), is_blocked=True)))
        return queryset

    def _to_int(self, value) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def get_presets(self) -> list[dict[str, object]]:
        return self.PRESETS

    def get_preset(self, key: str) -> dict[str, object] | None:
        for preset in self.PRESETS:
            if preset["key"] == key:
                return preset
        return None

    def _parse_builder(self, value):
        if not value:
            return None
        if isinstance(value, dict):
            return value
        if isinstance(value, (list, tuple)):
            return {"logic": "and", "children": list(value)}
        try:
            data = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None

    def _builder_to_q(self, node, annotation_names: set[str] | None = None) -> Q | None:
        if not isinstance(node, dict):
            return None

        if node.get("type") == "condition" or "field" in node:
            return self._condition_to_q(node, annotation_names)

        children = node.get("children") or []
        child_qs = [q for q in (self._builder_to_q(child, annotation_names) for child in children) if q is not None]
        if not child_qs:
            return None

        logic = str(node.get("logic") or node.get("op") or "and").lower()
        result = child_qs[0]
        for child_q in child_qs[1:]:
            result = result | child_q if logic == "or" else result & child_q
        return result

    def _condition_to_q(self, condition: dict, annotation_names: set[str] | None = None) -> Q | None:
        annotation_names = annotation_names or set()
        field = str(condition.get("field") or "").strip()
        operator = str(condition.get("operator") or "equals").strip().lower()
        value = condition.get("value")
        if value in (None, ""):
            return None

        if field == "q":
            q = Q(ico__icontains=value) | Q(nazov_UJ__icontains=value) | Q(dic__icontains=value) | Q(ic_dph__icontains=value) | Q(ulica__icontains=value) | Q(mesto__icontains=value) | Q(psc__icontains=value) | Q(ruz_id__icontains=value)
            return q

        if field in {"mesto", "psc", "kraj", "okres", "sidlo", "sk_nace", "tax_reliability", "pravna_forma", "velkost_organizacie"}:
            field_name = "sk_NACE" if field == "sk_nace" else field
            lookup = {
                "contains": "istartswith" if field in {"mesto", "psc", "sidlo", "sk_nace"} else "iexact",
                "equals": "iexact",
            }.get(operator, "iexact")
            return Q(**{f"{field_name}__{lookup}": value})

        if field == "active":
            return Q(datum_zrusenia__isnull=str(value) in self.BOOL_TRUE)

        if field in {"has_orsr", "has_financials", "vat_payer"}:
             bool_value = str(value) in self.BOOL_TRUE
             if field == "vat_payer":
                 return Q(vat_payer=bool_value)
             if field == "has_orsr":
                 if "has_orsr_flag" in annotation_names:
                     return Q(has_orsr_flag=bool_value)
                 # Fallback to Exists subquery (no implicit join)
                 orsr_exists = Exists(OrsrCompanyProfile.objects.filter(company_id=OuterRef("pk")))
                 return Q(orsr_exists) if bool_value else ~Q(orsr_exists)
             if field == "has_financials":
                 if "has_financials_flag" in annotation_names:
                     return Q(has_financials_flag=bool_value)
                 # Fallback to Exists subquery (no implicit join)
                 financials_exists = Exists(CompanyFinancialResult.objects.filter(company_id=OuterRef("pk")))
                 return Q(financials_exists) if bool_value else ~Q(financials_exists)
             return None

        if field == "debt_state":
            debt_q = Q(debt_vszp__gt=0) | Q(debt_soc_poist__gt=0) | Q(tax_debt__gt=0)
            if value == "has_debt":
                return debt_q
            if value == "no_debt":
                return ~debt_q
            return None

        if field == "profit_state":
            if value == "profit":
                if "latest_profit" in annotation_names:
                    return Q(latest_profit__gt=0)
                # Fallback to Exists subquery
                return Q(Exists(CompanyFinancialResult.objects.filter(company_id=OuterRef("pk"), profit__gt=0)))
            if value == "loss":
                if "latest_profit" in annotation_names:
                    return Q(latest_profit__lt=0)
                # Fallback to Exists subquery
                return Q(Exists(CompanyFinancialResult.objects.filter(company_id=OuterRef("pk"), profit__lt=0)))
            if value == "break_even":
                if "latest_profit" in annotation_names:
                    return Q(latest_profit=0)
                # Fallback to Exists subquery
                return Q(Exists(CompanyFinancialResult.objects.filter(company_id=OuterRef("pk"), profit=0)))
            if value == "unknown":
                if "latest_profit" in annotation_names:
                    return Q(latest_profit__isnull=True)
                # Fallback to Exists subquery
                return ~Q(Exists(CompanyFinancialResult.objects.filter(company_id=OuterRef("pk"), profit__isnull=False)))
            # Without annotation, skip builder filter - fallback in apply() will handle it
            return None

        if field == "revenue_state":
            if value == "revenue":
                if "latest_revenue" in annotation_names:
                    return Q(latest_revenue__gt=0)
                # Fallback to Exists subquery
                return Q(Exists(CompanyFinancialResult.objects.filter(company_id=OuterRef("pk"), revenue__gt=0)))
            if value == "no_revenue":
                if "latest_revenue" in annotation_names:
                    return Q(latest_revenue__lte=0) | Q(latest_revenue__isnull=True)
                # Fallback to Exists subquery
                return ~Q(Exists(CompanyFinancialResult.objects.filter(company_id=OuterRef("pk"), revenue__gt=0)))
            # Without annotation, skip builder filter - fallback in apply() will handle it
            return None

        if field == "debt_amount_state":
            debt_q = Q(debt_vszp__gt=0) | Q(debt_soc_poist__gt=0) | Q(tax_debt__gt=0)
            if value == "has_debt":
                return debt_q
            if value == "debt_free":
                return ~debt_q
            return None

        if field == "sync_state":
            if value == "healthy":
                if "sync_failures" in annotation_names:
                    return Q(sync_failures=0)
                # Fallback to Exists subquery with negation
                return ~Q(Exists(CompanySyncStatus.objects.filter(company_id=OuterRef("pk"), consecutive_failures__gt=0)))
            if value == "failing":
                if "sync_failures" in annotation_names:
                    return Q(sync_failures__gt=0)
                # Fallback to Exists subquery
                return Q(Exists(CompanySyncStatus.objects.filter(company_id=OuterRef("pk"), consecutive_failures__gt=0)))
            if value == "blocked":
                if "is_blocked_flag" in annotation_names:
                    return Q(is_blocked_flag=True)
                # Fallback to Exists subquery
                return Q(Exists(CompanySyncStatus.objects.filter(company_id=OuterRef("pk"), is_blocked=True)))
            # Without annotation, skip builder filter - fallback in apply() will handle it
            return None

        if field == "financial_year":
            integer_value = self._to_int(value)
            if integer_value is None:
                return None
            if "latest_financial_year" in annotation_names:
                lookup = {
                    "gte": "gte",
                    "lte": "lte",
                    "gt": "gt",
                    "lt": "lt",
                }.get(operator, "exact")
                return Q(**{f"latest_financial_year__{lookup}": integer_value})
            # Fallback to Exists subquery with proper lookup
            lookup_map = {
                "gte": "year__gte",
                "lte": "year__lte",
                "gt": "year__gt",
                "lt": "year__lt",
                "exact": "year",
            }
            year_field = lookup_map.get(operator, "year")
            filter_kwargs = {year_field: integer_value}
            return Q(Exists(CompanyFinancialResult.objects.filter(company_id=OuterRef("pk"), **filter_kwargs)))

        if field in {"lead_score", "confidence_min", "confidence_score"}:
            integer_value = self._to_int(value)
            if integer_value is None:
                return None
            field_name = {
                "lead_score": "lead_score__score",
                "confidence_min": "enrichment__confidence_score",
                "confidence_score": "enrichment__confidence_score",
            }[field]
            lookup = {
                "gte": "gte",
                "lte": "lte",
                "gt": "gt",
                "lt": "lt",
            }.get(operator, "exact")
            return Q(**{f"{field_name}__{lookup}": integer_value})

        return None

