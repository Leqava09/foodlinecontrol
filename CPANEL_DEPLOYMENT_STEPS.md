# cPanel Deployment Steps - Bonus Fields & Migration Fixes

## Changes Being Deployed
1. **Salary Costing**: Added % Bonus and Production Months fields with dynamic calculations
2. **Manufacturing Migrations**: Fixed model state sync using SeparateDatabaseAndState

## Pre-Deployment Backup (IMPORTANT!)
```bash
# Backup database before applying migrations
pg_dump -U your_db_user -d your_db_name > backup_$(date +%Y%m%d_%H%M%S).sql
```

## Deployment Steps

### 1. SSH into cPanel Server
```bash
ssh your_username@your_cpanel_server
```

### 2. Navigate to Project Directory
```bash
cd /path/to/foodlinecontrol
```

### 3. Check Current Status
```bash
git status
git log --oneline -3
```

### 4. Pull Latest Changes from GitHub
```bash
git pull origin master
```

**Expected output**: Should pull commits 07d238f, 0bd44e4, and 1e78048

### 5. Check Migrations Status
```bash
python manage.py showmigrations manufacturing
python manage.py showmigrations costing
```

### 6. Apply Migrations
```bash
# Run migrations - they will apply cleanly
python manage.py migrate

# Verify no new migrations needed
python manage.py makemigrations --check
```

**Important**: The manufacturing migrations use `SeparateDatabaseAndState`, so they won't try to recreate existing database fields. They only update Django's model state.

### 7. Collect Static Files (if needed)
```bash
python manage.py collectstatic --noinput
```

### 8. Restart Application
```bash
# Method depends on your cPanel setup:
# Option A - If using Passenger:
touch tmp/restart.txt

# Option B - If using systemd:
sudo systemctl restart your_app_name

# Option C - If using supervisord:
sudo supervisorctl restart your_app_name

# Option D - Through cPanel interface:
# Go to: Setup Python App > Restart Application
```

### 9. Verification

**Test in Django Admin:**
1. Go to: https://your_domain.com/admin/costing/salarycosting/
2. Open any salary costing record
3. Verify new fields appear: "% Bonus" and "Production Months"
4. Test calculation: Enter 100% bonus, 10 months - verify price updates
5. Check Grand Total displays next to Fixed Subtotal

**Verify Migrations Applied:**
```bash
python manage.py showmigrations | grep -E "(costing|manufacturing)"
```

All migrations should show `[X]` indicating they're applied.

### 10. Test Database Integrity
```bash
# Check for any migration issues
python manage.py migrate --check

# Verify no pending migrations
python manage.py makemigrations --dry-run
```

**Expected**: "No changes detected"

## Troubleshooting

### If Migration Fails
```bash
# Check which migration failed
python manage.py showmigrations manufacturing

# Check migration details
python manage.py sqlmigrate manufacturing 0014

# If needed, fake a specific migration (only if absolutely necessary)
python manage.py migrate manufacturing 0014 --fake
```

### If Fields Don't Appear in Admin
```bash
# Clear cache if using caching
python manage.py clear_cache  # if available

# Restart application again
touch tmp/restart.txt
```

### If Calculation Doesn't Work
- Check browser console for JavaScript errors
- Verify `/static/js/salary_dynamic_calc.js` was updated
- Clear browser cache (Ctrl+Shift+R)

## Database Differences Note
- **Local DB**: Has test data, may have different batch numbers
- **cPanel DB**: Production data with real records
- **Migrations**: Designed to work with both databases
- **SeparateDatabaseAndState**: Ensures migrations don't fail on existing production data

## Post-Deployment
- Monitor application logs for any errors
- Test creating new salary costing records
- Verify existing salary costing records still display correctly
- Check that batch manufacturing functionality still works

## Rollback Plan (If Needed)
```bash
# Restore from backup
psql -U your_db_user -d your_db_name < backup_YYYYMMDD_HHMMSS.sql

# Revert to previous commit
git reset --hard 9e417d4
touch tmp/restart.txt
```
