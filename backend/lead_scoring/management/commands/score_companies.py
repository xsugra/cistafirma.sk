"""
Management command to score companies using the lead scoring engine.

Usage:
    python manage.py score_companies                    # Score all active companies
    python manage.py score_companies --city Trnava      # Score companies in specific city
    python manage.py score_companies --limit 50         # Score only top 50
    python manage.py score_companies --top-only         # Show only top 20 scored companies
"""

from django.core.management.base import BaseCommand
from django.db.models import Q

from companies.models import Company
from lead_scoring.services.scoring import LeadScoringService


class Command(BaseCommand):
    help = 'Score companies using the lead scoring engine'

    def add_arguments(self, parser):
        parser.add_argument(
            '--city',
            type=str,
            help='Filter companies by city',
        )
        parser.add_argument(
            '--nace',
            type=str,
            help='Filter companies by SK NACE code',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limit number of companies to score',
        )
        parser.add_argument(
            '--top-only',
            action='store_true',
            help='Show only top 20 scored companies',
        )
        parser.add_argument(
            '--min-score',
            type=int,
            default=0,
            help='Minimum score to display (default: 0)',
        )

    def handle(self, *args, **options):
        service = LeadScoringService()

        # If --top-only, just show top companies
        if options['top_only']:
            self.stdout.write(self.style.SUCCESS('🏆 Top 20 Scored Companies:'))
            self.stdout.write('=' * 80)

            top_companies = service.get_top_companies(limit=20, min_score=options['min_score'])

            for i, score_obj in enumerate(top_companies, 1):
                company = score_obj.company
                self.stdout.write(
                    f"{i:2d}. {score_obj.score:3d}pts | {company.ico} | {company.nazov_UJ[:50]}"
                )

            self.stdout.write('=' * 80)
            return

        # Build queryset based on filters
        queryset = Company.objects.filter(datum_zrusenia__isnull=True)

        if options['city']:
            queryset = queryset.filter(mesto__icontains=options['city'])
            self.stdout.write(f"Filtering by city: {options['city']}")

        if options['nace']:
            queryset = queryset.filter(sk_NACE__contains=options['nace'])
            self.stdout.write(f"Filtering by NACE: {options['nace']}")

        if options['limit']:
            queryset = queryset[:options['limit']]
            self.stdout.write(f"Limiting to: {options['limit']} companies")

        self.stdout.write(self.style.SUCCESS(f'\n🚀 Starting score calculation for {queryset.count()} companies...'))

        # Run scoring
        scored_count, created_count, updated_count = service.score_companies(queryset=queryset)

        self.stdout.write(self.style.SUCCESS(f'\n✅ Scoring complete!'))
        self.stdout.write(f'   Scored: {scored_count}')
        self.stdout.write(f'   Created: {created_count}')
        self.stdout.write(f'   Updated: {updated_count}')

        # Show top results
        self.stdout.write(self.style.SUCCESS('\n🏆 Top 10 Companies (this run):'))
        self.stdout.write('=' * 80)

        top_results = service.get_top_companies(limit=10, min_score=options['min_score'])

        for i, score_obj in enumerate(top_results, 1):
            company = score_obj.company
            self.stdout.write(
                f"{i:2d}. {score_obj.score:3d}pts | {company.ico} | {company.nazov_UJ[:50]}"
            )

        self.stdout.write('=' * 80)
