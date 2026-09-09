# Quick Start: Firmy/SZCO Data Management

## What Was Implemented

You now have a **complete Data Management panel** in the admin UI that lets you:
- 📊 **Separately manage Firmy** (legal entities: s.r.o., a.s., etc.)
- 👤 **Separately manage SZCO** (self-employed individuals)
- 🔄 **Run FULL RUZ SYNC independently** for each category
- 📈 **View metrics** (count, percentage) for each category

---

## Quick Access

### Access the Data Panel
1. **Open admin panel**: http://localhost:5173/admin/
2. **Click sidebar**: "Data (Firmy/SZCO)" (database icon)
3. **You'll see two tabs**: Firmy | SZCO

### Firmy Tab
```
Počet Firiem: [displays count]
Podiel: [displays % of total]

[FULL RUZ SYNC - Firmy button]
├─ Syncs legal forms 111-995
├─ Excludes SZCO (100-110)
└─ Updates companies like s.r.o., a.s., etc.
```

### SZCO Tab
```
Počet SZCO: [displays count]
Podiel: [displays % of total]

[FULL RUZ SYNC - SZCO button]
├─ Syncs legal forms 100-110
├─ Excludes Firmy (111+)
└─ Updates self-employed individuals
```

---

## Legal Form Codes

### SZCO (Self-Employed) - Codes 100-110
- **100**: Casual activity (príležitostne)
- **101**: Entrepreneur (podnikateľ) ← Most common SZCO
- **102-110**: Farmer, freelancer, and other variations

### Firmy (Legal Entities) - Codes 111+
- **111**: v.o.s. (Verejná obchodná spoločnosť)
- **112**: s.r.o. (Spoločnosť s ručením obmedzeným) ← Most common
- **113**: k.s. (Komanditná spoločnosť)
- **121**: a.s. (Akciová spoločnosť - public company)
- **205**: Družstvo (cooperative)
- **301-995**: Government, foundations, associations, etc.

---

## How to Use

### Scenario 1: Sync Only Companies
```
1. Go to: http://localhost:5173/admin/
2. Click: Data (Firmy/SZCO)
3. Stay on: "Firmy" tab
4. Click: "FULL RUZ SYNC - Firmy"
5. Wait for: ✓ Success message

Result: Only s.r.o., a.s., etc. are updated from RUZ
Status: Check "Sync Joby" tab to monitor progress
```

### Scenario 2: Sync Only Self-Employed
```
1. Go to: http://localhost:5173/admin/
2. Click: Data (Firmy/SZCO)
3. Click: "SZCO" tab
4. Click: "FULL RUZ SYNC - SZCO"
5. Wait for: ✓ Success message

Result: Only individual entrepreneurs are updated
Status: Check "Sync Joby" tab to monitor progress
```

### Scenario 3: View Current Counts
```
1. Go to: Dashboard
2. Look at: "Companies" section
3. You'll see:
   ├─ Total: 12,500 companies
   ├─ Firmy: 8,500 (68%)
   ├─ SZCO: 4,000 (32%)
   └─ Active: 10,000
```

---

## Monitoring Syncs

### Track Active Syncs
1. Click: "Sync Joby" in sidebar
2. Look for: Recently queued jobs
3. Status options:
   - 🟠 **queued** = Waiting to start
   - 🔵 **running** = Currently syncing
   - 🟢 **completed** = Finished successfully
   - 🔴 **failed** = Encountered error

### View Sync Details
- Click job row to see:
  - Total items to process
  - Items processed so far
  - Success/failure counts
  - Progress percentage
  - Estimated time remaining

---

## Backend API (For Developers)

### Trigger Firmy Sync
```bash
curl -X POST http://localhost:8000/api/admin/sync/jobs/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "job_type": "ruz_full_firmy",
    "notes": "Manual sync for companies"
  }'
```

### Trigger SZCO Sync
```bash
curl -X POST http://localhost:8000/api/admin/sync/jobs/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "job_type": "ruz_full_szco",
    "notes": "Manual sync for self-employed"
  }'
```

### Get Dashboard Metrics
```bash
curl http://localhost:8000/api/admin/metrics/overview/ \
  -H "Authorization: Bearer <token>"

# Response includes:
{
  "companies": {
    "total": 12500,
    "firmy_count": 8500,      # ← NEW
    "szco_count": 4000,       # ← NEW
    "active": 10000,
    ...
  }
}
```

---

## Django Admin (Legacy)

The original Django admin (`/admin/`) still works and includes:
- Company list/detail views
- Filter by legal form
- Manual sync per company
- CSV/XLSX export

```
Access: http://localhost:8000/admin/
└─ Companies and SZCO
   ├─ Filter by legal form
   ├─ View 50+ at a time
   └─ Bulk actions (sync, export, etc.)
```

---

## Troubleshooting

### Issue: "Data" page not appearing in sidebar
**Solution**: 
1. Hard refresh browser: `Cmd+Shift+R` (Mac) or `Ctrl+Shift+R` (Windows)
2. Clear browser cache
3. Restart frontend: `make docker-up`

### Issue: Sync not starting
**Solution**:
1. Check Redis is running: `docker ps | grep redis`
2. Check Celery worker: `docker logs cistafirma_celery_ruz`
3. Check job in "Sync Joby" tab for error details

### Issue: Wrong count of Firmy/SZCO
**Solution**:
1. Some companies may have legal form '995' (unspecified)
2. These are counted as Firmy by default
3. Check Django admin for companies with pravna_forma=null or 995

---

## Files Changed

```
✅ backend/companies/models.py       - SZCO classification + functions
✅ backend/registers/tasks.py        - New Celery tasks (firmy_only, szco_only)
✅ backend/adminapi/views/sync.py    - Job dispatcher for new types
✅ backend/adminapi/views/dashboard.py - Dashboard metrics (firmy_count, szco_count)
✅ frontend/admin/pages/Data.tsx     - NEW: Complete Data page
✅ frontend/admin/AdminApp.tsx       - Route for Data page
✅ frontend/admin/AdminLayout.tsx    - Navigation item
✅ frontend/admin/types.ts           - TypeScript types
```

---

## Next Steps

### Immediate (Today)
- [ ] Test Firmy sync
- [ ] Test SZCO sync
- [ ] Verify counts match database
- [ ] Monitor "Sync Joby" for completion

### Short Term (This Week)
- [ ] Schedule periodic syncs (Celery Beat)
- [ ] Set up alerts on sync failure
- [ ] Document in team wiki
- [ ] Train team members

### Medium Term (This Month)
- [ ] Deploy to staging
- [ ] Deploy to production
- [ ] Monitor production syncs
- [ ] Adjust sync schedule based on data changes

---

## Support

For issues or questions:
1. Check logs: `make docker-logs`
2. Check Django admin: `http://localhost:8000/admin/`
3. Check sync jobs: Admin panel → "Sync Joby"
4. Review implementation doc: `FIRMY_SZCO_IMPLEMENTATION.md`

---

**Status**: ✅ Ready to use  
**Last Updated**: August 4, 2026  
**Frontend**: http://localhost:5173/admin/ (Data tab)  
**Backend**: http://localhost:8000/ (API)

