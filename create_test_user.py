import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'foodlinecontrol.settings')
django.setup()

from django.contrib.auth.models import User

# Create superuser TEST/TEST
username = 'TEST'
password = 'TEST'
email = 'test@foodlinecontrol.local'

# Check if user already exists
if User.objects.filter(username=username).exists():
    print(f"✗ User '{username}' already exists")
    user = User.objects.get(username=username)
    user.set_password(password)
    user.save()
    print(f"✓ Password reset for existing user '{username}'")
else:
    user = User.objects.create_superuser(username=username, email=email, password=password)
    print(f"✓ Superuser '{username}' created")

print(f"  Username: {user.username}")
print(f"  Is Staff: {user.is_staff}")
print(f"  Is Superuser: {user.is_superuser}")
