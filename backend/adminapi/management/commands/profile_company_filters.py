from __future__ import annotations

import json
from dataclasses import dataclass

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from adminapi.services import CompanyFilterService
from adminapi.views.companies import AdminCompanyViewSet

@dataclass(frozen=True)
class ProfileCase:
    name: str
    params: dict[str, str]
    light_report: bool = True


class Command(BaseCommand):
    help = "Profile company list/report queries with EXPLAIN ANALYZE for representative filters."

    def add_arguments(self, parser):
        parser.add_argument("--case", action="append", default=[], help="Profile a named case (may be supplied multiple times).")
        parser.add_argument("--params", default="", help='Inline JSON dict of query params to profile, e.g. "{\"mesto\":\"Trnava\"}".')
        parser.add_argument("--mode", choices=["list", "report", "both"], default="both", help="Which query shape to profile.")
        parser.add_argument("--analyze", action="store_true", help="Use EXPLAIN ANALYZE. Without this flag, only EXPLAIN is run.")
        parser.add_argument("--verbose-sql", action="store_true", help="Print the exact generated SQL before explaining it.")
        parser.add_argument("--cache-key-only", action="store_true", help="Only compute the report cache key for the supplied params and exit.")
        parser.add_argument("--force-analyze", action="store_true", help="Force EXPLAIN ANALYZE even when the backend would normally fall back to a plain plan.")

    def handle(self, *args, **options):
        cases = self._load_cases(options)
        if not cases:
            raise CommandError("No profiling cases resolved. Provide --case or --params.")

        service = CompanyFilterService()
        view = AdminCompanyViewSet()

        for case in cases:
            self.stdout.write(self.style.SUCCESS(f"\n=== CASE: {case.name} ==="))
            self.stdout.write(f"Params: {json.dumps(case.params, ensure_ascii=False, sort_keys=True)}")

            if options["cache_key_only"]:
                key = view._report_cache_key(self._fake_request(case.params), mode="light" if case.light_report else "full")
                self.stdout.write(f"Report cache key: {key}")
                continue

            queryset = service.apply(self._base_queryset(), case.params)
            self._profile_case(queryset, case, options)

    def _load_cases(self, options) -> list[ProfileCase]:
        cases: list[ProfileCase] = []

        named_cases = {
            "trnava_nace_62": ProfileCase("trnava_nace_62", {"mesto": "Trnava", "sk_nace": "62", "active": "1"}),
            "heavy_debt_filter": ProfileCase("heavy_debt_filter", {"debt_state": "has_debt", "active": "1"}),
            "full_builder_or": ProfileCase(
                "full_builder_or",
                {
                    "filter_builder": json.dumps(
                        {
                            "id": "root",
                            "type": "group",
                            "logic": "and",
                            "children": [
                                {"id": "c1", "type": "condition", "field": "mesto", "operator": "contains", "value": "Bratislava"},
                                {
                                    "id": "g1",
                                    "type": "group",
                                    "logic": "or",
                                    "children": [
                                        {"id": "c2", "type": "condition", "field": "sk_nace", "operator": "contains", "value": "62"},
                                        {"id": "c3", "type": "condition", "field": "sk_nace", "operator": "contains", "value": "70"},
                                    ],
                                },
                            ],
                        },
                        ensure_ascii=False,
                    )
                },
            ),
        }

        for name in options.get("case") or []:
            case = named_cases.get(name)
            if case:
                cases.append(case)
            else:
                self.stdout.write(self.style.WARNING(f"Unknown case '{name}', skipping."))

        raw_params = (options.get("params") or "").strip()
        if raw_params:
            try:
                params = json.loads(raw_params)
            except json.JSONDecodeError as exc:
                raise CommandError(f"--params must be valid JSON: {exc}") from exc
            if not isinstance(params, dict):
                raise CommandError("--params must decode to a JSON object")
            cases.append(ProfileCase(name="inline_params", params={str(k): self._stringify(v) for k, v in params.items()}))

        return cases

    def _profile_case(self, queryset, case: ProfileCase, options):
        explain_kwargs = self._explain_kwargs(options)

        if options["mode"] in {"list", "both"}:
            if options["verbose_sql"]:
                self.stdout.write("--- LIST SQL ---")
                self.stdout.write(str(queryset.query))
            self.stdout.write("--- LIST EXPLAIN ---")
            self.stdout.write(queryset.explain(**explain_kwargs))

        if options["mode"] in {"report", "both"}:
            if options["verbose_sql"]:
                self.stdout.write("--- REPORT BASE SQL ---")
                self.stdout.write(str(queryset.query))
            self.stdout.write("--- REPORT EXPLAIN (summary aggregates) ---")
            self._print_report_explain(queryset, case, explain_kwargs)

    def _explain_kwargs(self, options):
        analyze = bool(options["analyze"])
        if connection.vendor == "sqlite" and not options.get("force_analyze"):
            analyze = False
        kwargs = {}
        if connection.vendor != "sqlite":
            kwargs.update({"analyze": analyze, "verbose": True})
            kwargs["format"] = "text"
            kwargs["buffers"] = True
        return kwargs

    def _print_report_explain(self, queryset, case: ProfileCase, explain_kwargs):
        self.stdout.write("[raw filtered queryset]")
        self.stdout.write(self._safe_explain(queryset, explain_kwargs))

        self.stdout.write("[count wrapper]")
        self.stdout.write(self._explain_count_sql(queryset, analyze=bool(explain_kwargs.get("analyze", False))))

        self.stdout.write("[top-10 wrapper]")
        top_qs = queryset.order_by("-lead_score__score", "-id")[:10]
        if explain_kwargs.get("verbose"):
            self.stdout.write(str(top_qs.query))
        self.stdout.write(self._safe_explain(top_qs, explain_kwargs))

        if case.light_report:
            self.stdout.write("[note] light report avoids expensive avg/sum/top-company serialization in the API path.")

    def _explain_count_sql(self, queryset, analyze: bool) -> str:
        base_qs = queryset.order_by().values("pk")
        sql, params = base_qs.query.sql_with_params()
        if connection.vendor == "sqlite":
            wrapper = f"EXPLAIN QUERY PLAN SELECT COUNT(*) FROM ({sql}) company_count"
        else:
            wrapper = f"EXPLAIN ({'ANALYZE, ' if analyze else ''}VERBOSE, BUFFERS) SELECT COUNT(*) FROM ({sql}) company_count"
        with connection.cursor() as cursor:
            cursor.execute(wrapper, params)
            rows = cursor.fetchall()
        return "\n".join(str(row[0]) for row in rows)

    def _safe_explain(self, queryset, explain_kwargs) -> str:
        try:
            if connection.vendor == "sqlite":
                return queryset.explain()
            return queryset.explain(**explain_kwargs)
        except Exception as exc:
            return f"[explain unavailable: {exc}]"

    def _base_queryset(self):
        return Company.objects.all().select_related("orsr_profile", "lead_score", "enrichment")

    def _fake_request(self, params: dict[str, str]):
        class _Req:
            def __init__(self, qp):
                self.query_params = qp

        return _Req(params)

    def _stringify(self, value):
        if value is None:
            return ""
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return str(value)
