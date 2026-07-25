"""Tests for lead scoring functionality."""

from decimal import Decimal

from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from companies.models import Company, CompanyFinancialResult
from lead_scoring.models import CompanyScore, CompanyEnrichment
from lead_scoring.services.scoring import LeadScoringService
from registers.models import OrsrCompanyProfile


class LeadScoringServiceTests(TransactionTestCase):
    """Test the lead scoring service."""

    def setUp(self):
        """Set up test companies."""
        self.service = LeadScoringService()

        # Create a test company with good signals
        self.good_company = Company.objects.create(
            ruz_id=1,
            ico='12345678',
            nazov_UJ='TechCorp s.r.o.',
            sk_NACE='62.01',  # Target NACE code
            velkost_organizacie='mikro',
            druh_vlastnictva='domáce',
            debt_vszp=Decimal('0'),
            debt_soc_poist=Decimal('0'),
            tax_debt=Decimal('0'),
            vat_payer=True,
            tax_reliability='spoľahlivý',
        )

        # Create a test company with debts
        self.debt_company = Company.objects.create(
            ruz_id=2,
            ico='87654321',
            nazov_UJ='BadCorp s.r.o.',
            sk_NACE='62.02',
            debt_vszp=Decimal('5000'),
            tax_debt=Decimal('2000'),
        )

        # Create an inactive company
        self.inactive_company = Company.objects.create(
            ruz_id=3,
            ico='55555555',
            nazov_UJ='DeadCorp s.r.o.',
            sk_NACE='62.01',
            datum_zrusenia=timezone.now().date(),
        )

        # Add financial data to good_company
        CompanyFinancialResult.objects.create(
            company=self.good_company,
            year=2024,
            revenue=Decimal('100000'),
            profit=Decimal('20000'),
            assets_total=Decimal('150000'),
            equity=Decimal('50000'),
        )

        CompanyFinancialResult.objects.create(
            company=self.good_company,
            year=2023,
            revenue=Decimal('80000'),
            profit=Decimal('15000'),
            assets_total=Decimal('140000'),
            equity=Decimal('45000'),
        )

    def test_nace_score_target_code(self):
        """Test NACE scoring for target codes."""
        score, breakdown = self.service._calculate_nace_score(self.good_company)

        self.assertEqual(score, 40)
        self.assertEqual(breakdown['points'], 40)
        self.assertIn('Target NACE', breakdown['reason'])

    def test_nace_score_related_code(self):
        """Test NACE scoring for related codes."""
        self.debt_company.sk_NACE = '62.02'
        score, breakdown = self.service._calculate_nace_score(self.debt_company)

        self.assertEqual(score, 40)  # 62.02 is also a target code

    def test_nace_score_unrelated(self):
        """Test NACE scoring for unrelated codes."""
        self.debt_company.sk_NACE = '01.11'
        score, breakdown = self.service._calculate_nace_score(self.debt_company)

        self.assertEqual(score, 0)

    def test_data_quality_score_complete(self):
        """Test data quality scoring with complete data."""
        # Create ORSR profile
        OrsrCompanyProfile.objects.create(
            company=self.good_company,
            ico=self.good_company.ico,
            fetch_ok=True,
            obchodne_meno='TechCorp',
            last_synced_at=timezone.now(),
        )

        score, breakdown = self.service._calculate_data_quality_score(self.good_company)

        # Should get points for ORSR (10) + financials (10) = 20
        self.assertGreaterEqual(score, 20)
        self.assertTrue(breakdown['orsr_present'])
        self.assertTrue(breakdown['financials_present'])

    def test_financial_health_no_debt(self):
        """Test financial health scoring for company with no debt."""
        score, breakdown = self.service._calculate_financial_health_score(self.good_company)

        # Should get points for no debt (20) + growing revenue (10) = 30
        self.assertEqual(score, 30)
        self.assertFalse(breakdown['has_debt'])
        self.assertEqual(breakdown['revenue_trend'], 'growing')

    def test_financial_health_with_debt(self):
        """Test financial health scoring for company with debt."""
        score, breakdown = self.service._calculate_financial_health_score(self.debt_company)

        # Should get 0 points for debt
        self.assertEqual(score, 0)
        self.assertTrue(breakdown['has_debt'])

    def test_debt_penalty_active(self):
        """Test debt penalty."""
        penalty, breakdown = self.service._calculate_debt_penalty(self.debt_company)

        self.assertEqual(penalty, -30)

    def test_debt_penalty_none(self):
        """Test no debt penalty."""
        penalty, breakdown = self.service._calculate_debt_penalty(self.good_company)

        self.assertEqual(penalty, 0)

    def test_calculate_score_good_company(self):
        """Test full score calculation for good company."""
        # Add ORSR profile for complete data
        OrsrCompanyProfile.objects.create(
            company=self.good_company,
            ico=self.good_company.ico,
            fetch_ok=True,
            obchodne_meno='TechCorp',
            last_synced_at=timezone.now(),
        )

        score_data = self.service.calculate_score(self.good_company)

        # Should be high score (ideally 90+ = 40 NACE + 30 data + 30 financial - 0 debt - 0 inactive)
        self.assertGreater(score_data['score'], 70)
        self.assertEqual(score_data['nace_relevance_score'], 40)
        self.assertGreater(score_data['data_completeness_score'], 0)
        self.assertGreater(score_data['financial_health_score'], 0)

    def test_calculate_score_bad_company(self):
        """Test full score calculation for company with debt."""
        score_data = self.service.calculate_score(self.debt_company)

        # Should have debt penalty
        self.assertLess(score_data['score'], 50)
        self.assertEqual(score_data['debt_penalty'], -30)

    def test_calculate_score_inactive(self):
        """Test full score calculation for inactive company."""
        score_data = self.service.calculate_score(self.inactive_company)

        # Should be penalized for being inactive
        self.assertEqual(score_data['score'], 0)

    def test_score_companies(self):
        """Test scoring multiple companies."""
        queryset = Company.objects.filter(ico__in=['12345678', '87654321'])
        scored_count, created_count, updated_count = self.service.score_companies(queryset=queryset)

        self.assertEqual(scored_count, 2)
        self.assertEqual(created_count, 2)
        self.assertEqual(updated_count, 0)

        # Verify scores were saved
        good_score = CompanyScore.objects.get(company=self.good_company)
        bad_score = CompanyScore.objects.get(company=self.debt_company)

        self.assertGreater(good_score.score, bad_score.score)

    def test_get_top_companies(self):
        """Test getting top companies."""
        # Score some companies
        self.service.score_companies(queryset=Company.objects.all())

        top = self.service.get_top_companies(limit=2, min_score=0)

        self.assertLessEqual(len(top), 2)
        if len(top) > 1:
            # First should have higher score than second
            self.assertGreaterEqual(top[0].score, top[1].score)


class CompanyScoreModelTests(TestCase):
    """Test CompanyScore model."""

    def setUp(self):
        """Set up test data."""
        self.company = Company.objects.create(
            ruz_id=1,
            ico='12345678',
            nazov_UJ='Test Corp',
        )

    def test_create_score(self):
        """Test creating a score record."""
        score = CompanyScore.objects.create(
            company=self.company,
            score=75,
            nace_relevance_score=40,
            data_completeness_score=25,
            financial_health_score=10,
            debt_penalty=0,
        )

        self.assertEqual(score.score, 75)
        self.assertEqual(score.company, self.company)

    def test_score_string_representation(self):
        """Test string representation of score."""
        score = CompanyScore.objects.create(
            company=self.company,
            score=75,
        )

        self.assertIn('75', str(score))
        self.assertIn('Test Corp', str(score))


class CompanyEnrichmentModelTests(TestCase):
    """Test CompanyEnrichment model."""

    def setUp(self):
        """Set up test data."""
        self.company = Company.objects.create(
            ruz_id=1,
            ico='12345678',
            nazov_UJ='Test Corp',
        )

    def test_create_enrichment(self):
        """Test creating an enrichment record."""
        enrichment = CompanyEnrichment.objects.create(
            company=self.company,
            company_summary='A tech company',
            tech_stack=['Python', 'Django', 'PostgreSQL'],
            confidence_score=85,
        )

        self.assertEqual(enrichment.company, self.company)
        self.assertEqual(enrichment.confidence_score, 85)
        self.assertEqual(len(enrichment.tech_stack), 3)

    def test_enrichment_string_representation(self):
        """Test string representation of enrichment."""
        enrichment = CompanyEnrichment.objects.create(
            company=self.company,
        )

        self.assertIn('Test Corp', str(enrichment))
