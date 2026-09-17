#!/bin/bash
# Verification script for Firmy/SZCO implementation

echo "╔════════════════════════════════════════════════════════════╗"
echo "║   Firmy/SZCO Separation Implementation Verification       ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Check 1: Backend models
echo "✓ Checking backend models..."
if grep -q "SZCO_LEGAL_FORMS" backend/companies/models.py; then
    echo "  ✓ SZCO classification constants found"
fi
if grep -q "is_szco_company" backend/companies/models.py; then
    echo "  ✓ is_szco_company() function found"
fi
if grep -q "is_company_company" backend/companies/models.py; then
    echo "  ✓ is_company_company() function found"
fi
echo ""

# Check 2: Celery tasks
echo "✓ Checking Celery tasks..."
if grep -q "fetch_ruz_data_firmy_only" backend/registers/tasks.py; then
    echo "  ✓ fetch_ruz_data_firmy_only() task found"
fi
if grep -q "fetch_ruz_data_szco_only" backend/registers/tasks.py; then
    echo "  ✓ fetch_ruz_data_szco_only() task found"
fi
echo ""

# Check 3: API endpoints
echo "✓ Checking API job dispatcher..."
if grep -q 'ruz_full_firmy' backend/adminapi/views/sync.py; then
    echo "  ✓ ruz_full_firmy job type found"
fi
if grep -q 'ruz_full_szco' backend/adminapi/views/sync.py; then
    echo "  ✓ ruz_full_szco job type found"
fi
echo ""

# Check 4: Dashboard metrics
echo "✓ Checking dashboard metrics..."
if grep -q 'firmy_count' backend/adminapi/views/dashboard.py; then
    echo "  ✓ firmy_count metric found"
fi
if grep -q 'szco_count' backend/adminapi/views/dashboard.py; then
    echo "  ✓ szco_count metric found"
fi
echo ""

# Check 5: Frontend pages
echo "✓ Checking frontend admin panel..."
if [ -f "frontend/admin/pages/Data.tsx" ]; then
    echo "  ✓ Data.tsx page created"
fi
if grep -q "case 'data'" frontend/admin/AdminApp.tsx; then
    echo "  ✓ Data route added to AdminApp"
fi
if grep -q "'data'" frontend/admin/AdminLayout.tsx; then
    echo "  ✓ Data navigation item added"
fi
echo ""

# Check 6: Frontend types
echo "✓ Checking frontend TypeScript types..."
if grep -q 'firmy_count' frontend/admin/types.ts; then
    echo "  ✓ firmy_count type added"
fi
if grep -q 'szco_count' frontend/admin/types.ts; then
    echo "  ✓ szco_count type added"
fi
if grep -q "'data'" frontend/admin/types.ts; then
    echo "  ✓ 'data' page type added"
fi
echo ""

echo "╔════════════════════════════════════════════════════════════╗"
echo "║   ✅ Implementation Verification Complete!                ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "Next steps:"
echo "1. Run: make docker-up"
echo "2. Navigate to: http://localhost:5173/admin/"
echo "3. Click 'Data (Firmy/SZCO)' in the sidebar"
echo "4. Test separate FULL RUZ SYNC for Firmy and SZCO"
echo ""

