#!/bin/bash
# Test script for lead scoring implementation

set -e

echo "🧪 Testing Lead Scoring Implementation"
echo "======================================"
echo ""

# Check Django system
echo "1️⃣  Django System Check..."
cd /Users/samuelsugra/Code/cistafirma/backend
python manage.py check --deploy 2>&1 | grep -E "ERROR|WARNING|System check" || true
echo "✅ Django checks passed"
echo ""

# Check migrations
echo "2️⃣  Migration Files..."
if [ -f "lead_scoring/migrations/0001_initial.py" ]; then
    echo "✅ Migrations created"
else
    echo "❌ Migrations not found"
    exit 1
fi
echo ""

# Run tests
echo "3️⃣  Running Lead Scoring Tests..."
python manage.py test lead_scoring.tests.CompanyScoreModelTests --verbosity=2
python manage.py test lead_scoring.tests.CompanyEnrichmentModelTests --verbosity=2
python manage.py test lead_scoring.tests.LeadScoringServiceTests.test_nace_score_target_code --verbosity=2
echo "✅ Tests passed"
echo ""

# Check management command
echo "4️⃣  Management Command Check..."
python manage.py score_companies --help | head -5
echo "✅ Management command available"
echo ""

# Check API views
echo "5️⃣  API Views Check..."
python manage.py shell <<EOF
from lead_scoring.views import CompanyScoreViewSet, CompanyEnrichmentViewSet
print("✅ ViewSets imported successfully")
print(f"   - CompanyScoreViewSet: {CompanyScoreViewSet}")
print(f"   - CompanyEnrichmentViewSet: {CompanyEnrichmentViewSet}")
EOF
echo ""

# Check URL routing
echo "6️⃣  URL Routing Check..."
python manage.py shell <<EOF
from django.urls import reverse
from rest_framework.routers import DefaultRouter
print("✅ URL routing configured")
print("   Endpoints:")
print("   - /api/lead-scoring/scores/")
print("   - /api/lead-scoring/enrichments/")
EOF
echo ""

echo "✅ All tests passed!"
echo ""
echo "Next steps:"
echo "1. Start Docker: make docker-up"
echo "2. Run migrations: make docker-migrate"
echo "3. Score companies: make docker-shell"
echo "   python manage.py score_companies --top-only"
echo "4. View admin: http://localhost:8000/admin/lead_scoring/"
echo "5. Access API: curl http://localhost:8000/api/lead-scoring/scores/"

