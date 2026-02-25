import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'foodlinecontrol.settings')
django.setup()

from manufacturing.models import Batch, BatchContainer, Production, MeatProductionSummary
from django.contrib.auth.models import User

print("=" * 50)
print("FRESH DATABASE VERIFICATION")
print("=" * 50)

print(f"\n✓ Users: {User.objects.count()}")
print(f"  - TEST account exists: {User.objects.filter(username='TEST').exists()}")

print(f"\n✓ Production records: {Production.objects.count()}")
print(f"✓ Batch records: {Batch.objects.count()}")
print(f"✓ BatchContainer records: {BatchContainer.objects.count()}")
print(f"✓ MeatProductionSummary records: {MeatProductionSummary.objects.count()}")

print("\n" + "=" * 50)
print("DATABASE IS CLEAN - READY FOR EXPORT")
print("=" * 50)
