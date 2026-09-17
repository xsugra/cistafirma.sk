# Implementation Complete: Firmy/SZCO Separation with Individual RUZ Sync

## Overview
Successfully implemented complete separation of **Firmy** (legal entities) and **SZCO** (self-employed/individual entrepreneurs) with independent FULL RUZ SYNC capabilities. Both categories can now be managed and synchronized separately through the frontend admin panel.

## What's New

### 1. **Backend Model Changes** (`backend/companies/models.py`)

#### SZCO Classification System
```python
# Legal form codes 100-110 = SZCO (self-employed)
SZCO_LEGAL_FORMS = {'100', '101', '102', '103', '104', '105', '106', '107', '108', '109', '110'}

# Helper functions
is_szco_company(legal_form_code: str) -> bool      # Returns True if SZCO
is_company_company(legal_form_code: str) -> bool   # Returns True if Firma (legal entity)
```

### 2. **New Celery Tasks** (`backend/registers/tasks.py`)

Three new independent RUZ sync tasks:

```python
@shared_task(queue='ruz_full')
def fetch_ruz_data_firmy_only():
    """Sync ONLY Firmy (legal entities) - excludes SZCO"""
    # Filters out legal forms 100-110

@shared_task(queue='ruz_full')
def fetch_ruz_data_szco_only():
    """Sync ONLY SZCO - excludes Firmy"""
    # Only processes legal forms 100-110
```

- **fetch_ruz_data_task()** - Original full sync (all entities)
- **fetch_ruz_data_firmy_only()** - Companies only (legal entities)
- **fetch_ruz_data_szco_only()** - Self-employed only

### 3. **API Endpoints** (`backend/adminapi/views/sync.py`)

Updated task dispatcher to handle new job types:
- `"ruz_full_firmy"` → triggers `fetch_ruz_data_firmy_only()`
- `"ruz_full_szco"` → triggers `fetch_ruz_data_szco_only()`

### 4. **Dashboard Metrics** (`backend/adminapi/views/dashboard.py`)

Enhanced dashboard overview with:
```json
{
  "companies": {
    "total": 12500,
    "active": 10000,
    "firmy_count": 8500,      // ← NEW
    "szco_count": 4000,       // ← NEW
    "with_orsr": 6000,
    "with_financials": 7000
  }
}
```

### 5. **Frontend Admin Panel** (`frontend/admin/pages/Data.tsx`)

#### New "Data" Page
- **Location**: Admin panel → "Data (Firmy/SZCO)"
- **Tabs**: 
  - 📊 **Firmy** (Companies/Legal Entities)
    - Shows count of legal entities
    - Button: "FULL RUZ SYNC - Firmy"
    - Only syncs companies (legal forms 111+)
  
  - 👤 **SZCO** (Self-employed Individuals)
    - Shows count of self-employed persons
    - Button: "FULL RUZ SYNC - SZCO"
    - Only syncs SZCO (legal forms 100-110)

#### Features
- **Real-time counters**: Shows Firmy and SZCO counts with percentages
- **Independent triggers**: Each category can be synced separately
- **Status messages**: Real-time feedback on sync progress
- **Category info**: Explains legal form codes for each category

### 6. **Updated Navigation** (`frontend/admin/AdminLayout.tsx`)

```
Navigation Menu:
├── Dashboard
├── Data (Firmy/SZCO) ← NEW  [Database icon]
├── Firmy - Detaily
├── Používatelia
├── Sync Joby
├── Periodické úlohy
├── Audit Log
└── Systém
```

### 7. **Type Updates** (`frontend/admin/types.ts`)

```typescript
interface DashboardOverview {
  companies: {
    // ... existing fields ...
    firmy_count?: number;        // ← NEW
    szco_count?: number;         // ← NEW
  }
}

type AdminPage = 
  | 'dashboard'
  | 'data'          // ← NEW
  | 'companies'
  | ...
```

## Legal Form Classification

### SZCO (100-110)
- **100**: FO - příležitostná (casual activity)
- **101**: FO - podnikateľ (entrepreneur)
- **102**: FO - podnikateľ v OR (in commercial register)
- **103**: SHR (self-employed farmer)
- **104**: SHR v OR
- **105-110**: FO s rôznymi formami (various professional forms)

### Firmy (111+)
- **111**: Verejná obchodná spoločnosť (v.o.s.)
- **112**: Spoločnosť s ručením obmedzeným (s.r.o.) ← Most common
- **113**: Komanditná spoločnosť (k.s.)
- **121**: Akciová spoločnosť (a.s.) ← Public company
- **205**: Družstvo
- **301**: Štátny podnik
- **995**: Nešpecifikovaná (unspecified)

## How to Use

### 1. Access the Data Panel
1. Log in to Django admin or frontend admin panel
2. Navigate to "Data (Firmy/SZCO)" from sidebar
3. Choose tab: **Firmy** or **SZCO**

### 2. Trigger FULL RUZ SYNC

**For Firmy only:**
```
1. Click "Data (Firmy/SZCO)" in navigation
2. Stay on "Firmy" tab
3. Click "FULL RUZ SYNC - Firmy" button
4. Watch status message for progress
```

**For SZCO only:**
```
1. Click "Data (Firmy/SZCO)" in navigation
2. Click "SZCO" tab
3. Click "FULL RUZ SYNC - SZCO" button
4. Watch status message for progress
```

### 3. Monitor Progress
- Admin panel → "Sync Joby" tab shows all sync jobs
- Dashboard shows updated Firmy/SZCO counts
- Status messages confirm sync completion

## Backend Django Admin

The original Django admin (`/admin/`) continues to work with all existing features:
- Filter by legal form
- View company details
- Manual sync per company
- Export to CSV/XLSX

## Benefits

✅ **Separate Management**: Each category can be managed independently
✅ **Optimized Sync**: Run FULL RUZ SYNC only for needed category
✅ **Better Visibility**: Dashboard shows Firmy vs SZCO split
✅ **User-Friendly UI**: Clear tabs and explanations for each category
✅ **Backward Compatible**: Existing Django admin continues to work
✅ **API-Driven**: All operations trigger via REST API for scalability

## Files Modified

```
Backend:
✅ backend/companies/models.py        - Added SZCO classification + utility functions
✅ backend/registers/tasks.py         - Added 2 new Celery tasks (firmy_only, szco_only)
✅ backend/adminapi/views/sync.py     - Updated task dispatcher with new job types
✅ backend/adminapi/views/dashboard.py - Added firmy_count, szco_count to metrics

Frontend:
✅ frontend/admin/pages/Data.tsx      - NEW: Complete Data management page
✅ frontend/admin/AdminApp.tsx        - Added 'data' route
✅ frontend/admin/AdminLayout.tsx     - Added "Data" to navigation
✅ frontend/admin/types.ts            - Updated types for new fields
✅ frontend/admin/api.ts              - (No changes needed - uses existing dispatcher)
```

## Testing Checklist

- ✅ Docker services running (backend, frontend, database, redis, workers)
- ✅ Migrations applied successfully
- ✅ Frontend build completed without errors
- ✅ New Data page accessible in admin panel
- ✅ Both tabs (Firmy/SZCO) rendering with correct counts
- ✅ Sync buttons trigger without errors
- ✅ Dashboard shows firmy_count and szco_count
- ✅ Navigation includes "Data (Firmy/SZCO)" menu item

## Environment Setup

```bash
# Start all services
make docker-up

# Apply migrations
make docker-migrate

# View logs
make docker-logs

# Access services
- Backend: http://localhost:8000/
- Frontend: http://localhost:5173/
- Django Admin: http://localhost:8000/admin/
- API Admin: http://localhost:8000/api/admin/
```

## Next Steps (Optional)

1. **Deploy to production** (Kubernetes/Helm)
2. **Set up monitoring** (Prometheus/Sentry for sync metrics)
3. **Add scheduled tasks** (periodic SZCO-only or Firmy-only syncs)
4. **Create custom reports** (sync duration/success rate by category)
5. **Implement webhooks** (notify on sync completion)

---

**Status**: ✅ Implementation Complete  
**Date**: August 4, 2026  
**Frontend Framework**: React 19 + TypeScript + Vite  
**Backend Framework**: Django 6 + Django REST Framework  
**Task Queue**: Celery + Redis

