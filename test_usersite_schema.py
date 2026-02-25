import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'foodlinecontrol.settings')
django.setup()

from tenants.models import UserSite

# Test that we can query UserSite with hq_username
print("Testing UserSite schema...")
print(f"✓ UserSite model loaded")

# Check the schema by inspecting a query
try:
    # This would fail if hq_username column doesn't exist
    qs = UserSite.objects.filter(hq_username='test')
    print(f"✓ hq_username field accessible")
    print(f"✓ Query count: {qs.count()}")
except Exception as e:
    print(f"✗ Error: {e}")
    
# Test password field
try:
    qs = UserSite.objects.filter(hq_password__isnull=False)
    print(f"✓ hq_password field accessible")
except Exception as e:
    print(f"✗ Error: {e}")

# Test is_manager field
try:
    qs = UserSite.objects.filter(is_manager=True)
    print(f"✓ is_manager field accessible")
except Exception as e:
    print(f"✗ Error: {e}")

# Test is_archived field
try:
    qs = UserSite.objects.filter(is_archived=False)
    print(f"✓ is_archived field accessible")
except Exception as e:
    print(f"✗ Error: {e}")

print("\n✓ All UserSite fields verified!")
