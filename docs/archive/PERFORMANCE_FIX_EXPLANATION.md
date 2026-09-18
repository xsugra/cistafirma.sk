# Performance Fix Summary: Combined Filter Cartesian Product Elimination

## Problem Identified
The combined filter for 1.2M companies was experiencing **severe performance degradation**:
- Database load: **135%** (CPU overloaded)
- Backend load: **57%** 
- Query hangs indefinitely
- No results returned

### Root Cause
**Implicit OUTER JOIN in fallback logic** when annotations were missing or incomplete:
1. Lines 126, 131 in `company_filters.py` - `financial_results__isnull` creates JOIN without select_related
2. Lines 114, 119 - `orsr_profile__isnull` creates JOIN without select_related  
3. Lines 185 - `financial_results__year` creates JOIN
4. Lines 227, 231, 247, 251 - `sync_statuses` relationship creates JOIN
5. **Cartesian Product**: With 1.2M companies × millions of related records = explosion of rows in JOIN result

When combined filters trigger fallback logic (e.g., when annotations missing), Django executes massive OUTER JOINs that create billions of intermediate rows, causing:
- Quadratic memory usage
- CPU 100%+ 
- Query timeout

## Solution Implemented
**Replace all fallback JOINs with Exists() subqueries** - these are:
- **Much more efficient**: Scales O(n) instead of O(n²)
- **No cartesian product risk**: Only checks existence, not row counts
- **Database-native optimization**: Query planner can use indexes

### Changes Made to `/backend/adminapi/services/company_filters.py`

#### 1. **Imports**
```python
from django.db.models import Exists, OuterRef, Q, QuerySet
from companies.models import Company, CompanyFinancialResult
from registers.models import CompanySyncStatus, OrsrCompanyProfile
```

#### 2. **In `apply()` method** (lines 108-132)
**Before:**
```python
if "has_orsr_flag" not in annotation_names:
    qs = qs.filter(orsr_profile__isnull=False)  # ❌ JOIN
```

**After:**
```python
if "has_orsr_flag" not in annotation_names:
    qs = qs.filter(Exists(OrsrCompanyProfile.objects.filter(company_id=OuterRef("pk"))))  # ✅ Subquery
```

#### 3. **In `_apply_profit_state()` method**
Replaced `financial_results__profit__gt=0` with:
```python
qs.filter(Exists(CompanyFinancialResult.objects.filter(company_id=OuterRef("pk"), profit__gt=0)))
```

#### 4. **In `_apply_revenue_state()` method**
Similar pattern - use Exists instead of filtering relationship directly

#### 5. **In `_apply_sync_state()` method**
```python
qs.exclude(Exists(CompanySyncStatus.objects.filter(company_id=OuterRef("pk"), consecutive_failures__gt=0)))
```

#### 6. **In `_condition_to_q()` builder method**
- When annotations missing, return **None** instead of fallback Q objects
- Allows fallback logic in `apply()` to handle it with Exists subqueries

#### 7. **Financial year filter** (line 180-185)
```python
qs = qs.filter(Exists(CompanyFinancialResult.objects.filter(company_id=OuterRef("pk"), year=latest_financial_year)))
```

## SQL Query Impact

### Before (with fallback JOINs):
```sql
SELECT * FROM "Companies" 
LEFT OUTER JOIN "Company Financial Results" 
LEFT OUTER JOIN "registers_orsrcompanyprofile"
WHERE ... AND DISTINCT  -- ❌ Billions of rows, 135% CPU load
```

### After (with Exists subqueries):
```sql
SELECT * FROM "Companies"
WHERE EXISTS(SELECT 1 FROM "Company Financial Results" WHERE company_id = "Companies".id)
  AND EXISTS(SELECT 1 FROM "registers_orsrcompanyprofile" WHERE company_id = "Companies".id)
  AND ...  -- ✅ Scales linearly, minimal CPU
```

## Verification
✅ Diagnostic test shows:
- **3 EXISTS subqueries** instead of JOINs
- **Zero DISTINCT** (no cartesian product)
- No problematic LEFT OUTER JOINs
- Filter applies without error

## Expected Performance Improvement
- **Database CPU**: 135% → <20%
- **Backend Load**: 57% → <5%
- **Query Time**: Infinite → <500ms for 1.2M records
- **Memory Usage**: O(n²) → O(n)

## Files Modified
- `/backend/adminapi/services/company_filters.py` - All fallback JOINs replaced with Exists subqueries

## Testing Commands
```bash
# Verify fix
python diagnostic.py

# Run full test suite
make test

# Test in admin API
curl "http://localhost:8000/api/admin/companies/?has_financials=1&has_orsr=1&profit_state=profit"
```

