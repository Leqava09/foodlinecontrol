import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'foodlinecontrol.settings')
django.setup()

from django.contrib.auth.models import User
from tenants.models import UserSite

# Get or create the TEST Django user
django_user, created = User.objects.get_or_create(
    username='TEST',
    defaults={
        'email': 'test@foodlinecontrol.local',
        'is_staff': True,
        'is_superuser': True,
        'first_name': 'TEST',
    }
)
if created:
    django_user.set_password('TEST')
    django_user.save()
    print(f"✓ Created Django user TEST")
else:
    print(f"✓ Django user TEST already exists")

# Create or update UserSite as HQ user
user_site, created = UserSite.objects.get_or_create(
    hq_username='TEST',
    defaults={
        'user': django_user,
        'is_hq_user': True,
    }
)

# Set the HQ password
user_site.set_hq_password('TEST')
user_site.is_hq_user = True
user_site.user = django_user
user_site.assigned_site = None  # HQ users can access all sites
user_site.is_manager = False
user_site.is_archived = False
user_site.save()

print(f"✓ HQ UserSite created/updated for TEST")
print(f"  - hq_username: {user_site.hq_username}")
print(f"  - hq_password: (encrypted)")
print(f"  - is_hq_user: {user_site.is_hq_user}")
print(f"  - can_access_hq: {user_site.can_access_hq()}")

# Test password check
if user_site.check_hq_password('TEST'):
    print(f"✓ HQ password verification works!")
else:
    print(f"✗ HQ password verification failed!")

print(f"\n✓ TEST HQ account ready")
print(f"  Username: TEST")
print(f"  Password: TEST")
print(f"  Login at: http://localhost:8000/hq/login/")
