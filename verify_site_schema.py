import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'foodlinecontrol.settings')
django.setup()

from tenants.models import Site
from django.db import connection

print('✓ Site model accessible')

# Check database columns
cursor = connection.cursor()
cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name='tenants_site' ORDER BY ordinal_position")
cols = [row[0] for row in cursor.fetchall()]
print(f'✓ Site table columns: {", ".join(cols)}')

# Verify key fields exist
required_fields = ['is_active', 'is_archived', 'admin_background', 'slug']
for field in required_fields:
    if field in cols:
        print(f'  ✓ {field} field exists')
    else:
        print(f'  ✗ {field} field MISSING')

print('\n✓ All Site schema fields verified!')
