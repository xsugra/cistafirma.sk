#!/usr/bin/env python
"""Test combined filter performance with 1.2M companies"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.test.utils import override_settings
from django.db import connection
from django.test import TestCase
from companies.models import Company, CompanyFinancialResult
from adminapi.services.company_filters import CompanyFilterService
from registers.models import OrsrCompanyProfile

# Enable query logging
from django.db import reset_queries
from django.conf import settings

@override_settings(DEBUG=True)
def test_combined_filter():
    """Test that combined filter doesn't cause cartesian product or O(n^2) queries"""
    reset_queries()

    # Create test data
    company = Company.objects.create(
        ruz_id=1,
        ico="12345678",
        nazov_UJ="Test Company",
    )

    CompanyFinancialResult.objects.create(
        company=company,
        year=2023,
        revenue=100000,
        profit=50000,
    )

    OrsrCompanyProfile.objects.create(
        company=company,
    )

    # Test filter with multiple conditions
    filter_service = CompanyFilterService()
    params = {
        'has_financials': '1',
        'has_orsr': '1',
        'profit_state': 'profit',
    }

    qs = Company.objects.all()
    # Apply listing queryset annotations
    from adminapi.views.companies import AdminCompanyViewSet
    view = AdminCompanyViewSet()
    qs = view._listing_queryset()

    # Apply filter
    filtered_qs = filter_service.apply(qs, params)

    # Execute query and count
    count = filtered_qs.count()

    # Check query count
    query_count = len(connection.queries)
    print(f"\nTest Results:")
    print(f"  Total queries: {query_count}")
    print(f"  Companies found: {count}")
    print(f"\nFirst few queries:")
    for i, q in enumerate(connection.queries[:5]):
        sql = q['sql'][:200]
        print(f"  {i+1}. {sql}...")

    # Check for DISTINCT (which indicates JOIN problems)
    has_distinct = any('DISTINCT' in q['sql'] for q in connection.queries)
    has_cartesian = any('LEFT OUTER JOIN' in q['sql'] and 'COUNT(*)' in q['sql'] for q in connection.queries)

    print(f"\nPerformance Checks:")
    print(f"  Has DISTINCT: {has_distinct}")
    print(f"  Potential cartesian product: {has_cartesian}")

    if query_count > 50:
        print(f"\n⚠️  WARNING: Too many queries ({query_count})")
    else:
        print(f"\n✅ Query count OK ({query_count} queries)")

    # Print full SQL of main count query
    if connection.queries:
        print(f"\nMain query SQL:")
        print(connection.queries[-1]['sql'][:500])

if __name__ == '__main__':
    test_combined_filter()

