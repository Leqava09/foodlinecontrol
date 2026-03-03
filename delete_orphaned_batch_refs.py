#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'foodlinecontrol.settings')
django.setup()

from inventory.models import PackagingBalance

deleted_containers = ['Test 123', 'TCLU1331172']

print("="*70)
print("DELETING ORPHANED BATCH REFERENCES")
print("="*70)

for ref in deleted_containers:
    pb_refs = PackagingBalance.objects.filter(batch_ref=ref)
    if pb_refs.exists():
        print(f"\nDeleting {pb_refs.count()} PackagingBalance records for '{ref}':")
        for pb in pb_refs:
            print(f"  - {pb.production_date} - {pb.stock_item.name}")
            pb.delete()
        print(f"  ✅ Deleted {pb_refs.count()} records")
    else:
        print(f"\nNo PackagingBalance records found for '{ref}'")

print("\n" + "="*70)
print("✅ CLEANUP COMPLETE")
print("="*70)

# Verify deletion
print("\nVerifying deletion...")
for ref in deleted_containers:
    remaining = PackagingBalance.objects.filter(batch_ref=ref).count()
    if remaining > 0:
        print(f"  ❌ '{ref}': Still {remaining} records remaining")
    else:
        print(f"  ✅ '{ref}': All removed")
