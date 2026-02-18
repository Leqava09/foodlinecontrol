#!/usr/bin/env python
"""
Find batches with A-NO 007 and 008 for 01/10/25
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'foodlinecontrol.settings')
django.setup()

from manufacturing.models import Batch
from datetime import date

# Get all batches for 01/10/25
target_date = date(2025, 10, 1)
batches = Batch.objects.filter(production_date=target_date).order_by('a_no')

print(f"\nBatches for {target_date}:\n")
for b in batches:
    print(f"ID: {b.id} | A-NO: {b.a_no:10s} | Batch: {b.batch_number:20s} | Product: {str(b.product)[:40]:40s} | Site: {b.site_id}")

# Look for 007 and 008
batch_007 = batches.filter(a_no__icontains='007').first()
batch_008 = batches.filter(a_no__icontains='008').first()

print(f"\n{'='*100}")
print("SEARCH RESULTS:")
print(f"{'='*100}\n")

if batch_007:
    print(f"Batch 007 found:")
    print(f"  ID: {batch_007.id}")
    print(f"  A-NO: {batch_007.a_no}")
    print(f"  Batch: {batch_007.batch_number}")
    print(f"  Product: {batch_007.product}")
    print(f"  Site: {batch_007.site_id}")
    print(f"  Status: {batch_007.status}")
else:
    print("Batch 007: NOT FOUND")

print()

if batch_008:
    print(f"Batch 008 found:")
    print(f"  ID: {batch_008.id}")
    print(f"  A-NO: {batch_008.a_no}")
    print(f"  Batch: {batch_008.batch_number}")
    print(f"  Product: {batch_008.product}")
    print(f"  Site: {batch_008.site_id}")
    print(f"  Status: {batch_008.status}")
else:
    print("Batch 008: NOT FOUND")
