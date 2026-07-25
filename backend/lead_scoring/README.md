# Lead Scoring Engine

The Lead Scoring Engine provides automated, explainable scoring of companies to identify high-quality prospects for
outreach. Companies are scored on a scale of 0-100 based on business fit, data quality, and financial health.

## Quick Start

### 1. Score All Companies

```bash
# Score all active companies
docker-compose exec backend python manage.py score_companies

# Score specific city
docker-compose exec backend python manage.py score_companies --city Bratislava

# Score specific industry
docker-compose exec backend python manage.py score_companies --nace 62.01

# Show top 20 companies
docker-compose exec backend python manage.py score_companies --top-only
```

### 2. View Scores in Admin

1. Go to `http://localhost:8000/admin/lead_scoring/companyscore/`
2. Companies are sorted by score (highest first)
3. Click on a company to see detailed breakdown

### 3. Access via API

```bash
# Get all scores
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/lead-scoring/scores/

# Get top 10
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/lead-scoring/scores/top/?limit=10

# Get scoring report
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/lead-scoring/scores/report/

# Trigger scoring (admin only)
curl -X POST -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/lead-scoring/scores/calculate/?city=Bratislava
```

## Scoring Methodology

### Overall Score (0-100)

The score is calculated as:

```
score = NACE_SCORE + DATA_QUALITY_SCORE + FINANCIAL_HEALTH_SCORE + DEBT_PENALTY + INACTIVE_PENALTY

where:
- NACE_SCORE: 0-40 points (business fit)
- DATA_QUALITY_SCORE: 0-30 points (data completeness)
- FINANCIAL_HEALTH_SCORE: 0-30 points (financial stability)
- DEBT_PENALTY: 0 or -30 (debt presence)
- INACTIVE_PENALTY: 0 or -100 (company deleted)
```

### Component Scoring

#### 1. NACE Relevance (0-40 points)

Matches company's SK NACE code against target industries:

- **40 points**: Target NACE codes (62.01, 62.02, 62.03, 62.09, 63.11)
    - 62.01 - Computer programming
    - 62.02 - IT consultancy
    - 62.03 - Computer facilities management
    - 62.09 - Other IT services
    - 63.11 - Data processing

- **20 points**: Related IT/business services (codes starting with 62 or 63)

- **0 points**: Other industries

#### 2. Data Quality (0-30 points)

Evaluates completeness and freshness of company data:

- **10 points**: ORSR profile synced successfully
- **10 points**: Financial data available
- **10 points**: Good sync health (< 2 avg consecutive failures)
- **5 points**: Fair sync health (< 5 avg consecutive failures)
- **0 points**: Poor sync health (≥ 5 avg consecutive failures)

#### 3. Financial Health (0-30 points)

Assesses financial stability and growth:

- **20 points**: No debts (VSZP + Social insurance + tax debt = 0)
- **10 points**: Growing revenue (last year > prior year)
- **5 points**: Single year of revenue data available
- **Bonus**: Strong equity ratio (≥ 30% of assets)

#### 4. Debt Penalty (-30 points)

- **-30 points**: Any debt detected (VSZP + Social + Tax combined > 0)

#### 5. Inactive Penalty (-100 points)

- **-100 points**: Company marked as deleted/zrušená

### Score Interpretation

| Score  | Interpretation | Recommendation               |
|--------|----------------|------------------------------|
| 80-100 | Excellent      | High priority prospect       |
| 60-79  | Good           | Qualified lead               |
| 40-59  | Medium         | Consider with due diligence  |
| 20-39  | Low            | Monitor for improvement      |
| 0-19   | Very Low       | Not recommended for outreach |

## Data Models

### CompanyScore

Stores the calculated lead score with explainable breakdowns.

```python
class CompanyScore(models.Model):
    company: OneToOneField(Company)
    score: int(0 - 100)

    # Components
    nace_relevance_score: int(0 - 40)
    data_completeness_score: int(0 - 30)
    financial_health_score: int(0 - 30)
    debt_penalty: int(0 or -30)

    # Detailed breakdown
    breakdown: JSON
    {
        'nace': {...},
        'data_quality': {...},
        'financial_health': {...},
        'debts': {...},
        'inactive': {...}
    }

    calculated_at: DateTime
    updated_at: DateTime
```

### CompanyEnrichment

Stores AI-generated enrichment data (for future AI integration).

```python
class CompanyEnrichment(models.Model):
    company: OneToOneField(Company)

    # Enrichment data
    tech_stack: JSON(list
    of
    technologies)
    company_summary: str(AI - generated
    summary)
    outreach_angle: str(suggested
    contact
    angle)
    outreach_draft: str(suggested
    outreach
    message)
    sources_used: JSON(list
    of
    data
    sources)

    confidence_score: int(0 - 100)

    enriched_at: DateTime
    updated_at: DateTime
```

## API Endpoints

### Scores ViewSet

| Method | Endpoint                              | Description                  |
|--------|---------------------------------------|------------------------------|
| GET    | `/api/lead-scoring/scores/`           | List all scores              |
| GET    | `/api/lead-scoring/scores/{id}/`      | Get single score             |
| GET    | `/api/lead-scoring/scores/top/`       | Get top scores               |
| GET    | `/api/lead-scoring/scores/report/`    | Get scoring report           |
| POST   | `/api/lead-scoring/scores/calculate/` | Trigger scoring (admin only) |

### Query Parameters

**GET /api/lead-scoring/scores/**

- `score`: Filter by score value
- `nace_relevance_score`: Filter by NACE score
- `search`: Search by ICO or company name
- `ordering`: Sort field (score, updated_at, nace_relevance_score)

**GET /api/lead-scoring/scores/top/**

- `limit`: Number of companies to return (default: 20)
- `min_score`: Minimum score threshold (default: 0)

**GET /api/lead-scoring/scores/report/**

- Returns aggregated statistics and top companies

**POST /api/lead-scoring/scores/calculate/**

- `city`: Filter by city
- `nace`: Filter by NACE code
- `limit`: Limit companies to score

### Enrichment ViewSet

| Method | Endpoint                                         | Description                     |
|--------|--------------------------------------------------|---------------------------------|
| GET    | `/api/lead-scoring/enrichments/`                 | List all enrichments            |
| GET    | `/api/lead-scoring/enrichments/{id}/`            | Get single enrichment           |
| GET    | `/api/lead-scoring/enrichments/high-confidence/` | Get high-confidence enrichments |

## Management Command

### score_companies

Calculates and saves lead scores for companies.

**Usage:**

```bash
python manage.py score_companies [options]
```

**Options:**

- `--city CITY`: Filter by city (substring match)
- `--nace NACE`: Filter by SK NACE code (substring match)
- `--limit N`: Limit to N companies
- `--top-only`: Show only top 20 companies (don't score)
- `--min-score N`: Minimum score to display (default: 0)

**Examples:**

```bash
# Score all companies
python manage.py score_companies

# Score companies in Bratislava
python manage.py score_companies --city Bratislava

# Score first 100 IT companies
python manage.py score_companies --nace 62 --limit 100

# Show top 20 companies without scoring
python manage.py score_companies --top-only

# Show companies with score >= 70
python manage.py score_companies --top-only --min-score 70
```

## Running Scores via Celery

For production, scores should be run as background tasks:

```python
from lead_scoring.services.scoring import LeadScoringService
from celery import shared_task


@shared_task
def score_companies_task():
    service = LeadScoringService()
    scored_count, created_count, updated_count = service.score_companies()
    return {
        'scored': scored_count,
        'created': created_count,
        'updated': updated_count,
    }
```

## Scheduling

To run scoring on a regular schedule (e.g., daily):

1. Go to Django admin: `/admin/django_celery_beat/periodictask/`
2. Create new Periodic Task:
    - **Name**: "Score Companies Daily"
    - **Task**: `lead_scoring.tasks.score_companies_task`
    - **Schedule**: Daily at 2 AM
    - **Enabled**: True

## Admin Interface

### CompanyScore Admin

- **List View**: Shows all scores sorted by score (highest first)
- **Filters**: Score range, NACE score, update date
- **Search**: ICO or company name
- **Display**: Color-coded scores (🟢 ≥70, 🟡 50-69, 🔴 <50)
- **Detailed View**: Full breakdown with all components

### CompanyEnrichment Admin

- **List View**: Shows enrichments sorted by confidence
- **Filters**: Confidence score, enrichment date
- **Search**: ICO, company name, summary
- **Display**: Confidence badge with percentage

## Testing

Run the test suite:

```bash
# All scoring tests
python manage.py test lead_scoring

# Specific test class
python manage.py test lead_scoring.tests.LeadScoringServiceTests

# Specific test method
python manage.py test lead_scoring.tests.LeadScoringServiceTests.test_calculate_score_good_company
```

## Future Enhancements

1. **AI Enrichment**: Use GPT-4 to generate company summaries and outreach angles
2. **Custom Scoring**: Allow users to define custom NACE codes and weights
3. **Predictive Scoring**: ML model to predict conversion likelihood
4. **Batch Export**: Export top scores to CSV/Excel
5. **Scoring Dashboard**: React component for score visualization
6. **Competitor Tracking**: Monitor scores of specific competitors
7. **Email Notifications**: Alert on new high-scoring companies

## Troubleshooting

### Scores not updating

Check:

1. No companies match the filter criteria
2. Scoring service ran without errors: `docker-compose logs backend`
3. Database connection is active

### Low scores for expected companies

Review the breakdown:

1. SK NACE code must match target (62.01, 62.02, etc.)
2. ORSR profile must exist and sync successfully
3. No debts (VSZP, social, tax)
4. Recent financial data required for financial health score

### Performance issues with large datasets

- Use `--limit` to score subset of companies
- Run scoring during off-peak hours
- Increase database connection pool size

## Contributing

To extend the scoring methodology:

1. Edit `LeadScoringService` in `backend/lead_scoring/services/scoring.py`
2. Add new scoring component methods
3. Update `calculate_score()` to include new component
4. Add tests to `backend/lead_scoring/tests.py`
5. Run `python manage.py test lead_scoring`
6. Update this README with new scoring logic

## See Also

- `DEVELOPER_GUIDE.md` - General development instructions
- `API_REFERENCE.md` - Full API documentation
- `ARCHITECTURE.md` - System architecture and data flows

