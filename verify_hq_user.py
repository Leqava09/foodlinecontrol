import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'foodlinecontrol.settings')
django.setup()

from tenants.models import UserSite

try:
    u = UserSite.objects.get(hq_username='TEST')
    print('✓ HQ User found:')
    print(f'  Username: {u.hq_username}')
    print(f'  Is HQ User: {u.is_hq_user}')
    print(f'  Can Access HQ: {u.can_access_hq()}')
    print(f'  Password check for TEST: {u.check_hq_password("TEST")}')
    print(f'\n✓ Ready to login at: http://localhost:8000/hq/login/')
    print(f'  Use credentials: TEST / TEST')
except UserSite.DoesNotExist:
    print('✗ HQ User not found')
