#!/usr/bin/env python
"""
Restore batch A00725CH02A from backup
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'foodlinecontrol.settings')
django.setup()

from manufacturing.models import Batch, BatchProductInventoryUsed
from product_details.models import Product
from tenants.models import Site
from datetime import date
from decimal import Decimal

# Batch data from dump.sql line 1670
batch_data = {
    'id': 1,
    'size': '425 gr',
    'production_date': date(2025, 11, 11),
    'a_no': 'A010',
    'batch_number': 'A00725CH02A',
    'expiry_date': date(2028, 11, 11),
    'shift_total': 26251,
    'incubation_start': date(2025, 11, 13),
    'incubation_end': date(2025, 11, 22),
    'certification_date': date(2025, 11, 30),
    'dispatch_date': None,
    'status': 'certified',
    'nsi_submission_date': date(2025, 11, 23),
    'category_id': 2,
    'product_id': 1,
    'site_id': 1,
    'production_id': 2,
    'sku': None,
}

# Get product and site
try:
    product = Product.objects.get(id=batch_data['product_id'])
    site = Site.objects.get(id=batch_data['site_id'])
    
    # Create the batch
    batch, created = Batch.objects.update_or_create(
        id=batch_data['id'],
        defaults={
            'size': batch_data['size'],
            'production_date': batch_data['production_date'],
            'a_no': batch_data['a_no'],
            'batch_number': batch_data['batch_number'],
            'expiry_date': batch_data['expiry_date'],
            'shift_total': batch_data['shift_total'],
            'incubation_start': batch_data['incubation_start'],
            'incubation_end': batch_data['incubation_end'],
            'certification_date': batch_data['certification_date'],
            'dispatch_date': batch_data['dispatch_date'],
            'status': batch_data['status'],
            'nsi_submission_date': batch_data['nsi_submission_date'],
            'category_id': batch_data['category_id'],
            'product': product,
            'site': site,
            'production_id': batch_data['production_id'],
            'sku': batch_data['sku'],
        }
    )
    
    action = "Updated" if not created else "Created"
    print(f"✓ {action} Batch {batch_data['id']}: {batch_data['batch_number']}")
    print(f"  Production Date: {batch_data['production_date']}")
    print(f"  Product: {product}")
    print(f"  Site: {site}")
    print(f"  Status: {batch_data['status']}")
    print(f"  Shift Total: {batch_data['shift_total']}\n")
    
except Product.DoesNotExist:
    print(f"❌ Error: Product with ID {batch_data['product_id']} not found!")
except Site.DoesNotExist:
    print(f"❌ Error: Site with ID {batch_data['site_id']} not found!")
