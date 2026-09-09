# Professional Admin Panel Setup for CistaFirma

## Entity-Type Separation in Django Admin

### Overview

The admin panel now features advanced entity-type separation with independent views for:
- **Companies (LPO)** - Právnické osoby (Legal entities: s.r.o., a.s., atď.)
- **Individuals (SZCO)** - Fyzické osoby (Natural persons)
- **Synchronization Control** - Separate RUZ sync for each entity type

---

## Admin Panel Architecture

### 1. Company Admin (Legal Entities)

**Location:** `Firmy → Firmy` (Companies → Companies)

**Features:**
- Advanced filtering by legal form, region, sector, status
- Risk assessment badges (debt, VAT payer status, tax reliability)
- Data quality indicators (ORSR profile, financial statements)
- Bulk actions:
  - Sync from RUZ API
  - Sync from ORSR Register
  - Check insurance debts
  - Sync financial statements
  - Full data refresh

**Filters Available:**
- Legal form (s.r.o., a.s., v.o.s., atď.)
- Founded year
- Region (Kraj)
- Debt status (Has debts / Debt-free)
- VAT payer status
- Data completeness (ORSR + financials)
- Tax reliability

**Display Columns:**
- ICO + Name (linked)
- City
- Legal form (abbreviated with tooltip)
- Founded date
- Status (Active/Terminated)
- VAT payer status
- Tax reliability badge
- Risk indicator
- Data quality (OR/FIN/DPH)
- Last update date

### 2. Individual Entity Admin (SZCO)

**Location:** `Registre → Fyzické osoby/SZCO`

**Features:**
- Separate management of natural person entities
- Insurance debt tracking (VSZP, social insurance)
- VAT payer status from FS
- Tax authority information
- Debt monitoring
- No ORSR profile (SZCO don't have commercial register entry)

**Filters Available:**
- Legal form (100-110, 422)
- Organization size
- Region
- Debt status
- VAT payer status

**Display Columns:**
- ICO
- Name
- Legal form
- City
- Debt status badge
- VAT status badge
- Last update date

### 3. RUZ Sync Progress Admin

**Location:** `Registre → Synchronizácia`

**Enhanced Features:**

#### Entity-Type Display
Each sync record now shows:
- **Sync Type** with icon:
  - 🔄 Full sync (Mixed)
  - 🏢 Full Companies (LPO only)
  - 👤 Full Individuals (SZCO only)
  - ⚡ Incremental (Mixed)
  - 🔧 Repair
- **Entity Type Badge**: Shows which entity type is being synced
- **Visual Progress Bar**: Percentage completion with animated fill
- **Detailed Statistics**: Created, Updated, Skipped, Errors
- **Processing Rate**: Records/hour

#### Dashboard Statistics
- Total Companies (LPO)
- Total Individuals (SZCO)
- Companies with ORSR profiles
- Companies with financial statements
- Running syncs count
- Failed syncs with error details

#### Sync Control Buttons
```
🔄 Full Sync (Mixed)      - Syncs both LPO and SZCO into their tables
🏢 Full Companies         - LPO only - Fast, focused sync
👤 Full Individuals       - SZCO only - Independent progress tracking
⚡ Incremental            - Updates changed records
🔍 Gap Analysis           - Analyzes missing records
```

#### Status Indicators
- `▶ Running` (green)
- `⏸ Paused` (yellow) - Can resume from checkpoint
- `✗ Failed` (red) - Can resume from checkpoint
- `✓ Completed` (emerald)
- `⏸ Idle` (gray)

#### Progress Tracking Details
- Last processed RUZ ID (checkpoint for resume)
- Changed since (start date)
- Processing start/end times
- Duration
- Processing rate
- Estimated completion time

#### Quick Actions
- **Resume** - Continue paused/failed sync from exact checkpoint
- **Pause** - Pause running sync (can resume later)

---

## Use Cases & Workflows

### Use Case 1: Daily Data Update (Recommended)

**Scenario:** Update changed companies daily

```
1. Click "⚡ Incremental Sync (Mixed)"
2. Wait for completion
3. Check statistics:
   - Total created/updated
   - Any errors?
4. Monitor in "Recent Syncs" section
```

**Result:** Both LPO and SZCO updated to their respective tables

---

### Use Case 2: Full Resync of Companies Only

**Scenario:** Re-sync all legal entities without touching SZCO data

```
1. Click "🏢 Full Companies"
2. Confirm action
3. System creates/updates separate "full_companies" SyncProgress record
4. Can monitor in list view:
   - Look for row with "🏢 Full Companies (LPO)" type
   - Shows percentage completion
   - Independent from SZCO sync
5. Can pause/resume independently
```

**Benefits:**
- SZCO data untouched
- Faster than syncing both
- Independent checkpoint

---

### Use Case 3: Recovery from Interrupted Sync

**Scenario:** Sync was interrupted at 50%

```
1. Go to "Registre → Synchronizácia"
2. Find the paused sync (status = "⏸ Pozastavený")
3. Click "▶ Pokračovať" (Resume) button
4. System resumes from exact RUZ ID checkpoint
5. No duplicate processing
```

**Details:**
- Last processed RUZ ID: 1,234,567
- Records processed before: 50,000
- Continues from ID 1,234,568
- Saves time and API calls

---

### Use Case 4: Data Quality Monitoring

**Scenario:** Check data completeness for companies

```
Admin: Companies → Companies

Filters:
1. Data Completeness = "Chýba ORSR"
   → Shows companies missing ORSR profile
   → Select all → Sync from ORSR

2. Debt Status = "S dlhmi"
   → Shows all companies with debts
   → Check amounts and types

3. Tax Reliability = "Nespoľahlivý"
   → High-risk companies
   → Action needed
```

---

### Use Case 5: Regional Analysis

**Scenario:** Analyze specific region

```
Companies →Companies

Filters:
1. Region (Kraj) = "Bratislava"
2. Founded Year = "2020"
3. Data Completeness = "ORSR + financie"

Result: 
- All companies founded in Bratislava in 2020 with complete data
- Can export to CSV/XLSX for analysis
- Bulk actions available
```

---

### Use Case 6: Monitoring SZCO Entities

**Scenario:** Track physical entrepreneurs

```
Admin: Registre → Fyzické osoby/SZCO

Filters:
1. Legal Form = "101" (Podnikateľ-FO)
2. Debt Status = "S dlhmi"
3. Region = "specific"

Result:
- All entrepreneurs with debt in region
- Can track insurance debts
- Monitor VAT payer status
```

---

## API Endpoints Usage (Programmatic Sync)

### Full Sync - Companies Only

```bash
docker exec cistafirma_backend \
  python manage.py fetch_ruz_data \
    --full-resync \
    --entity-type companies

# Creates/Updates: SyncProgress with sync_type = 'full_companies'
# Progress saved to separate record
# Can be monitored in admin: look for "🏢 Full Companies" row
```

### Full Sync - Individuals Only

```bash
docker exec cistafirma_backend \
  python manage.py fetch_ruz_data \
    --full-resync \
    --entity-type individuals

# Creates/Updates: SyncProgress with sync_type = 'full_individuals'
# Independent progress tracking
# SZCO data goes to IndividualEntity table
```

### Resume Paused Sync

```bash
docker exec cistafirma_backend \
  python manage.py fetch_ruz_data --resume

# Finds most recent paused/failed sync
# Resumes from exact checkpoint
# Works for any entity type
```

---

## Dashboard Statistics & Metrics

### Real-Time Statistics (Refreshed Every 2 Minutes)

| Metric | Description |
|--------|-------------|
| Total Companies (LPO) | All legal entities in database |
| Total Individuals (SZCO) | All natural persons/SZCO in database |
| Companies with ORSR | Count of companies with commercial register data |
| Companies without ORSR | Pending ORSR synchronization |
| Companies with Financials | Count with financial statements |
| Companies without Financials | Pending financial data sync |
| Running Syncs | Active synchronization processes |
| Failed Syncs | Sync processes that failed (can resume) |
| Completed Syncs | Successfully completed syncs |

### Recent Syncs List

Shows last 8 sync operations with:
- Sync type (with entity type badge)
- Status (with color indicator)
- Progress percentage
- Statistics (created/updated/errors)
- Processing rate
- Last activity time
- Action buttons (Resume/Pause)

---

## Professional Features & Best Practices

### 1. Error Recovery & Resilience

✅ **Checkpoint System**
- Every sync saves checkpoint (last_processed_ruz_id)
- Can resume from exact point if interrupted
- No duplicate processing
- Data integrity maintained

✅ **Error Logging**
- Last error message stored
- Can be viewed in detail view
- Helps with debugging

✅ **Status Tracking**
- Detailed status: idle, running, paused, completed, failed
- Can pause running sync manually
- Failed syncs can be resumed

### 2. Entity Type Separation

✅ **Independent Syncing**
- Companies (LPO) and Individuals (SZCO) sync separately
- Can run simultaneously without interference
- Independent progress tracking
- Each has own checkpoint

✅ **Logical Separation**
- Different database tables
- Different SYNC_TYPES in SyncProgress
- Different data sources (ORSR for LPO only)

### 3. Data Quality Monitoring

✅ **Risk Badges**
- Debt status (VSZP, social insurance, tax)
- VAT payer status
- Tax authority reliability rating
- Missing data indicators

✅ **Completeness Indicators**
- OR = ORSR profile status
- FIN = Financial statements available
- DPH = VAT information from FS

### 4. Performance Optimizations

✅ **Caching**
- Dashboard statistics cached for 2 minutes
- Filter options cached for 5 minutes
- Reduces database queries significantly

✅ **Pagination**
- List display: 50 records per page
- Max show all: 500 records
- Optimized for large datasets (1.2M records)

✅ **Annotations & Prefetch**
- Uses database-level annotations for ORSR/financials
- No N+1 query problems
- Efficient filters

### 5. User Experience

✅ **Visual Indicators**
- Icons for entity types (🏢 for companies, 👤 for individuals)
- Color-coded badges (green/red/yellow)
- Progress bars with percentages
- Status indicators with emojis

✅ **Responsive Design**
- Works on desktop and tablet
- Unfold admin theme responsive
- Mobile-friendly filter interface

✅ **Export Capabilities**
- Export to CSV (semicolon-delimited)
- Export to XLSX with formatting
- Can export selected or all filtered records

---

## Configuration & Customization

### Adding New Filters

Example: Add "Has Insurance Debt" filter

```python
class InsuranceDebtFilter(admin.SimpleListFilter):
    title = 'Dlh v poisťovniach'
    parameter_name = 'has_insurance_debt'

    def lookups(self, request, model_admin):
        return [
            ('yes', 'S dlhom VSZP'),
            ('no', 'Bez dlhu VSZP'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(debt_vszp__gt=0)
        if self.value() == 'no':
            return queryset.filter(Q(debt_vszp__isnull=True) | Q(debt_vszp=0))
        return queryset
```

Then add to `list_filter`:
```python
list_filter = [..., InsuranceDebtFilter]
```

### Customizing Display Columns

Add new method to admin class:

```python
@admin.display(description='Custom Metric')
def custom_metric_display(self, obj):
    return format_html(
        '<span class="cf-badge cf-badge--{}">{}</span>',
        'success' if obj.some_field else 'danger',
        'Value' if obj.some_field else 'No Value'
    )
```

Then add to `list_display`:
```python
list_display = [..., 'custom_metric_display']
```

---

## Troubleshooting

### Sync Not Appearing

**Problem:** Started sync, but don't see it in admin

**Solution:**
1. Refresh admin page (F5)
2. Check "Recent Syncs" list
3. Check database directly:
   ```bash
   docker exec cistafirma_db psql -U cistafirma_user -d cistafirma -c \
     "SELECT sync_type, status, total_processed FROM registers_syncprogress ORDER BY last_activity DESC LIMIT 1;"
   ```

### Sync Stuck on Status

**Problem:** Sync shows "Running" but no progress

**Solution:**
1. Check Celery workers:
   ```bash
   docker compose logs -f celery_worker_ruz
   ```
2. Check Redis:
   ```bash
   docker compose exec redis redis-cli PING
   ```
3. Pause manually and check last error message

### Duplicate Records After Sync

**Problem:** Same company appears twice

**Solution:**
1. Check LEGAL_FORMS in fetch_ruz_data.py
2. Verify SZCO_LEGAL_FORMS constant includes 100-110, 422
3. Run manual check on company's SZCO status

---

## Monitoring & Maintenance

### Daily Checks

```bash
# Check sync health
docker exec cistafirma_backend python manage.py shell
>>> from registers.models import SyncProgress
>>> SyncProgress.objects.filter(status='failed').count()
# Should be 0 or manageable

# Check entity-type distribution
>>> from companies.models import Company
>>> from registers.models import IndividualEntity
>>> print(f"Companies: {Company.objects.count():,}")
>>> print(f"Individuals: {IndividualEntity.objects.count():,}")
```

### Weekly Maintenance

```bash
# Clear old completed syncs (keep last 10)
>>> old_syncs = SyncProgress.objects.filter(
...   status='completed',
...   completed_at__lt=timezone.now() - timedelta(days=30)
... ).order_by('-completed_at')[10:]
>>> old_syncs.delete()

# Analyze gap distribution
```

---

## Summary

The professional admin panel provides:

✅ **Entity-Type Separation** - Companies and SZCO managed separately  
✅ **Advanced Filtering** - 20+ filter combinations  
✅ **Real-Time Monitoring** - Live sync progress tracking  
✅ **Error Recovery** - Resume from checkpoint capability  
✅ **Data Quality** - Risk and completeness indicators  
✅ **Performance** - Optimized for 1M+ records  
✅ **Export** - CSV and XLSX capabilities  
✅ **Professional UX** - Badges, progress bars, responsive design  

**Production Ready** ✅

