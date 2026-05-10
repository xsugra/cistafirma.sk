from rest_framework import serializers

from companies.models import Company, CompanyFinancialResult
from registers.models import CompanySyncStatus


class AdminCompanyListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = [
            "id",
            "ico",
            "ruz_id",
            "nazov_UJ",
            "pravna_forma",
            "sidlo",
            "datum_zalozenia",
            "datum_zrusenia",
            "last_insurance_debt",
        ]


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
