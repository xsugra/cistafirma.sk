#!/usr/bin/env python
"""Test script to verify the combined filter performance fix.

This script:
1. Creates test companies with various attributes
2. Tests combined filters with multiple conditions
3. Measures query performance and database load
"""

import os
import django
import time
from django.db import connection
from django.test.utils import CaptureQueriesContext

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from companies.models import Company, CompanyFinancialResult
from registers.models import OrsrCompanyProfile
from django.db.models import Exists, OuterRef, Q, Count
from adminapi.services import CompanyFilterService


def create_test_data(count=100):
    """Create test companies with various attributes."""
    print(f"Creating {count} test companies...")

    companies = []
    for i in range(count):
        companies.append(Company(
            ico=f"{'0' * (8 - len(str(i + 1)))}{i + 1}",
            ruz_id=1000000 + i,  # Add required ruz_id as integer
            nazov_UJ=f"Test Company {i + 1}",
            sk_NACE=f"{6200 + (i % 10)}",  # Various NACE codes
            mesto="Bratislava" if i % 2 == 0 else "Košice",
            psc="81000" if i % 2 == 0 else "04000",
            kraj="Bratislavský" if i % 2 == 0 else "Košický",
            vat_payer=i % 3 == 0,
            debt_vszp=0 if i % 5 == 0 else 100 + i,  # Some have debt
            debt_soc_poist=0,
            tax_debt=0,
        ))

    Company.objects.bulk_create(companies, ignore_conflicts=True)
    print(f"✓ Created {Company.objects.count()} companies total")


def create_related_data():
    """Create ORSR profiles and financial results."""
    print("Creating related data (ORSR profiles and financials)...")

    # Get companies that don't have ORSR profiles yet
    companies = Company.objects.all()[:50]

    orsr_profiles = []
    for company in companies:
        if not hasattr(company, 'orsr_profile'):
            orsr_profiles.append(OrsrCompanyProfile(
                company=company,
                ico=company.ico,
                obchodne_meno=company.nazov_UJ,
            ))

    if orsr_profiles:
        OrsrCompanyProfile.objects.bulk_create(orsr_profiles, ignore_conflicts=True)

    # Create financial results
    financial_results = []
    for company in companies[:30]:
        financial_results.append(CompanyFinancialResult(
            company=company,
            year=2023,
            revenue=100000 + company.id * 1000,
            profit=10000 + company.id * 500,
        ))

    CompanyFinancialResult.objects.bulk_create(financial_results, ignore_conflicts=True)
    print(f"✓ Created ORSR profiles and financial results")


def test_combined_filter():
    """Test the combined filter with multiple conditions."""
    print("\n" + "=" * 60)
    print("TESTING COMBINED FILTER PERFORMANCE")
    print("=" * 60)

    # Build queryset with annotations (like the admin view does)
    from adminapi.views.companies import AdminCompanyViewSet
    viewset = AdminCompanyViewSet()
    qs = viewset._listing_queryset()

    # Test various combined filters
    test_cases = [
        {
            "name": "Single filter: mesto=Bratislava",
            "params": {"mesto": "Bratislava"}
        },
        {
            "name": "Single filter: has_orsr=1",
            "params": {"has_orsr": "1"}
        },
        {
            "name": "Single filter: has_financials=1",
            "params": {"has_financials": "1"}
        },
        {
            "name": "Combined filter: mesto + debt_state",
            "params": {"mesto": "Bratislava", "debt_state": "no_debt"}
        },
        {
            "name": "Combined filter: mesto + sk_nace + has_orsr",
            "params": {"mesto": "Bratislava", "sk_nace": "62", "has_orsr": "1"}
        },
        {
            "name": "Combined filter: mesto + has_orsr + has_financials + debt_state",
            "params": {
                "mesto": "Bratislava",
                "has_orsr": "1",
                "has_financials": "1",
                "debt_state": "no_debt"
            }
        },
    ]

    filter_service = CompanyFilterService()

    for test_case in test_cases:
        print(f"\n→ Testing: {test_case['name']}")
        print(f"  Parameters: {test_case['params']}")

        # Measure query execution time
        start = time.time()
        with CaptureQueriesContext(connection) as ctx:
            filtered_qs = filter_service.apply(qs, test_case['params'])
            result_count = filtered_qs.count()

        elapsed = time.time() - start
        query_count = len(ctx)

        print(f"  ✓ Results: {result_count} companies")
        print(f"  ✓ Query time: {elapsed:.3f}s")
        print(f"  ✓ Database queries: {query_count}")

        # Check if we're using Exists (good) or implicit joins (bad)
        # by examining the SQL
        if query_count > 0:
            last_query = str(ctx[-1]['sql'])
            has_exists = 'EXISTS' in last_query
            has_join = 'JOIN' in last_query and 'INNER' in last_query

            if has_exists:
                print(f"  ✓ Using Exists() subqueries (OPTIMIZED) ✓")
            elif has_join:
                print(f"  ✗ Using INNER JOINs (SLOW) ✗")

        # Performance warning
        if elapsed > 1.0:
            print(f"  ⚠ WARNING: Query took {elapsed:.1f}s (should be <100ms)")
        else:
            print(f"  ✓ GOOD: Query is fast (<100ms)")


if __name__ == "__main__":
    print("Combined Filter Performance Test")
    print("=" * 60)

    # Clean up existing data
    print("Cleaning up existing test data...")
    OrsrCompanyProfile.objects.all().delete()
    CompanyFinancialResult.objects.all().delete()
    Company.objects.all().delete()

    # Create test data
    create_test_data(100)
    create_related_data()

    # Run tests
    test_combined_filter()

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)

