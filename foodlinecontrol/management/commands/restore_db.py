"""
Django management command to restore database from SQL dump
Place in: foodlinecontrol/management/commands/restore_db.py
Run: python manage.py restore_db
"""

from django.core.management.base import BaseCommand
from django.db import connection
from pathlib import Path


class Command(BaseCommand):
    help = 'Restore database from foodlinecontrol_full.sql'

    def handle(self, *args, **options):
        self.stdout.write("=" * 80)
        self.stdout.write("PostgreSQL Database Restore via Django")
        self.stdout.write("=" * 80)
        self.stdout.write("")

        # Find the SQL dump file (try multiple names)
        base_dir = Path(__file__).resolve().parent.parent.parent.parent
        dump_file = base_dir / 'foodlinecontrol_pg13.sql'
        
        if not dump_file.exists():
            dump_file = base_dir / 'foodlinecontrol_clean.sql'
        
        if not dump_file.exists():
            dump_file = base_dir / 'foodlinecontrol_utf8.sql'
        
        if not dump_file.exists():
            dump_file = base_dir / 'foodlinecontrol_full.sql'
        
        if not dump_file.exists():
            self.stdout.write(self.style.ERROR(f"ERROR: Dump file not found"))
            self.stdout.write("Please upload foodlinecontrol_pg13.sql to /home/leqavaco/foodlinecontrol/foodlinecontrol/")
            return

        file_size = dump_file.stat().st_size
        file_size_mb = round(file_size / 1024 / 1024, 2)

        self.stdout.write(f"Dump file: {dump_file}")
        self.stdout.write(f"Size: {file_size_mb} MB ({file_size:,} bytes)")
        self.stdout.write("")

        self.stdout.write("Step 1: Testing database connection...")
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT version();")
                version = cursor.fetchone()[0]
                self.stdout.write(self.style.SUCCESS(f"✓ Connected to PostgreSQL"))
                self.stdout.write(f"  Version: {version[:50]}...")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Connection failed: {e}"))
            return

        self.stdout.write("")
        self.stdout.write("Step 2: Reading SQL dump file...")
        sql = dump_file.read_text(encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(f"✓ Loaded {len(sql):,} characters"))

        self.stdout.write("")
        self.stdout.write("Step 3: Executing restore...")
        self.stdout.write("(This may take 1-2 minutes)")
        self.stdout.write("")

        try:
            with connection.cursor() as cursor:
                cursor.execute(sql)
            self.stdout.write(self.style.SUCCESS("✓ Database restored successfully"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Restore failed: {e}"))
            return

        self.stdout.write("")
        self.stdout.write("=" * 80)
        self.stdout.write("Step 4: Verification")
        self.stdout.write("=" * 80)
        self.stdout.write("")

        # Verify data
        from django.contrib.auth import get_user_model
        from tenants.models import Site
        from commercial.models import Supplier
        from manufacturing.models import Batch

        User = get_user_model()

        try:
            self.stdout.write(self.style.SUCCESS(f"✓ Users:                        {User.objects.count()} records"))
            self.stdout.write(self.style.SUCCESS(f"✓ Sites:                        {Site.objects.count()} records"))
            self.stdout.write(self.style.SUCCESS(f"✓ Suppliers:                    {Supplier.objects.count()} records"))
            self.stdout.write(self.style.SUCCESS(f"✓ Batches:                      {Batch.objects.count()} records"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Verification error: {e}"))

        self.stdout.write("")
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS("✓✓✓ DATABASE RESTORE COMPLETE! ✓✓✓"))
        self.stdout.write("=" * 80)
        self.stdout.write("")
        self.stdout.write("Next steps:")
        self.stdout.write("-----------")
        self.stdout.write("1. Test admin login:")
        self.stdout.write("   Visit: https://leqava.co.za/admin/")
        self.stdout.write("   Site User: Flip / Petroon14@")
        self.stdout.write("   HQ User: Fliptest / Petroon14@")
        self.stdout.write("")
        self.stdout.write("2. DELETE THESE FILES:")
        self.stdout.write("   - foodlinecontrol/management/commands/restore_db.py")
        self.stdout.write("   - foodlinecontrol_full.sql")
        self.stdout.write("   - All restore_db*.php files from public/")
        self.stdout.write("   - All complete_fix*.php files from public/")
        self.stdout.write("")
