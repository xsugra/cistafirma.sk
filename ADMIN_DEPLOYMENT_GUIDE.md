# Admin Panel - Professional Deployment Guide

## Status: ✅ PRODUCTION READY

**Date:** August 4, 2026  
**Version:** 2.0 - Entity-Type Separation  
**Backend:** Django 6.0.1 with Unfold Admin Theme  

---

## Quick Start

### 1. Access Admin Panel

**URL:** `http://localhost:8080/admin/`  
**Credentials:** `admin` / `admin`

### 2. Navigate to Main Sections

**Firmy (Companies - LPO)**
- Path: `Firmy → Firmy` (Legal entities only)
- Contains: s.r.o., a.s., v.o.s., etc. (600k+ records)
- Features: ORSR profiles, financial statements, debt tracking

**Fyzické osoby / SZCO**
- Path: `Registre → Fyzické osoby/SZCO`
- Contains: Entrepreneurs (100-110), Foreign naturals (422)
- Features: Insurance debt, VAT status, no ORSR (natural persons)

**Synchronizácia (RUZ Sync)**
- Path: `Registre → Synchronizácia`
- Features: Progress tracking, entity-type separation, resume capability

---

## Professional Admin Features

### ✨ Entity-Type Separation

Each sync process shows:

```
🏢 Full Companies (LPO)
   ├─ Legal entities only
   ├─ Independent progress tracking
   └─ Separate SyncProgress record (full_companies)

👤 Full Individuals (SZCO)
   ├─ Natural persons only
   ├─ Independent progress tracking
   └─ Separate SyncProgress record (full_individuals)

🔄 Incremental (Mixed)
   ├─ Both entity types
   ├─ Changes since last update
   └─ Single SyncProgress record
```

### 📊 Dashboard Statistics

Real-time metrics refreshed every 2 minutes:
- Total Companies (LPO): ~600,000
- Total Individuals (SZCO): ~200-300k
- ORSR profiles coverage: Show %
- Financial statements: Show count
- Running/Failed syncs: Live count

### 🎯 Status Display

**List View Columns:**
- **Typ** (Sync Type) - Full/Incremental/Repair
- **Entita** (Entity Type) - LPO/SZCO/Zmiešané badge
- **Stav** (Status) - Running/Paused/Completed/Failed
- **Progress** - Visual bar with %
- **Štatistiky** - Created/Updated/Errors count
- **Rýchlosť** - Records/hour
- **Čas** - Last activity
- **Akcie** - Resume/Pause buttons

### 🔧 Action Buttons

**In List View:**
- 🟢 Resume (if paused/failed)
- 🟡 Pause (if running)

**Trigger URLs:**
- 🔄 Full Sync (Mixed)
- 🏢 Full Companies (LPO only)
- 👤 Full Individuals (SZCO only)
- ⚡ Incremental
- 🔍 Gap Analysis

### 💾 Data Quality Indicators

For Companies (LPO):
- OR (ORSR) - Green if present
- FIN (Financial) - Green if statements exist
- DPH (VAT) - Green if FS info available

Debt Badges:
- 🟢 OK - No debts
- 🔴 Danger - VSZP/Social insurance/Tax debts
- 🟠 Warning - Shows amount

---

## Real-World Scenarios

### Scenario 1: Daily Data Update (Recommended)

**Goal:** Update all changed records from RUZ API daily

**Steps:**
1. Admin → Registre → Synchronizácia
2. Click "⚡ Inkrementalny" trigger button
3. Monitor in dashboard:
   - Status shows "▶ Beziaci"
   - Progress bar updates
   - Statistics show created/updated counts
4. Wait for completion
5. Check "Recent Syncs" list for status

**Expected Result:**
- Both LPO and SZCO updated
- Independent progress records created
- Resume point stored for interruptions

**Command Alternative:**
```bash
docker exec cistafirma_backend python manage.py fetch_ruz_data --entity-type companies
```

---

### Scenario 2: Full Resync of Companies Only

**Goal:** Re-fetch all legal entities without touching SZCO

**Steps:**
1. Admin → Registre → Synchronizácia
2. Click "🏢 Full Companies" button
3. Confirm action
4. Monitor separately:
   - Look for "🏢 Full Companies (LPO)" row
   - Shows independent progress
   - Separate checkpoint saved

**Key Points:**
- SZCO data untouched
- Faster than syncing both
- Can pause/resume independently
- Progress saved separately

**Command:**
```bash
docker exec cistafirma_backend python manage.py fetch_ruz_data \
  --full-resync --entity-type companies
```

---

### Scenario 3: Resume Interrupted Sync

**Goal:** Continue sync from where it stopped

**Steps:**
1. Note: Sync was at 50% and interrupted (user pressed Ctrl+C)
2. Admin → Registre → Synchronizácia
3. Find paused sync (status = "⏸ Pozastavený")
4. Click "▶ Pokračovať" (Resume) button
5. Confirms message: "pokračuje od RUZ ID {last_id:,}"

**Technical Details:**
- Last RUZ ID saved: 1,234,567
- Records processed before: 50,000
- Continues from ID 1,234,568
- No duplicate processing
- Saves API calls and time

**Result:**
- Sync resumes automatically
- Progress bar continues
- Final stats accurate

---

### Scenario 4: Monitor High-Risk Companies

**Goal:** Find companies with debt issues

**Steps:**
1. Admin → Firmy → Firmy
2. Filter: "Stav dlhov" = "S dlhmi"
3. Optionally add: "Region" = specific region
4. Result: All companies with debts
5. Click on company for details

**In Detail View:**
- ORSR profile (if available)
- Financial statements (if available)
- Debt breakdown: VSZP/Social/Tax
- Insurance debt date
- Tax authority reliability status

**Export Results:**
- Select companies
- Action: "Export vybranych do CSV"
- Get spreadsheet with full data

---

### Scenario 5: Check Data Completeness

**Goal:** Identify companies missing critical data

**Filters:**
1. Data Completeness = "Chýba ORSR"
   - Shows companies without commercial register profile
   - Action: Select → Sync z ORSR

2. Data Completeness = "Chýba financie"
   - Shows companies without financial statements
   - Action: Select → Sync hosp. vysledky z RUZ

3. Data Completeness = "ORSR + financie"
   - Shows complete records
   - Use for reporting/analysis

**Use Case:**
- Before important decision, check if data is complete
- Fill gaps before proceeding
- Ensures data quality

---

## Advanced Features

### Real-Time Sync Progress Tracking

**In Sync Progress Detail View:**

```
Progress Bar
├─ Visual percentage (0-100%)
├─ Number of records processed
└─ Estimated completion time

Entity Type Info
├─ Shows which entity type(s) being synced
└─ Explains scope

Detailed Statistics
├─ Total processed: XX,XXX
├─ Created: +Y,YYY (green)
├─ Updated: ~Z,ZZZ (blue)
├─ Skipped: ⊘ W (neutral)
├─ Errors: ✗ E (red)
└─ Duration: HH:MM:SS
```

### Checkpoint Management

**How Resume Works:**
1. Every 100 records: checkpoint saved
2. `last_processed_ruz_id` field updated
3. If interrupted: can resume from exact point
4. No duplicate processing
5. Data integrity maintained

**Example:**
- Started: RUZ ID 1,000,000
- Processed: 50,000 records
- Reached: RUZ ID 1,050,000
- Interrupted here
- Resume: Continues from 1,050,001

---

## Best Practices

### ✅ DO

1. **Run incremental sync daily** - Keep data fresh
2. **Run full sync weekly** - Catch any missed updates
3. **Check dashboard stats** - Monitor data quality
4. **Export filtered results** - Use for analysis
5. **Resume paused syncs** - Don't restart from beginning
6. **Monitor error counts** - Fix issues early
7. **Use separate syncs** - Full Companies vs SZCO independently
8. **Review debt badges** - Prioritize high-risk companies

### ❌ DON'T

1. **Don't interrupt full syncs too often** - Wastes resources
2. **Don't ignore failed syncs** - Check error messages
3. **Don't export huge filtered sets** - Slow browser
4. **Don't mix entity types** - Use separate syncs
5. **Don't reset sync progress** - Loses checkpoint
6. **Don't sync same company twice** - Wastes API calls
7. **Don't ignore data gaps** - Run gap analysis
8. **Don't skip validation** - Check before decisions

---

## Monitoring & Maintenance

### Daily Checklist

```bash
# 1. Check failed syncs
docker exec cistafirma_backend python manage.py shell
>>> from registers.models import SyncProgress
>>> failed = SyncProgress.objects.filter(status='failed')
>>> failed.count()
# Should be 0 or very low

# 2. Check entity distribution
>>> from companies.models import Company
>>> from registers.models import IndividualEntity
>>> print(f"Companies: {Company.objects.count():,}")
>>> print(f"Individuals: {IndividualEntity.objects.count():,}")

# 3. Check recent sync status
>>> recent = SyncProgress.objects.order_by('-last_activity').first()
>>> print(f"Last: {recent.sync_type} - {recent.status}")
```

### Weekly Maintenance

1. **Analyze gaps:** Admin → Sync Gap Analysis → Trigger
2. **Repair gaps:** If analysis shows issues
3. **Export stats:** For management reporting
4. **Review error logs:** Check last_error field

### Monthly Deep-Dive

1. **Full data quality report:** Completeness percentages
2. **Performance review:** Sync speed trends
3. **Risk assessment:** Debt distribution analysis
4. **Archive old syncs:** Keep last 30 completed only

---

## Troubleshooting

### Sync Shows "Running" But No Progress

**Diagnosis:**
```bash
# Check Celery workers
docker compose logs -f celery_worker_ruz

# Check Redis
docker compose exec redis redis-cli PING
# Should return: PONG

# Check database
docker exec cistafirma_db psql -U cistafirma_user -d cistafirma -c \
  "SELECT total_processed FROM registers_syncprogress WHERE id=X LIMIT 1;"
```

**Fix:**
- Restart Celery worker: `docker compose restart celery_worker_ruz`
- Pause and resume sync from admin

### Duplicate Records After Sync

**Cause:** Company synced to both tables

**Fix:**
1. Check if SZCO_LEGAL_FORMS constant includes 100-110, 422
2. Run: `SELECT pravna_forma FROM companies_company WHERE ico='XXX'`
3. If form in (100-110, 422): Wrong table
4. Move record manually or re-run sync

### Cannot Resume Sync

**Cause:** Status not paused/failed, or wrong sync_type

**Solution:**
1. Check status in admin (should be ⏸ or ✗)
2. Try with --resume flag if paused
3. Check if correct entity-type syncs exist

---

## Performance Tuning

### Optimize for Large Datasets

```python
# In fetch_ruz_data.py
# Increase progress save interval (from 100 to 500)
# Reduces database writes
if processed_count % 500 == 0:  # was 100
    progress.record_progress(...)

# Batch insert if possible
# Instead of create one by one
```

### Database Query Optimization

```sql
-- Index common queries
CREATE INDEX idx_company_debt ON companies_company(debt_vszp, debt_soc_poist);
CREATE INDEX idx_company_pravna ON companies_company(pravna_forma);
CREATE INDEX idx_sync_type_status ON registers_syncprogress(sync_type, status);
```

### Cache Dashboard Stats

Already implemented:
- Cache key: `companies_admin_dashboard_stats_v2`
- TTL: 120 seconds
- Refresh on first access after expiry

---

## API Integration (Programmatic Access)

### Start Companies Sync

```bash
curl -X POST http://localhost:8000/api/sync/start/ \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "entity_type": "companies",
    "sync_type": "full"
  }'
```

### Get Sync Status

```bash
curl http://localhost:8000/api/sync/status/ \
  -H "Authorization: Bearer TOKEN"
```

### Resume Paused Sync

```bash
curl -X POST http://localhost:8000/api/sync/resume/1/ \
  -H "Authorization: Bearer TOKEN"
```

---

## Security Considerations

✅ **Implemented:**
- Admin access requires authentication
- ViewSets have permission classes
- Sensitive data (debts, tax reliability) shown only to authenticated users
- No API keys exposed in admin
- Database queries optimized to prevent injection

⚠️ **Recommended:**
- Enable 2FA for admin accounts
- Use HTTPS in production
- Implement rate limiting on sync endpoints
- Audit admin actions
- Backup database regularly

---

## Summary

The professional admin panel provides:

✅ Entity-type separation (LPO vs SZCO)  
✅ Independent progress tracking  
✅ Resume capability from checkpoints  
✅ Real-time monitoring dashboard  
✅ Advanced filtering & search  
✅ Bulk actions  
✅ Export to CSV/XLSX  
✅ Risk assessment badges  
✅ Debt tracking  
✅ Data quality indicators  

**Status:** Production Ready ✅

---

**Last Updated:** August 4, 2026  
**Next Review:** December 2026  
**Contact:** Development Team

