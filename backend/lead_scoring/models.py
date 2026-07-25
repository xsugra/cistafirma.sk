"""
Lead scoring and enrichment models.

CompanyScore: Stores the calculated lead score with explainable breakdowns.
CompanyEnrichment: Stores AI-generated enrichment data (tech stack, summary, outreach draft, etc.).
"""

from django.db import models
from django.utils import timezone

from companies.models import Company


class CompanyScore(models.Model):
    """
    Calculated lead score for a company with explainable breakdowns.
    One record per company; updated when scoring runs.
    """

    company = models.OneToOneField(
        Company,
        on_delete=models.CASCADE,
        related_name='lead_score',
        verbose_name='Firma',
    )

    # Overall score (0-100)
    score = models.PositiveIntegerField(
        default=0,
        verbose_name='Celkové skóre',
        help_text='Výsledné skóre od 0 do 100',
    )

    # Score breakdowns (explainability)
    # Business fit signals (max 40 points)
    nace_relevance_score = models.PositiveIntegerField(
        default=0,
        verbose_name='SK NACE relevancia',
        help_text='Skóre za zhodnosť s cieľovým SK NACE (0-40)',
    )

    # Data quality signals (max 30 points)
    data_completeness_score = models.PositiveIntegerField(
        default=0,
        verbose_name='Úplnosť údajov',
        help_text='Skóre za dostupnosť ORSR, financií, VšZP (0-30)',
    )

    financial_health_score = models.PositiveIntegerField(
        default=0,
        verbose_name='Finančné zdravie',
        help_text='Skóre za absenciu dlhov a pozitívnu dynamiku (0-30)',
    )

    # Risk signals (penalties, max -30 points)
    debt_penalty = models.IntegerField(
        default=0,
        verbose_name='Penalizácia za dlhy',
        help_text='Penalizácia za prítomnosť dlhov (0 alebo negatívny)',
    )

    # JSON breakdown for detailed analysis
    breakdown = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Detailný rozpad',
        help_text='Detailný rozpad signálov a bodov',
    )

    # Metadata
    calculated_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Vypočítané',
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Aktualizované',
    )

    class Meta:
        verbose_name = 'Skóre firmy'
        verbose_name_plural = 'Skóre firiem'
        ordering = ['-score', '-updated_at']
        indexes = [
            models.Index(fields=['-score']),
            models.Index(fields=['-updated_at']),
        ]

    def __str__(self):
        return f"{self.company.nazov_UJ} ({self.company.ico}) - {self.score} bodov"


class CompanyEnrichment(models.Model):
    """
    AI-generated enrichment data for a company.
    Includes tech stack inference, company summary, and suggested outreach angle.
    """

    company = models.OneToOneField(
        Company,
        on_delete=models.CASCADE,
        related_name='enrichment',
        verbose_name='Firma',
    )

    # Tech stack and business info
    tech_stack = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Technologický základ',
        help_text='Inferovaný tech stack (jazyky, frameworky, tools)',
    )

    # AI-generated summary
    company_summary = models.TextField(
        blank=True,
        default='',
        verbose_name='Zhrnutie firmy',
        help_text='Gpt-4-generated business summary (SK)',
    )

    # Suggested outreach angle
    outreach_angle = models.TextField(
        blank=True,
        default='',
        verbose_name='Uhol pre kontaktovanie',
        help_text='Personalizovaný návrh na kontaktovanie',
    )

    outreach_draft = models.TextField(
        blank=True,
        default='',
        verbose_name='Návrh správy',
        help_text='Návrh otváracej správy (SK)',
    )

    # Data sources
    sources_used = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Použité zdroje',
        help_text='Zoznam zdrojov, z ktorých pochádza obohacenie',
    )

    # Confidence score (0-100)
    confidence_score = models.PositiveIntegerField(
        default=50,
        verbose_name='Spoľahlivosť',
        help_text='Stupeň spoľahlivosti AI obohacenia (0-100)',
    )

    # Metadata
    enriched_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Obohacené',
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Aktualizované',
    )

    class Meta:
        verbose_name = 'Obohacenie firmy'
        verbose_name_plural = 'Obohacenie firiem'
        ordering = ['-confidence_score', '-updated_at']

    def __str__(self):
        return f"Obohacenie: {self.company.nazov_UJ} ({self.company.ico})"
