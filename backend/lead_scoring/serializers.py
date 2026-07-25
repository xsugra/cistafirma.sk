"""Serializers for lead scoring API endpoints."""

from rest_framework import serializers

from .models import CompanyScore, CompanyEnrichment


class CompanyScoreSerializer(serializers.ModelSerializer):
    """Serializer for CompanyScore model."""

    company_ico = serializers.CharField(source='company.ico', read_only=True)
    company_name = serializers.CharField(source='company.nazov_UJ', read_only=True)
    company_nace = serializers.CharField(source='company.sk_NACE', read_only=True)

    class Meta:
        model = CompanyScore
        fields = [
            'id',
            'company_ico',
            'company_name',
            'company_nace',
            'score',
            'nace_relevance_score',
            'data_completeness_score',
            'financial_health_score',
            'debt_penalty',
            'breakdown',
            'calculated_at',
            'updated_at',
        ]
        read_only_fields = fields


class CompanyEnrichmentSerializer(serializers.ModelSerializer):
    """Serializer for CompanyEnrichment model."""

    company_ico = serializers.CharField(source='company.ico', read_only=True)
    company_name = serializers.CharField(source='company.nazov_UJ', read_only=True)

    class Meta:
        model = CompanyEnrichment
        fields = [
            'id',
            'company_ico',
            'company_name',
            'tech_stack',
            'company_summary',
            'outreach_angle',
            'outreach_draft',
            'sources_used',
            'confidence_score',
            'enriched_at',
            'updated_at',
        ]
        read_only_fields = fields


class LeadScoreReportSerializer(serializers.Serializer):
    """Serializer for lead scoring report (read-only)."""

    total_companies = serializers.IntegerField(read_only=True)
    avg_score = serializers.FloatField(read_only=True)
    high_score_count = serializers.IntegerField(read_only=True)
    medium_score_count = serializers.IntegerField(read_only=True)
    low_score_count = serializers.IntegerField(read_only=True)
    top_companies = CompanyScoreSerializer(many=True, read_only=True)
    score_distribution = serializers.DictField(read_only=True)
    last_scored_at = serializers.DateTimeField(read_only=True)
