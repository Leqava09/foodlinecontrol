#!/usr/bin/env python
"""
Find all batches named A00725CH02A
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'foodlinecontrol.settings')
django.setup()

from manufacturing.models import Batch
from datetime import date

# Search all dates
batches = Batch.objects.filter(batch_number='A00725CH02A')

print(f"\nAll batches named 'A00725CH02A':\n")
for b in batches:
    print(f"ID: {b.id} | Date: {b.production_date} | A-NO: {b.a_no} | Status: {b.status} | Site: {b.site_id}")

# Also check for 01/10/25
print(f"\n\nAll batches for 2025-10-01:\n")
batches_010 = Batch.objects.filter(production_date=date(2025, 10, 1))
for b in batches_010:
    print(f"ID: {b.id} | Batch: {b.batch_number:20s} | A-NO: {b.a_no:10s} | Status: {b.status} | Site: {b.site_id}")
