from django.contrib import admin
from django.db.models import Q
from django.urls import reverse
from django.utils.html import format_html
from unfold.admin import ModelAdmin

from .models import CompanyScore, CompanyEnrichment


@admin.register(CompanyScore)
class CompanyScoreAdmin(ModelAdmin):
    """Admin interface for company lead scores."""

    list_display = (
        'score_badge',
        'company_link',
        'ico',
        'nace_code',
        'nace_score_display',
        'data_quality_display',
        'financial_health_display',
        'debt_penalty_display',
        'updated_at_short',
    )

    list_filter = (
        'score',
        'nace_relevance_score',
        'financial_health_score',
        'updated_at',
    )

    search_fields = (
        'company__ico',
        'company__nazov_UJ',
    )

    readonly_fields = (
        'company',
        'score',
        'nace_relevance_score',
        'data_completeness_score',
        'financial_health_score',
        'debt_penalty',
        'breakdown_pretty',
        'calculated_at',
        'updated_at',
    )

    fieldsets = (
        ('Company', {
            'fields': ('company',),
        }),
        ('Overall Score', {
            'fields': ('score', 'updated_at', 'calculated_at'),
        }),
        ('Score Breakdown', {
            'fields': (
                'nace_relevance_score',
                'data_completeness_score',
                'financial_health_score',
                'debt_penalty',
            ),
            'classes': ('collapse',),
        }),
        ('Detailed Analysis', {
            'fields': ('breakdown_pretty',),
            'classes': ('collapse',),
        }),
    )

    def score_badge(self, obj):
        """Display score with color coding."""
        score = obj.score
        if score >= 70:
            color = '#28a745'  # Green
            label = '🟢'
        elif score >= 50:
            color = '#ffc107'  # Yellow
            label = '🟡'
        else:
            color = '#dc3545'  # Red
            label = '🔴'

        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-weight: bold;">{} {}</span>',
            color,
            label,
            score
        )

    score_badge.short_description = 'Score'

    def company_link(self, obj):
        """Link to company."""
        url = reverse('admin:companies_company_change', args=[obj.company.pk])
        return format_html('<a href="{}">{}</a>', url, obj.company.nazov_UJ[:50])

    company_link.short_description = 'Company'

    def ico(self, obj):
        """Display ICO."""
        return obj.company.ico

    ico.short_description = 'IČO'

    def nace_code(self, obj):
        """Display SK NACE code."""
        return obj.company.sk_NACE or '—'

    nace_code.short_description = 'SK NACE'

    def nace_score_display(self, obj):
        """Display NACE score with points."""
        return f"{obj.nace_relevance_score}/40"

    nace_score_display.short_description = 'NACE (40)'

    def data_quality_display(self, obj):
        """Display data quality score."""
        return f"{obj.data_completeness_score}/30"

    data_quality_display.short_description = 'Data (30)'

    def financial_health_display(self, obj):
        """Display financial health score."""
        return f"{obj.financial_health_score}/30"

    financial_health_display.short_description = 'Finance (30)'

    def debt_penalty_display(self, obj):
        """Display debt penalty."""
        if obj.debt_penalty == 0:
            return format_html('<span style="color: green;">{}</span>', '✓ None')
        else:
            return format_html('<span style="color: red;">{}</span>', obj.debt_penalty)

    debt_penalty_display.short_description = 'Debt Penalty'

    def updated_at_short(self, obj):
        """Display short date format."""
        return obj.updated_at.strftime('%Y-%m-%d %H:%M')

    updated_at_short.short_description = 'Updated'

    def breakdown_pretty(self, obj):
        """Display breakdown as formatted JSON."""
        import json
        try:
            pretty_json = json.dumps(obj.breakdown, indent=2, ensure_ascii=False)
            return format_html(
                '<pre style="background-color: #f5f5f5; padding: 10px; border-radius: 4px; overflow-x: auto;">{}</pre>',
                pretty_json
            )
        except:
            return '—'

    breakdown_pretty.short_description = 'Detailed Breakdown'

    def has_add_permission(self, request):
        """Disable add button - scores are calculated only."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Disable delete button."""
        return False

    ordering = ['-score', '-updated_at']


@admin.register(CompanyEnrichment)
class CompanyEnrichmentAdmin(ModelAdmin):
    """Admin interface for company enrichment data."""

    list_display = (
        'company_link',
        'ico',
        'confidence_badge',
        'sources_count',
        'enriched_at_short',
    )

    list_filter = (
        'confidence_score',
        'enriched_at',
        'updated_at',
    )

    search_fields = (
        'company__ico',
        'company__nazov_UJ',
        'company_summary',
    )

    readonly_fields = (
        'company',
        'enriched_at',
        'updated_at',
    )

    fieldsets = (
        ('Company', {
            'fields': ('company', 'confidence_score'),
        }),
        ('Business Intelligence', {
            'fields': ('company_summary', 'tech_stack'),
        }),
        ('Outreach', {
            'fields': ('outreach_angle', 'outreach_draft'),
        }),
        ('Metadata', {
            'fields': ('sources_used', 'enriched_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def company_link(self, obj):
        """Link to company."""
        url = reverse('admin:companies_company_change', args=[obj.company.pk])
        return format_html('<a href="{}">{}</a>', url, obj.company.nazov_UJ[:50])

    company_link.short_description = 'Company'

    def ico(self, obj):
        """Display ICO."""
        return obj.company.ico

    ico.short_description = 'IČO'

    def confidence_badge(self, obj):
        """Display confidence with color coding."""
        score = obj.confidence_score
        if score >= 80:
            color = '#28a745'  # Green
            label = '✓'
        elif score >= 60:
            color = '#ffc107'  # Yellow
            label = '⊙'
        else:
            color = '#dc3545'  # Red
            label = '⚠'

        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{} {}%</span>',
            color,
            label,
            score
        )

    confidence_badge.short_description = 'Confidence'

    def sources_count(self, obj):
        """Display number of sources used."""
        count = len(obj.sources_used) if obj.sources_used else 0
        return f'{count} sources'

    sources_count.short_description = 'Sources'

    def enriched_at_short(self, obj):
        """Display short date format."""
        return obj.enriched_at.strftime('%Y-%m-%d %H:%M')

    enriched_at_short.short_description = 'Enriched'

    def has_add_permission(self, request):
        """Disable add button - enrichment is AI-generated."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Disable delete button."""
        return False

    ordering = ['-confidence_score', '-updated_at']
