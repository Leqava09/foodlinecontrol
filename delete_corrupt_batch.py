#!/usr/bin/env python
"""
Delete batch A00725CH02A and all related data
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'foodlinecontrol.settings')
django.setup()

from manufacturing.models import Batch, BatchContainer, BatchProductInventoryUsed
from datetime import date

# Find the batch
batch = Batch.objects.filter(batch_number='A00725CH02A').first()

if not batch:
    print("❌ Batch A00725CH02A not found!")
else:
    print(f"Found batch to delete:")
    print(f"  ID: {batch.id}")
    print(f"  Batch Number: {batch.batch_number}")
    print(f"  A-NO: {batch.a_no}")
    print(f"  Production Date: {batch.production_date}")
    print(f"  Product: {batch.product}")
    print(f"  Site: {batch.site_id}")
    print(f"  Status: {batch.status}\n")
    
    # Count related records
    containers = BatchContainer.objects.filter(production_date=batch.production_date)
    inventory = BatchProductInventoryUsed.objects.filter(batch=batch)
    
    print(f"Related records:")
    print(f"  - Containers for this date: {containers.count()}")
    print(f"  - Product inventory used: {inventory.count()}\n")
    
    # Show what will be deleted
    print(f"Records to be deleted:")
    print(f"  - Batch (ID {batch.id})")
    if inventory.exists():
        print(f"  - ProductInventoryUsed records: {inventory.count()}")
    
    # Delete the batch (cascade will handle related records)
    batch_id = batch.id
    batch.delete()
    
    print(f"\n✓ Batch {batch_id} (A00725CH02A) successfully deleted!")
    
    # Verify deletion
    batch_check = Batch.objects.filter(id=batch_id).exists()
    if not batch_check:
        print("✓ Verified: Batch no longer exists in database")
