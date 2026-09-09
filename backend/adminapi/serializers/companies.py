from django.db.models import Max
from rest_framework import serializers

from companies.models import Company, CompanyFinancialResult
from registers.models import CompanySyncStatus


class AdminCompanyListSerializer(serializers.ModelSerializer):
    has_orsr = serializers.SerializerMethodField()
    has_financials = serializers.SerializerMethodField()
    debt_state = serializers.SerializerMethodField()
    latest_revenue = serializers.SerializerMethodField()
    latest_profit = serializers.SerializerMethodField()
    latest_financial_year = serializers.SerializerMethodField()
    lead_score = serializers.SerializerMethodField()
    lead_confidence = serializers.SerializerMethodField()
    sync_failures = serializers.SerializerMethodField()
    is_blocked = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = [
            "id",
            "ico",
            "ruz_id",
            "nazov_UJ",
            "pravna_forma",
            "mesto",
            "ulica",
            "psc",
            "kraj",
            "okres",
            "sk_NACE",
            "velkost_organizacie",
            "sidlo",
            "datum_zalozenia",
            "datum_zrusenia",
            "vat_payer",
            "tax_reliability",
            "tax_debt",
            "debt_vszp",
            "debt_soc_poist",
            "last_insurance_debt",
            "has_orsr",
            "has_financials",
            "debt_state",
            "latest_financial_year",
            "latest_revenue",
            "latest_profit",
            "lead_score",
            "lead_confidence",
            "sync_failures",
            "is_blocked",
        ]

    def get_has_orsr(self, obj):
        annotated = getattr(obj, "has_orsr_flag", None)
        if annotated is not None:
            return bool(annotated)
        return hasattr(obj, "orsr_profile") and obj.orsr_profile is not None

    def get_has_financials(self, obj):
        annotated = getattr(obj, "has_financials_flag", None)
        if annotated is not None:
            return bool(annotated)
        return obj.financial_results.exists()

    def get_debt_state(self, obj):
        total = sum(float(v or 0) for v in (obj.debt_vszp, obj.debt_soc_poist, obj.tax_debt))
        return "debt_free" if total <= 0 else "has_debt"

    def get_latest_financial_year(self, obj):
        annotated = getattr(obj, "latest_financial_year", None)
        if annotated is not None:
            return annotated
        latest = obj.financial_results.order_by("-year").first()
        return latest.year if latest else None

    def get_latest_revenue(self, obj):
        annotated = getattr(obj, "latest_revenue", None)
        if annotated is not None:
            return annotated
        latest = obj.financial_results.order_by("-year").first()
        return latest.revenue if latest else None

    def get_latest_profit(self, obj):
        annotated = getattr(obj, "latest_profit", None)
        if annotated is not None:
            return annotated
        latest = obj.financial_results.order_by("-year").first()
        return latest.profit if latest else None

    def get_lead_score(self, obj):
        lead = getattr(obj, "lead_score", None)
        return lead.score if lead else None

    def get_lead_confidence(self, obj):
        enrichment = getattr(obj, "enrichment", None)
        return enrichment.confidence_score if enrichment else None

    def get_sync_failures(self, obj):
        annotated = getattr(obj, "sync_failures", None)
        if annotated is not None:
            return annotated or 0
        failures = obj.sync_statuses.aggregate(max_failures=Max("consecutive_failures"))
        return failures.get("max_failures") or 0

    def get_is_blocked(self, obj):
        annotated = getattr(obj, "is_blocked_flag", None)
        if annotated is not None:
            return bool(annotated)
        return obj.sync_statuses.filter(is_blocked=True).exists()


class _CompanyFinancialMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyFinancialResult
        fields = ["year", "revenue", "profit", "source", "updated_at"]


class _SyncStatusMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanySyncStatus
        fields = [
            "source",
            "last_attempted_at",
            "last_succeeded_at",
            "consecutive_failures",
            "last_error_type",
            "is_blocked",
            "next_retry_at",
        ]


class AdminCompanyDetailSerializer(serializers.ModelSerializer):
    financial_results = _CompanyFinancialMiniSerializer(many=True, read_only=True)
    sync_statuses = _SyncStatusMiniSerializer(many=True, read_only=True)

    class Meta:
        model = Company
        fields = "__all__"
        read_only_fields = ["financial_results", "sync_statuses"]
