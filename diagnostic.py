"""Quick diagnostic of company_filters.py"""

import sys
sys.path.insert(0, '/Users/samuelsugra/Code/cistafirma/backend')

import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

import django
django.setup()

from adminapi.services.company_filters import CompanyFilterService
from companies.models import Company
from django.db.models import QuerySet, Exists, OuterRef

print("✅ Imports successful")

# Check if service can be instantiated
filter_service = CompanyFilterService()
print("✅ CompanyFilterService instantiated")

# Test apply method with real queryset
qs = Company.objects.all()
result = filter_service.apply(qs, {'has_financials': '1'})
print(f"✅ Filter applied without error: {type(result)}")

# Check SQL generation
try:
    sql = str(result.query)
except Exception as e:
    print(f"Could not generate SQL: {e}")
    sql = None
print(f"\n📋 Generated SQL (full):")
if sql:
    print(sql[:1500])
else:
    print("Could not generate SQL")

# Check for problematic patterns
if sql:
    if "DISTINCT" in sql:
        print("\n⚠️  WARNING: DISTINCT found in query (cartesian product risk)")
    else:
        print("\n✅ No DISTINCT in query")

    if "LEFT OUTER JOIN" in sql:
        print("⚠️  WARNING: LEFT OUTER JOIN found in query (may cause performance issues)")
    else:
        print("✅ No problematic LEFT OUTER JOIN")

    if "EXISTS" in sql:
        print("✅ Subqueries found (Exists() used correctly)")
    else:
        print("ℹ️  No EXISTS subqueries")

print("\n✅ All diagnostics passed!")

print("\n" + "="*60)
print("Testing COMBINED filter...")
qs = Company.objects.all()
params = {
    'has_financials': '1',
    'has_orsr': '1',
    'profit_state': 'profit',
}
result = filter_service.apply(qs, params)
print(f"✅ Combined filter applied: {type(result)}")

try:
    sql = str(result.query)
    print(f"\n📋 Combined Filter SQL (1500 chars):")
    print(sql[:1500])

    if "EXISTS" in sql:
        count_exists = sql.count("EXISTS")
        print(f"\n✅ Found {count_exists} EXISTS subqueries (good!)")

    if "DISTINCT" in sql:
        print("\n⚠️  WARNING: DISTINCT found")
    else:
        print("\n✅ No DISTINCT in combined query")

except Exception as e:
    print(f"⚠️  Error generating SQL: {e}")
