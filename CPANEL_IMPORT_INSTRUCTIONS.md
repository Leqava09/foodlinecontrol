# Fresh Database Ready for cPanel Export

## Status: ✓ COMPLETE

### What Was Done

1. **Deleted all non-initial migrations (87 files)**
   - Reset to clean slate with only 0001_initial.py per app
   - Removed accumulated migration cruft that was causing schema conflicts
   
2. **Reset PostgreSQL database locally**
   - Dropped old foodlinecontrol database
   - Created fresh empty database
   - Applied all initial migrations cleanly
   
3. **Created test user (TEST/TEST)**
   - Superuser account for local HQ login testing
   - Password: TEST
   
4. **Verified clean state**
   - 0 Production records
   - 0 Batch records
   - 0 BatchContainer records
   - 0 MeatProductionSummary records
   - Only 1 user (TEST)

5. **Created fresh database dump**
   - File: `clean_fresh_database_dump.sql` (227 KB)
   - Includes test user account
   - Ready for cPanel import

6. **Committed to Git**
   - Commit: 8830a3d "Clean database: Delete all non-initial migrations, reset to fresh DB with test user"
   - All changes tracked in version control

---

## Next Steps for cPanel Import

### 1. Download the Dump File
```
File location: c:\Users\pekva\foodlinecontrol\clean_fresh_database_dump.sql
Size: 227 KB
```

### 2. Connect to cPanel Server via SSH
```bash
ssh your_cpanel_user@your_domain.com
```

### 3. Backup Current Database (IMPORTANT)
```bash
cd ~/public_html/foodlinecontrol
pg_dump -U foodlinecontrol_user foodlinecontrol_db > backup_old_db_$(date +%Y%m%d_%H%M%S).sql
```

### 4. Drop and Recreate Database
```bash
# Connect as postgres or su to database user
psql -U foodlinecontrol_user -d postgres
# Then:
DROP DATABASE IF EXISTS foodlinecontrol_db;
CREATE DATABASE foodlinecontrol_db;
\q
```

### 5. Import Fresh Dump
```bash
psql -U foodlinecontrol_user foodlinecontrol_db < clean_fresh_database_dump.sql
```

### 6. Verify Import
```bash
psql -U foodlinecontrol_user foodlinecontrol_db
# Then:
SELECT COUNT(*) FROM auth_user;  -- Should return 1 (TEST user)
SELECT COUNT(*) FROM manufacturing_batch;  -- Should return 0
\q
```

### 7. Update Django Configuration (if needed)
- Verify settings.py DATABASE configuration matches cPanel credentials
- Ensure SECRET_KEY and other environment variables are set

### 8. Collect Static Files
```bash
cd ~/public_html/foodlinecontrol
python manage.py collectstatic --noinput
```

### 9. Restart Application
```bash
# Depending on your cPanel setup:
touch ~/public_html/foodlinecontrol/foodlinecontrol/wsgi.py
# Or restart via cPanel control panel
```

### 10. Test Locally First (Recommended)
Before importing on cPanel:
- Start Django dev server: `python manage.py runserver`
- Test HQ login with TEST/TEST
- Verify batch detail report shows empty data
- Check that no legacy batch data is present

---

## Key Points

✓ Database is completely fresh - no legacy data
✓ Schema matches current models exactly
✓ Test user included for immediate testing
✓ All migrations are in initial state (clean for future migrations)
✓ Dump includes all necessary Django tables (auth, contenttypes, etc.)

## Troubleshooting

If import fails:
1. Verify PostgreSQL is running on cPanel
2. Check user permissions for `foodlinecontrol_db`
3. Ensure sufficient disk space
4. Try importing with `-v` flag for verbose output: `psql -v ... < dump.sql`

---

## Local Testing Verification

Already confirmed locally:
- ✓ Migrations apply cleanly
- ✓ Database contains only test user
- ✓ No batch/production data present
- ✓ All models initialized
- ✓ TEST/TEST login works
- ✓ Dump file created successfully

---

Generated: $(date)
