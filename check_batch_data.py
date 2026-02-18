#!/usr/bin/env python
"""
Check for duplicate or extra batch records for 01/10/25
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'foodlinecontrol.settings')
django.setup()

from manufacturing.models import Batch, BatchContainer
from datetime import date

# Get all batches for 01/10/25
target_date = date(2025, 10, 1)
batches = Batch.objects.filter(production_date=target_date).order_by('id').select_related('product', 'site')

print(f"\n{'='*120}")
print(f"BATCHES FOR {target_date}")
print(f"{'='*120}\n")
print(f"Total batches: {batches.count()}\n")

for b in batches:
    print(f"ID: {b.id:2d} | Batch: {b.batch_number:20s} | A-NO: {str(b.a_no):6s} | Product: {str(b.product)[:35]:35s} | Shift: {b.shift_total:6d} | Site: {b.site_id} | Status: {b.status}")

print(f"\n{'='*120}")
print("BATCH CONTAINERS FOR THIS DATE")
print(f"{'='*120}\n")

containers = BatchContainer.objects.filter(production_date=target_date).order_by('id')
print(f"Total containers: {containers.count()}\n")

for c in containers:
    container_id = c.container.container_number if c.container else c.batch_ref or "Unknown"
    print(f"ID: {c.id:3d} | Date: {c.production_date} | Container/Ref: {container_id:20s} | Meat Filled: {c.meat_filled:8.2f} | Waste Factor: {c.waste_factor:6.2f}%")

print(f"\n{'='*120}\n")

# Count by site
print("SUMMARY BY SITE:\n")
for site_id in set(batches.values_list('site_id', flat=True)):
    site_batches = batches.filter(site_id=site_id)
    print(f"Site {site_id}: {site_batches.count()} batches")
    for b in site_batches:
        print(f"  - {b.batch_number} ({b.a_no})")
